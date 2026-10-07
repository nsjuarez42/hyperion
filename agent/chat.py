"""One chat message in, a stream of SSE events out.

Order of checks for every message:
1. A pending delete/overwrite? A yes/no settles it; anything else cancels it.
2. A bare yes/no with nothing pending gets a short reply.
3. Otherwise the router picks a route:
   off_topic  -> fixed refusal, no LLM call, not saved to memory
   ide_action -> tools (plan, template, validate, IDE action event)
   hyperai    -> retrieve documentation, answer only from it
   chitchat   -> answer with the conversation as context
"""

import asyncio
import re

from langchain_core.messages import HumanMessage, SystemMessage

from agent.config import API_KEY, BASE_URL, EMBED_MODEL
from agent.language import is_spanish
from agent.llm import chat_llm
from agent.memory import get_history, save_turn, session_lock
from agent.prompts import (
    LLM_UNAVAILABLE,
    NOTHING_PENDING,
    OFF_TOPIC_REFUSAL,
    OFF_TOPIC_REFUSAL_ES,
    PENDING_CANCELLED,
    RAG_PROMPT,
    SYSTEM_PROMPT,
)
from agent.router import classify
from agent.sse import DONE, sse
from agent.tools import (
    cancel_pending,
    has_pending,
    interpret_confirmation,
    stream_ide_action,
    stream_pending,
)
from rag import Retriever

# Built once at startup: chunks the knowledge base and embeds it.
retriever = Retriever(base_url=BASE_URL, api_key=API_KEY, embed_model=EMBED_MODEL)

BARE_CONFIRMATION = re.compile(r"(yes|y|yep|no|n|nope|confirm|cancel)[.!]*", re.IGNORECASE)


async def system_prompt_for(route: str, question: str) -> str:
    """The plain system prompt, plus documentation excerpts for HYPER-AI questions."""
    if route != "hyperai":
        return SYSTEM_PROMPT
    # retrieve() makes a blocking HTTP call for the query embedding; a thread
    # keeps it from freezing every other user's stream while it waits.
    chunks = await asyncio.to_thread(retriever.retrieve, question)
    print(f"rag={[chunk['source'] for chunk in chunks]}", flush=True)
    if chunks:
        context = "\n\n".join(
            f"Source: {chunk['source']}\n{chunk['text']}" for chunk in chunks
        )
    else:
        context = "(none)"
    return RAG_PROMPT.format(system_prompt=SYSTEM_PROMPT, context=context)


async def stream_llm(messages: list, user_id: str, user_text: str):
    """Stream the model's answer; save the turn only if it completed."""
    reply = ""
    try:
        async for chunk in chat_llm.astream(messages):
            if chunk.text:
                reply += chunk.text
                yield sse(chunk.text)
    except Exception as e:
        print(f"Error generating reply: {e}")
        yield sse(LLM_UNAVAILABLE)
    else:
        save_turn(user_id, user_text, reply)
    yield DONE


async def _reply(user_id: str, text: str):
    if has_pending(user_id) and interpret_confirmation(text) is None:
        # Not a yes/no: the user moved on, so drop the pending action and handle
        # the new message normally instead of blocking the chat until they answer.
        action = cancel_pending(user_id)
        yield sse(PENDING_CANCELLED.format(op=action["op"], path=action["path"]))

    if has_pending(user_id):
        reply = ""
        async for kind, payload in stream_pending(user_id, text):
            if kind == "text":
                reply = payload
            yield sse(payload)
        save_turn(user_id, text, reply)
        yield DONE
        return

    if BARE_CONFIRMATION.fullmatch(text.strip()):
        # A lone yes/no with nothing pending must not reach the planner, which
        # would guess an action (even a delete) from the conversation history.
        yield sse(NOTHING_PENDING)
        yield DONE
        return

    route = await classify(user_id, text)
    print(f"route={route} text={text!r}", flush=True)
    if route == "off_topic":
        # Not saved: a refusal must not become context the model can be talked out of.
        yield sse(OFF_TOPIC_REFUSAL_ES if is_spanish(text) else OFF_TOPIC_REFUSAL)
        yield DONE
        return

    if route == "ide_action":
        reply = ""
        failed = False
        async for kind, payload in stream_ide_action(user_id, text, get_history(user_id)):
            if kind == "error":
                failed = True
            elif kind == "text":
                reply = payload
            yield sse(payload)
        if not failed:
            save_turn(user_id, text, reply)
        yield DONE
        return

    messages = [
        SystemMessage(content=await system_prompt_for(route, text)),
        *get_history(user_id),
        HumanMessage(content=text),
    ]
    async for event in stream_llm(messages, user_id, text):
        yield event


async def generate_reply(user_id: str, text: str):
    """Entry point for POST /chat. One turn at a time per user."""
    async with session_lock(user_id):
        async for event in _reply(user_id, text):
            yield event

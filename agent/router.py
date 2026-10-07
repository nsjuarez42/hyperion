"""Decides which route handles a message: hyperai, ide_action, chitchat or off_topic."""

from langchain_core.messages import HumanMessage, SystemMessage

from agent.config import FALLBACK_ROUTE, ROUTER_HISTORY_MESSAGES, ROUTES
from agent.llm import router_llm
from agent.memory import get_history
from agent.prompts import ROUTER_PROMPT, ROUTER_SYSTEM_PROMPT


async def classify(user_id: str, text: str) -> str:
    """Ask the router model for a route; fall back to chitchat if that fails.

    The history goes in as plain text, not chat messages: given a real
    conversation the model tends to answer it instead of classifying it.
    """
    history = "\n".join(
        f"{m.type}: {m.content}"
        for m in get_history(user_id)[-ROUTER_HISTORY_MESSAGES:]
    )
    prompt = ROUTER_PROMPT.format(history=history or "(none)", text=text)
    try:
        reply = await router_llm.ainvoke(
            [SystemMessage(content=ROUTER_SYSTEM_PROMPT), HumanMessage(content=prompt)]
        )
    except Exception as e:
        print(f"Router error, falling back to {FALLBACK_ROUTE}: {e}")
        return FALLBACK_ROUTE

    answer = reply.content.strip().lower()
    for route in ROUTES:
        if route in answer:
            return route
    print(f"Router gave an unknown answer {answer!r}, falling back to {FALLBACK_ROUTE}")
    return FALLBACK_ROUTE

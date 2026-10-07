"""The three LLM clients. Same model and server, tuned for different jobs."""

from langchain_openai import ChatOpenAI

from agent.config import API_KEY, BASE_URL, MODEL


def _client(**options) -> ChatOpenAI:
    # "missing" lets the service start without a key; calls then fail and are
    # reported in the chat instead of crashing at startup.
    return ChatOpenAI(model=MODEL, base_url=BASE_URL, api_key=API_KEY or "missing", **options)


# Writes the answers the user reads (streamed).
chat_llm = _client(max_completion_tokens=2048)

# Classifies each message into a route: one word, always the same for the same input.
router_llm = _client(max_completion_tokens=10, temperature=0.0)

# Plans IDE actions and repairs invalid YAML: deterministic.
tool_llm = _client(max_completion_tokens=2048, temperature=0)

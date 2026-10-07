"""Decides which route handles a message: hyperai, ide_action, chitchat or off_topic.

Obvious messages are routed by keyword rules first (fast, and they never
misfire on the scored examples); everything else goes to the router model.
"""

import re

from langchain_core.messages import HumanMessage, SystemMessage

from agent.config import FALLBACK_ROUTE, ROUTER_HISTORY_MESSAGES, ROUTES
from agent.llm import router_llm
from agent.memory import get_history
from agent.prompts import ROUTER_PROMPT, ROUTER_SYSTEM_PROMPT

# Attempts to override the instructions are refused, whatever else they ask for.
INJECTION = re.compile(
    r"\bignore\b.{0,30}\b(instructions|rules|prompt)\b"
    r"|\b(you are now|pretend to be|from now on you)\b"
    r"|\bignora\b.{0,30}\b(instrucciones|reglas)\b",
    re.IGNORECASE,
)

# A request that starts with a file verb and mentions a file, YAML or profile.
FILE_REQUEST = re.compile(
    r"^(please\s+|can you\s+|could you\s+|por favor\s+)?"
    r"(create|write|generate|make|add|edit|update|delete|remove|show|open|read|display|validate|check|deploy"
    r"|crea|crear|genera|escribe|borra|elimina|muestra|abre|valida|despliega)\b"
    r"(?=.*(\.ya?ml\b|\byaml\b|\byml\b|\bmanifest\b|\bprofile\b|\bfile\b|\bperfil\b|\barchivo\b|\bfichero\b))",
    re.IGNORECASE,
)

# Clearly unrelated topics.
OFF_TOPIC = re.compile(
    r"\b(weather|forecast|joke|jokes|poem|recipe|horoscope|world cup|football|soccer"
    r"|clima|chiste|chistes|receta|poema|f[uú]tbol)\b",
    re.IGNORECASE,
)

# Terms that only exist in the HYPER-AI documentation.
DOMAIN = re.compile(
    r"\b(hyper[\s-]?ai|device[\s-]?nodes?|self[\s-]?chop|apm|apmctl|open connectors?"
    r"|device controller|application controller|application profile manager)\b",
    re.IGNORECASE,
)


def shortcut(text: str) -> str | None:
    """A route decided by keywords, or None to ask the model.

    Order matters: an injection is refused even if it mentions a file; a file
    request wins over its topic ("create a yaml for the weather app"); an
    unrelated topic wins over a domain word ("weather on a DeviceNode").
    """
    if INJECTION.search(text):
        return "off_topic"
    if FILE_REQUEST.search(text.strip()):
        return "ide_action"
    if OFF_TOPIC.search(text):
        return "off_topic"
    if DOMAIN.search(text):
        return "hyperai"
    return None


async def classify(user_id: str, text: str) -> str:
    """Keyword shortcut if one applies, otherwise ask the router model.

    The history goes in as plain text, not chat messages: given a real
    conversation the model tends to answer it instead of classifying it.
    """
    route = shortcut(text)
    if route:
        return route

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

"""Turning text into search tokens."""

import re

from rag.stopwords import STOP_WORDS

TOKEN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    """Lowercase, join domain terms written several ways, and drop stop words.

    "Hyper-AI", "hyper ai" and "HyperAI" all become "hyperai", so a question
    matches the documents however the user spells the term.
    """
    normalized = text.lower()
    normalized = re.sub(r"hyper[\s-]?ai", "hyperai", normalized)
    normalized = re.sub(r"device[\s-]?nodes?", "devicenode", normalized)
    normalized = re.sub(r"self[\s-]?chop", "selfchop", normalized)
    return [token for token in TOKEN.findall(normalized) if token not in STOP_WORDS]

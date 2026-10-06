import re
from pathlib import Path

from rank_bm25 import BM25Okapi

KNOWLEDGE_DIR = Path(__file__).resolve().parent / "knowledge"
TOKEN = re.compile(r"[a-z0-9]+")
STOP = {
    "a",
    "an",
    "the",
    "is",
    "are",
    "was",
    "were",
    "what",
    "whats",
    "how",
    "does",
    "do",
    "did",
    "of",
    "to",
    "in",
    "on",
    "for",
    "and",
    "or",
    "me",
    "my",
    "about",
    "please",
    "explain",
    "mean",
    "means",
    "tell",
    "describe",
    "with",
    "from",
    "that",
    "this",
    "it",
    "its",
    "be",
    "can",
    "you",
}
MAX_CHUNK = 900


def tokenize(text: str) -> list[str]:
    normalized = text.lower()
    normalized = re.sub(r"hyper[\s-]?ai", "hyperai", normalized)
    normalized = re.sub(r"device[\s-]?nodes?", "devicenode", normalized)
    normalized = re.sub(r"self[\s-]?chop", "selfchop", normalized)
    return [token for token in TOKEN.findall(normalized) if token not in STOP]


def _load_chunks() -> list[dict]:
    chunks = []
    if not KNOWLEDGE_DIR.is_dir():
        return chunks
    for path in sorted(KNOWLEDGE_DIR.glob("*.md")):
        paragraphs = [
            part.strip()
            for part in re.split(r"\n\s*\n", path.read_text(encoding="utf-8"))
            if part.strip()
        ]
        buffer: list[str] = []
        size = 0
        for paragraph in paragraphs:
            if buffer and size + len(paragraph) > MAX_CHUNK:
                chunks.append({"source": path.name, "text": "\n\n".join(buffer)})
                buffer, size = [], 0
            buffer.append(paragraph)
            size += len(paragraph)
        if buffer:
            chunks.append({"source": path.name, "text": "\n\n".join(buffer)})
    return chunks


class Retriever:
    def __init__(self) -> None:
        self.chunks = _load_chunks()
        corpus = [tokenize(chunk["text"]) for chunk in self.chunks]
        self._bm25 = BM25Okapi(corpus) if corpus else None

    def retrieve(self, query: str, k: int = 4) -> list[dict]:
        if self._bm25 is None:
            return []
        tokens = tokenize(query)
        if not tokens:
            return []
        scores = self._bm25.get_scores(tokens)
        order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        return [self.chunks[i] for i in order[:k] if scores[i] > 0]


RETRIEVER = Retriever()

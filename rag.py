import os
import re
from pathlib import Path

import httpx
from dotenv import load_dotenv
from rank_bm25 import BM25Okapi

load_dotenv()

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


EMBED_MODEL = os.environ.get("EMBED_MODEL", "nomic-embed-text")


def _dot(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right))


def _fuse(rankings: list[list[int]]) -> list[int]:
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, index in enumerate(ranking):
            scores[index] = scores.get(index, 0.0) + 1.0 / (60 + rank + 1)
    return sorted(scores, key=lambda index: scores[index], reverse=True)


class Retriever:
    def __init__(self) -> None:
        self.chunks = _load_chunks()
        corpus = [tokenize(chunk["text"]) for chunk in self.chunks]
        self._bm25 = BM25Okapi(corpus) if corpus else None
        self._http: httpx.Client | None = None
        self._vectors: list[list[float]] | None = None
        self._load_embeddings()

    def _embed(self, texts: list[str]) -> list[list[float]]:
        assert self._http is not None
        response = self._http.post(
            "/embeddings", json={"model": EMBED_MODEL, "input": texts}
        )
        response.raise_for_status()
        rows = sorted(response.json()["data"], key=lambda item: item["index"])
        return [row["embedding"] for row in rows]

    def _load_embeddings(self) -> None:
        api_key = os.environ.get("API_KEY", "")
        if not api_key or not self.chunks:
            return
        base_url = os.environ.get("BASE_URL", "https://legion1.di.uoa.gr/v1").rstrip(
            "/"
        )
        try:
            self._http = httpx.Client(
                base_url=base_url,
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=60,
            )
            texts = [f"search_document: {chunk['text']}" for chunk in self.chunks]
            vectors: list[list[float]] = []
            for start in range(0, len(texts), 16):
                vectors.extend(self._embed(texts[start : start + 16]))
            self._vectors = vectors
            print(f"embeddings={EMBED_MODEL} chunks={len(vectors)}", flush=True)
        except Exception as exc:
            self._http = None
            print(
                f"Embeddings unavailable, using keyword search only: {exc}", flush=True
            )

    def retrieve(self, query: str, k: int = 4) -> list[dict]:
        if self._bm25 is None:
            return []
        tokens = tokenize(query)
        rankings: list[list[int]] = []
        if tokens:
            scores = self._bm25.get_scores(tokens)
            rankings.append(
                sorted(
                    (index for index, score in enumerate(scores) if score > 0),
                    key=lambda index: scores[index],
                    reverse=True,
                )
            )
        if self._vectors is not None and self._http is not None:
            try:
                query_vector = self._embed([f"search_query: {query}"])[0]
                rankings.append(
                    sorted(
                        range(len(self._vectors)),
                        key=lambda index: _dot(query_vector, self._vectors[index]),
                        reverse=True,
                    )
                )
            except Exception as exc:
                print(f"Embedding query failed: {exc}", flush=True)
        if not rankings:
            return []
        order = _fuse(rankings)
        picked: list[dict] = []
        per_source: dict[str, int] = {}
        for index in order:
            source = self.chunks[index]["source"]
            if per_source.get(source, 0) >= 2:
                continue
            picked.append(self.chunks[index])
            per_source[source] = per_source.get(source, 0) + 1
            if len(picked) == k:
                break
        return picked


RETRIEVER = Retriever()

"""Hybrid retrieval: BM25 keyword search plus embeddings, fused by rank."""

from rank_bm25 import BM25Okapi

from rag.chunking import load_chunks
from rag.config import (
    DOCUMENT_PREFIX,
    KNOWLEDGE_DIR,
    MAX_PER_SOURCE,
    QUERY_PREFIX,
    TOP_K,
)
from rag.embeddings import EmbeddingClient
from rag.fusion import dot, reciprocal_rank_fusion
from rag.text import tokenize


class Retriever:
    """Loads and indexes the knowledge base once, then answers retrieve() calls.

    Without an API key, or if the embedding server fails at startup, it falls
    back to keyword search only instead of failing.
    """

    def __init__(self, base_url: str, api_key: str, embed_model: str) -> None:
        self.chunks = load_chunks(KNOWLEDGE_DIR)
        corpus = [tokenize(chunk["text"]) for chunk in self.chunks]
        self._bm25 = BM25Okapi(corpus) if corpus else None
        self._embedder: EmbeddingClient | None = None
        self._vectors: list[list[float]] | None = None
        if api_key and self.chunks:
            self._load_embeddings(EmbeddingClient(base_url, api_key, embed_model))

    def _load_embeddings(self, embedder: EmbeddingClient) -> None:
        try:
            texts = [DOCUMENT_PREFIX + chunk["text"] for chunk in self.chunks]
            self._vectors = embedder.embed(texts)
            self._embedder = embedder
            print(f"embeddings={embedder.model} chunks={len(self._vectors)}", flush=True)
        except Exception as exc:
            print(f"Embeddings unavailable, using keyword search only: {exc}", flush=True)

    def _keyword_ranking(self, query: str) -> list[int] | None:
        tokens = tokenize(query)
        if self._bm25 is None or not tokens:
            return None
        scores = self._bm25.get_scores(tokens)
        matching = (index for index, score in enumerate(scores) if score > 0)
        return sorted(matching, key=lambda index: scores[index], reverse=True)

    def _embedding_ranking(self, query: str) -> list[int] | None:
        if self._embedder is None or self._vectors is None:
            return None
        try:
            query_vector = self._embedder.embed([QUERY_PREFIX + query])[0]
        except Exception as exc:
            print(f"Embedding query failed: {exc}", flush=True)
            return None
        vectors = self._vectors
        return sorted(
            range(len(vectors)),
            key=lambda index: dot(query_vector, vectors[index]),
            reverse=True,
        )

    def retrieve(self, query: str, k: int = TOP_K) -> list[dict]:
        """The k best chunks for a question, at most MAX_PER_SOURCE per file."""
        if self._bm25 is None:
            return []
        rankings = [
            ranking
            for ranking in (self._keyword_ranking(query), self._embedding_ranking(query))
            if ranking is not None
        ]
        if not rankings:
            return []
        picked: list[dict] = []
        per_source: dict[str, int] = {}
        for index in reciprocal_rank_fusion(rankings):
            source = self.chunks[index]["source"]
            if per_source.get(source, 0) >= MAX_PER_SOURCE:
                continue
            picked.append(self.chunks[index])
            per_source[source] = per_source.get(source, 0) + 1
            if len(picked) == k:
                break
        return picked

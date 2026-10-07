"""Embeddings from the LLM server.

This calls POST /embeddings with plain httpx on purpose: the OpenAI SDK (and
LangChain's OpenAIEmbeddings) send an `encoding_format` field that the
organisers' litellm/ollama server rejects.
"""

import httpx

from rag.config import EMBED_BATCH, EMBED_TIMEOUT


class EmbeddingClient:
    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        self.model = model
        self._http = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=EMBED_TIMEOUT,
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        """One vector per text, in the same order, sent in batches."""
        vectors: list[list[float]] = []
        for start in range(0, len(texts), EMBED_BATCH):
            response = self._http.post(
                "/embeddings",
                json={"model": self.model, "input": texts[start : start + EMBED_BATCH]},
            )
            response.raise_for_status()
            rows = sorted(response.json()["data"], key=lambda item: item["index"])
            vectors.extend(row["embedding"] for row in rows)
        return vectors

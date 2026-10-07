"""Retrieval over the knowledge/ documents. Independent of the agent: give it a
server URL, key and embedding model, then call retrieve(question)."""

from rag.retriever import Retriever

__all__ = ["Retriever"]

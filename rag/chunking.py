"""Splitting the knowledge base into chunks the model can read."""

import re
from pathlib import Path

from rag.config import MAX_CHUNK


def load_chunks(knowledge_dir: Path) -> list[dict]:
    """Read every .md file and pack its paragraphs into chunks.

    Paragraphs are never split; a chunk closes when the next paragraph would
    take it past MAX_CHUNK characters. Each chunk remembers its source file.
    """
    chunks: list[dict] = []
    if not knowledge_dir.is_dir():
        return chunks
    for path in sorted(knowledge_dir.glob("*.md")):
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

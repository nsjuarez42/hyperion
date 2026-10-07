"""Retrieval settings. Change these to tune what the model gets to read."""

from pathlib import Path

# Markdown documents that make up the knowledge base (shipped inside the image).
KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent / "knowledge"

# Paragraphs are packed into chunks of at most this many characters.
MAX_CHUNK = 900

# How many chunks a question gets, and at most how many from one document,
# so a single long file cannot crowd out the others.
TOP_K = 4
MAX_PER_SOURCE = 2

# Reciprocal rank fusion constant: higher values flatten the difference
# between rank 1 and rank 10 when keyword and embedding rankings are merged.
RRF_K = 60

# Embedding requests: chunks per request and seconds before giving up.
EMBED_BATCH = 16
EMBED_TIMEOUT = 60

# nomic-embed-text expects these task prefixes on documents and queries.
DOCUMENT_PREFIX = "search_document: "
QUERY_PREFIX = "search_query: "

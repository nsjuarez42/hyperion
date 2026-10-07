from rag import Retriever
from rag.chunking import load_chunks
from rag.config import KNOWLEDGE_DIR, MAX_CHUNK, MAX_PER_SOURCE
from rag.fusion import reciprocal_rank_fusion
from rag.text import tokenize


def test_tokenize_joins_spellings_of_domain_terms():
    assert tokenize("What is Hyper-AI?") == ["hyperai"]
    assert tokenize("a device node") == ["devicenode"]
    assert tokenize("self CHOP") == ["selfchop"]


def test_chunks_keep_their_source_and_size():
    chunks = load_chunks(KNOWLEDGE_DIR)
    assert chunks
    for chunk in chunks:
        assert chunk["source"].endswith(".md")
        paragraphs = chunk["text"].split("\n\n")
        # Paragraphs are never split, so only a lone paragraph may exceed the
        # limit; otherwise the text is at most MAX_CHUNK plus the separators.
        if len(paragraphs) > 1:
            assert sum(len(p) for p in paragraphs) <= MAX_CHUNK


def test_rank_fusion_prefers_chunks_high_in_both_rankings():
    assert reciprocal_rank_fusion([[1, 2, 3], [3, 1, 0]])[0] == 1


def keyword_retriever() -> Retriever:
    # No API key: keyword search only, no network.
    return Retriever(base_url="http://unused", api_key="", embed_model="unused")


def test_keyword_retrieval_finds_the_right_documents():
    retriever = keyword_retriever()
    sources = [chunk["source"] for chunk in retriever.retrieve("what is a DeviceNode?")]
    assert sources[0] == "D4.2_3.1_High_Level_Architecture.md"
    sources = [chunk["source"] for chunk in retriever.retrieve("What is HyperAI?")]
    assert "hyper-ai-overview.md" in sources


def test_no_source_gets_more_than_its_share():
    retriever = keyword_retriever()
    sources = [chunk["source"] for chunk in retriever.retrieve("application profile yaml native device")]
    assert all(sources.count(source) <= MAX_PER_SOURCE for source in sources)

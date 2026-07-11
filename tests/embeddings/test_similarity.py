"""Embedding similarity tests."""

from infercache.embeddings import TfidfEmbedding


def test_paraphrase_similarity_above_threshold():
    emb = TfidfEmbedding()
    score = emb.text_similarity(
        "What is the capital of France?",
        "Tell me France's capital city.",
    )
    assert score >= 0.55

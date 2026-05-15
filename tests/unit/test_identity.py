import pytest
from unittest.mock import AsyncMock, MagicMock
from council.graph.nodes import Claim, ClaimType
from council.identity.embedder import NullEmbedder
from council.identity.deduplicator import check_identity


def make_claim(text: str, cid: str = None) -> Claim:
    c = Claim.create(text=text, claim_type=ClaimType.FACT, proposer="a", round_introduced=0)
    if cid:
        c.id = cid
    return c


class FakeEmbedder:
    """Returns predefined similarity-inducing embeddings."""
    def __init__(self, mapping: dict[str, list[float]]):
        self.mapping = mapping

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [self.mapping.get(t, [0.0] * 8) for t in texts]


class TestCheckIdentity:
    @pytest.mark.asyncio
    async def test_null_embedder_new_claim(self):
        existing = [make_claim("existing claim")]
        result = await check_identity(
            new_text="brand new thing",
            existing_claims=existing,
            embedder=NullEmbedder(),
            llm=MagicMock(),
            disambiguation_model="x",
        )
        assert not result.is_duplicate
        assert result.method == "null_embedder"

    @pytest.mark.asyncio
    async def test_exact_text_match(self):
        existing = [make_claim("exact same text")]
        result = await check_identity(
            new_text="exact same text",
            existing_claims=existing,
            embedder=NullEmbedder(),
            llm=MagicMock(),
            disambiguation_model="x",
        )
        assert result.is_duplicate
        assert result.method == "exact_text"
        assert result.similarity == 1.0

    @pytest.mark.asyncio
    async def test_high_similarity_auto_merge(self):
        # Parallel vectors → similarity=1.0
        vec = [1.0, 0.0, 0.0, 0.0]
        text_a = "climate change is real"
        text_b = "climate change exists"
        embedder = FakeEmbedder({text_a: vec, text_b: vec})
        existing = [make_claim(text_a, "claim:existing")]
        result = await check_identity(
            new_text=text_b,
            existing_claims=existing,
            embedder=embedder,
            llm=MagicMock(),
            disambiguation_model="x",
            similarity_high=0.9,
            similarity_low=0.7,
        )
        assert result.is_duplicate
        assert result.method == "embedding_high"
        assert result.merge_into == "claim:existing"

    @pytest.mark.asyncio
    async def test_low_similarity_new_claim(self):
        vec_a = [1.0, 0.0, 0.0, 0.0]
        vec_b = [0.0, 1.0, 0.0, 0.0]  # orthogonal → similarity=0.0
        text_a = "cats are great"
        text_b = "nuclear power is clean"
        embedder = FakeEmbedder({text_a: vec_a, text_b: vec_b})
        existing = [make_claim(text_a)]
        result = await check_identity(
            new_text=text_b,
            existing_claims=existing,
            embedder=embedder,
            llm=MagicMock(),
            disambiguation_model="x",
            similarity_high=0.9,
            similarity_low=0.7,
        )
        assert not result.is_duplicate
        assert result.method == "embedding_low"

    @pytest.mark.asyncio
    async def test_empty_existing_claims(self):
        result = await check_identity(
            new_text="anything",
            existing_claims=[],
            embedder=NullEmbedder(),
            llm=MagicMock(),
            disambiguation_model="x",
        )
        assert not result.is_duplicate

    @pytest.mark.asyncio
    async def test_merge_log_populated(self):
        existing = [make_claim("exact same text")]
        log = []
        await check_identity(
            new_text="exact same text",
            existing_claims=existing,
            embedder=NullEmbedder(),
            llm=MagicMock(),
            disambiguation_model="x",
            merge_log=log,
        )
        assert len(log) == 1
        assert log[0]["is_duplicate"] is True

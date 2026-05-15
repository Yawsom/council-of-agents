import pytest
from council.graph.edges import Edge, EdgeType, EdgeValidationError
from council.graph.graph import ClaimGraph
from council.graph.nodes import Claim, ClaimStatus, ClaimType, Evidence, EvidenceType


def make_claim(text="A claim", agent="agent_a", round=0, confidence=0.9) -> Claim:
    return Claim.create(text=text, claim_type=ClaimType.FACT, proposer=agent,
                        round_introduced=round, confidence=confidence)


def make_evidence(text="Some evidence", agent="agent_a") -> Evidence:
    return Evidence.create(text=text, source="test", evidence_type=EvidenceType.EMPIRICAL,
                           proposer=agent, round_introduced=0)


class TestClaimGraph:
    def test_add_and_retrieve_claim(self):
        g = ClaimGraph()
        c = make_claim()
        g.add_claim(c)
        assert g.get_node(c.id) is c
        assert len(g.claims) == 1

    def test_open_claims(self):
        g = ClaimGraph()
        c1 = make_claim("open")
        c2 = make_claim("also open")
        g.add_claim(c1)
        g.add_claim(c2)
        assert len(g.open_claims()) == 2

    def test_add_edge_marks_claim_contested(self):
        g = ClaimGraph()
        c1 = make_claim("original")
        c2 = make_claim("challenger")
        g.add_claim(c1)
        g.add_claim(c2)
        edge = Edge.create(EdgeType.REBUTS, c2.id, c1.id, "attacks it", "agent_b", 1)
        g.add_edge(edge)
        assert c1.status == ClaimStatus.CONTESTED

    def test_merge_claims_preserves_phrasings(self):
        g = ClaimGraph()
        c1 = make_claim("Nuclear power is safe")
        c2 = make_claim("Nuclear energy has a good safety record")
        g.add_claim(c1)
        g.add_claim(c2)
        g.merge_claims(c1.id, c2.id)
        assert "Nuclear energy has a good safety record" in c1.merged_phrasings
        assert c2.id not in {c.id for c in g.claims}

    def test_merge_merges_confidence_maps(self):
        g = ClaimGraph()
        c1 = make_claim()
        c1.per_agent_confidence["agent_a"] = 0.9
        c2 = make_claim()
        c2.per_agent_confidence["agent_b"] = 0.7
        g.add_claim(c1)
        g.add_claim(c2)
        g.merge_claims(c1.id, c2.id)
        assert c1.per_agent_confidence["agent_b"] == 0.7

    def test_merge_repoints_edges(self):
        g = ClaimGraph()
        c1 = make_claim("target")
        c2 = make_claim("secondary")
        ev = make_evidence()
        g.add_claim(c1)
        g.add_claim(c2)
        g.add_evidence(ev)
        edge = Edge.create(EdgeType.SUPPORTS, ev.id, c2.id, "supports", "agent_a", 0)
        g.add_edge(edge)
        g.merge_claims(c1.id, c2.id)
        assert edge.to_id == c1.id

    def test_update_claim_status(self):
        g = ClaimGraph()
        c = make_claim()
        g.add_claim(c)
        g.update_claim_status(c.id, ClaimStatus.SUPPORTED)
        assert c.status == ClaimStatus.SUPPORTED

    def test_update_claim_status_unknown_raises(self):
        g = ClaimGraph()
        with pytest.raises(KeyError):
            g.update_claim_status("claim:nonexistent", ClaimStatus.REJECTED)

    def test_json_roundtrip(self):
        g = ClaimGraph()
        c = make_claim("roundtrip claim")
        ev = make_evidence()
        g.add_claim(c)
        g.add_evidence(ev)
        edge = Edge.create(EdgeType.SUPPORTS, ev.id, c.id, "supports", "agent_a", 0)
        g.add_edge(edge)

        d = g.to_dict()
        g2 = ClaimGraph.from_dict(d)
        assert g2.get_node(c.id).text == c.text
        assert len(g2.edges) == 1


class TestEdgeValidation:
    def test_rebuts_must_target_claim(self):
        ev = make_evidence()
        with pytest.raises(EdgeValidationError):
            Edge.create(EdgeType.REBUTS, "claim:abc", ev.id, "wrong target", "a", 0)

    def test_supports_can_target_claim(self):
        # Should not raise
        Edge.create(EdgeType.SUPPORTS, "evidence:abc", "claim:xyz", "fine", "a", 0)

    def test_depends_on_must_target_assumption(self):
        with pytest.raises(EdgeValidationError):
            Edge.create(EdgeType.DEPENDS_ON, "claim:abc", "claim:xyz", "wrong", "a", 0)

    def test_contradicts_must_target_claim(self):
        with pytest.raises(EdgeValidationError):
            Edge.create(EdgeType.CONTRADICTS, "claim:abc", "evidence:xyz", "wrong", "a", 0)

    def test_edge_gets_uuid(self):
        e = Edge.create(EdgeType.SUPPORTS, "evidence:abc", "claim:xyz", "ok", "a", 0)
        assert e.id.startswith("edge:")

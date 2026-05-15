from council.graph.graph import ClaimGraph
from council.graph.nodes import Claim, ClaimType, Evidence, EvidenceType
from council.graph.edges import Edge, EdgeType
from council.graph.serializer import serialize_open_state


def test_empty_graph():
    g = ClaimGraph()
    text = serialize_open_state(g, "agent_a")
    assert "No active claims yet" in text


def test_open_claim_appears_in_state():
    g = ClaimGraph()
    c = Claim.create("Nuclear power is safe", ClaimType.FACT, "agent_a", 0)
    g.add_claim(c)
    text = serialize_open_state(g, "agent_a")
    assert "Nuclear power is safe" in text
    assert c.id in text


def test_agent_confidence_shown_for_correct_agent():
    g = ClaimGraph()
    c = Claim.create("A fact", ClaimType.FACT, "agent_a", 0, confidence=0.75)
    g.add_claim(c)
    text_a = serialize_open_state(g, "agent_a")
    assert "0.75" in text_a
    text_b = serialize_open_state(g, "agent_b")
    assert "unknown" in text_b


def test_falsifier_shown():
    g = ClaimGraph()
    c = Claim.create("Claim X", ClaimType.CAUSAL, "a", 0, falsifier="If Y then no")
    g.add_claim(c)
    text = serialize_open_state(g, "a")
    assert "If Y then no" in text


def test_edges_shown_per_claim():
    g = ClaimGraph()
    c1 = Claim.create("main claim", ClaimType.FACT, "a", 0)
    c2 = Claim.create("challenger", ClaimType.FACT, "b", 1)
    g.add_claim(c1)
    g.add_claim(c2)
    e = Edge.create(EdgeType.REBUTS, c2.id, c1.id, "attacks truth", "b", 1)
    g.add_edge(e)
    text = serialize_open_state(g, "a")
    assert e.id in text
    assert "rebuts" in text

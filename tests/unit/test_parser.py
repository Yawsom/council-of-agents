import json
import pytest
from council.agents.parser import (
    ParseError,
    SchemaError,
    parse_phase1,
    parse_phase2,
    parse_arbiter,
    parse_observer,
    parse_verdict,
)


def _p1(overrides=None) -> str:
    base = {
        "agent_id": "agent_a",
        "round": 0,
        "scratchpad": "thinking...",
        "new_claims": [
            {"text": "A claim", "type": "fact", "confidence": 0.8, "falsifier": "if X then no"},
        ],
        "new_evidence": [],
        "new_edges": [],
        "position_updates": [],
    }
    if overrides:
        base.update(overrides)
    return json.dumps(base)


def _p2(overrides=None) -> str:
    base = {
        "agent_id": "agent_a",
        "round": 1,
        "scratchpad": "thinking...",
        "new_claims": [],
        "new_evidence": [],
        "new_edges": [],
        "position_updates": [],
    }
    if overrides:
        base.update(overrides)
    return json.dumps(base)


class TestParsePhase1:
    def test_valid(self):
        r = parse_phase1(_p1(), "agent_a")
        assert r.agent_id == "agent_a"
        assert len(r.new_claims) == 1
        assert r.new_claims[0]["type"] == "fact"

    def test_invalid_claim_type(self):
        bad = _p1({"new_claims": [{"text": "x", "type": "OPINION"}]})
        with pytest.raises(SchemaError):
            parse_phase1(bad, "agent_a")

    def test_missing_claim_text(self):
        bad = _p1({"new_claims": [{"type": "fact"}]})
        with pytest.raises(SchemaError):
            parse_phase1(bad, "agent_a")

    def test_malformed_json_raises(self):
        with pytest.raises(ParseError):
            parse_phase1("not json at all", "agent_a")

    def test_json_embedded_in_prose(self):
        prose = 'Here is my response:\n' + _p1() + '\nThank you.'
        r = parse_phase1(prose, "agent_a")
        assert r.agent_id == "agent_a"

    def test_confidence_defaults_to_1(self):
        content = json.dumps({
            "agent_id": "a",
            "round": 0,
            "scratchpad": "",
            "new_claims": [{"text": "x", "type": "fact"}],
            "new_evidence": [],
            "new_edges": [],
            "position_updates": [],
        })
        r = parse_phase1(content, "a")
        assert r.new_claims[0]["confidence"] == 1.0


class TestParsePhase2:
    def test_valid_empty(self):
        r = parse_phase2(_p2(), "agent_a", 1, set(), set())
        assert r.agent_id == "agent_a"
        assert r.new_claims == []

    def test_invalid_edge_type(self):
        bad = _p2({
            "new_edges": [{"type": "undercuts", "from": "claim:abc", "to": "claim:xyz", "rationale": "x"}]
        })
        with pytest.raises(SchemaError):
            parse_phase2(bad, "agent_a", 1, set(), set())

    def test_position_update_missing_triggered_by(self):
        bad = _p2({
            "position_updates": [{
                "claim_id": "claim:abc",
                "new_confidence": 0.5,
                "reasoning": "changed my mind",
            }]
        })
        with pytest.raises(SchemaError):
            parse_phase2(bad, "agent_a", 1, {"claim:abc"}, {"claim:abc"})

    def test_foreign_position_update_dropped(self):
        content = _p2({
            "position_updates": [{
                "claim_id": "claim:notmine",
                "new_confidence": 0.5,
                "triggered_by": "evidence:xyz",
                "reasoning": "other agent's claim",
            }]
        })
        r = parse_phase2(content, "agent_a", 1, {"claim:notmine"}, set())
        assert r.position_updates == []

    def test_own_position_update_accepted(self):
        content = _p2({
            "position_updates": [{
                "claim_id": "claim:mine",
                "new_confidence": 0.4,
                "triggered_by": "evidence:x",
                "reasoning": "compelling evidence",
            }]
        })
        r = parse_phase2(content, "agent_a", 1, {"claim:mine"}, {"claim:mine"})
        assert len(r.position_updates) == 1


class TestParseArbiter:
    def test_valid(self):
        content = json.dumps({
            "scratchpad": "thinking",
            "round": 1,
            "graph_operations": {"merges": [], "status_changes": []},
            "targeted_query": "probe this",
            "termination_signal": "continue",
            "termination_reasoning": "still active",
        })
        r = parse_arbiter(content, 1)
        assert r.termination_signal == "continue"
        assert r.targeted_query == "probe this"

    def test_invalid_termination_signal(self):
        content = json.dumps({
            "scratchpad": "",
            "round": 1,
            "graph_operations": {},
            "targeted_query": "",
            "termination_signal": "maybe",
            "termination_reasoning": "",
        })
        with pytest.raises(SchemaError):
            parse_arbiter(content, 1)


class TestParseObserver:
    def test_valid(self):
        content = json.dumps({
            "round": 1,
            "check_type": "agent_faithfulness",
            "subject_id": "agent_a",
            "passed": True,
            "issues": [],
            "recommended_action": "continue",
        })
        r = parse_observer(content, 1)
        assert r.passed is True
        assert r.recommended_action == "continue"

    def test_invalid_action(self):
        content = json.dumps({
            "round": 1,
            "check_type": "x",
            "subject_id": "a",
            "passed": True,
            "issues": [],
            "recommended_action": "skip",
        })
        with pytest.raises(SchemaError):
            parse_observer(content, 1)

"""Mock LLM provider — canned JSON responses keyed by prompt phase/role.

Enables full pipeline dry runs via `council run --mock` without API keys.
"""
from __future__ import annotations

import json
from typing import Optional

from ..providers.base import LLMProvider, LLMResponse

# --------------------------------------------------------------------------
# Canned responses keyed by a rough prompt-content pattern
# --------------------------------------------------------------------------

_PHASE1_TEMPLATE = {
    "agent_id": "__AGENT__",
    "round": 0,
    "scratchpad": "Let me think about this carefully. There are several important dimensions to consider here.",
    "new_claims": [
        {
            "text": "The core premise of this question rests on contested empirical assumptions.",
            "type": "fact",
            "confidence": 0.8,
            "falsifier": "If peer-reviewed meta-analyses showed consistent results, I would revise this.",
        },
        {
            "text": "Practical implementation challenges outweigh theoretical benefits in most contexts.",
            "type": "causal",
            "confidence": 0.7,
            "falsifier": "If controlled trials demonstrated net positive outcomes, I would abandon this position.",
        },
        {
            "text": "The question assumes a false dichotomy between available options.",
            "type": "value",
            "confidence": 0.6,
            "falsifier": "If the choice space is genuinely binary, I would need to revise.",
        },
    ],
    "new_evidence": [
        {
            "text": "Historical precedent shows that comparable interventions had mixed results.",
            "source": "General historical record",
            "type": "empirical",
            "supports": "__CLAIM_0__",
        }
    ],
    "new_edges": [],
    "position_updates": [],
}

_PHASE2_TEMPLATE = {
    "agent_id": "__AGENT__",
    "round": "__ROUND__",
    "scratchpad": "Reviewing the peer challenges, I see some compelling points but also some weak arguments.",
    "new_claims": [
        {
            "text": "The challenge raised by peers ignores second-order effects that reverse the conclusion.",
            "type": "causal",
            "confidence": 0.75,
            "falsifier": "If second-order effects were quantified and shown to be negligible, I would concede.",
        }
    ],
    "new_evidence": [],
    "new_edges": [],
    "position_updates": [],
}

_PHASE2_WITH_UPDATE_TEMPLATE = {
    "agent_id": "__AGENT__",
    "round": "__ROUND__",
    "scratchpad": "The evidence cited by my peer is actually compelling. I need to update my position.",
    "new_claims": [],
    "new_evidence": [],
    "new_edges": [],
    "position_updates": [
        {
            "claim_id": "__CLAIM_ID__",
            "new_confidence": 0.4,
            "triggered_by": "__TRIGGERED_BY__",
            "reasoning": "The cited evidence directly undermines the empirical basis I relied on.",
        }
    ],
}

_ARBITER_TEMPLATE = {
    "scratchpad": "Looking at the claim graph, the most contested area is around empirical foundations. I should probe that.",
    "round": "__ROUND__",
    "graph_operations": {
        "merges": [],
        "status_changes": [],
    },
    "targeted_query": "None of the agents have addressed the counterfactual: what specific evidence would change your position? Please state concrete falsifiers for your top claims.",
    "termination_signal": "continue",
    "termination_reasoning": "Novel challenges are still being introduced.",
}

_ARBITER_TERMINATE_TEMPLATE = {
    "scratchpad": "Position update rates have dropped significantly. The debate has reached a natural plateau.",
    "round": "__ROUND__",
    "graph_operations": {
        "merges": [],
        "status_changes": [],
    },
    "targeted_query": "",
    "termination_signal": "terminate",
    "termination_reasoning": "No new challenges introduced in the last two rounds. Terminating stress-test phase.",
}

_OBSERVER_TEMPLATE = {
    "round": "__ROUND__",
    "check_type": "__CHECK_TYPE__",
    "subject_id": "__SUBJECT__",
    "passed": True,
    "issues": [],
    "recommended_action": "continue",
}

_PHASE3_TEMPLATE = {
    "agent_id": "__AGENT__",
    "final_position": "After reviewing all challenges and evidence, my position is that the question requires more contextual specificity before a definitive answer is possible.",
    "original_claims_surviving": [],
    "original_claims_abandoned": [],
    "compelling_challenges_from_others": [],
    "rejected_challenges_from_others": [],
    "remaining_uncertainties": [
        "The empirical data on long-term effects remains ambiguous.",
        "Implementation variance across contexts was not adequately addressed.",
    ],
}


class MockProvider(LLMProvider):
    """Returns canned responses without making network calls. For development and testing."""

    def __init__(self, round_counter: Optional[list[int]] = None) -> None:
        self._call_count = 0
        # Shared mutable counter so orchestration can influence mock behavior
        self._round_counter = round_counter or [0]

    async def call(
        self,
        messages: list[dict],
        model: str,
        temperature: float = 0.7,
        seed: Optional[int] = None,
        timeout: float = 90.0,
        json_mode: bool = False,
        provider_pin: Optional[str] = None,
    ) -> LLMResponse:
        self._call_count += 1
        content = self._pick_response(messages, model)
        return LLMResponse(
            content=content,
            model=model,
            prompt_tokens=150,
            completion_tokens=300,
            cost_usd=0.0001,
        )

    def _pick_response(self, messages: list[dict], model: str) -> str:
        last_user = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                last_user = m.get("content", "")
                break

        lower = last_user.lower()

        # Arbiter: user prompt has "## Unchallenged Claim IDs" and "## Termination Stats"
        if "unchallenged claim ids" in lower or "termination stats" in lower:
            return self._make_arbiter()
        # Observer: user prompt has "Check type:" line
        if "check type:" in lower or "faithfulness" in lower:
            return self._make_observer()
        # Phase 3: user prompt has "Your Original Claim IDs"
        if "your original claim ids" in lower or "final verdict" in lower:
            return self._make_phase3(model)
        # Phase 2: user prompt has "## Arbiter's Query for This Round"
        if "arbiter's query" in lower or "reformat" in lower:
            return self._make_phase2(model)
        # Phase 1: "Provide your initial analysis" or default
        return self._make_phase1(model)

    def _make_phase1(self, model: str) -> str:
        agent_id = model.split("/")[-1][:20]
        resp = json.loads(json.dumps(_PHASE1_TEMPLATE))
        resp["agent_id"] = agent_id
        return json.dumps(resp)

    def _make_phase2(self, model: str) -> str:
        agent_id = model.split("/")[-1][:20]
        # Alternate between a regular and update response
        if self._call_count % 3 == 0:
            resp = json.loads(json.dumps(_PHASE2_WITH_UPDATE_TEMPLATE))
        else:
            resp = json.loads(json.dumps(_PHASE2_TEMPLATE))
        resp["agent_id"] = agent_id
        resp["round"] = self._round_counter[0]
        return json.dumps(resp)

    def _make_arbiter(self) -> str:
        round_num = self._round_counter[0]
        if round_num >= 3:
            resp = json.loads(json.dumps(_ARBITER_TERMINATE_TEMPLATE))
        else:
            resp = json.loads(json.dumps(_ARBITER_TEMPLATE))
        resp["round"] = round_num
        return json.dumps(resp)

    def _make_observer(self) -> str:
        resp = json.loads(json.dumps(_OBSERVER_TEMPLATE))
        resp["round"] = self._round_counter[0]
        resp["check_type"] = "agent_faithfulness"
        resp["subject_id"] = "mock_agent"
        return json.dumps(resp)

    def _make_phase3(self, model: str) -> str:
        agent_id = model.split("/")[-1][:20]
        resp = json.loads(json.dumps(_PHASE3_TEMPLATE))
        resp["agent_id"] = agent_id
        return json.dumps(resp)

from __future__ import annotations

import json

from memmark.agents.memory_agent import LLMMemoryAgent
from memmark.backends.json_store import JsonMemoryStore
from memmark.verifier.full_log import verify_full_log


class FakeLLMClient:
    def complete(self, messages, *, temperature=0.0, max_tokens=None):
        system = messages[0]["content"]
        user = messages[-1]["content"]
        if "Assess feasibility of fixed memory watermark carriers" in user:
            return json.dumps(
                [
                    {
                        "carrier_type": "semantic_variant",
                        "feasible": True,
                        "score": 0.95,
                        "reason": "The extracted fact can be paraphrased safely.",
                    },
                    {"carrier_type": "link_target", "feasible": False, "score": 0.1, "reason": "No stable links."},
                    {"carrier_type": "update_target", "feasible": False, "score": 0.1, "reason": "No update target."},
                    {"carrier_type": "merge_strategy", "feasible": False, "score": 0.1, "reason": "No merge."},
                ]
            )
        if "Generate semantic-equivalent memory variants" in user:
            payload = json.loads(user)
            event = payload["event"]
            return json.dumps(
                [
                    {"text": event},
                    {"text": f"User preference: {event}"},
                    {"text": f"Remember that the user wants: {event}"},
                ]
            )
        if "Score candidate acceptability" in user:
            payload = json.loads(user)
            weights = [0.4, 0.35, 0.25]
            return json.dumps(
                {
                    candidate["candidate_id"]: weights[idx] if idx < len(weights) else 0.1
                    for idx, candidate in enumerate(payload["candidates"])
                }
            )
        if "Extract durable long-term memory facts" in system:
            user_message = user.split("Assistant response:", 1)[0].lower()
            if "prefer" in user_message:
                return json.dumps(["User prefers concise technical answers."])
            if "like" in user_message:
                return json.dumps(["User likes Python implementations."])
            if "want" in user_message:
                return json.dumps(["User wants minimal background explanation."])
            return "[]"
        return "I will follow your preference and answer concisely."


def main() -> None:
    payload_bits = "101101"
    agent = LLMMemoryAgent(
        backend=JsonMemoryStore(),
        payload_bits=payload_bits,
        agent_id="llm-demo-agent",
        session_id="llm-demo-session",
        llm_client=FakeLLMClient(),
    )
    turns = [
        "I prefer concise technical answers.",
        "Tell me what MemMark is.",
        "I like Python implementations.",
        "I want minimal background explanation.",
        "I prefer direct conclusions first.",
    ]
    previous_bit_index = 0
    decoded = ""
    for user_input in turns:
        turn = agent.handle_turn(user_input)
        print({"user": turn.user_input, "response": turn.response, "memory_events": turn.memory_events})
        for result in turn.evolve_results:
            verification = verify_full_log(
                result.decision,
                result.audit,
                payload_bits=payload_bits,
                previous_bit_index=previous_bit_index,
            )
            previous_bit_index = result.audit.bit_index_after
            decoded += verification.decoded_bits[: len(verification.expected_prefix)]
            print(
                {
                    "memory": result.memory_record,
                    "selected": result.audit.selected_candidate_id,
                    "embedded": result.audit.bits_embedded,
                    "decoded": verification.decoded_bits,
                    "commitment_valid": verification.commitment_valid,
                    "bits_match": verification.bits_match,
                }
            )
    recovered = decoded[: len(payload_bits)]
    print(
        {
            "payload_bits": payload_bits,
            "recovered_bits": recovered,
            "bit_recovery_rate": sum(a == b for a, b in zip(payload_bits, recovered)) / len(payload_bits),
            "audit_records": len(agent.memmark_audit_log),
            "memory_snapshot": agent.memmark.backend.snapshot(),
        }
    )


if __name__ == "__main__":
    main()

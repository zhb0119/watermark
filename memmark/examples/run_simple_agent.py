from __future__ import annotations

from memmark.agents.memory_agent import SimpleMemoryAgent
from memmark.backends.json_store import JsonMemoryStore
from memmark.verifier.full_log import verify_full_log


def main() -> None:
    payload_bits = "101101"
    agent = SimpleMemoryAgent(
        backend=JsonMemoryStore(),
        payload_bits=payload_bits,
        agent_id="demo-agent",
        session_id="agent-session",
    )
    turns = [
        "I prefer concise technical answers.",
        "Please explain MemMark briefly.",
        "I like Python implementations.",
        "我希望你先给结论。",
        "I want minimal background explanation.",
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

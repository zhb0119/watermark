from __future__ import annotations

import argparse

from memmark.agents.memory_agent import LLMMemoryAgent
from memmark.backends.json_store import JsonMemoryStore
from memmark.verifier.full_log import verify_full_log


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--payload-bits", default="101101")
    parser.add_argument("--agent-id", default="real-llm-agent")
    parser.add_argument("--session-id", default="real-llm-session")
    parser.add_argument("--memory-path", default=None)
    parser.add_argument("--turn", action="append", default=[])
    return parser


def main() -> None:
    args = build_parser().parse_args()
    agent = LLMMemoryAgent(
        backend=JsonMemoryStore(args.memory_path),
        payload_bits=args.payload_bits,
        agent_id=args.agent_id,
        session_id=args.session_id,
    )
    turns = args.turn or [
        "I prefer concise technical answers.",
        "Tell me what MemMark is.",
        "I like Python implementations.",
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
                payload_bits=args.payload_bits,
                previous_bit_index=previous_bit_index,
            )
            previous_bit_index = result.audit.bit_index_after
            decoded += verification.decoded_bits[: len(verification.expected_prefix)]
            print(
                {
                    "tau": result.decision.tau,
                    "candidate_count": len(result.decision.candidates),
                    "probabilities": result.decision.probabilities,
                    "memory": result.memory_record,
                    "selected": result.audit.selected_candidate_id,
                    "embedded": result.audit.bits_embedded,
                    "decoded": verification.decoded_bits,
                    "commitment_valid": verification.commitment_valid,
                    "bits_match": verification.bits_match,
                }
            )
    recovered = decoded[: len(args.payload_bits)]
    print(
        {
            "payload_bits": args.payload_bits,
            "recovered_bits": recovered,
            "bit_recovery_rate": sum(a == b for a, b in zip(args.payload_bits, recovered)) / len(args.payload_bits),
            "audit_records": len(agent.memmark_audit_log),
            "memory_snapshot": agent.memmark.backend.snapshot(),
        }
    )


if __name__ == "__main__":
    main()

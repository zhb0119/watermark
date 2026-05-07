from __future__ import annotations

from memmark.backends.json_store import JsonMemoryStore
from memmark.sdk.memory_watermarker import MemoryWatermarker
from memmark.verifier.full_log import verify_full_log


def main() -> None:
    backend = JsonMemoryStore()
    payload_bits = "101101"
    watermarker = MemoryWatermarker(
        backend=backend,
        payload_bits=payload_bits,
        agent_id="demo-agent",
        session_id="demo-session",
    )
    events = [
        "prefers concise technical answers",
        "likes Python implementations",
        "wants direct conclusions first",
        "prefers minimal background explanation",
    ]
    previous_bit_index = 0
    decoded = ""
    for event in events:
        if previous_bit_index >= len(payload_bits):
            break
        result = watermarker.evolve(event)
        verification = verify_full_log(
            result.decision,
            result.audit,
            payload_bits=payload_bits,
            previous_bit_index=previous_bit_index,
        )
        previous_bit_index = result.audit.bit_index_after
        decoded += verification.decoded_bits
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
            "memory_snapshot": backend.snapshot(),
        }
    )


if __name__ == "__main__":
    main()

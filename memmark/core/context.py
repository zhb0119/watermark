from __future__ import annotations

import hashlib
import json
from typing import Any


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def build_context(
    *,
    agent_id: str,
    session_id: str,
    turn_id: int,
    tau: str,
    event_text: str,
    memory_snapshot: Any,
    previous_commitment: str = "",
) -> str:
    payload = {
        "agent_id": agent_id,
        "session_id": session_id,
        "turn_id": turn_id,
        "tau": tau,
        "event_hash": sha256_text(event_text),
        "memory_hash": sha256_text(stable_json(memory_snapshot)),
        "previous_commitment": previous_commitment,
    }
    return stable_json(payload)

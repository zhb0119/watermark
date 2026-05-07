from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional

from memmark.backends.base import MemoryBackendAdapter
from memmark.llm.openai_client import OpenAIChatClient
from memmark.sdk.memory_watermarker import EvolveResult, MemoryWatermarker


MemoryExtractor = Callable[[str, str], List[str]]
ResponseGenerator = Callable[[str], str]


@dataclass(frozen=True)
class AgentTurnResult:
    user_input: str
    response: str
    memory_events: List[str]
    evolve_results: List[EvolveResult] = field(default_factory=list)


class MemMarkAgentMixin:
    def init_memmark(
        self,
        *,
        backend: MemoryBackendAdapter,
        payload_bits: str,
        agent_id: str,
        session_id: str,
    ) -> None:
        self.memmark = MemoryWatermarker(
            backend=backend,
            payload_bits=payload_bits,
            agent_id=agent_id,
            session_id=session_id,
        )
        self.memmark_audit_log = []
        self.memmark_decision_log = []

    def write_memory_watermarked(self, text: str) -> EvolveResult:
        if not hasattr(self, "memmark"):
            raise RuntimeError("MemMark is not initialized. Call init_memmark() first.")
        result = self.memmark.evolve(text)
        self.memmark_audit_log.append(result.audit)
        self.memmark_decision_log.append(result.decision)
        return result


class SimpleMemoryAgent(MemMarkAgentMixin):
    def __init__(
        self,
        *,
        backend: MemoryBackendAdapter,
        payload_bits: str,
        agent_id: str = "simple-agent",
        session_id: str = "simple-session",
        response_generator: Optional[ResponseGenerator] = None,
        memory_extractor: Optional[MemoryExtractor] = None,
    ) -> None:
        self.init_memmark(
            backend=backend,
            payload_bits=payload_bits,
            agent_id=agent_id,
            session_id=session_id,
        )
        self.response_generator = response_generator or self._default_response_generator
        self.memory_extractor = memory_extractor or self._default_memory_extractor
        self.turn_history: List[AgentTurnResult] = []

    def handle_turn(self, user_input: str) -> AgentTurnResult:
        response = self.response_generator(user_input)
        memory_events = self.memory_extractor(user_input, response)
        evolve_results = [self.write_memory_watermarked(event) for event in memory_events]
        turn_result = AgentTurnResult(
            user_input=user_input,
            response=response,
            memory_events=memory_events,
            evolve_results=evolve_results,
        )
        self.turn_history.append(turn_result)
        return turn_result

    @staticmethod
    def _default_response_generator(user_input: str) -> str:
        return f"Acknowledged: {user_input}"

    @staticmethod
    def _default_memory_extractor(user_input: str, response: str) -> List[str]:
        lowered = user_input.strip().lower()
        triggers = ["prefer", "like", "want", "需要", "喜欢", "偏好", "希望"]
        if any(trigger in lowered for trigger in triggers):
            return [lowered]
        return []


class LLMMemoryAgent(MemMarkAgentMixin):
    def __init__(
        self,
        *,
        backend: MemoryBackendAdapter,
        payload_bits: str,
        agent_id: str = "llm-agent",
        session_id: str = "llm-session",
        llm_client: Optional[Any] = None,
    ) -> None:
        self.init_memmark(
            backend=backend,
            payload_bits=payload_bits,
            agent_id=agent_id,
            session_id=session_id,
        )
        self.llm_client = llm_client or OpenAIChatClient()
        self.turn_history: List[AgentTurnResult] = []
        self.raw_memory_extraction_outputs: List[str] = []

    def handle_turn(self, user_input: str) -> AgentTurnResult:
        response = self._generate_response(user_input)
        memory_events = self._extract_memory_events(user_input, response)
        evolve_results = [self.write_memory_watermarked(event) for event in memory_events]
        turn_result = AgentTurnResult(
            user_input=user_input,
            response=response,
            memory_events=memory_events,
            evolve_results=evolve_results,
        )
        self.turn_history.append(turn_result)
        return turn_result

    def _generate_response(self, user_input: str) -> str:
        memory_snapshot = self.memmark.backend.snapshot()
        messages = [
            {
                "role": "system",
                "content": "You are a helpful agent. Use long-term memory only when it is relevant.",
            },
            {
                "role": "user",
                "content": (
                    "Long-term memory snapshot:\n"
                    f"{json.dumps(memory_snapshot, ensure_ascii=False)}\n\n"
                    f"User input:\n{user_input}"
                ),
            },
        ]
        return self.llm_client.complete(messages, temperature=0.2)

    def _extract_memory_events(self, user_input: str, response: str) -> List[str]:
        messages = [
            {
                "role": "system",
                "content": (
                    "Extract durable long-term memory facts from the user message and assistant response. "
                    "Return only a strict JSON array of strings. "
                    "Include stable user preferences, goals, constraints, project facts, or decisions. "
                    "Return [] if nothing should be stored."
                ),
            },
            {
                "role": "user",
                "content": f"User message:\n{user_input}\n\nAssistant response:\n{response}",
            },
        ]
        raw = self.llm_client.complete(messages, temperature=0.0)
        self.raw_memory_extraction_outputs.append(raw)
        return self._parse_memory_events(raw)

    @staticmethod
    def _parse_memory_events(raw: str) -> List[str]:
        text = raw.strip()
        start = text.find("[")
        end = text.rfind("]")
        if start < 0 or end < start:
            return []
        try:
            parsed = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return []
        events = []
        for item in parsed:
            if isinstance(item, str) and item.strip():
                events.append(item.strip())
            elif isinstance(item, dict):
                value = item.get("text") or item.get("memory") or item.get("fact")
                if isinstance(value, str) and value.strip():
                    events.append(value.strip())
        return events

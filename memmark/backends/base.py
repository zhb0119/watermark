from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict


class MemoryBackendAdapter(ABC):
    @abstractmethod
    def snapshot(self) -> Any:
        raise NotImplementedError

    @abstractmethod
    def apply(self, operation: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

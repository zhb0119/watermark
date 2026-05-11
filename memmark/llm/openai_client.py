from __future__ import annotations

import os
from typing import Any, Dict, List, Optional


class OpenAIChatClient:
    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        client: Any = None,
    ) -> None:
        if client is not None:
            self.client = client
        else:
            try:
                from openai import OpenAI
            except ModuleNotFoundError as exc:
                raise RuntimeError("openai package is required for LLMMemoryAgent") from exc
            resolved_api_key = api_key or os.getenv("MEMMARK_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("DEEPSEEK_API_KEY")
            if not resolved_api_key:
                raise RuntimeError("Set MEMMARK_API_KEY, OPENAI_API_KEY, or DEEPSEEK_API_KEY")
            resolved_base_url = base_url or os.getenv("MEMMARK_BASE_URL") or os.getenv("TARGET_LLM_BASE")
            default_headers = self._default_headers()
            self.client = OpenAI(
                api_key=resolved_api_key,
                base_url=resolved_base_url,
                default_headers=default_headers or None,
            )
        self.model = model or os.getenv("MEMMARK_MODEL") or os.getenv("TARGET_LLM_MODEL") or "deepseek-chat"

    def complete(
        self,
        messages: List[Dict[str, str]],
        *,
        temperature: float = 0.0,
        max_tokens: Optional[int] = None,
    ) -> str:
        kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        if self.model.startswith("deepseek-v4-"):
            kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
        response = self.client.chat.completions.create(**kwargs)
        return response.choices[0].message.content or ""

    @staticmethod
    def _default_headers() -> Dict[str, str]:
        headers = {}
        site_url = OpenAIChatClient._ascii_header_value(os.getenv("OPENROUTER_SITE_URL"))
        app_name = OpenAIChatClient._ascii_header_value(os.getenv("OPENROUTER_APP_NAME"))
        if site_url:
            headers["HTTP-Referer"] = site_url
        if app_name:
            headers["X-Title"] = app_name
        return headers

    @staticmethod
    def _ascii_header_value(value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        encoded = value.encode("ascii", errors="ignore").decode("ascii").strip()
        return encoded or None

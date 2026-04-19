from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass
from typing import Optional, Protocol


class LLMClient(Protocol):
    def complete(self, prompt: str) -> str: ...


@dataclass(frozen=True)
class OpenAIChatCompletionsClient:
    """
    Minimal OpenAI client using stdlib HTTP (no extra deps).

    Enabled when OPENAI_API_KEY is set. Uses /v1/chat/completions.
    """

    api_key: str
    model: str = "gpt-4o-mini"
    timeout_seconds: float = 20.0

    def complete(self, prompt: str) -> str:
        url = "https://api.openai.com/v1/chat/completions"
        payload = {
            "model": self.model,
            "temperature": 0.0,
            "messages": [
                {"role": "system", "content": "You are a precise JSON-only incident diagnosis engine."},
                {"role": "user", "content": prompt},
            ],
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:  # nosec - controlled endpoint
            body = resp.read().decode("utf-8")
        parsed = json.loads(body)
        return parsed["choices"][0]["message"]["content"]


@dataclass
class LlamaCppClient:
    """
    Local CPU LLM via llama.cpp Python bindings (GGUF models).

    Requires: `pip install llama-cpp-python`
    """

    model_path: str
    n_ctx: int = 2048
    temperature: float = 0.0
    max_tokens: int = 256

    def __post_init__(self) -> None:
        try:
            from llama_cpp import Llama  # type: ignore
        except Exception as e:  # pragma: no cover
            raise RuntimeError(
                "llama-cpp-python is not installed. Install with: pip install llama-cpp-python"
            ) from e

        object.__setattr__(
            self,
            "_llm",
            Llama(
                model_path=self.model_path,
                n_ctx=self.n_ctx,
                n_threads=int(os.getenv("AGENTCLOUD_LLM_THREADS", "4")),
                n_batch=int(os.getenv("AGENTCLOUD_LLM_BATCH", "64")),
                verbose=False,
            ),
        )

    def complete(self, prompt: str) -> str:
        llm = getattr(self, "_llm")
        out = llm.create_chat_completion(
            messages=[
                {"role": "system", "content": "You are a precise JSON-only incident diagnosis engine."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=self.max_tokens,
            temperature=self.temperature,
        )
        return out["choices"][0]["message"]["content"]


def build_llm_from_env() -> Optional[LLMClient]:
    # Prefer local LLM if configured
    local_path = os.getenv("AGENTCLOUD_LOCAL_MODEL_PATH", "").strip()
    if local_path:
        if not os.path.exists(local_path):
            # Invalid path should not crash the app; diagnosis will fall back.
            print(f"[DIAGNOSIS][FALLBACK] Local model path not found: {local_path}")
            return None
        n_ctx = int(os.getenv("AGENTCLOUD_LOCAL_MODEL_CTX", "2048"))
        max_tokens = int(os.getenv("AGENTCLOUD_LOCAL_MODEL_MAX_TOKENS", "256"))
        temp = float(os.getenv("AGENTCLOUD_LOCAL_MODEL_TEMPERATURE", "0"))
        try:
            return LlamaCppClient(
                model_path=local_path,
                n_ctx=n_ctx,
                max_tokens=max_tokens,
                temperature=temp,
            )
        except Exception as e:
            print(f"[DIAGNOSIS][FALLBACK] Local LLM init failed: {e}")
            return None

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None
    model = os.getenv("AGENTCLOUD_LLM_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
    timeout = float(os.getenv("AGENTCLOUD_LLM_TIMEOUT_SECONDS", "20"))
    return OpenAIChatCompletionsClient(api_key=api_key, model=model, timeout_seconds=timeout)


"""
Lightweight LLM client for OpenRouter API calls.
Handles chat completions with retry logic, cost tracking, and structured responses.
"""

import time
import uuid
from dataclasses import dataclass, field
from typing import Optional

import httpx
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from prompt_ops.config import settings, get_model_cost


@dataclass
class LLMResponse:
    """Structured response from an LLM API call."""

    content: str
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    latency_ms: float
    cost_usd: float
    request_id: str
    temperature: float
    finish_reason: str = "stop"
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        """Returns True if the response has no error and contains content."""
        return self.error is None and bool(self.content)


class LLMClient:
    """Client for making LLM API calls through OpenRouter."""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.api_key = api_key or settings.api_key
        self.base_url = base_url or settings.base_url

        self._client = httpx.Client(
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/prompt-ops",
                "X-Title": "PROMPT-OPS",
            },
            timeout=httpx.Timeout(60.0, connect=10.0),
        )

    def chat(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        system_prompt: Optional[str] = None,
    ) -> LLMResponse:
        """Send a chat completion request and return a structured response."""
        model = model or settings.default_model
        request_id = str(uuid.uuid4())
        start_time = time.perf_counter()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        try:
            raw = self._call_api(payload)

            content = raw["choices"][0]["message"]["content"]
            usage = raw.get("usage", {})
            input_tokens = usage.get("prompt_tokens", 0)
            output_tokens = usage.get("completion_tokens", 0)
            total_tokens = usage.get("total_tokens", 0)
            finish_reason = raw["choices"][0].get("finish_reason", "stop")

            latency_ms = (time.perf_counter() - start_time) * 1000
            cost_usd = get_model_cost(model, input_tokens, output_tokens)

            logger.debug(
                "LLM call | model={} tokens={} latency={:.0f}ms cost=${:.6f}",
                model, total_tokens, latency_ms, cost_usd,
            )

            return LLMResponse(
                content=content,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                latency_ms=latency_ms,
                cost_usd=cost_usd,
                request_id=request_id,
                temperature=temperature,
                finish_reason=finish_reason,
            )

        except Exception as exc:
            latency_ms = (time.perf_counter() - start_time) * 1000
            logger.error("LLM call failed | model={} error={}", model, exc)

            return LLMResponse(
                content="",
                model=model,
                input_tokens=0,
                output_tokens=0,
                total_tokens=0,
                latency_ms=latency_ms,
                cost_usd=0.0,
                request_id=request_id,
                temperature=temperature,
                finish_reason="error",
                error=str(exc),
            )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.HTTPStatusError)),
    )
    def _call_api(self, payload: dict) -> dict:
        """POST to the chat completions endpoint with retry logic."""
        response = self._client.post(
            f"{self.base_url}/chat/completions",
            json=payload,
        )
        response.raise_for_status()
        return response.json()

    def estimate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Estimate the cost for a given model and token counts."""
        return get_model_cost(model, input_tokens, output_tokens)

    def close(self):
        """Close the underlying HTTP client."""
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


# Module-level singleton
llm_client = LLMClient()

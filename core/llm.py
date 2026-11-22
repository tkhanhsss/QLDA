"""Send text prompts to the local 9Router API."""

import os
from dataclasses import dataclass
from time import perf_counter, sleep

from dotenv import load_dotenv
from openai import APIError, APIStatusError, APITimeoutError, OpenAI

DEFAULT_BASE_URL = "http://localhost:20128/v1"
REQUEST_TIMEOUT = 120
MAX_RETRIES = 3


@dataclass(frozen=True)
class LLMResult:
    """Text and request metadata returned by the router."""

    text: str
    model: str
    tokens_in: int | None
    tokens_out: int | None
    duration_ms: int


class LLMError(RuntimeError):
    """A configuration or API error suitable for display in the terminal."""


def _router_client() -> OpenAI:
    load_dotenv()
    base_url = os.getenv("ROUTER_BASE_URL", "").strip() or DEFAULT_BASE_URL
    api_key = os.getenv("ROUTER_API_KEY", "").strip()
    if not api_key:
        raise LLMError("Thiếu ROUTER_API_KEY. Hãy điền API key vào .env.")
    return OpenAI(
        base_url=base_url,
        api_key=api_key,
        timeout=REQUEST_TIMEOUT,
        max_retries=0,
    )


def check_router() -> None:
    """Check that 9Router responds to GET /models."""
    with _router_client() as client:
        try:
            client.models.list()
        except APIError as error:
            raise LLMError(str(error).replace(client.api_key, "[redacted]")) from None


def _should_retry(error: APIError) -> bool:
    if isinstance(error, APITimeoutError):
        return True
    if isinstance(error, APIStatusError):
        return error.status_code == 429 or 500 <= error.status_code < 600
    return False


def chat(agent: str, system: str, user: str) -> LLMResult:
    """Send a text prompt using the agent model or MODEL_DEFAULT."""
    with _router_client() as client:
        model_var = f"MODEL_{agent.upper()}"
        model = (
            os.getenv(model_var, "").strip() or os.getenv("MODEL_DEFAULT", "").strip()
        )
        if not model:
            raise LLMError(f"Thiếu {model_var} hoặc MODEL_DEFAULT. Hãy kiểm tra .env.")

        started = perf_counter()
        for attempt in range(MAX_RETRIES + 1):
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                )
                break
            except APIError as error:
                if attempt == MAX_RETRIES or not _should_retry(error):
                    raise LLMError(
                        str(error).replace(client.api_key, "[redacted]")
                    ) from None
                sleep(2**attempt)

        if not response.choices or not response.choices[0].message.content:
            raise LLMError("9Router không trả về nội dung văn bản.")

        usage = response.usage
        return LLMResult(
            text=response.choices[0].message.content,
            model=response.model or model,
            tokens_in=usage.prompt_tokens if usage else None,
            tokens_out=usage.completion_tokens if usage else None,
            duration_ms=round((perf_counter() - started) * 1000),
        )

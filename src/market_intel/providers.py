from __future__ import annotations

import hashlib
from datetime import datetime
from threading import Lock
from typing import Any, Protocol, TypeVar
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from market_intel.models import SearchResult

T = TypeVar("T", bound=BaseModel)


class SearchProvider(Protocol):
    def search(self, query: str, *, count: int, freshness: str | None = None) -> list[SearchResult]: ...


class StructuredLLM(Protocol):
    def generate(self, schema: type[T], *, system: str, prompt: str) -> T: ...


class YouSearchClient:
    """Adapter for You.com's POST Web Search API."""

    endpoint = "https://ydc-index.io/v1/search"

    def __init__(self, api_key: str, timeout_seconds: float = 30) -> None:
        if not api_key:
            raise ValueError("YDC_API_KEY is required")
        self._client = httpx.Client(
            headers={"X-API-Key": api_key, "Content-Type": "application/json"},
            timeout=timeout_seconds,
        )
        self._calls = 0
        self._usage_lock = Lock()

    @retry(
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.TransportError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, max=4),
        reraise=True,
    )
    def search(self, query: str, *, count: int = 8, freshness: str | None = None) -> list[SearchResult]:
        payload: dict[str, Any] = {"query": query, "count": count}
        if freshness:
            payload["freshness"] = freshness
        with self._usage_lock:
            self._calls += 1
        response = self._client.post(self.endpoint, json=payload)
        response.raise_for_status()
        data = response.json().get("results", {})
        results: list[SearchResult] = []
        for kind in ("web", "news"):
            for raw in data.get(kind, []) or []:
                url = raw.get("url")
                if not url:
                    continue
                published = raw.get("page_age") or raw.get("published_at")
                try:
                    published_at = datetime.fromisoformat(published) if published else None
                except (TypeError, ValueError):
                    published_at = None
                results.append(
                    SearchResult(
                        id=hashlib.sha1(url.encode(), usedforsecurity=False).hexdigest()[:10],
                        query=query,
                        result_type=kind,
                        title=raw.get("title") or url,
                        url=url,
                        description=raw.get("description") or "",
                        snippets=raw.get("snippets") or [],
                        published_at=published_at,
                        source_domain=urlparse(url).netloc.removeprefix("www."),
                    )
                )
        return results

    def usage_snapshot(self) -> dict[str, int]:
        with self._usage_lock:
            return {"calls": self._calls}


class OpenAIStructuredLLM:
    """Official OpenAI Responses API adapter with thread-safe token metering."""

    def __init__(self, api_key: str, model: str, timeout_seconds: float = 30) -> None:
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required")
        from openai import OpenAI

        self._client = OpenAI(
            api_key=api_key,
            timeout=timeout_seconds,
            max_retries=2,
        )
        self._model = model
        self._calls = 0
        self._input_tokens = 0
        self._cached_input_tokens = 0
        self._output_tokens = 0
        self._usage_lock = Lock()

    def generate(self, schema: type[T], *, system: str, prompt: str) -> T:
        response = self._client.responses.parse(
            model=self._model,
            instructions=system,
            input=prompt,
            text_format=schema,
            max_output_tokens=8_000,
            temperature=0,
        )
        if response.output_parsed is None:
            raise ValueError("OpenAI returned no parsed structured output")
        usage = response.usage
        cached = 0
        if usage and usage.input_tokens_details:
            cached = usage.input_tokens_details.cached_tokens or 0
        with self._usage_lock:
            self._calls += 1
            if usage:
                self._input_tokens += usage.input_tokens
                self._cached_input_tokens += cached
                self._output_tokens += usage.output_tokens
        return response.output_parsed

    def usage_snapshot(self) -> dict[str, int]:
        with self._usage_lock:
            return {
                "calls": self._calls,
                "input_tokens": self._input_tokens,
                "cached_input_tokens": self._cached_input_tokens,
                "output_tokens": self._output_tokens,
            }

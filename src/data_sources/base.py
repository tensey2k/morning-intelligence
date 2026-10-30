"""
Base classes for data sources.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from datetime import datetime

import httpx
from pydantic import BaseModel


class DataSourceError(Exception):
    """Base exception for data source errors."""
    def __init__(self, message: str, source: str, details: Optional[Dict] = None):
        self.message = message
        self.source = source
        self.details = details or {}
        super().__init__(f"[{source}] {message}")


class RateLimitError(DataSourceError):
    """Rate limit exceeded."""
    def __init__(self, source: str, retry_after: Optional[int] = None):
        super().__init__("Rate limit exceeded", source, {"retry_after": retry_after})


class DataSourceBase(ABC):
    """Abstract base class for all data sources."""

    def __init__(
        self,
        name: str,
        base_url: str,
        api_key: Optional[str] = None,
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        self.name = name
        self.base_url = base_url
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(self.timeout),
                headers=self.default_headers,
            )
        return self._client

    @property
    def default_headers(self) -> Dict[str, str]:
        """Default headers for requests."""
        return {
            "User-Agent": "MorningIntelligence/1.0",
            "Accept": "application/json",
        }

    async def close(self):
        """Close HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        headers: Optional[Dict] = None,
    ) -> Any:
        """Make HTTP request with retries and error handling."""
        request_headers = {**self.default_headers}
        if headers:
            request_headers.update(headers)

        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = await self.client.request(
                    method=method,
                    url=endpoint,
                    params=params,
                    headers=request_headers,
                )

                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After")
                    raise RateLimitError(self.name, int(retry_after) if retry_after else None)

                response.raise_for_status()
                return response.json()

            except httpx.TimeoutException as e:
                last_error = DataSourceError(f"Request timeout: {e}", self.name)
            except httpx.HTTPStatusError as e:
                last_error = DataSourceError(
                    f"HTTP {e.response.status_code}: {e.response.text}",
                    self.name,
                    {"status_code": e.response.status_code},
                )
                # Don't retry client errors (4xx)
                if 400 <= e.response.status_code < 500:
                    break
            except Exception as e:
                last_error = DataSourceError(f"Request failed: {e}", self.name)

            # Exponential backoff
            if attempt < self.max_retries - 1:
                import asyncio
                await asyncio.sleep(2 ** attempt)

        raise last_error

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if data source is available."""
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
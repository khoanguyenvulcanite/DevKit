import asyncio
import logging
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)


class ApiClientError(Exception):
    pass


class ApiRateLimitError(ApiClientError):
    pass


class ApiServerError(ApiClientError):
    pass


class RestClient:
    def __init__(
        self,
        base_url: str,
        token: Optional[str] = None,
        timeout: tuple[int, int] = (5, 30),
        max_retries: int = 4,
        backoff_factor: float = 1.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor

        headers = {
            "Accept": "application/json",
            "User-Agent": "my-python-client/1.0",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"

        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=headers,
            timeout=httpx.Timeout(connect=timeout[0], read=timeout[1], write=timeout[1], pool=timeout[0]),
        )

    def _should_retry(self, status_code: int) -> bool:
        return status_code in {429, 500, 502, 503, 504}

    def _handle_response(self, response: httpx.Response) -> Any:
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            raise ApiRateLimitError(f"Rate limited. Retry-After={retry_after}")

        if 500 <= response.status_code < 600:
            raise ApiServerError(
                f"Server error {response.status_code}: {response.text[:300]}"
            )

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise ApiClientError(
                f"HTTP {response.status_code}: {response.text[:300]}"
            ) from e

        content_type = response.headers.get("Content-Type", "")
        if "application/json" in content_type:
            return response.json()
        return response.text

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Any:
        if not path.startswith("/"):
            path = f"/{path}"

        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                logger.info("HTTP %s %s", method.upper(), f"{self.base_url}{path}")
                response = await self.client.request(
                    method=method.upper(),
                    url=path,
                    params=params,
                    json=json,
                    headers=headers,
                )

                if self._should_retry(response.status_code) and attempt < self.max_retries:
                    retry_after = response.headers.get("Retry-After")
                    if retry_after and retry_after.isdigit():
                        sleep_seconds = float(retry_after)
                    else:
                        sleep_seconds = self.backoff_factor * (2 ** attempt)

                    logger.warning(
                        "Retryable response %s on %s %s. Retrying in %.1fs",
                        response.status_code,
                        method.upper(),
                        path,
                        sleep_seconds,
                    )
                    await asyncio.sleep(sleep_seconds)
                    continue

                return self._handle_response(response)

            except httpx.RequestError as e:
                last_error = e
                if attempt >= self.max_retries:
                    break

                sleep_seconds = self.backoff_factor * (2 ** attempt)
                logger.warning(
                    "Request error on %s %s: %s. Retrying in %.1fs",
                    method.upper(),
                    path,
                    str(e),
                    sleep_seconds,
                )
                await asyncio.sleep(sleep_seconds)

        raise ApiClientError(f"Request failed after retries: {last_error}")

    async def get(self, path: str, **kwargs: Any) -> Any:
        return await self.request("GET", path, **kwargs)

    async def post(self, path: str, **kwargs: Any) -> Any:
        return await self.request("POST", path, **kwargs)

    async def patch(self, path: str, **kwargs: Any) -> Any:
        return await self.request("PATCH", path, **kwargs)

    async def delete(self, path: str, **kwargs: Any) -> Any:
        return await self.request("DELETE", path, **kwargs)

    async def aclose(self) -> None:
        await self.client.aclose()
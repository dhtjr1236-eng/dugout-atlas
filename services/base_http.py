from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import aiohttp
import requests

from config.settings import SETTINGS

LOGGER = logging.getLogger(__name__)
RETRYABLE = {408, 425, 429, 500, 502, 503, 504}
JSON_LIMIT = 20 * 1024 * 1024
BYTES_LIMIT = 5 * 1024 * 1024
TEXT_LIMIT = 100 * 1024 * 1024


class HttpError(RuntimeError):
    def __init__(self, message: str, *, status: int | None = None, retry_after: float | None = None):
        super().__init__(message)
        self.status = status
        self.retry_after = retry_after


def _retry_after(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return min(60.0, max(0.0, float(value)))
    except ValueError:
        try:
            return min(60.0, max(0.0, (parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds()))
        except (ValueError, TypeError, OverflowError):
            return None


def _delay(attempt: int, error: Exception) -> float:
    retry_after = getattr(error, "retry_after", None)
    return retry_after if retry_after is not None else min(2 ** (attempt - 1), 8) + random.uniform(0, 0.25)


def _should_retry(error: Exception) -> bool:
    return not isinstance(error, HttpError) or error.status in RETRYABLE


async def _read_limited(response: aiohttp.ClientResponse, limit: int) -> bytes:
    length = response.headers.get("Content-Length")
    if length and length.isdecimal() and int(length) > limit:
        raise HttpError("Response exceeds size limit")
    chunks = bytearray()
    async for chunk in response.content.iter_chunked(64 * 1024):
        if len(chunks) + len(chunk) > limit:
            raise HttpError("Response exceeds size limit")
        chunks.extend(chunk)
    return bytes(chunks)


async def _async_get(url: str, *, params: dict[str, Any] | None, timeout: int | None,
                     retries: int | None, limit: int, json_result: bool) -> Any:
    timeout = timeout or SETTINGS.request_timeout_seconds
    retries = max(1, retries if retries is not None else SETTINGS.request_retries)
    headers = {"User-Agent": SETTINGS.user_agent}
    if json_result:
        headers["Accept"] = "application/json"
    client_timeout = aiohttp.ClientTimeout(total=timeout, connect=min(timeout, 10), sock_read=timeout)
    last_error: Exception | None = None
    # A single session is reused for all attempts and closed deterministically.
    async with aiohttp.ClientSession(timeout=client_timeout, headers=headers) as session:
        for attempt in range(1, retries + 1):
            try:
                async with session.get(url, params=params) as response:
                    if response.status >= 400:
                        raise HttpError(f"HTTP {response.status}", status=response.status,
                                        retry_after=_retry_after(response.headers.get("Retry-After")))
                    raw = await _read_limited(response, limit)
                    if not json_result:
                        return raw
                    payload = json.loads(raw)
                    if not isinstance(payload, dict):
                        raise HttpError("Expected JSON object")
                    return payload
            except (aiohttp.ClientError, asyncio.TimeoutError, HttpError) as exc:
                last_error = exc
                LOGGER.warning("GET failed attempt %s/%s (%s)", attempt, retries, exc)
                if attempt >= retries or not _should_retry(exc):
                    break
                await asyncio.sleep(_delay(attempt, exc))
    raise HttpError(str(last_error or "Unknown HTTP error"), status=getattr(last_error, "status", None))


async def async_get_json(url: str, *, params: dict[str, Any] | None = None,
                         timeout: int | None = None, retries: int | None = None) -> dict[str, Any]:
    return await _async_get(url, params=params, timeout=timeout, retries=retries,
                            limit=JSON_LIMIT, json_result=True)


async def async_get_bytes(url: str, *, timeout: int | None = None,
                          retries: int | None = None) -> bytes:
    return await _async_get(url, params=None, timeout=timeout, retries=retries,
                            limit=BYTES_LIMIT, json_result=False)


def sync_get_text(url: str, *, params: dict[str, Any] | None = None,
                  timeout: int | None = None, retries: int | None = None) -> str:
    timeout = timeout or SETTINGS.request_timeout_seconds
    retries = max(1, retries if retries is not None else SETTINGS.request_retries)
    last_error: Exception | None = None
    with requests.Session() as session:
        session.headers.update({"User-Agent": SETTINGS.user_agent})
        for attempt in range(1, retries + 1):
            try:
                with session.get(url, params=params, timeout=(min(timeout, 10), timeout), stream=True) as response:
                    if response.status_code >= 400:
                        raise HttpError(f"HTTP {response.status_code}", status=response.status_code,
                                        retry_after=_retry_after(response.headers.get("Retry-After")))
                    length = response.headers.get("Content-Length")
                    if length and length.isdecimal() and int(length) > TEXT_LIMIT:
                        raise HttpError("Response exceeds size limit")
                    chunks = bytearray()
                    for chunk in response.iter_content(chunk_size=64 * 1024):
                        if len(chunks) + len(chunk) > TEXT_LIMIT:
                            raise HttpError("Response exceeds size limit")
                        chunks.extend(chunk)
                    return chunks.decode(response.encoding or "utf-8", errors="replace")
            except (requests.RequestException, HttpError) as exc:
                last_error = exc
                LOGGER.warning("GET failed attempt %s/%s (%s)", attempt, retries, exc)
                if attempt >= retries or not _should_retry(exc):
                    break
                time.sleep(_delay(attempt, exc))
    raise HttpError(str(last_error or "Unknown HTTP error"), status=getattr(last_error, "status", None))

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp
import requests

from config.settings import SETTINGS

LOGGER = logging.getLogger(__name__)


class HttpError(RuntimeError):
    pass


async def async_get_json(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    timeout: int | None = None,
    retries: int | None = None,
) -> dict[str, Any]:
    timeout = timeout or SETTINGS.request_timeout_seconds
    retries = retries or SETTINGS.request_retries
    headers = {"User-Agent": SETTINGS.user_agent, "Accept": "application/json"}
    last_error: Exception | None = None

    client_timeout = aiohttp.ClientTimeout(total=timeout)
    for attempt in range(1, retries + 1):
        try:
            async with aiohttp.ClientSession(timeout=client_timeout, headers=headers) as session:
                async with session.get(url, params=params) as response:
                    if response.status >= 500:
                        raise HttpError(f"Server error {response.status}: {url}")
                    if response.status >= 400:
                        text = await response.text()
                        raise HttpError(
                            f"HTTP {response.status}: {url} | {text[:300]}"
                        )
                    payload = await response.json(content_type=None)
                    if not isinstance(payload, dict):
                        raise HttpError(f"Expected JSON object from {url}")
                    return payload
        except (aiohttp.ClientError, asyncio.TimeoutError, HttpError) as exc:
            last_error = exc
            LOGGER.warning(
                "GET failed attempt %s/%s: %s (%s)", attempt, retries, url, exc
            )
            if attempt < retries:
                await asyncio.sleep(min(2 ** (attempt - 1), 5))
    raise HttpError(str(last_error or "Unknown HTTP error"))


async def async_get_bytes(
    url: str,
    *,
    timeout: int | None = None,
    retries: int | None = None,
) -> bytes:
    timeout = timeout or SETTINGS.request_timeout_seconds
    retries = retries or SETTINGS.request_retries
    headers = {"User-Agent": SETTINGS.user_agent}
    client_timeout = aiohttp.ClientTimeout(total=timeout)
    last_error: Exception | None = None

    for attempt in range(1, retries + 1):
        try:
            async with aiohttp.ClientSession(timeout=client_timeout, headers=headers) as session:
                async with session.get(url) as response:
                    if response.status >= 400:
                        raise HttpError(f"HTTP {response.status}: {url}")
                    return await response.read()
        except (aiohttp.ClientError, asyncio.TimeoutError, HttpError) as exc:
            last_error = exc
            if attempt < retries:
                await asyncio.sleep(min(2 ** (attempt - 1), 5))
    raise HttpError(str(last_error or "Unknown HTTP error"))


def sync_get_text(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    timeout: int | None = None,
    retries: int | None = None,
) -> str:
    timeout = timeout or SETTINGS.request_timeout_seconds
    retries = retries or SETTINGS.request_retries
    headers = {"User-Agent": SETTINGS.user_agent}
    last_error: Exception | None = None

    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, params=params, headers=headers, timeout=timeout)
            response.raise_for_status()
            return response.text
        except requests.RequestException as exc:
            last_error = exc
            LOGGER.warning(
                "GET failed attempt %s/%s: %s (%s)", attempt, retries, url, exc
            )
    raise HttpError(str(last_error or "Unknown HTTP error"))

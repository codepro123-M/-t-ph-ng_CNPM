"""Bounded providers, persistent translation cache and provider cooldowns."""

import asyncio
import hashlib
import html
import json
import logging
import math
import os
import ssl
import tempfile
import time
from pathlib import Path
from weakref import WeakValueDictionary

import requests
from fastapi import HTTPException
from starlette.concurrency import run_in_threadpool

from app.core.config import settings

logger = logging.getLogger("smartstay.translation")


def trusted_ca():
    return (
        os.environ.get("REQUESTS_CA_BUNDLE")
        or os.environ.get("CURL_CA_BUNDLE")
        or ssl.get_default_verify_paths().cafile
        or True
    )


def byte_chunks(text, maximum):
    """Never cut a Unicode code point or exceed a provider's UTF-8 byte limit."""
    while text:
        segment = text.encode("utf-8")[:maximum].decode("utf-8", errors="ignore")
        end = len(segment)
        if end < len(text):
            boundary = max(segment.rfind(" "), segment.rfind("\n"))
            if boundary > len(segment) // 2:
                end = boundary + 1
        if not end:
            raise ValueError("Chunk size is smaller than one Unicode character")
        yield text[:end]
        text = text[end:]


class ProviderError(Exception):
    def __init__(self, reason, retry_after=60):
        self.reason = reason
        self.retry_after = retry_after
        super().__init__(reason)


def mymemory_translate(text, source, target):
    params = {"q": text, "langpair": source + "|" + target, "mt": 1}
    if settings.MYMEMORY_EMAIL.strip():
        params["de"] = settings.MYMEMORY_EMAIL.strip()
    with requests.get(
        "https://api.mymemory.translated.net/get",
        params=params,
        timeout=(3, 15),
        verify=trusted_ca(),
    ) as response:
        response.raise_for_status()
        payload = response.json()
    if not isinstance(payload, dict):
        raise ProviderError("invalid provider response")
    data = payload.get("responseData")
    translated = data.get("translatedText") if isinstance(data, dict) else None
    quota = str(payload.get("quotaFinished", False)).lower() == "true"
    warning = isinstance(translated, str) and translated.upper().startswith(
        "MYMEMORY WARNING:"
    )
    if quota or warning:
        raise ProviderError("daily quota reached", retry_after=86400)
    if str(payload.get("responseStatus")) != "200":
        raise ProviderError("request rejected by provider")
    if not isinstance(translated, str) or not translated.strip():
        raise ProviderError("empty translation")
    return html.unescape(translated).strip()


def read_record(path):
    try:
        if path.stat().st_size > 1024 * 1024:
            return None
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except (OSError, ValueError):
        return None


def write_record(path, value):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False
        ) as output:
            temporary = Path(output.name)
            json.dump(value, output, ensure_ascii=False)
        temporary.replace(path)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)


class TranslationService:
    def __init__(self, cache_dir, semaphore):
        self._cache_dir = cache_dir
        self._semaphore = semaphore
        self._locks = WeakValueDictionary()

    @property
    def cache_dir(self):
        return Path(self._cache_dir())

    def cooldown(self, provider):
        state = read_record(self.cache_dir / ("cooldown-" + provider + ".json"))
        try:
            until = float((state or {}).get("until", 0))
            remaining = (
                max(0, math.ceil(until - time.time())) if math.isfinite(until) else 0
            )
        except (ValueError, TypeError):
            remaining = 0
        return remaining, (state or {}).get("reason", "provider cooling down")

    def block(self, provider, error):
        remaining, _ = self.cooldown(provider)
        delay = min(86400, max(remaining, error.retry_after, 1))
        write_record(
            self.cache_dir / ("cooldown-" + provider + ".json"),
            {"until": time.time() + delay, "reason": error.reason},
        )

    @staticmethod
    def provider_error(provider, error):
        if isinstance(error, ProviderError):
            return error
        response = getattr(error, "response", None)
        if response is not None and response.status_code == 429:
            delay = (
                settings.TRANSLATION_GOOGLE_COOLDOWN_SECONDS
                if provider == "google"
                else 600
            )
            try:
                delay = max(delay, int(response.headers.get("Retry-After", 0)))
            except (ValueError, TypeError):
                pass
            return ProviderError("rate-limited", retry_after=delay)
        return ProviderError("provider unavailable")

    async def translate(
        self, text, source, target, google_translate, *, use_cache=True
    ):
        mode = settings.TRANSLATION_PROVIDER
        signature = json.dumps(
            ["translation-v1", mode, source, target, text], ensure_ascii=False
        )
        key = hashlib.sha256(signature.encode()).hexdigest()
        path = self.cache_dir / (key + ".json")
        lock = self._locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[key] = lock
        async with lock:
            cached = read_record(path) if use_cache else None
            try:
                valid = bool(
                    cached
                    and cached.get("key") == key
                    and cached.get("provider") in {"google", "mymemory"}
                    and isinstance(cached.get("text"), str)
                    and cached["text"].strip()
                    and float(cached["expires_at"]) > time.time()
                )
            except (KeyError, ValueError, TypeError):
                valid = False
            if valid:
                return {
                    "text": cached["text"],
                    "provider": cached["provider"],
                    "cache_hit": True,
                }
            failures, delays = [], []
            for provider in ["google", "mymemory"] if mode == "auto" else [mode]:
                remaining, reason = self.cooldown(provider)
                if remaining:
                    failures.append(provider + ": " + reason)
                    delays.append(remaining)
                    continue
                try:
                    pieces = []
                    async with self._semaphore:
                        for part in byte_chunks(
                            text, 4000 if provider == "google" else 500
                        ):
                            if not part.strip():
                                continue
                            call = (
                                google_translate
                                if provider == "google"
                                else (
                                    lambda value: mymemory_translate(
                                        value, source, target
                                    )
                                )
                            )
                            translated = await asyncio.wait_for(
                                run_in_threadpool(call, part), timeout=25
                            )
                            if (
                                not isinstance(translated, str)
                                or not translated.strip()
                            ):
                                raise ProviderError("empty translation")
                            pieces.append(translated.strip())
                except Exception as error:
                    failure = self.provider_error(provider, error)
                    try:
                        self.block(provider, failure)
                    except OSError:
                        raise HTTPException(
                            503, "Translation cache unavailable; retry later"
                        ) from None
                    failures.append(provider + ": " + failure.reason)
                    delays.append(self.cooldown(provider)[0])
                    logger.warning(
                        "%s translation failed (%s)", provider, type(error).__name__
                    )
                    continue
                translated = " ".join(pieces)
                record = {
                    "key": key,
                    "text": translated,
                    "provider": provider,
                    "expires_at": time.time() + settings.TRANSLATION_CACHE_TTL_SECONDS,
                }
                try:
                    write_record(path, record)
                except OSError:
                    raise HTTPException(
                        503, "Translation cache unavailable; retry later"
                    ) from None
                return {"text": translated, "provider": provider, "cache_hit": False}
            raise HTTPException(
                503,
                "Translation unavailable (" + "; ".join(failures) + "). Retry later.",
                headers={"Retry-After": str(max(1, min(delays or [60])))},
            )

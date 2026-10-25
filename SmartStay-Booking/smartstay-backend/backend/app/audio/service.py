"""Real translation and Edge speech, bounded calls and validated atomic audio cache."""

import asyncio
import hashlib
import json
import os
import tempfile
import time
from pathlib import Path
from weakref import WeakValueDictionary

import edge_tts
from edge_tts.communicate import _SSL_CTX
import requests
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator
from fastapi import HTTPException
from starlette.concurrency import run_in_threadpool

from app.content.media import inspect_audio
from app.core.config import MAX_CONCURRENT_TTS, VOICE_CATALOG_TTL_SECONDS, settings
from app.audio.translation import TranslationService, trusted_ca

# The pinned Edge client starts with bundled roots. Add the operating system's
# trusted roots as well, keeping certificate and hostname verification enabled.
_SSL_CTX.load_default_certs()
if os.environ.get("REQUESTS_CA_BUNDLE"):
    _SSL_CTX.load_verify_locations(cafile=os.environ["REQUESTS_CA_BUNDLE"])

NEURAL_VOICE_MAP = {
    "vi": {
        "voice": "vi-VN-HoaiMyNeural",
        "short_name": "HoaiMyNeural",
        "lang_name": "Tiếng Việt",
    },
    "en": {
        "voice": "en-US-JennyNeural",
        "short_name": "JennyNeural",
        "lang_name": "English",
    },
    "zh": {
        "voice": "zh-CN-XiaoxiaoNeural",
        "short_name": "XiaoxiaoNeural",
        "lang_name": "中文",
    },
    "ja": {
        "voice": "ja-JP-NanamiNeural",
        "short_name": "NanamiNeural",
        "lang_name": "日本語",
    },
    "ko": {
        "voice": "ko-KR-SunHiNeural",
        "short_name": "SunHiNeural",
        "lang_name": "한국어",
    },
}
PRIORITY_LANGUAGES = ["en", "vi", "zh", "ja", "ko"]
VOICE_CATALOG_TTL = VOICE_CATALOG_TTL_SECONDS


class BoundedGoogleTranslator(GoogleTranslator):
    """The pinned provider's parser/language map with explicit HTTP timeouts."""

    def translate(self, text, **kwargs):
        params = dict(self._url_params, sl=self._source, tl=self._target)
        params[self.payload_key or "q"] = text
        with requests.get(
            self._base_url,
            params=params,
            proxies=self.proxies,
            timeout=(3, 15),
            verify=trusted_ca(),
        ) as response:
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
        element = soup.find(self._element_tag, self._element_query) or soup.find(
            self._element_tag, self._alt_element_query
        )
        if element is None or not element.get_text(strip=True):
            raise ValueError("No translation returned")
        return element.get_text(strip=True)


class TTSService:
    def __init__(self, cache_dir=None):
        self._cache_dir = Path(cache_dir) if cache_dir else None
        self._locks = WeakValueDictionary()
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_TTS)
        self._catalog = None
        self._catalog_time = 0
        self._all_voices = None
        self._all_voices_time = 0
        self._translations = TranslationService(
            lambda: self.cache_dir / "_translations_v1", self._semaphore
        )

    @property
    def cache_dir(self):
        return self._cache_dir or settings.CONTENT_MEDIA_DIR / "_tts_cache_v2"

    def get_voice_catalog(self, force_refresh=False):
        now = time.monotonic()
        cached = bool(
            self._catalog
            and not force_refresh
            and now - self._catalog_time < VOICE_CATALOG_TTL
        )
        if not cached:
            self._catalog = [
                dict(lang=code, provider="edge-tts", **meta)
                for code, meta in NEURAL_VOICE_MAP.items()
            ]
            self._catalog_time = now
        return {
            "cached": cached,
            "ttl_seconds": VOICE_CATALOG_TTL,
            "ttl_remaining_seconds": max(
                0, int(VOICE_CATALOG_TTL - now + self._catalog_time)
            ),
            "voices": self._catalog,
        }

    async def voice_for(self, language):
        language = language.lower().split("-")[0]
        if language in NEURAL_VOICE_MAP:
            return NEURAL_VOICE_MAP[language]["voice"]
        try:
            if (
                not self._all_voices
                or time.monotonic() - self._all_voices_time >= VOICE_CATALOG_TTL
            ):
                self._all_voices = await asyncio.wait_for(
                    edge_tts.list_voices(), timeout=20
                )
                self._all_voices_time = time.monotonic()
        except Exception:
            raise HTTPException(
                503, "Speech provider unavailable; retry later"
            ) from None
        choices = [
            voice
            for voice in self._all_voices
            if voice["Locale"].lower().split("-")[0] == language
        ]
        if not choices:
            raise HTTPException(422, "No speech voice is available for this language")
        choices.sort(
            key=lambda voice: (voice.get("Gender") != "Female", voice["ShortName"])
        )
        return choices[0]["ShortName"]

    async def translate_text(self, text, target_lang, source_lang="vi"):
        return (await self.translate_with_info(text, target_lang, source_lang))["text"]

    async def translate_with_info(
        self, text, target_lang, source_lang="vi", *, use_cache=True
    ):
        source, target = (
            source_lang.lower().split("-")[0],
            target_lang.lower().split("-")[0],
        )
        if not text.strip() or source == target:
            return {"text": text, "provider": "identity", "cache_hit": True}
        codes = {"zh": "zh-CN"}

        def translate_google(part):
            return BoundedGoogleTranslator(
                source=codes.get(source, source), target=codes.get(target, target)
            ).translate(part)

        return await self._translations.translate(
            text, source, target, translate_google, use_cache=use_cache
        )

    async def synthesize_mp3(self, text, lang, updated_at=None):
        if not text.strip():
            raise HTTPException(422, "Speech text must not be empty")
        voice = await self.voice_for(lang)
        key = hashlib.sha256(
            json.dumps(["edge-real-v2", voice, lang, text], ensure_ascii=False).encode()
        ).hexdigest()
        lock = self._locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[key] = lock
        async with lock:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            path = self.cache_dir / (key + ".mp3")
            cache_hit = False
            if path.is_file() and path.stat().st_size <= settings.MAX_AUDIO_SIZE_BYTES:
                try:
                    await run_in_threadpool(inspect_audio, path.read_bytes())
                    cache_hit = True
                except HTTPException as error:
                    if error.status_code == 503:
                        raise
                    path.unlink(missing_ok=True)
            if not cache_hit:
                temporary = None
                try:
                    with tempfile.NamedTemporaryFile(
                        dir=self.cache_dir, suffix=".mp3", delete=False
                    ) as file:
                        temporary = Path(file.name)
                    async with self._semaphore:
                        data = bytearray()
                        communicator = edge_tts.Communicate(
                            text, voice, connect_timeout=5, receive_timeout=25
                        )

                        async def receive():
                            async for message in communicator.stream():
                                if message["type"] == "audio":
                                    data.extend(message["data"])
                                    if len(data) > settings.MAX_AUDIO_SIZE_BYTES:
                                        raise HTTPException(
                                            413,
                                            "Generated audio exceeds the configured size limit",
                                        )

                        await asyncio.wait_for(receive(), timeout=90)
                    try:
                        await run_in_threadpool(inspect_audio, bytes(data))
                    except HTTPException as error:
                        if error.status_code == 415:
                            raise HTTPException(
                                503,
                                "Speech provider returned invalid audio; retry later",
                            ) from None
                        raise
                    temporary.write_bytes(data)
                    temporary.replace(path)
                except HTTPException:
                    raise
                except Exception:
                    raise HTTPException(
                        503, "Speech provider unavailable; retry later"
                    ) from None
                finally:
                    if temporary:
                        temporary.unlink(missing_ok=True)
            data = path.read_bytes()
            return {
                "audio_bytes": data,
                "sha256": hashlib.sha256(data).hexdigest(),
                "filename": path.name,
                "file_path": str(path),
                "lang": lang,
                "voice": voice,
                "cache_hit": cache_hit,
                "size_bytes": len(data),
                "updated_at": updated_at,
            }


tts_service = TTSService()

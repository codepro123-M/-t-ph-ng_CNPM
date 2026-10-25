"""Provider HTTP contracts, quota errors, restart cache and concurrent requests."""

import asyncio
import threading
import time

import pytest
import requests
from fastapi import HTTPException

from app.audio import translation
from app.audio.service import BoundedGoogleTranslator, TTSService
from app.core.config import settings


class Response:
    def __init__(self, payload, status=200, headers=None):
        self.payload, self.status_code, self.headers = payload, status, headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(response=self)

    def json(self):
        return self.payload


def blocked():
    return requests.HTTPError(response=Response({}, 429, {"Retry-After": "1200"}))


@pytest.fixture
def setup(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "TRANSLATION_PROVIDER", "auto")
    monkeypatch.setattr(settings, "MYMEMORY_EMAIL", "")
    return TTSService(tmp_path / "cache")


@pytest.mark.asyncio
async def test_google_429_falls_back_once_and_cache_survives_restart(
    setup, monkeypatch
):
    calls = {"google": 0, "mymemory": 0}

    def google(*args):
        calls["google"] += 1
        raise blocked()

    def get(url, **kwargs):
        assert url == "https://api.mymemory.translated.net/get"
        assert kwargs["params"]["langpair"] == "vi|en"
        assert kwargs["timeout"] == (3, 15) and kwargs["verify"] is not False
        assert "de" not in kwargs["params"]
        calls["mymemory"] += 1
        time.sleep(0.01)
        return Response(
            {
                "responseStatus": 200,
                "responseData": {"translatedText": "Welcome &amp; enjoy!"},
            }
        )

    monkeypatch.setattr(BoundedGoogleTranslator, "translate", google)
    monkeypatch.setattr(translation.requests, "get", get)
    first, second = await asyncio.gather(
        setup.translate_with_info("Xin chào!", "en"),
        setup.translate_with_info("Xin chào!", "en"),
    )
    assert first["text"] == second["text"] == "Welcome & enjoy!"
    assert first["provider"] == "mymemory"
    assert sorted([first["cache_hit"], second["cache_hit"]]) == [False, True]
    restarted = TTSService(setup.cache_dir)
    assert (await restarted.translate_with_info("Xin chào!", "en"))["cache_hit"]
    assert calls == {"google": 1, "mymemory": 1}
    assert restarted._translations.cooldown("google")[0] >= 1199
    await restarted.translate_text("Hướng dẫn nhận phòng.", "en")
    assert calls == {"google": 1, "mymemory": 2}


@pytest.mark.asyncio
async def test_mymemory_respects_500_utf8_bytes_and_opt_in_email(setup, monkeypatch):
    monkeypatch.setattr(settings, "TRANSLATION_PROVIDER", "mymemory")
    monkeypatch.setattr(settings, "MYMEMORY_EMAIL", "developer@example.com")
    segments = []

    def get(url, **kwargs):
        params = kwargs["params"]
        assert params["de"] == "developer@example.com"
        assert params["langpair"] == "vi|ja"
        assert len(params["q"].encode("utf-8")) <= 500
        segments.append(params["q"])
        return Response(
            {"responseStatus": "200", "responseData": {"translatedText": "ようこそ"}}
        )

    monkeypatch.setattr(translation.requests, "get", get)
    text = "Phòng nghỉ tiện nghi 🌴. " * 80
    result = await setup.translate_with_info(text, "ja")
    assert "".join(segments) == text
    assert len(segments) > 1 and result["provider"] == "mymemory"
    assert result["text"] == " ".join(["ようこそ"] * len(segments))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {
            "responseStatus": 403,
            "quotaFinished": True,
            "responseData": {"translatedText": "limit"},
        },
        {
            "responseStatus": 200,
            "responseData": {
                "translatedText": "MYMEMORY WARNING: YOU USED ALL AVAILABLE FREE TRANSLATIONS"
            },
        },
    ],
)
async def test_quota_message_never_becomes_a_translation(setup, monkeypatch, payload):
    monkeypatch.setattr(settings, "TRANSLATION_PROVIDER", "mymemory")
    calls = []

    def get(*args, **kwargs):
        calls.append(1)
        return Response(payload)

    monkeypatch.setattr(translation.requests, "get", get)
    with pytest.raises(HTTPException) as failure:
        await setup.translate_text("Xin chào.", "en")
    assert failure.value.status_code == 503
    assert "daily quota reached" in failure.value.detail
    assert int(failure.value.headers["Retry-After"]) >= 86399
    restarted = TTSService(setup.cache_dir)
    with pytest.raises(HTTPException):
        await restarted.translate_text("Mô tả khác.", "en")
    assert calls == [1]
    records = list((setup.cache_dir / "_translations_v1").glob("*.json"))
    assert all(path.name.startswith("cooldown-") for path in records)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        [],
        {},
        {"responseStatus": 200, "responseData": {}},
        {"responseStatus": 400, "responseData": {"translatedText": "ERROR"}},
    ],
)
async def test_invalid_provider_reply_is_not_success(setup, monkeypatch, payload):
    monkeypatch.setattr(settings, "TRANSLATION_PROVIDER", "mymemory")
    monkeypatch.setattr(
        translation.requests, "get", lambda *args, **kwargs: Response(payload)
    )
    with pytest.raises(HTTPException) as failure:
        await setup.translate_text("Xin chào.", "en")
    assert failure.value.status_code == 503


@pytest.mark.asyncio
async def test_google_only_does_not_silently_switch_providers(setup, monkeypatch):
    monkeypatch.setattr(settings, "TRANSLATION_PROVIDER", "google")

    def google(*args):
        raise blocked()

    def unexpected(*args, **kwargs):
        pytest.fail("MyMemory should not be called in Google-only mode")

    monkeypatch.setattr(BoundedGoogleTranslator, "translate", google)
    monkeypatch.setattr(translation.requests, "get", unexpected)
    with pytest.raises(HTTPException) as failure:
        await setup.translate_text("Xin chào.", "en")
    assert "google: rate-limited" in failure.value.detail


@pytest.mark.asyncio
async def test_cache_expiry_and_source_language_changes_refetch(setup, monkeypatch):
    monkeypatch.setattr(settings, "TRANSLATION_PROVIDER", "mymemory")
    clock = [1000.0]
    monkeypatch.setattr(translation.time, "time", lambda: clock[0])
    calls = []

    def get(*args, **kwargs):
        calls.append(kwargs["params"]["langpair"])
        return Response(
            {"responseStatus": 200, "responseData": {"translatedText": "Welcome"}}
        )

    monkeypatch.setattr(translation.requests, "get", get)
    assert not (await setup.translate_with_info("Chào", "en"))["cache_hit"]
    assert (await setup.translate_with_info("Chào", "en"))["cache_hit"]
    await setup.translate_text("Chào khác", "en")
    await setup.translate_text("Chào", "en", "fr")
    clock[0] += settings.TRANSLATION_CACHE_TTL_SECONDS + 1
    assert not (await setup.translate_with_info("Chào", "en"))["cache_hit"]
    assert calls == ["vi|en", "vi|en", "fr|en", "vi|en"]


@pytest.mark.asyncio
async def test_different_translations_share_concurrency_limit(setup, monkeypatch):
    monkeypatch.setattr(settings, "TRANSLATION_PROVIDER", "mymemory")
    lock = threading.Lock()
    active, highest = 0, 0

    def get(*args, **kwargs):
        nonlocal active, highest
        with lock:
            active += 1
            highest = max(highest, active)
        time.sleep(0.03)
        with lock:
            active -= 1
        return Response(
            {"responseStatus": 200, "responseData": {"translatedText": "Welcome"}}
        )

    monkeypatch.setattr(translation.requests, "get", get)
    await asyncio.gather(
        *(setup.translate_text("Xin chào " + str(i), "en") for i in range(9))
    )
    assert 1 < highest <= 3

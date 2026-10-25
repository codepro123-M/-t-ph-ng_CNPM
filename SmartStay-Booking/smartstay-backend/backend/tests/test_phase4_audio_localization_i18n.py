"""Provider calls are mocked; MP3 validation, API, Mongo writes and media reads are real."""

import asyncio
import hashlib
import subprocess
from functools import partial
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.audio import service as speech_module
from app.audio import translation as translation_module
from app.audio.router import task_events
from app.audio.service import TTSService, tts_service
from app.audio.task_manager import audio_task_manager
from app.content.media import inspect_audio
from app.localization.service import localization_service
from test_content import SOURCE
from test_phase2 import auth


@pytest.fixture(scope="session")
def mp3_bytes():
    return subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=0.2",
            "-f",
            "mp3",
            "pipe:1",
        ],
        check=True,
        capture_output=True,
    ).stdout


@pytest.fixture
def providers(monkeypatch, tmp_path, mp3_bytes):
    calls = {"speech": 0, "translation": []}
    monkeypatch.setattr(speech_module.settings, "TRANSLATION_PROVIDER", "google")

    class Speech:
        def __init__(self, text, voice, **kwargs):
            self.voice = voice

        async def stream(self):
            calls["speech"] += 1
            await asyncio.sleep(0.01)
            yield {"type": "audio", "data": mp3_bytes}

    def translate(self, text, **kwargs):
        calls["translation"].append((self._target, text))
        return "Translated " + text

    monkeypatch.setattr(speech_module.edge_tts, "Communicate", Speech)
    monkeypatch.setattr(speech_module.BoundedGoogleTranslator, "translate", translate)
    monkeypatch.setattr(tts_service, "_cache_dir", tmp_path / "audio-cache")
    return calls


def make_poi(client, root):
    result = client.post("/poi", json=SOURCE, headers=auth(root))
    assert result.status_code == 201
    return result.json()["id"]


@pytest.mark.asyncio
async def test_real_provider_interface_validated_cache_and_concurrent_dedup(
    providers, tmp_path, mp3_bytes
):
    service = TTSService(tmp_path / "separate-cache")
    first, second = await asyncio.gather(
        service.synthesize_mp3("Welcome", "en"), service.synthesize_mp3("Welcome", "en")
    )
    assert providers["speech"] == 1
    assert sorted([first["cache_hit"], second["cache_hit"]]) == [False, True]
    assert first["audio_bytes"] == second["audio_bytes"] == mp3_bytes
    assert inspect_audio(first["audio_bytes"])["content_type"] == "audio/mpeg"
    assert first["voice"] == "en-US-JennyNeural"
    assert first["sha256"] == hashlib.sha256(mp3_bytes).hexdigest()


@pytest.mark.asyncio
async def test_invalid_provider_audio_is_not_cached(monkeypatch, tmp_path):
    class InvalidSpeech:
        def __init__(self, *args, **kwargs):
            pass

        async def stream(self):
            yield {"type": "audio", "data": b"ID3 fake audio"}

    monkeypatch.setattr(speech_module.edge_tts, "Communicate", InvalidSpeech)
    with pytest.raises(HTTPException) as invalid:
        await TTSService(tmp_path).synthesize_mp3("Welcome", "en")
    assert invalid.value.status_code == 503
    assert list(tmp_path.glob("*.mp3")) == []


def test_on_demand_queue_persists_real_media_and_uses_frontend_contract(
    client, root, services, providers, mp3_bytes
):
    poi_id = make_poi(client, root)
    queued = client.post(
        "/localizations/on-demand", json={"poi_id": poi_id, "lang": "en"}
    )
    assert queued.status_code == 202
    duplicate = client.post(
        "/localizations/on-demand", json={"poi_id": poi_id, "lang": "en"}
    )
    assert duplicate.json()["task_id"] == queued.json()["task_id"]
    assert services.db.raw.audio_tasks.count_documents({}) == 1
    task = client.portal.call(audio_task_manager.run_task, queued.json()["task_id"])
    assert task["status"] == "completed" and task["progress_pct"] == 100
    status = client.get(f"/localizations/poi/{poi_id}/status?lang=en").json()
    assert status["status"] == "ready" and status["audio_url"].startswith("/media/")
    detail = client.get(f"/poi/{poi_id}?language=en").json()
    assert detail["language"] == "en" and detail["audio_url"] == status["audio_url"]
    assert client.get(detail["audio_url"]).content == mp3_bytes
    assert (
        client.post(
            "/localizations/on-demand", json={"poi_id": poi_id, "lang": "en"}
        ).status_code
        == 200
    )
    assert providers["speech"] == 1 and providers["translation"]


def test_provider_failure_is_explicit_and_can_retry_without_placeholder_success(
    client, root, services, providers, monkeypatch
):
    poi_id = make_poi(client, root)
    original = speech_module.BoundedGoogleTranslator.translate

    def unavailable(*args, **kwargs):
        raise ConnectionError("test outage")

    monkeypatch.setattr(speech_module.BoundedGoogleTranslator, "translate", unavailable)
    job = client.post(
        "/localizations/on-demand", json={"poi_id": poi_id, "lang": "en"}
    ).json()
    failed = client.portal.call(audio_task_manager.run_task, job["task_id"])
    assert failed["status"] == "failed" and "unavailable" in failed["error"]
    assert services.db.raw.poi_localizations.count_documents({}) == 0
    assert client.get(f"/poi/{poi_id}?language=en").json()["audio_url"] is None
    monkeypatch.setattr(speech_module.BoundedGoogleTranslator, "translate", original)
    assert (
        client.post(
            "/localizations/on-demand", json={"poi_id": poi_id, "lang": "en"}
        ).json()["status"]
        == "queued"
    )
    assert (
        client.portal.call(audio_task_manager.run_task, job["task_id"])["status"]
        == "failed"
    )
    # Restoring the provider does not bypass its persisted backoff window.
    after_cooldown = translation_module.time.time() + 61
    monkeypatch.setattr(translation_module.time, "time", lambda: after_cooldown)
    client.post("/localizations/on-demand", json={"poi_id": poi_id, "lang": "en"})
    assert (
        client.portal.call(audio_task_manager.run_task, job["task_id"])["status"]
        == "completed"
    )


def test_english_gate_pause_resume_and_published_pack(client, root, providers):
    response = client.post(
        "/poi?auto_run_tts=true&activation_requested=true",
        json=SOURCE,
        headers=auth(root),
    )
    poi_id, task_id = response.json()["id"], response.json()["audio_task_id"]
    assert client.get("/poi/" + poi_id).status_code == 404
    stepped = client.portal.call(
        partial(audio_task_manager.run_task, task_id, one_language="en")
    )
    assert stepped["status"] == "paused" and stepped["english_gate_passed"]
    assert client.get("/poi/" + poi_id).status_code == 200
    assert (
        client.post(
            f"/admin/audio-tasks/{task_id}/resume", headers=auth(root)
        ).status_code
        == 200
    )
    complete = client.portal.call(audio_task_manager.run_task, task_id)
    assert (
        complete["status"] == "completed" and len(complete["completed_languages"]) == 5
    )
    manifest = client.get("/audio/pack-manifest?lang=en").json()
    assert manifest["total_files"] == 1
    assert len(manifest["files"][0]["sha256"]) == 64
    assert client.get(manifest["files"][0]["audio_url"]).status_code == 200
    assert (
        client.post("/audio/tts", json={"text": "Hello", "lang": "en"}).status_code
        == 401
    )
    direct = client.post(
        "/audio/tts", json={"text": "Hello", "lang": "en"}, headers=auth(root)
    )
    assert direct.status_code == 200 and direct.headers["content-type"].startswith(
        "audio/mpeg"
    )


def test_source_revision_invalidates_vietnamese_recording_and_stale_jobs(
    client, root, services, providers
):
    poi_id = make_poi(client, root)
    client.portal.call(localization_service.localize_single_poi, poi_id, "vi")
    before = client.get("/poi/" + poi_id).json()
    assert before["audio_url"]
    stale = client.post(
        "/admin/audio-tasks",
        headers=auth(root),
        json={"poi_id": poi_id, "languages": ["en"]},
    ).json()
    assert (
        client.patch(
            "/poi/" + poi_id,
            headers=auth(root),
            json={
                "expected_revision": before["revision"],
                "description": "Updated source text",
            },
        ).status_code
        == 200
    )
    assert client.get("/poi/" + poi_id).json()["audio_url"] is None
    assert (
        client.portal.call(audio_task_manager.run_task, stale["id"])["status"]
        == "failed"
    )
    assert (
        services.db.raw.media_cleanup_jobs.count_documents(
            {"reason": "source_text_changed"}
        )
        == 1
    )


def test_public_job_scope_rate_limit_and_private_properties(client, root):
    private = client.post(
        "/poi", headers=auth(root), json=SOURCE | {"is_active": False}
    ).json()
    assert (
        client.post(
            "/localizations/on-demand", json={"poi_id": private["id"], "lang": "en"}
        ).status_code
        == 404
    )
    assert client.post("/localizations/warmup", json={"lang": "en"}).status_code == 401
    for _ in range(29):
        assert (
            client.post(
                "/localizations/on-demand", json={"poi_id": private["id"], "lang": "en"}
            ).status_code
            == 404
        )
    limited = client.post(
        "/localizations/on-demand", json={"poi_id": private["id"], "lang": "en"}
    )
    assert limited.status_code == 429 and limited.headers["retry-after"] == "600"


def test_hotset_warmup_and_sse_snapshots_use_persistent_jobs(client, root, providers):
    make_poi(client, root)
    result = client.post(
        "/localizations/prepare-hotset",
        json={"lat": SOURCE["latitude"], "lng": SOURCE["longitude"], "lang": "ko"},
    )
    assert result.status_code == 202 and result.json()["queued_count"] == 1
    first = client.post(
        "/localizations/warmup", headers=auth(root), json={"lang": "en"}
    ).json()
    second = client.post(
        "/localizations/warmup", headers=auth(root), json={"lang": "en"}
    ).json()
    assert first["total_pois"] == 1 and second["idempotent_reused"]

    async def events():
        generator = task_events(
            SimpleNamespace(is_disconnected=AsyncMock(return_value=False))
        )
        try:
            return await generator.__anext__(), await generator.__anext__()
        finally:
            await generator.aclose()

    snapshot, heartbeat = client.portal.call(events)
    assert "event: snapshot" in snapshot and "claim_token" not in snapshot
    assert "event: heartbeat" in heartbeat


def test_ui_translation_preserves_placeholders_and_reports_provider_failure(
    client, providers, monkeypatch
):
    initial = client.get("/api/v1/ui-bundles/fr").json()
    assert initial["status"] == "pending" and initial["is_fallback"]
    ready = client.get("/api/v1/ui-bundles/fr").json()
    assert ready["status"] == "ready" and not ready["is_fallback"]
    assert "{{guest_name}}" in ready["messages"]["welcome_banner"]
    assert all("{{" not in text for _, text in providers["translation"])

    def fail(*args, **kwargs):
        raise ConnectionError("provider outage")

    monkeypatch.setattr(speech_module.BoundedGoogleTranslator, "translate", fail)
    client.get("/api/v1/ui-bundles/de")
    failed = client.get("/api/v1/ui-bundles/de").json()
    assert failed["status"] == "failed" and failed["is_fallback"]


def test_translation_http_adapter_has_timeouts_and_keeps_tls_verification(monkeypatch):
    import ssl

    observed = {}

    class ProviderResponse:
        text = '<div class="result-container">Welcome, guest.</div>'

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def raise_for_status(self):
            pass

    def get(url, **kwargs):
        observed.update(url=url, **kwargs)
        return ProviderResponse()

    monkeypatch.setattr(speech_module.requests, "get", get)
    translated = speech_module.BoundedGoogleTranslator(
        source="vi", target="en"
    ).translate("Xin chao.")
    assert translated == "Welcome, guest."
    assert observed["params"]["q"] == "Xin chao."
    assert observed["params"]["sl"] == "vi" and observed["params"]["tl"] == "en"
    assert observed["timeout"] == (3, 15) and observed["verify"] is not False
    assert speech_module._SSL_CTX.verify_mode == ssl.CERT_REQUIRED
    assert speech_module._SSL_CTX.check_hostname is True


def test_google_429_fallback_completes_public_audio_job(
    client, root, services, providers, monkeypatch, mp3_bytes
):
    import requests

    from test_translation_providers import Response

    monkeypatch.setattr(speech_module.settings, "TRANSLATION_PROVIDER", "auto")
    calls = {"google": 0, "mymemory": 0}

    def google(*args, **kwargs):
        calls["google"] += 1
        raise requests.HTTPError(response=Response({}, 429))

    def mymemory(url, **kwargs):
        calls["mymemory"] += 1
        return Response(
            {
                "responseStatus": 200,
                "responseData": {"translatedText": "English " + kwargs["params"]["q"]},
            }
        )

    monkeypatch.setattr(speech_module.BoundedGoogleTranslator, "translate", google)
    monkeypatch.setattr(translation_module.requests, "get", mymemory)
    poi_id = make_poi(client, root)
    queued = client.post(
        "/localizations/on-demand", json={"poi_id": poi_id, "lang": "en"}
    )
    assert queued.status_code == 202
    completed = client.portal.call(
        audio_task_manager.run_task, queued.json()["task_id"]
    )
    assert completed["status"] == "completed"
    detail = client.get("/poi/" + poi_id + "?language=en").json()
    assert detail["language"] == "en"
    assert client.get(detail["audio_url"]).content == mp3_bytes
    assert calls == {"google": 1, "mymemory": 3}
    assert (
        services.db.raw.poi_localizations.count_documents(
            {"poi_id": poi_id, "language": "en"}
        )
        == 1
    )

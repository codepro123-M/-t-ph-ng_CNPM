"""UI translations preserve placeholders and never label failed translations ready."""

import hashlib
import json
import re

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request
from pymongo.errors import DuplicateKeyError

from app.audio.service import tts_service
from app.content.schemas import language_code
from app.core.database import get_db
from app.core.security import random_id, utcnow
from app.core.sessions import rate_limit

router = APIRouter(tags=["ui_i18n"])

STATIC_UI_BUNDLES = {
    "en": {
        "welcome_banner": "Welcome {{guest_name}} to {{property_name}}!",
        "checkin_guide": "Check-in starts at {{checkin_time}} using smart PIN {{pin_code}}.",
        "nearby_title": "Explore {{count}} stays within {{radius}}m",
        "audio_play_button": "Play Audio Guide ({{lang_label}})",
    },
    "vi": {
        "welcome_banner": "Chào mừng {{guest_name}} đến với {{property_name}}!",
        "checkin_guide": "Nhận phòng từ {{checkin_time}} bằng mã PIN {{pin_code}}.",
        "nearby_title": "Khám phá {{count}} cơ sở lưu trú trong bán kính {{radius}}m",
        "audio_play_button": "Phát thuyết minh ({{lang_label}})",
    },
    "zh": {
        "welcome_banner": "欢迎 {{guest_name}} 来到 {{property_name}}！",
        "checkin_guide": "入住时间为 {{checkin_time}}，请使用智能密码 {{pin_code}}。",
        "nearby_title": "探索 {{radius}} 米内的 {{count}} 家住宿",
        "audio_play_button": "播放语音导览 ({{lang_label}})",
    },
    "ja": {
        "welcome_banner": "{{guest_name}}様、{{property_name}}へようこそ！",
        "checkin_guide": "チェックインは{{checkin_time}}より、暗証番号{{pin_code}}をご利用ください。",
        "nearby_title": "{{radius}}m以内の宿泊施設{{count}}件を探索",
        "audio_play_button": "音声ガイドを再生 ({{lang_label}})",
    },
    "ko": {
        "welcome_banner": "{{guest_name}}님, {{property_name}}에 오신 것을 환영합니다!",
        "checkin_guide": "체크인은 {{checkin_time}}부터 스마트 PIN {{pin_code}}로 가능합니다.",
        "nearby_title": "{{radius}}m 이내 {{count}}개 숙소 탐색",
        "audio_play_button": "오디오 가이드 재생 ({{lang_label}})",
    },
}

PLACEHOLDER_REGEX = re.compile(r"({{[a-zA-Z0-9_]+}})")


def compute_source_hash(messages):
    return hashlib.sha256(
        json.dumps(messages, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()[:16]


async def translate_preserving_placeholders(text, locale):
    result = []
    for part in PLACEHOLDER_REGEX.split(text):
        if not part or PLACEHOLDER_REGEX.fullmatch(part) or not part.strip():
            result.append(part)
        else:
            leading = part[: len(part) - len(part.lstrip())]
            trailing = part[len(part.rstrip()) :]
            translated = await tts_service.translate_text(part.strip(), locale, "en")
            result.append(leading + translated + trailing)
    return "".join(result)


async def translate_bundle(query, locale):
    try:
        messages = {
            key: await translate_preserving_placeholders(text, locale)
            for key, text in STATIC_UI_BUNDLES["en"].items()
        }
        changes = {
            "status": "ready",
            "messages": messages,
            "is_fallback": False,
            "error": None,
        }
    except Exception:
        changes = {
            "status": "failed",
            "is_fallback": True,
            "error": "Translation provider unavailable; retry later",
        }
    await get_db()["ui_translation_bundles"].update_one(
        query, {"$set": changes | {"updated_at": utcnow()}}
    )


@router.get("/api/v1/ui-i18n/ping", include_in_schema=False)
async def ping():
    return {"lane": "ui_i18n", "status": "ok"}


@router.get("/api/v1/ui-bundles/{locale}")
async def ui_bundle(
    locale: str,
    request: Request,
    background_tasks: BackgroundTasks,
    namespace: str = Query("public-ui", max_length=64, pattern=r"^[a-zA-Z0-9_.-]+$"),
    retry: bool = False,
):
    try:
        locale = language_code(locale)
    except ValueError:
        raise HTTPException(422, "Invalid locale") from None
    signature = compute_source_hash(STATIC_UI_BUNDLES["en"])
    if locale in STATIC_UI_BUNDLES:
        return {
            "namespace": namespace,
            "locale": locale,
            "status": "ready",
            "is_fallback": False,
            "source_hash": signature,
            "messages": STATIC_UI_BUNDLES[locale],
        }
    db, key = get_db(), namespace + ":" + locale
    previous = await db["ui_translation_bundles"].find_one({"_id": key})
    if (
        previous
        and previous["source_hash"] == signature
        and not (retry and previous["status"] == "failed")
    ):
        if (
            previous["status"] != "pending"
            or (
                utcnow() - previous["updated_at"].replace(tzinfo=utcnow().tzinfo)
            ).total_seconds()
            < 120
        ):
            return {k: v for k, v in previous.items() if k not in {"_id", "job_key"}}
    await rate_limit(request, "ui-translation", limit=30, seconds=600)
    job_key = random_id()
    pending = {
        "namespace": namespace,
        "locale": locale,
        "status": "pending",
        "is_fallback": True,
        "source_hash": signature,
        "messages": STATIC_UI_BUNDLES["en"],
        "job_key": job_key,
        "updated_at": utcnow(),
    }
    query = (
        {"_id": key}
        if previous is None
        else {"_id": key, "updated_at": previous["updated_at"]}
    )
    try:
        changed = await db["ui_translation_bundles"].update_one(
            query, {"$set": pending}, upsert=previous is None
        )
    except DuplicateKeyError:
        changed = None
    if changed and (changed.modified_count or changed.upserted_id):
        background_tasks.add_task(
            translate_bundle, {"_id": key, "job_key": job_key}, locale
        )
    return {k: v for k, v in pending.items() if k != "job_key"}

"""Probe real external providers with a public demo sentence; never prints secrets."""

import asyncio
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.audio.service import tts_service
from app.core.config import settings


async def run(*, fresh=False):
    passed = True
    try:
        translated = await tts_service.translate_with_info(
            "Xin chào quý khách.", "en", "vi", use_cache=not fresh
        )
        print("PASS: translation:", translated["text"])
        print(
            "  provider:",
            translated["provider"],
            "cache:",
            "HIT" if translated["cache_hit"] else "MISS",
        )
    except Exception as error:
        passed = False
        print("FAIL: translation:", getattr(error, "detail", type(error).__name__))
    try:
        text = "Welcome to SmartStay."
        if fresh:
            text += " Connection test " + str(time.time_ns()) + "."
        audio = await tts_service.synthesize_mp3(text, "en")
        print("PASS: real speech, validated MP3:", audio["size_bytes"], "bytes")
        print("  cache:", "HIT" if audio["cache_hit"] else "MISS")
    except Exception as error:
        passed = False
        print("FAIL: speech:", getattr(error, "detail", type(error).__name__))
    return 0 if passed else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=["auto", "google", "mymemory"])
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Bypass result cache, while respecting provider cooldowns",
    )
    args = parser.parse_args()
    if args.provider:
        settings.TRANSLATION_PROVIDER = args.provider
    print("Translation mode:", settings.TRANSLATION_PROVIDER)
    raise SystemExit(asyncio.run(run(fresh=args.fresh)))

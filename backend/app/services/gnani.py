"""
All calls to Gnani's speech APIs live in this one file.

- speech_to_text(): Gnani Prisma turns a voice recording into text.
- text_to_speech(): Gnani Timbre turns text into spoken audio (MP3).

The rest of the app only calls these two functions, which makes Gnani easy to
mock in tests or swap out later. We call the REST API directly with httpx
rather than the gnani-vachana SDK: it's about as short, and it shows exactly
what goes over the wire.

Docs: https://docs.gnani.ai/api/STT/speech-to-text.md
      https://docs.gnani.ai/api/TTS/tts-inference.md
"""

import logging
import mimetypes
import time
from typing import NamedTuple

import httpx

from app import usage
from app.config import settings

logger = logging.getLogger("odhu.gnani")

STT_URL = "https://api.vachana.ai/stt/v3"
# Prisma v3.0 can listen for several languages at once and tells us which one it
# heard, so the user can ask in Kannada, Hindi or English without choosing first.
STT_MODEL = "prisma-v3.0"
TTS_URL = "https://api.vachana.ai/api/v1/tts/inference"
TTS_MODEL = "timbre-v3.0"  # every v3.0 voice speaks all 10 languages, including kn-IN, hi-IN and en-IN

SUPPORTED_LANGUAGES = {"kn-IN", "hi-IN", "en-IN"}

# One shared HTTP client, which reuses connections between calls.
# Tests swap it for a fake client so no real requests are made.
http_client = httpx.Client(timeout=60.0)


class GnaniError(Exception):
    """Raised when a Gnani call fails. The message is safe to show in logs."""


class Transcript(NamedTuple):
    text: str  # what was said ("" if nothing was heard)
    language: str | None  # the language Gnani heard, e.g. "hi-IN"; None if it couldn't tell


def _headers() -> dict:
    if not settings.gnani_api_key:
        raise GnaniError("GNANI_API_KEY is not set. Add it to your .env file.")
    return {"X-API-Key-ID": settings.gnani_api_key}


def _check_language(language: str) -> None:
    if language not in SUPPORTED_LANGUAGES:
        raise GnaniError(f"Unsupported language {language!r}. Use one of {sorted(SUPPORTED_LANGUAGES)}.")


def _post(kind: str, **request_kwargs) -> httpx.Response:
    """
    Send one POST to Gnani. Every call is saved to the database (usage.py) with
    its duration, and we log the running total so we can watch our credits.
    `kind` is "stt" or "tts".
    """
    url = STT_URL if kind == "stt" else TTS_URL
    headers = _headers()  # fails early, before counting, if the key is missing

    start = time.perf_counter()
    response = None
    try:
        response = http_client.post(url, headers=headers, **request_kwargs)
    except httpx.HTTPError as exc:  # network problem, timeout, etc.
        raise GnaniError(f"Could not reach Gnani {kind.upper()}: {exc}") from exc
    finally:
        # Count every attempt, because a failed request may still use a credit.
        duration_ms = (time.perf_counter() - start) * 1000
        ok = response is not None and response.status_code == 200
        usage.record_call(f"gnani_{kind}", duration_ms, ok)
        total = usage.gnani_calls_total()
        logger.info(
            "gnani %s call took %.0f ms (Gnani call #%d overall, about %d credits left)",
            kind, duration_ms, total, settings.gnani_credit_budget - total,
        )

    if response.status_code != 200:
        raise GnaniError(f"Gnani {kind.upper()} failed with HTTP {response.status_code}: {response.text[:300]}")
    return response


def speech_to_text(audio: bytes, filename: str, languages: list[str]) -> Transcript:
    """
    Transcribe a short voice recording (30 seconds at most) and detect its language.

    `languages` are the languages the speaker might use, most likely first, e.g.
    ["en-IN", "kn-IN", "hi-IN"]. They are hints, not a lock: the transcript follows
    the language actually spoken, and Gnani tells us which one it was.

    `filename` only needs the right extension (.wav, .mp3, ...) so Gnani can tell
    the format. format="transcribe" makes spoken numbers come back as digits.
    """
    for language in languages:
        _check_language(language)
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

    response = _post(
        "stt",
        files={"audio_file": (filename, audio, content_type)},
        data={"language_code": ",".join(languages), "format": "transcribe", "model": STT_MODEL},
    )
    body = response.json()
    if not body.get("success", True) or "transcript" not in body:
        raise GnaniError(f"Gnani STT returned an unexpected response: {str(body)[:300]}")

    detected = body.get("detected_language_code")
    if detected not in SUPPORTED_LANGUAGES:  # missing, or a language we don't support
        detected = None
    return Transcript(text=body["transcript"].strip(), language=detected)


def text_to_speech(text: str, language: str, voice: str | None = None, speed: float | None = None) -> bytes:
    """
    Turn text into speech and return the MP3 audio as bytes.

    Amounts and dates in `text` should already be written as words (the LLM
    does this), because Timbre can misread raw digits, e.g. "23/06" as a fraction.
    """
    _check_language(language)
    if not text.strip():
        raise GnaniError("Cannot speak empty text.")

    payload = {
        "text": text,
        "model": TTS_MODEL,
        "voice": voice or settings.tts_voice,
        "language": language,
        "speed": speed if speed is not None else settings.tts_speed,
        "audio_config": {"container": "mp3", "sample_rate": 24000},
    }
    response = _post("tts", json=payload)
    if not response.content:
        raise GnaniError("Gnani TTS returned empty audio.")
    return response.content

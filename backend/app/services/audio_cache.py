"""
Speaks text with Gnani TTS and caches the MP3 on disk.

The cache key (the "audio_id") is a SHA-256 hash of everything that changes the
sound: text, voice, language and speed. The same sentence spoken the same way
always gets the same audio_id, so replays and repeated messages are read from
disk and don't spend Gnani credits.
"""

import hashlib
import logging
import re
from pathlib import Path

from app.config import settings
from app.services import gnani

logger = logging.getLogger("odhu.audio")

AUDIO_ID_PATTERN = re.compile(r"^[0-9a-f]{64}$")  # what a valid audio_id looks like


def audio_dir() -> Path:
    path = settings.data_dir / "audio"
    path.mkdir(parents=True, exist_ok=True)
    return path


def make_audio_id(text: str, voice: str, language: str, speed: float) -> str:
    key = f"{text}|{voice}|{language}|{speed}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def audio_path(audio_id: str) -> Path | None:
    """Return the MP3 file for this audio_id, or None if it's invalid or missing."""
    # Checking the format also stops tricks like "../../.env" in the URL.
    if not AUDIO_ID_PATTERN.match(audio_id):
        return None
    path = audio_dir() / f"{audio_id}.mp3"
    return path if path.exists() else None


def speak(text: str, language: str) -> str:
    """Make sure audio for `text` exists on disk, and return its audio_id."""
    voice, speed = settings.tts_voice, settings.tts_speed
    audio_id = make_audio_id(text, voice, language, speed)
    path = audio_dir() / f"{audio_id}.mp3"

    if path.exists():
        logger.info("tts cache hit %s", audio_id[:12])
        return audio_id

    audio = gnani.text_to_speech(text, language, voice=voice, speed=speed)
    path.write_bytes(audio)
    return audio_id

"""GET /api/audio/{audio_id}: serve a cached MP3 made by text-to-speech."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.services import audio_cache

router = APIRouter(prefix="/api/audio", tags=["audio"])


@router.get("/{audio_id}")
def get_audio(audio_id: str) -> FileResponse:
    path = audio_cache.audio_path(audio_id)
    if path is None:
        raise HTTPException(404, "Audio not found.")
    # The file never changes for a given audio_id, so the browser may cache it forever.
    return FileResponse(path, media_type="audio/mpeg", headers={"Cache-Control": "public, max-age=31536000, immutable"})

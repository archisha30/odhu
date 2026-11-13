"""
Counts calls to Gnani and Gemini, saved in the api_calls table so the count
survives server restarts. We have 5,000 Gnani credits for the whole challenge,
and Gemini's free tier has a daily limit per model, so we watch both.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.config import settings
from app.db import ApiCallRecord, SessionLocal


def record_call(service: str, duration_ms: float, ok: bool, model: str = "") -> None:
    """Save one call to the database."""
    with SessionLocal() as db:
        db.add(ApiCallRecord(service=service, model=model, duration_ms=duration_ms, ok=ok))
        db.commit()


def gnani_calls_total() -> int:
    with SessionLocal() as db:
        return db.scalar(select(func.count()).where(ApiCallRecord.service.like("gnani%")))


def summary() -> dict:
    """Numbers for the /api/usage endpoint."""
    # Gemini's daily limits reset at midnight Pacific time, which is about 08:00 UTC.
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    with SessionLocal() as db:
        by_service = dict(
            db.execute(
                select(ApiCallRecord.service, func.count()).group_by(ApiCallRecord.service)
            ).all()
        )
        gemini_last_24h = dict(
            db.execute(
                select(ApiCallRecord.model, func.count())
                .where(ApiCallRecord.service == "gemini", ApiCallRecord.created_at >= since)
                .group_by(ApiCallRecord.model)
            ).all()
        )
    gnani_total = by_service.get("gnani_stt", 0) + by_service.get("gnani_tts", 0)
    return {
        "gnani": {
            "stt_calls": by_service.get("gnani_stt", 0),
            "tts_calls": by_service.get("gnani_tts", 0),
            "total_calls": gnani_total,
            # Assumes 1 credit per call. Check the Gnani dashboard for the real number.
            "credits_left_estimate": settings.gnani_credit_budget - gnani_total,
        },
        "gemini": {
            "total_calls": by_service.get("gemini", 0),
            "last_24h_by_model": gemini_last_24h,
        },
    }

"""
POST /api/documents/{id}/ask: ask a follow-up question about a document by voice.

Steps: Gnani STT turns the recording into text and tells us which language was
spoken (Kannada, Hindi or English) -> Gemini answers from the saved facts only,
in that same language -> code adds the amount/date sentences -> Gnani TTS speaks it.
"""

import io
import logging
import uuid
import wave
from pathlib import Path
from typing import get_args

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import messages, spoken
from app.db import DocumentRecord, QuestionRecord, get_db
from app.schemas import ExtractedDocument, Language, QuestionOut
from app.services import audio_cache, gnani
from app.services.llm import LLMError, LLMProvider, get_llm

logger = logging.getLogger("odhu.questions")
router = APIRouter(prefix="/api/documents", tags=["questions"])

# Formats Gnani STT accepts. The frontend sends WAV.
ALLOWED_AUDIO = {".wav", ".mp3", ".ogg", ".flac", ".aac", ".m4a"}
MAX_AUDIO_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_SECONDS = 30  # Gnani Prisma v3.0's limit; the frontend also stops recording at 30


@router.post("/{document_id}/ask", response_model=QuestionOut)
def ask_question(
    document_id: str,
    audio: UploadFile,
    # The language the person is listening in right now. It's only a hint for which
    # language to expect: if they speak another one, we answer in that one instead.
    language: Language | None = Form(None),
    llm: LLMProvider = Depends(get_llm),
    db: Session = Depends(get_db),
) -> QuestionOut:
    # 1. Find the document. We can only answer about documents we read successfully.
    record = db.get(DocumentRecord, document_id)
    if record is None:
        raise HTTPException(404, "Document not found.")
    if record.status != "ok" or not record.extracted_json:
        raise HTTPException(409, "This document could not be read, so questions can't be answered. Please scan it again.")
    document = ExtractedDocument.model_validate_json(record.extracted_json)
    expected: Language = language or record.language

    # 2. Check the recording.
    data = audio.file.read()
    extension = Path(audio.filename or "").suffix.lower()
    check_audio(data, extension)

    # 3. Speech to text. Listen for all our languages, the expected one first.
    languages = [expected] + [lang for lang in get_args(Language) if lang != expected]
    try:
        heard = gnani.speech_to_text(data, f"question{extension}", languages)
    except gnani.GnaniError as exc:
        logger.error("stt failed: %s", exc)
        raise HTTPException(502, "Could not hear the question right now. Please try again.") from exc
    transcript = heard.text
    # Answer in the language they spoke. If Gnani couldn't tell, use the expected one.
    language: Language = heard.language or expected

    # 4. Work out the answer text.
    answer = answer_text(transcript, document, language, record, llm, db)

    # 5. Speak it. If TTS fails we still return the text.
    audio_id = None
    try:
        audio_id = audio_cache.speak(answer, language)
    except gnani.GnaniError as exc:
        logger.error("tts failed: %s", exc)

    # 6. Save it, so it shows up when the document is opened again.
    question = QuestionRecord(
        id=uuid.uuid4().hex,
        document_id=record.id,
        transcript=transcript,
        language=language,
        answer=answer,
        audio_id=audio_id,
    )
    db.add(question)
    db.commit()
    return to_output(question)


def check_audio(data: bytes, extension: str) -> None:
    if extension not in ALLOWED_AUDIO:
        raise HTTPException(400, f"Please send audio as one of: {', '.join(sorted(ALLOWED_AUDIO))}.")
    if not data:
        raise HTTPException(400, "The recording is empty.")
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(400, "The recording is too large.")
    if extension == ".wav":  # for WAV we can easily check the length ourselves
        try:
            with wave.open(io.BytesIO(data)) as w:
                seconds = w.getnframes() / w.getframerate()
        except (wave.Error, EOFError, ZeroDivisionError) as exc:
            raise HTTPException(400, "The recording is not a valid WAV file.") from exc
        if seconds > MAX_SECONDS:
            raise HTTPException(400, f"Please keep questions under {MAX_SECONDS} seconds.")


def answer_text(
    transcript: str,
    document: ExtractedDocument,
    language: Language,
    record: DocumentRecord,
    llm: LLMProvider,
    db: Session,
) -> str:
    """Decide what to say back. Uses fixed messages and saved answers where possible."""
    # Nothing heard (silence or noise): no point asking the LLM.
    if not transcript.strip():
        return messages.DIDNT_HEAR[language]

    # Exactly the same question about this document before? Reuse that answer.
    earlier = db.scalars(
        select(QuestionRecord).where(
            QuestionRecord.document_id == record.id,
            QuestionRecord.transcript == transcript,
            QuestionRecord.language == language,
        )
    ).first()
    if earlier is not None:
        logger.info("same question asked before, reusing answer")
        return earlier.answer

    try:
        reading = llm.answer_question(document, transcript, language)
    except LLMError as exc:
        logger.error("answer failed: %s", exc)
        raise HTTPException(502, "Could not answer right now. Please try again.") from exc

    if not reading.answerable:
        return messages.NOT_IN_DOCUMENT[language]

    # Safety net: every rupee amount the LLM wrote must really be in the facts.
    invented = spoken.invented_amounts(reading.answer, document)
    if invented:
        logger.warning("answer mentioned amounts not in the document %s: %r", invented, reading.answer)
        return messages.NOT_IN_DOCUMENT[language]

    text = spoken.build_answer(document, reading.answer, reading.say_amount_due, reading.say_due_date, language)
    return text or messages.NOT_IN_DOCUMENT[language]


def to_output(question: QuestionRecord) -> QuestionOut:
    return QuestionOut(
        id=question.id,
        created_at=question.created_at,
        transcript=question.transcript,
        language=question.language,
        answer=question.answer,
        audio_url=f"/api/audio/{question.audio_id}" if question.audio_id else None,
    )

"""
Document endpoints:
  POST /api/documents        upload a photo and get it explained
  GET  /api/documents        history, newest first
  GET  /api/documents/{id}   one past document
  POST /api/documents/{id}/explanations   the explanation in another language
"""

import hashlib
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import messages, spoken
from app.db import DocumentRecord, ExplanationRecord, get_db
from app.routes import questions
from app.schemas import (
    SUPPORTED_TYPES,
    DocumentOut,
    DocumentReading,
    DocumentStatus,
    DocumentType,
    ExplanationOut,
    ExplanationRequest,
    ExtractedDocument,
    Language,
)
from app.services import audio_cache, image_check
from app.services.gnani import GnaniError
from app.services.llm import LLMError, LLMProvider, get_llm

logger = logging.getLogger("odhu.documents")
router = APIRouter(prefix="/api/documents", tags=["documents"])

# Below this confidence we ask for a clearer photo instead of risking wrong facts.
CONFIDENCE_THRESHOLD = 0.6
# Between the two thresholds (or if parts were hard to read) we still explain the
# document, but also ask the person to double-check the amount and date.
DOUBLE_CHECK_THRESHOLD = 0.8

MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif"}


@router.post("", response_model=DocumentOut)
def scan_document(
    image: UploadFile,
    language: Language = Form(...),
    llm: LLMProvider = Depends(get_llm),
    db: Session = Depends(get_db),
) -> DocumentOut:
    # 1. Check the upload.
    if image.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(400, f"Please upload a photo (JPEG, PNG, WEBP or HEIC), not {image.content_type}.")
    data = image.file.read()
    if not data:
        raise HTTPException(400, "The uploaded photo is empty.")
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(400, "The photo is too large. Please keep it under 10 MB.")

    # 2. Same photo scanned before in this language? Reuse it: no Gemini call needed.
    image_hash = hashlib.sha256(data).hexdigest()
    earlier = db.scalars(
        select(DocumentRecord).where(
            DocumentRecord.image_hash == image_hash,
            DocumentRecord.language == language,
            DocumentRecord.status != "unclear",  # an unclear result is worth retrying
        )
    ).first()
    if earlier is not None:
        logger.info("same photo scanned before, reusing document %s", earlier.id)
        earlier.created_at = datetime.now(timezone.utc)  # move it to the top of history
        db.commit()
        return to_output(earlier)

    # 3. Check sharpness and shrink big photos. Hopelessly blurry: don't even ask Gemini.
    send_data, send_type, sharpness = image_check.prepare_image(data, image.content_type)
    if sharpness is not None and sharpness < image_check.MIN_SHARPNESS:
        logger.info("photo too blurry (sharpness %.1f), skipping Gemini", sharpness)
        status, explanation, reading = "unclear", messages.UNCLEAR_PHOTO[language], None
    else:
        # 4. Read the document with the vision LLM (facts + explanation in one call).
        try:
            reading = llm.read_document(send_data, send_type, language)
        except LLMError as exc:
            logger.error("reading failed: %s", exc)
            raise HTTPException(502, "Could not read the document right now. Please try again.") from exc
        status, explanation = decide_explanation(reading, language)

    # 5. Speak it. If TTS fails we still return the text, so the user can read it.
    audio_id = None
    try:
        audio_id = audio_cache.speak(explanation, language)
    except GnaniError as exc:
        logger.error("tts failed: %s", exc)

    # 6. Save to history.
    record = DocumentRecord(
        id=uuid.uuid4().hex,
        language=language,
        image_hash=image_hash,
        status=status,
        extracted_json=reading.document.model_dump_json() if reading and status != "unclear" else None,
        explanation=explanation,
        audio_id=audio_id,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return to_output(record)


def decide_explanation(reading: DocumentReading, language: Language) -> tuple[DocumentStatus, str]:
    """Return (status, text to speak) for what the LLM read."""
    document = reading.document
    if (
        document.document_type == DocumentType.UNREADABLE
        or document.legibility == "unreadable"
        or document.confidence < CONFIDENCE_THRESHOLD
    ):
        return "unclear", messages.UNCLEAR_PHOTO[language]
    if document.document_type not in SUPPORTED_TYPES:
        return "unsupported", messages.UNSUPPORTED_DOCUMENT[language]
    return "ok", compose_explanation(document, reading.intro, reading.action, language)


def compose_explanation(document: ExtractedDocument, intro: str, action: str, language: Language) -> str:
    """
    Turn the LLM's two sentences into the full explanation: safety checks, then the
    amount and date sentences built in code, then a double-check note if needed.
    """
    # Safety net: the LLM was told not to mention amounts. Drop any sentence that
    # has a rupee amount that isn't really in the facts.
    if spoken.invented_amounts(intro, document):
        logger.warning("intro mentioned an amount not in the document: %r", intro)
        intro = ""
    if spoken.invented_amounts(action, document):
        logger.warning("action mentioned an amount not in the document: %r", action)
        action = ""

    if not intro:
        logger.error("LLM read the document but wrote no usable explanation")
        raise HTTPException(502, "Could not explain the document right now. Please try again.")
    text = spoken.build_explanation(document, intro, action, language)
    if needs_double_check(document):
        text += " " + messages.CHECK_PAPER[language]
    return text


def needs_double_check(document: ExtractedDocument) -> bool:
    """True if the photo was readable but not perfectly clear."""
    return document.legibility == "partly_readable" or document.confidence < DOUBLE_CHECK_THRESHOLD


@router.post("/{document_id}/explanations", response_model=ExplanationOut)
def explain_in_language(
    document_id: str,
    request: ExplanationRequest,
    llm: LLMProvider = Depends(get_llm),
    db: Session = Depends(get_db),
) -> ExplanationOut:
    """
    The explanation of an earlier document in another language. It's made from the
    saved facts (the photo isn't needed again), then saved, so asking again is free.
    """
    record = db.get(DocumentRecord, document_id)
    if record is None:
        raise HTTPException(404, "Document not found.")
    language = request.language

    # The language it was scanned in, or one we've already made: nothing to do.
    if language == record.language:
        return ExplanationOut(language=language, explanation=record.explanation, audio_url=audio_url(record.audio_id))
    saved = next((e for e in record.explanations if e.language == language), None)
    if saved is not None:
        return to_explanation_output(saved)

    # Unclear or unsupported documents just get the fixed message in that language.
    if record.status == "unclear" or not record.extracted_json:
        text = messages.UNCLEAR_PHOTO[language]
    elif record.status == "unsupported":
        text = messages.UNSUPPORTED_DOCUMENT[language]
    else:
        document = ExtractedDocument.model_validate_json(record.extracted_json)
        try:
            intro, action = llm.explain(document, language)
        except LLMError as exc:
            logger.error("explanation in %s failed: %s", language, exc)
            raise HTTPException(502, "Could not explain the document right now. Please try again.") from exc
        text = compose_explanation(document, intro, action, language)

    audio_id = None
    try:
        audio_id = audio_cache.speak(text, language)
    except GnaniError as exc:
        logger.error("tts failed: %s", exc)

    saved = ExplanationRecord(document_id=record.id, language=language, text=text, audio_id=audio_id)
    db.add(saved)
    db.commit()
    return to_explanation_output(saved)


@router.get("", response_model=list[DocumentOut])
def list_documents(db: Session = Depends(get_db)) -> list[DocumentOut]:
    records = db.scalars(select(DocumentRecord).order_by(DocumentRecord.created_at.desc()).limit(50))
    return [to_output(r) for r in records]


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(document_id: str, db: Session = Depends(get_db)) -> DocumentOut:
    record = db.get(DocumentRecord, document_id)
    if record is None:
        raise HTTPException(404, "Document not found.")
    return to_output(record)


def to_output(record: DocumentRecord) -> DocumentOut:
    """Convert a database row into the API response shape."""
    return DocumentOut(
        id=record.id,
        created_at=record.created_at,
        language=record.language,
        status=record.status,
        document=ExtractedDocument.model_validate_json(record.extracted_json) if record.extracted_json else None,
        explanation=record.explanation,
        audio_url=audio_url(record.audio_id),
        questions=[questions.to_output(q) for q in record.questions],
        explanations=[to_explanation_output(e) for e in record.explanations],
    )


def to_explanation_output(explanation: ExplanationRecord) -> ExplanationOut:
    return ExplanationOut(
        language=explanation.language, explanation=explanation.text, audio_url=audio_url(explanation.audio_id)
    )


def audio_url(audio_id: str | None) -> str | None:
    return f"/api/audio/{audio_id}" if audio_id else None

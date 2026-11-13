"""
Pydantic models: the shapes of data moving through the app.

ExtractedDocument is what the LLM must return after reading a photo. We validate
the LLM's JSON against it, so a bad answer (wrong type, made-up field, date in
the wrong format) raises an error instead of reaching the user.
"""

from datetime import date, datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Language = Literal["kn-IN", "hi-IN", "en-IN"]


class DocumentType(str, Enum):
    ELECTRICITY_BILL = "electricity_bill"
    BANK_LETTER = "bank_letter"  # includes bank SMS screenshots
    OFFICIAL_NOTICE = "official_notice"
    OTHER = "other"  # a readable document we don't support yet
    UNREADABLE = "unreadable"  # blurry, dark, cut off, or not a document


# The three types Odhu explains. Anything else gets a polite "can't help" message.
SUPPORTED_TYPES = {DocumentType.ELECTRICITY_BILL, DocumentType.BANK_LETTER, DocumentType.OFFICIAL_NOTICE}


class ExtractedDocument(BaseModel):
    """Facts read from the document photo. None means 'not on the document'."""

    model_config = ConfigDict(extra="forbid")  # reject any field we didn't ask for

    # The LLM judges this FIRST, before reading any field, so it commits to
    # "I can't read this" instead of guessing values.
    legibility: Literal["clear", "partly_readable", "unreadable"] = "clear"
    document_type: DocumentType
    sender: str | None = None
    amount_due: float | None = Field(default=None, ge=0)  # rupees
    due_date: date | None = None
    account_holder_name: str | None = None
    key_points: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)  # the LLM's own estimate, from 0 to 1


class DocumentReading(BaseModel):
    """What the LLM returns for one photo: the facts plus two spoken sentences."""

    document: ExtractedDocument
    intro: str  # what the document is and who sent it; empty if it couldn't be explained
    action: str  # the most important thing to do


class AnswerReading(BaseModel):
    """What the LLM returns for one question about a document."""

    answerable: bool  # False if the facts don't contain the answer
    answer: str  # 1-2 sentences in the user's language, without the amount due or due date
    say_amount_due: bool  # code adds the amount sentence after the answer
    say_due_date: bool  # code adds the due date sentence after the answer


# "ok" = explained normally, "unclear" = asked for a clearer photo,
# "unsupported" = readable, but not one of our three document types.
DocumentStatus = Literal["ok", "unclear", "unsupported"]


class QuestionOut(BaseModel):
    """One voice question and its answer."""

    id: str
    created_at: datetime
    transcript: str  # what we heard
    language: Language | None  # the language the person spoke; the answer is in it too
    answer: str  # the text that is spoken out loud
    audio_url: str | None


class ExplanationRequest(BaseModel):
    language: Language


class ExplanationOut(BaseModel):
    """A document's explanation in one language."""

    language: Language
    explanation: str
    audio_url: str | None


class DocumentOut(BaseModel):
    """What the API sends back for one scanned document."""

    id: str
    created_at: datetime
    language: Language
    status: DocumentStatus
    document: ExtractedDocument | None  # None when the photo couldn't be read
    explanation: str  # the text that is spoken out loud
    audio_url: str | None  # None if text-to-speech failed; the text is still shown
    questions: list[QuestionOut] = []  # follow-up questions asked so far, oldest first
    explanations: list[ExplanationOut] = []  # the explanation in other languages, if asked for

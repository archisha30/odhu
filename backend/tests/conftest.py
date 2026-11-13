"""
Shared test setup. pytest runs this before any test file.

The environment variables below are set BEFORE the app is imported, so the app
uses a throwaway data folder and fake keys, never your real database or credits.
"""

import os
import tempfile

os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="odhu-test-")
os.environ["GNANI_API_KEY"] = "fake-gnani-key"
os.environ["GEMINI_API_KEY"] = "fake-gemini-key"
os.environ["TTS_VOICE"] = "Shivani"
os.environ["TTS_SPEED"] = "0.9"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.schemas import AnswerReading, DocumentReading, ExtractedDocument  # noqa: E402
from app.services import gnani  # noqa: E402
from app.services.llm import get_llm  # noqa: E402


class FakeLLM:
    """Stands in for Gemini. Tests set `.document`, `.intro` and `.action` to control what it 'reads'."""

    def __init__(self):
        self.document = ExtractedDocument(
            document_type="electricity_bill",
            sender="Namma Vidyut Supply Corporation",
            amount_due=1179.0,
            due_date="2026-11-19",
            account_holder_name="Sarojamma H",
            key_points=["No arrears"],
            confidence=0.95,
        )
        self.intro = "ಇದು ವಿದ್ಯುತ್ ಬಿಲ್."
        self.action = "ಬೇಗ ಕಟ್ಟಿ."
        self.calls = 0
        self.answer = AnswerReading(
            answerable=True, answer="ಕೊನೆಯ ದಿನಾಂಕದ ಒಳಗೆ ಕಟ್ಟಬೇಕು.", say_amount_due=False, say_due_date=True
        )
        self.questions: list[str] = []
        self.answer_languages: list[str] = []
        self.explain_calls: list[str] = []

    def read_document(self, image: bytes, mime_type: str, language: str) -> DocumentReading:
        self.calls += 1
        return DocumentReading(document=self.document, intro=self.intro, action=self.action)

    def answer_question(self, document: ExtractedDocument, question: str, language: str) -> AnswerReading:
        self.questions.append(question)
        self.answer_languages.append(language)
        return self.answer

    def explain(self, document: ExtractedDocument, language: str) -> tuple[str, str]:
        self.explain_calls.append(language)
        return f"intro in {language}.", f"action in {language}."


@pytest.fixture
def fake_llm():
    llm = FakeLLM()
    app.dependency_overrides[get_llm] = lambda: llm
    yield llm
    app.dependency_overrides.clear()


@pytest.fixture
def tts_calls(monkeypatch):
    """Replace Gnani TTS with a fake that records each text it was asked to speak."""
    calls: list[str] = []

    def fake_tts(text, language, voice=None, speed=None):
        calls.append(text)
        return b"ID3-fake-mp3-" + text.encode("utf-8")

    monkeypatch.setattr(gnani, "text_to_speech", fake_tts)
    return calls


@pytest.fixture
def fake_stt(monkeypatch):
    """
    Replace Gnani STT. Tests set `fake_stt.transcript` and `fake_stt.language` to
    choose what was 'heard', and read `fake_stt.languages` to see what we listened for.
    """

    class FakeSTT:
        transcript = "ಈ ಬಿಲ್ ಯಾವಾಗ ಕಟ್ಟಬೇಕು"
        language: str | None = "kn-IN"
        languages: list[str] = []
        calls = 0

    def fake_speech_to_text(audio, filename, languages):
        FakeSTT.calls += 1
        FakeSTT.languages = languages
        return gnani.Transcript(text=FakeSTT.transcript, language=FakeSTT.language)

    monkeypatch.setattr(gnani, "speech_to_text", fake_speech_to_text)
    return FakeSTT


@pytest.fixture
def client(fake_llm, tts_calls, fake_stt):
    with TestClient(app) as c:  # "with" runs the startup code that creates tables
        yield c

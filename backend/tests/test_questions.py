"""Tests for POST /api/documents/{id}/ask. Gnani STT/TTS and Gemini are faked (see conftest.py)."""

import io
import uuid
import wave

from app import messages
from app.schemas import AnswerReading


def make_wav(seconds: float = 1.0) -> bytes:
    """A silent WAV file of the given length."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\0\0" * int(16000 * seconds))
    return buffer.getvalue()


def scan(client, language="kn-IN") -> str:
    """Scan a fresh fake document and return its id."""
    data = b"\x89PNG fake " + uuid.uuid4().bytes
    response = client.post("/api/documents", files={"image": ("b.png", data, "image/png")}, data={"language": language})
    return response.json()["id"]


def ask(client, document_id, audio=None, filename="question.wav", language=None):
    audio = audio if audio is not None else make_wav()
    data = {"language": language} if language else {}
    return client.post(f"/api/documents/{document_id}/ask", files={"audio": (filename, audio, "audio/wav")}, data=data)


def test_ask_returns_transcript_answer_with_code_built_date_and_audio(client, fake_llm):
    doc_id = scan(client)

    response = ask(client, doc_id)

    assert response.status_code == 200
    body = response.json()
    assert body["transcript"] == "ಈ ಬಿಲ್ ಯಾವಾಗ ಕಟ್ಟಬೇಕು"
    assert body["answer"] == "ಕೊನೆಯ ದಿನಾಂಕದ ಒಳಗೆ ಕಟ್ಟಬೇಕು. ಕೊನೆಯ ದಿನಾಂಕ ನವೆಂಬರ್ ಹತ್ತೊಂಬತ್ತನೇ ತಾರೀಖು."
    assert client.get(body["audio_url"]).status_code == 200
    assert fake_llm.questions == ["ಈ ಬಿಲ್ ಯಾವಾಗ ಕಟ್ಟಬೇಕು"]


def test_amount_flag_adds_the_exact_amount(client, fake_llm):
    fake_llm.answer = AnswerReading(answerable=True, answer="ಇಷ್ಟು ಕಟ್ಟಬೇಕು.", say_amount_due=True, say_due_date=False)
    doc_id = scan(client)

    assert ask(client, doc_id).json()["answer"] == "ಇಷ್ಟು ಕಟ್ಟಬೇಕು. ಪಾವತಿಸಬೇಕಾದ ಮೊತ್ತ ₹1,179."


def test_questions_show_up_on_the_document(client):
    doc_id = scan(client)
    ask(client, doc_id)

    document = client.get(f"/api/documents/{doc_id}").json()

    assert len(document["questions"]) == 1
    assert document["questions"][0]["transcript"] == "ಈ ಬಿಲ್ ಯಾವಾಗ ಕಟ್ಟಬೇಕು"


def test_silence_gets_didnt_hear_message_without_calling_llm(client, fake_llm, fake_stt):
    fake_stt.transcript = ""
    fake_stt.language = None  # like real Gnani: nothing heard, so no language detected
    doc_id = scan(client, language="hi-IN")

    body = ask(client, doc_id).json()

    assert body["answer"] == messages.DIDNT_HEAR["hi-IN"]
    assert fake_llm.questions == []


def test_unanswerable_question_gets_polite_message(client, fake_llm):
    fake_llm.answer = AnswerReading(answerable=False, answer="", say_amount_due=False, say_due_date=False)
    doc_id = scan(client)

    assert ask(client, doc_id).json()["answer"] == messages.NOT_IN_DOCUMENT["kn-IN"]


def test_answer_with_invented_amount_is_thrown_away(client, fake_llm):
    fake_llm.answer = AnswerReading(answerable=True, answer="ನೀವು ₹5,000 ಕಟ್ಟಬೇಕು.", say_amount_due=False, say_due_date=False)
    doc_id = scan(client)

    assert ask(client, doc_id).json()["answer"] == messages.NOT_IN_DOCUMENT["kn-IN"]


def test_answer_with_real_amount_from_key_points_is_kept(client, fake_llm):
    fake_llm.document = fake_llm.document.model_copy(update={"key_points": ["Amount after due date: ₹1,199.00"]})
    fake_llm.answer = AnswerReading(
        answerable=True, answer="ತಡವಾದರೆ ₹1,199 ಕಟ್ಟಬೇಕು.", say_amount_due=False, say_due_date=False
    )
    doc_id = scan(client)

    assert ask(client, doc_id).json()["answer"] == "ತಡವಾದರೆ ₹1,199 ಕಟ್ಟಬೇಕು."


def test_same_question_twice_calls_llm_once(client, fake_llm):
    doc_id = scan(client)

    first = ask(client, doc_id).json()
    second = ask(client, doc_id).json()

    assert len(fake_llm.questions) == 1
    assert first["answer"] == second["answer"]


def test_cannot_ask_about_unreadable_document(client, fake_llm):
    fake_llm.document = fake_llm.document.model_copy(update={"confidence": 0.1})
    doc_id = scan(client)

    assert ask(client, doc_id).status_code == 409


def test_unknown_document_is_404(client):
    assert ask(client, "nope").status_code == 404


def test_rejects_unsupported_audio_format(client, fake_stt):
    doc_id = scan(client)

    response = ask(client, doc_id, audio=b"webm bytes", filename="question.webm")

    assert response.status_code == 400
    assert fake_stt.calls == 0


def test_rejects_wav_longer_than_30_seconds(client, fake_stt):
    doc_id = scan(client)

    response = ask(client, doc_id, audio=make_wav(seconds=31))

    assert response.status_code == 400
    assert fake_stt.calls == 0


def test_rejects_broken_wav(client):
    doc_id = scan(client)
    assert ask(client, doc_id, audio=b"not a wav").status_code == 400


def test_stt_failure_is_a_friendly_502(client, monkeypatch):
    from app.services import gnani

    def broken(*args, **kwargs):
        raise gnani.GnaniError("down")

    monkeypatch.setattr(gnani, "speech_to_text", broken)
    doc_id = scan(client)

    assert ask(client, doc_id).status_code == 502


def test_usage_endpoint_reports_counts(client):
    body = client.get("/api/usage").json()

    assert set(body) == {"gnani", "gemini"}
    assert body["gnani"]["credits_left_estimate"] <= 5000


def test_answers_in_the_language_the_person_spoke(client, fake_llm, fake_stt):
    doc_id = scan(client, language="kn-IN")  # scanned in Kannada...
    fake_stt.transcript = "यह बिल कब तक भरना है"
    fake_stt.language = "hi-IN"  # ...but asked in Hindi

    body = ask(client, doc_id).json()

    assert body["language"] == "hi-IN"
    assert fake_llm.answer_languages == ["hi-IN"]
    assert body["answer"].endswith("आख़िरी तारीख़ उन्नीस नवंबर है।")  # code-built date, in Hindi


def test_listens_for_all_languages_with_the_expected_one_first(client, fake_stt):
    doc_id = scan(client, language="kn-IN")

    ask(client, doc_id, language="en-IN")  # the person is listening in English

    assert fake_stt.languages == ["en-IN", "kn-IN", "hi-IN"]


def test_undetected_language_falls_back_to_the_expected_one(client, fake_llm, fake_stt):
    fake_stt.language = None
    doc_id = scan(client, language="kn-IN")

    body = ask(client, doc_id, language="en-IN").json()

    assert body["language"] == "en-IN"
    assert fake_llm.answer_languages == ["en-IN"]


def test_silence_message_uses_the_expected_language(client, fake_stt):
    fake_stt.transcript = ""
    fake_stt.language = None
    doc_id = scan(client, language="kn-IN")

    assert ask(client, doc_id, language="hi-IN").json()["answer"] == messages.DIDNT_HEAR["hi-IN"]

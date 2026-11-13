"""
Tests for GeminiProvider. No real network calls: httpx.MockTransport sends each
request to a function that returns queued fake responses, one per call.
"""

import json

import httpx
import pytest

from app.config import Settings
from app.schemas import ExtractedDocument
from app.services.llm import GeminiProvider, LLMError, _output_text

GOOD_JSON = {
    "legibility": "clear",
    "document_type": "electricity_bill",
    "sender": "Namma Vidyut Supply Corporation",
    "amount_due": 1179.0,
    "due_date": "2026-11-19",
    "account_holder_name": "Sarojamma H",
    "key_points": ["Late fee after due date"],
    "confidence": 0.92,
    "intro": "ಇದು ವಿದ್ಯುತ್ ಬಿಲ್.",
    "action": "ಬೇಗ ಕಟ್ಟಿ.",
}


def interaction(text: str) -> httpx.Response:
    """A fake successful Interactions API response, shaped like the real one."""
    return httpx.Response(
        200,
        json={
            "status": "completed",
            "steps": [
                {"type": "thought", "signature": "abc"},
                {"type": "model_output", "content": [{"type": "text", "text": text}]},
            ],
        },
    )


def make_provider(*responses: httpx.Response, models=("main-model", "backup-model")):
    """Build a provider whose HTTP calls return `responses` in order. Also returns the sent bodies."""
    queue = list(responses)
    sent: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return queue.pop(0)

    provider = GeminiProvider(
        api_key="k", models=list(models), http_client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    return provider, sent


def test_read_document_returns_facts_and_sentences_in_one_call():
    provider, sent = make_provider(interaction(json.dumps(GOOD_JSON)))

    reading = provider.read_document(b"img", "image/png", "kn-IN")

    assert reading.document.amount_due == 1179.0
    assert str(reading.document.due_date) == "2026-11-19"
    assert reading.intro == "ಇದು ವಿದ್ಯುತ್ ಬಿಲ್."
    assert reading.action == "ಬೇಗ ಕಟ್ಟಿ."
    assert len(sent) == 1
    body = sent[0]
    assert body["store"] is False  # documents must not be stored by Google
    assert body["response_format"]["mime_type"] == "application/json"
    assert body["input"][1]["type"] == "image"
    assert "Kannada" in body["input"][0]["text"]


def test_rejects_json_that_breaks_the_schema():
    bad = {**GOOD_JSON, "due_date": "19th November"}  # not YYYY-MM-DD
    provider, _ = make_provider(interaction(json.dumps(bad)))

    with pytest.raises(LLMError, match="invalid document JSON"):
        provider.read_document(b"img", "image/png", "kn-IN")


def test_rejects_extra_invented_fields():
    bad = {**GOOD_JSON, "aadhaar_number": "0000"}
    provider, _ = make_provider(interaction(json.dumps(bad)))

    with pytest.raises(LLMError):
        provider.read_document(b"img", "image/png", "kn-IN")


def test_rejects_answer_that_is_not_json():
    provider, _ = make_provider(interaction("Sorry, I can't help with that."))

    with pytest.raises(LLMError):
        provider.read_document(b"img", "image/png", "kn-IN")


@pytest.mark.parametrize("status", [429, 503, 400])
def test_failing_model_falls_back_to_next_model(status):
    provider, sent = make_provider(httpx.Response(status, json={"error": "nope"}), interaction(json.dumps(GOOD_JSON)))

    reading = provider.read_document(b"img", "image/png", "kn-IN")

    assert reading.document.sender == "Namma Vidyut Supply Corporation"
    assert [b["model"] for b in sent] == ["main-model", "backup-model"]


def test_timeout_falls_back_to_next_model():
    calls = []

    def handler(request):
        calls.append(json.loads(request.content)["model"])
        if len(calls) == 1:
            raise httpx.ReadTimeout("slow")
        return interaction(json.dumps(GOOD_JSON))

    provider = GeminiProvider(api_key="k", models=["a", "b"], http_client=httpx.Client(transport=httpx.MockTransport(handler)))

    provider.read_document(b"img", "image/png", "kn-IN")
    assert calls == ["a", "b"]


def test_all_models_failing_raises_friendly_error():
    provider, _ = make_provider(httpx.Response(503), httpx.Response(429))

    with pytest.raises(LLMError, match="try again"):
        provider.read_document(b"img", "image/png", "kn-IN")


def test_digits_in_a_sentence_are_rewritten_as_words():
    with_digits = {**GOOD_JSON, "action": "ನೀವು 1179 ರೂಪಾಯಿ ಕಟ್ಟಬೇಕು."}
    provider, sent = make_provider(
        interaction(json.dumps(with_digits)),
        interaction("ನೀವು ಒಂದು ಸಾವಿರದ ನೂರ ಎಪ್ಪತ್ತೊಂಬತ್ತು ರೂಪಾಯಿ ಕಟ್ಟಬೇಕು."),
    )

    reading = provider.read_document(b"img", "image/png", "kn-IN")

    assert "1179" not in reading.action
    assert len(sent) == 2
    assert "1179" in sent[1]["input"][0]["text"]  # the rewrite request includes the original text


def test_sentence_in_english_letters_is_rewritten_in_kannada_script():
    romanized = {**GOOD_JSON, "intro": "Sahyadri Grameena Bank inda bandiro sandesha idu."}
    provider, sent = make_provider(
        interaction(json.dumps(romanized)),
        interaction("ಇದು ಸಹ್ಯಾದ್ರಿ ಗ್ರಾಮೀಣ ಬ್ಯಾಂಕಿನಿಂದ ಬಂದ ಸಂದೇಶ."),
    )

    reading = provider.read_document(b"img", "image/png", "kn-IN")

    assert reading.intro == "ಇದು ಸಹ್ಯಾದ್ರಿ ಗ್ರಾಮೀಣ ಬ್ಯಾಂಕಿನಿಂದ ಬಂದ ಸಂದೇಶ."
    assert "Kannada script" in sent[1]["input"][0]["text"]


def test_short_english_word_inside_kannada_is_fine():
    mixed = {**GOOD_JSON, "intro": "ಇದು ಸಹ್ಯಾದ್ರಿ ಬ್ಯಾಂಕಿನ KYC ಪತ್ರ."}
    provider, sent = make_provider(interaction(json.dumps(mixed)))

    provider.read_document(b"img", "image/png", "kn-IN")

    assert len(sent) == 1  # mostly Kannada, so no rewrite call


def test_doubled_vowel_sign_glitch_is_cleaned_up():
    glitchy = {**GOOD_JSON, "intro": "ಸರೋೋಜಮ್ಮ ಅವರ ಬಿಲ್."}
    provider, _ = make_provider(interaction(json.dumps(glitchy)))

    reading = provider.read_document(b"img", "image/png", "kn-IN")

    assert reading.intro == "ಸರೋಜಮ್ಮ ಅವರ ಬಿಲ್."


def test_output_text_ignores_thought_steps_and_fails_on_empty():
    assert _output_text(interaction("hello").json()) == "hello"
    with pytest.raises(LLMError):
        _output_text({"status": "failed", "steps": []})


def test_model_list_from_settings_has_no_blanks_or_repeats():
    settings = Settings(gemini_model="a", gemini_fallback_models=" b, ,a,c ")
    assert settings.gemini_models() == ["a", "b", "c"]


def test_answer_question_sends_facts_not_photo_and_parses_answer():
    reply = {"answerable": True, "answer": "ಕೊನೆಯ ದಿನಾಂಕದ ಒಳಗೆ ಕಟ್ಟಿ.", "say_amount_due": False, "say_due_date": True}
    provider, sent = make_provider(interaction(json.dumps(reply)))
    document = ExtractedDocument(**{k: v for k, v in GOOD_JSON.items() if k not in ("intro", "action")})

    answer = provider.answer_question(document, "ಯಾವಾಗ ಕಟ್ಟಬೇಕು", "kn-IN")

    assert answer.say_due_date is True
    prompt = sent[0]["input"][0]["text"]
    assert "ಯಾವಾಗ ಕಟ್ಟಬೇಕು" in prompt
    assert "Namma Vidyut Supply Corporation" in prompt  # the facts are in the prompt
    assert all(part["type"] == "text" for part in sent[0]["input"])  # no image sent


def test_rupee_amounts_in_answer_do_not_trigger_a_rewrite():
    reply = {"answerable": True, "answer": "ತಡವಾದರೆ ₹1,199 ಕಟ್ಟಬೇಕು.", "say_amount_due": False, "say_due_date": False}
    provider, sent = make_provider(interaction(json.dumps(reply)))
    document = ExtractedDocument(**{k: v for k, v in GOOD_JSON.items() if k not in ("intro", "action")})

    answer = provider.answer_question(document, "ತಡವಾದರೆ ಎಷ್ಟು", "kn-IN")

    assert answer.answer == "ತಡವಾದರೆ ₹1,199 ಕಟ್ಟಬೇಕು."
    assert len(sent) == 1


def test_english_mode_keeps_english_and_rewrites_kannada():
    # In English mode, English letters are correct, so no rewrite.
    english = {**GOOD_JSON, "intro": "This is an electricity bill from Namma Vidyut.", "action": "Please pay it on time."}
    provider, sent = make_provider(interaction(json.dumps(english)))
    provider.read_document(b"img", "image/png", "en-IN")
    assert len(sent) == 1
    assert "Indian English" in sent[0]["input"][0]["text"]

    # But a Kannada sentence in English mode is the wrong script: rewrite it.
    kannada = {**GOOD_JSON, "intro": "ಇದು ವಿದ್ಯುತ್ ಬಿಲ್.", "action": "Please pay on time."}
    provider, sent = make_provider(interaction(json.dumps(kannada)), interaction("This is an electricity bill."))
    reading = provider.read_document(b"img", "image/png", "en-IN")
    assert reading.intro == "This is an electricity bill."


def test_explain_writes_two_sentences_from_saved_facts():
    provider, sent = make_provider(interaction(json.dumps({"intro": "This is a bill.", "action": "Pay on time."})))
    document = ExtractedDocument(**{k: v for k, v in GOOD_JSON.items() if k not in ("intro", "action")})

    intro, action = provider.explain(document, "en-IN")

    assert (intro, action) == ("This is a bill.", "Pay on time.")
    prompt = sent[0]["input"][0]["text"]
    assert "Namma Vidyut Supply Corporation" in prompt and "Indian English" in prompt
    assert all(part["type"] == "text" for part in sent[0]["input"])  # no photo needed

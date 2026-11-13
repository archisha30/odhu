"""Tests for the /api/documents and /api/audio endpoints. Gemini and Gnani are faked (see conftest.py)."""

import uuid
from pathlib import Path

from app import messages
from app.schemas import DocumentType
from app.services import gnani


def upload(client, language="kn-IN", content_type="image/png", data=None):
    # Unique bytes by default, so the "same photo" cache doesn't kick in by accident.
    data = data if data is not None else b"\x89PNG fake " + uuid.uuid4().bytes
    return client.post(
        "/api/documents",
        files={"image": ("bill.png", data, content_type)},
        data={"language": language},
    )


def test_scan_returns_facts_explanation_and_playable_audio(client, tts_calls):
    response = upload(client)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["document"]["amount_due"] == 1179.0
    assert body["document"]["due_date"] == "2026-11-19"
    # LLM intro + amount and date sentences built by code + LLM action
    assert body["explanation"] == (
        "ಇದು ವಿದ್ಯುತ್ ಬಿಲ್. ಪಾವತಿಸಬೇಕಾದ ಮೊತ್ತ ₹1,179. ಕೊನೆಯ ದಿನಾಂಕ ನವೆಂಬರ್ ಹತ್ತೊಂಬತ್ತನೇ ತಾರೀಖು. ಬೇಗ ಕಟ್ಟಿ."
    )

    audio = client.get(body["audio_url"])
    assert audio.status_code == 200
    assert audio.headers["content-type"] == "audio/mpeg"
    assert audio.content.startswith(b"ID3-fake-mp3")


def test_low_confidence_asks_for_clearer_photo(client, fake_llm):
    fake_llm.document = fake_llm.document.model_copy(update={"confidence": 0.3})

    body = upload(client, language="hi-IN").json()

    assert body["status"] == "unclear"
    assert body["explanation"] == messages.UNCLEAR_PHOTO["hi-IN"]  # not the LLM's text
    assert body["document"] is None  # don't show facts we aren't sure of


def test_unreadable_type_asks_for_clearer_photo(client, fake_llm):
    fake_llm.document = fake_llm.document.model_copy(
        update={"document_type": DocumentType.UNREADABLE, "confidence": 0.9}
    )

    assert upload(client).json()["status"] == "unclear"


def test_llm_saying_unreadable_asks_for_clearer_photo(client, fake_llm):
    fake_llm.document = fake_llm.document.model_copy(update={"legibility": "unreadable", "confidence": 0.9})

    assert upload(client).json()["status"] == "unclear"


def test_very_blurry_photo_is_rejected_without_calling_gemini(client, fake_llm):
    blurry = (Path(__file__).resolve().parents[2] / "samples" / "06_blurry_photo.png").read_bytes()

    body = upload(client, data=blurry).json()

    assert body["status"] == "unclear"
    assert body["explanation"] == messages.UNCLEAR_PHOTO["kn-IN"]
    assert fake_llm.calls == 0


def test_letter_without_amount_never_mentions_an_amount(client, fake_llm):
    fake_llm.document = fake_llm.document.model_copy(update={"document_type": DocumentType.BANK_LETTER, "amount_due": None})

    body = upload(client, language="hi-IN").json()

    assert "₹" not in body["explanation"]
    assert "आख़िरी तारीख़ उन्नीस नवंबर है।" in body["explanation"]


def test_explanation_sentence_with_invented_amount_is_dropped(client, fake_llm):
    fake_llm.action = "₹9,999 ಕಟ್ಟಿ."  # not on the document

    body = upload(client).json()

    assert "9,999" not in body["explanation"]
    assert body["explanation"].startswith("ಇದು ವಿದ್ಯುತ್ ಬಿಲ್.")


def test_other_document_type_is_politely_unsupported(client, fake_llm):
    fake_llm.document = fake_llm.document.model_copy(update={"document_type": DocumentType.OTHER})

    body = upload(client).json()

    assert body["status"] == "unsupported"
    assert body["explanation"] == messages.UNSUPPORTED_DOCUMENT["kn-IN"]


def test_supported_document_without_explanation_is_an_error(client, fake_llm):
    fake_llm.intro = ""

    assert upload(client).status_code == 502


def test_same_photo_twice_calls_gemini_only_once(client, fake_llm):
    photo = b"\x89PNG the very same photo"

    first = upload(client, data=photo).json()
    second = upload(client, data=photo).json()

    assert fake_llm.calls == 1
    assert first["id"] == second["id"]


def test_same_photo_in_another_language_is_read_again(client, fake_llm):
    photo = b"\x89PNG photo read in two languages"

    upload(client, data=photo, language="kn-IN")
    upload(client, data=photo, language="hi-IN")

    assert fake_llm.calls == 2


def test_unclear_result_is_not_reused(client, fake_llm):
    fake_llm.document = fake_llm.document.model_copy(update={"confidence": 0.2})
    photo = b"\x89PNG blurry photo"

    upload(client, data=photo)
    upload(client, data=photo)

    assert fake_llm.calls == 2  # Gemini may do better on a second try


def test_same_text_is_spoken_only_once_thanks_to_cache(client, fake_llm, tts_calls):
    fake_llm.intro = "ಕ್ಯಾಶ್ ಪರೀಕ್ಷೆ."  # text no other test uses

    first = upload(client).json()
    second = upload(client).json()  # a different photo, but the same text to speak

    assert first["audio_url"] == second["audio_url"]
    assert len([t for t in tts_calls if t.startswith("ಕ್ಯಾಶ್ ಪರೀಕ್ಷೆ.")]) == 1  # second time it came from disk


def test_tts_failure_still_returns_text(client, fake_llm, monkeypatch):
    def broken_tts(*args, **kwargs):
        raise gnani.GnaniError("Gnani is down")

    monkeypatch.setattr(gnani, "text_to_speech", broken_tts)
    fake_llm.intro = "ಟಿಟಿಎಸ್ ವಿಫಲ ಪರೀಕ್ಷೆ."  # not cached yet, so TTS is really called

    body = upload(client).json()

    assert body["status"] == "ok"
    assert body["explanation"].startswith("ಟಿಟಿಎಸ್ ವಿಫಲ ಪರೀಕ್ಷೆ.")
    assert body["audio_url"] is None


def test_rejects_non_image_upload(client):
    assert upload(client, content_type="application/pdf").status_code == 400


def test_rejects_unknown_language(client):
    assert upload(client, language="ta-IN").status_code == 422


def test_history_lists_newest_first_and_get_by_id_works(client):
    first_id = upload(client).json()["id"]
    second_id = upload(client).json()["id"]

    history = client.get("/api/documents").json()
    ids = [d["id"] for d in history]
    assert ids.index(second_id) < ids.index(first_id)

    one = client.get(f"/api/documents/{first_id}")
    assert one.status_code == 200
    assert one.json()["id"] == first_id


def test_unknown_document_and_audio_return_404(client):
    assert client.get("/api/documents/does-not-exist").status_code == 404
    assert client.get("/api/audio/" + "0" * 64).status_code == 404
    assert client.get("/api/audio/..%2F..%2F.env").status_code == 404


def test_english_scan_uses_english_sentences(client, fake_llm):
    fake_llm.intro = "This is an electricity bill."
    fake_llm.action = "Please pay on time."

    body = upload(client, language="en-IN").json()

    assert body["language"] == "en-IN"
    assert body["explanation"] == (
        "This is an electricity bill. The amount to pay is ₹1,179. "
        "The last date is the nineteenth of November. Please pay on time."
    )


def test_partly_readable_document_adds_double_check_message(client, fake_llm):
    fake_llm.document = fake_llm.document.model_copy(update={"legibility": "partly_readable", "confidence": 0.9})

    body = upload(client).json()

    assert body["status"] == "ok"
    assert body["explanation"].endswith(messages.CHECK_PAPER["kn-IN"])


def test_middling_confidence_adds_double_check_message(client, fake_llm):
    fake_llm.document = fake_llm.document.model_copy(update={"confidence": 0.7})

    assert upload(client, language="en-IN").json()["explanation"].endswith(messages.CHECK_PAPER["en-IN"])


def test_clear_document_has_no_double_check_message(client):
    assert messages.CHECK_PAPER["kn-IN"] not in upload(client).json()["explanation"]


def explain(client, doc_id, language):
    return client.post(f"/api/documents/{doc_id}/explanations", json={"language": language})


def test_explanation_in_another_language_is_made_once_then_reused(client, fake_llm, tts_calls):
    doc_id = upload(client, language="kn-IN").json()["id"]

    first = explain(client, doc_id, "en-IN").json()
    second = explain(client, doc_id, "en-IN").json()

    assert first["language"] == "en-IN"
    assert first["explanation"] == (
        "intro in en-IN. The amount to pay is ₹1,179. The last date is the nineteenth of November. action in en-IN."
    )
    assert first == second
    assert fake_llm.explain_calls == ["en-IN"]  # the second request was served from the database
    assert client.get(first["audio_url"]).status_code == 200


def test_explanation_in_the_scanned_language_is_the_original(client, fake_llm):
    doc = upload(client, language="kn-IN").json()

    body = explain(client, doc["id"], "kn-IN").json()

    assert body["explanation"] == doc["explanation"]
    assert fake_llm.explain_calls == []


def test_other_language_versions_come_back_with_the_document(client):
    doc_id = upload(client, language="kn-IN").json()["id"]
    explain(client, doc_id, "hi-IN")

    document = client.get(f"/api/documents/{doc_id}").json()

    assert [e["language"] for e in document["explanations"]] == ["hi-IN"]


def test_unclear_document_gets_the_fixed_message_in_the_new_language(client, fake_llm):
    fake_llm.document = fake_llm.document.model_copy(update={"confidence": 0.2})
    doc_id = upload(client, language="kn-IN").json()["id"]

    body = explain(client, doc_id, "en-IN").json()

    assert body["explanation"] == messages.UNCLEAR_PHOTO["en-IN"]
    assert fake_llm.explain_calls == []


def test_explanation_for_unknown_document_is_404(client):
    assert explain(client, "nope", "en-IN").status_code == 404

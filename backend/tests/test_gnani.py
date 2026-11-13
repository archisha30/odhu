"""
Tests for the Gnani service. They make no real network calls: we replace the
module's HTTP client with one that uses httpx.MockTransport, which sends every
request to a small Python function and returns whatever that function returns.
"""

import json

import httpx
import pytest

from app import usage
from app.services import gnani


@pytest.fixture
def fake_gnani(monkeypatch):
    """
    Swap in a fake HTTP client. Tests set `fake.reply` to control the response,
    and read `fake.requests` to see what was sent.
    """

    class Fake:
        requests: list[httpx.Request] = []
        reply = httpx.Response(200, json={"success": True, "transcript": "ನಮಸ್ಕಾರ"})

    def handler(request: httpx.Request) -> httpx.Response:
        Fake.requests.append(request)
        return Fake.reply

    Fake.requests = []
    monkeypatch.setattr(gnani, "http_client", httpx.Client(transport=httpx.MockTransport(handler)))
    monkeypatch.setattr(gnani.settings, "gnani_api_key", "test-key")
    return Fake


def test_stt_sends_the_right_fields_and_returns_transcript(fake_gnani):
    fake_gnani.reply = httpx.Response(
        200, json={"success": True, "transcript": "  ಬಿಲ್ ಯಾವಾಗ ಕಟ್ಟಬೇಕು  ", "detected_language_code": "kn-IN"}
    )

    transcript = gnani.speech_to_text(b"fake-audio", "question.mp3", ["kn-IN", "hi-IN", "en-IN"])

    assert transcript.text == "ಬಿಲ್ ಯಾವಾಗ ಕಟ್ಟಬೇಕು"  # surrounding spaces stripped
    assert transcript.language == "kn-IN"
    request = fake_gnani.requests[0]
    assert str(request.url) == gnani.STT_URL
    assert request.headers["X-API-Key-ID"] == "test-key"
    body = request.read().decode("utf-8", errors="ignore")
    assert 'name="audio_file"; filename="question.mp3"' in body
    assert "kn-IN,hi-IN,en-IN" in body  # all the languages we listen for
    assert "transcribe" in body
    assert "prisma-v3.0" in body


def test_tts_sends_json_body_and_returns_audio_bytes(fake_gnani, monkeypatch):
    monkeypatch.setattr(gnani.settings, "tts_voice", "Shivani")
    monkeypatch.setattr(gnani.settings, "tts_speed", 0.9)
    fake_gnani.reply = httpx.Response(200, content=b"ID3-fake-mp3", headers={"content-type": "audio/mpeg"})

    audio = gnani.text_to_speech("ನಮಸ್ಕಾರ", "kn-IN")

    assert audio == b"ID3-fake-mp3"
    sent = json.loads(fake_gnani.requests[0].content)
    assert sent == {
        "text": "ನಮಸ್ಕಾರ",
        "model": "timbre-v3.0",
        "voice": "Shivani",
        "language": "kn-IN",
        "speed": 0.9,
        "audio_config": {"container": "mp3", "sample_rate": 24000},
    }


def test_http_error_becomes_gnani_error(fake_gnani):
    fake_gnani.reply = httpx.Response(403, json={"success": False, "error": {"message": "Forbidden"}})

    with pytest.raises(gnani.GnaniError, match="HTTP 403"):
        gnani.text_to_speech("ನಮಸ್ಕಾರ", "kn-IN")


def test_every_call_is_saved_to_the_database(fake_gnani):
    before = usage.summary()["gnani"]

    gnani.speech_to_text(b"a", "a.wav", ["hi-IN"])
    fake_gnani.reply = httpx.Response(500, text="boom")
    with pytest.raises(gnani.GnaniError):
        gnani.speech_to_text(b"a", "a.wav", ["hi-IN"])

    after = usage.summary()["gnani"]
    assert after["stt_calls"] == before["stt_calls"] + 2  # failed calls count too
    assert after["credits_left_estimate"] == before["credits_left_estimate"] - 2


def test_rejects_unsupported_language_without_calling_api(fake_gnani):
    with pytest.raises(gnani.GnaniError, match="Unsupported language"):
        gnani.text_to_speech("vanakkam", "ta-IN")
    assert fake_gnani.requests == []


def test_missing_api_key_gives_clear_error(fake_gnani, monkeypatch):
    monkeypatch.setattr(gnani.settings, "gnani_api_key", "")
    before = usage.gnani_calls_total()
    with pytest.raises(gnani.GnaniError, match="GNANI_API_KEY is not set"):
        gnani.text_to_speech("ನಮಸ್ಕಾರ", "kn-IN")
    assert usage.gnani_calls_total() == before  # no call was made, so nothing counted


def test_unknown_or_missing_detected_language_becomes_none(fake_gnani):
    fake_gnani.reply = httpx.Response(200, json={"success": True, "transcript": "x", "detected_language_code": "mr-IN"})
    assert gnani.speech_to_text(b"a", "a.wav", ["kn-IN"]).language is None

    fake_gnani.reply = httpx.Response(200, json={"success": True, "transcript": ""})
    assert gnani.speech_to_text(b"a", "a.wav", ["kn-IN"]).language is None

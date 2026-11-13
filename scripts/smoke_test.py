"""
Smoke test: calls the REAL Gnani and Gemini APIs once through the whole flow,
to check our keys and code work end to end, without the frontend.

Run from the backend folder (so it uses the backend's uv environment):
    cd backend
    uv run python ../scripts/smoke_test.py

What it does:
  1. TTS (Gnani Timbre): speak a fixed Kannada question, as if the user asked it.
  2. STT (Gnani Prisma v3.0): transcribe that audio and detect its language.
  3. Gemini: read samples/01_electricity_bill_kn.png (facts + two sentences in one
     call). Code adds the amount and date sentences (app/spoken.py).
  4. TTS: speak the explanation.
  5. Gemini: answer the transcribed question using only the extracted facts.
  6. TTS: speak the answer.

Credits: TTS results are cached on disk (backend/data/audio), so re-running
only spends Gnani credits on new text. The STT call costs 1 credit every run.
"""

import logging
import shutil
import sys
import time
from pathlib import Path

# Let this script import the backend's `app` package.
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app import spoken, usage  # noqa: E402
from app.config import settings  # noqa: E402
from app.services import audio_cache, gnani  # noqa: E402
from app.services.llm import LLMError, get_llm  # noqa: E402

OUTPUT_DIR = REPO_ROOT / "scripts" / "output"
SAMPLE_BILL = REPO_ROOT / "samples" / "01_electricity_bill_kn.png"
LANGUAGE = "kn-IN"

# "When do I have to pay this bill?"
QUESTION_KN = "ಈ ಬಿಲ್ ಅನ್ನು ನಾನು ಯಾವಾಗ ಕಟ್ಟಬೇಕು?"


def step(title: str) -> float:
    print(f"\n== {title}")
    return time.perf_counter()


def done(start: float) -> None:
    print(f"   ({time.perf_counter() - start:.1f}s)")


def speak_to_file(text: str, name: str) -> None:
    audio_id = audio_cache.speak(text, LANGUAGE)
    shutil.copy(audio_cache.audio_path(audio_id), OUTPUT_DIR / name)


def main() -> None:
    # Show the timing log lines from our service modules.
    logging.basicConfig(level=logging.INFO, format="   [log] %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    llm = get_llm()

    start = step(f"1) TTS question (Timbre, voice={settings.tts_voice})")
    print(f"   text: {QUESTION_KN}")
    speak_to_file(QUESTION_KN, "question_kn.mp3")
    done(start)

    start = step("2) STT on that audio (Prisma)")
    heard = gnani.speech_to_text((OUTPUT_DIR / "question_kn.mp3").read_bytes(), "question_kn.mp3", ["kn-IN", "hi-IN", "en-IN"])
    transcript = heard.text
    print(f"   transcript: {transcript}   (detected language: {heard.language})")
    done(start)

    start = step(f"3) Gemini reads {SAMPLE_BILL.name} (models: {', '.join(settings.gemini_models())})")
    reading = llm.read_document(SAMPLE_BILL.read_bytes(), "image/png", LANGUAGE)
    document = reading.document
    print("   " + document.model_dump_json(indent=2).replace("\n", "\n   "))
    explanation = spoken.build_explanation(document, reading.intro, reading.action, LANGUAGE)
    print(f"   explanation: {explanation}")
    done(start)

    start = step("4) TTS explanation")
    speak_to_file(explanation, "explanation_kn.mp3")
    done(start)

    start = step("5) Gemini answers the transcribed question")
    answer = llm.answer_question(document, transcript, LANGUAGE)
    print(f"   {answer.model_dump()}")
    answer_text = spoken.build_answer(document, answer.answer, answer.say_amount_due, answer.say_due_date, LANGUAGE)
    print(f"   spoken answer: {answer_text}")
    done(start)

    start = step("6) TTS answer")
    speak_to_file(answer_text, "answer_kn.mp3")
    done(start)

    gnani_usage = usage.summary()["gnani"]
    print(f"\nDone. Gnani calls so far (all time): {gnani_usage['total_calls']}, "
          f"about {gnani_usage['credits_left_estimate']} credits left.")
    print(f"Listen: open {OUTPUT_DIR}")


if __name__ == "__main__":
    try:
        main()
    except (gnani.GnaniError, LLMError) as exc:
        print(f"\nFAILED: {exc}")
        sys.exit(1)

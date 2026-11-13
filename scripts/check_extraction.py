"""
Checks Gemini's reading of the sample documents against the known answers in
samples/expected.json. Uses Gemini only (no Gnani credits).

    cd backend
    uv run python ../scripts/check_extraction.py               # all samples, Kannada
    uv run python ../scripts/check_extraction.py 04 06         # only samples starting with 04 or 06
    uv run python ../scripts/check_extraction.py --hindi 02    # explanations in Hindi
    uv run python ../scripts/check_extraction.py --english 05  # explanations in English

Each sample is one Gemini request. We pause between requests so we stay under
the free tier's requests-per-minute limit.
"""

import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app import spoken  # noqa: E402
from app.config import settings  # noqa: E402
from app.routes.documents import CONFIDENCE_THRESHOLD  # noqa: E402
from app.services.llm import LLMError, get_llm  # noqa: E402

SAMPLES = REPO_ROOT / "samples"
FIELDS = ["document_type", "sender", "amount_due", "due_date", "account_holder_name"]
PAUSE_SECONDS = 6  # at most 10 requests per minute


def same(field: str, got, want) -> bool:
    if got is None or want is None:
        return got == want
    if field in ("sender", "account_holder_name"):  # allow small spelling/case/title differences
        return want.lower() in got.lower() or got.lower() in want.lower()
    return got == want


def main() -> None:
    args = sys.argv[1:]
    language = "hi-IN" if "--hindi" in args else "en-IN" if "--english" in args else "kn-IN"
    prefixes = [a for a in args if not a.startswith("--")]

    expected = json.loads((SAMPLES / "expected.json").read_text())
    names = [n for n in expected if not n.startswith("_") and (not prefixes or n.startswith(tuple(prefixes)))]
    llm = get_llm()
    print(f"models: {', '.join(settings.gemini_models())}   language: {language}\n")
    failures = 0

    for i, name in enumerate(names):
        if i > 0:
            time.sleep(PAUSE_SECONDS)
        want = expected[name]
        start = time.perf_counter()
        try:
            reading = llm.read_document((SAMPLES / name).read_bytes(), "image/png", language)
        except LLMError as exc:
            print(f"{name}\n  FAIL Gemini error: {exc}")
            failures += 1
            continue
        doc = reading.document
        got = json.loads(doc.model_dump_json())
        print(f"{name}  ({time.perf_counter() - start:.1f}s, confidence {doc.confidence:.2f})")

        if "_expect" in want:  # the blurry photo: we only expect it to be treated as unclear
            ok = doc.confidence < CONFIDENCE_THRESHOLD or doc.document_type.value == "unreadable"
            print(f"  {'OK  ' if ok else 'FAIL'} should be unclear -> type={got['document_type']}")
            failures += not ok
            continue

        for field in FIELDS:
            ok = same(field, got[field], want[field])
            failures += not ok
            print(f"  {'OK  ' if ok else 'FAIL'} {field}: {got[field]!r}" + ("" if ok else f" (expected {want[field]!r})"))
        print(f"       key_points: {got['key_points']}")
        print(f"       explanation: {spoken.build_explanation(doc, reading.intro, reading.action, language)}")

    print(f"\n{failures} problem(s)")


if __name__ == "__main__":
    main()

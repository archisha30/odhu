"""
The vision + reasoning LLM, kept behind a small interface so we can switch providers.

The rest of the app only knows about `LLMProvider`:
  - read_document(): read a document photo and, in the SAME call, write two
    short spoken sentences (what it is, and what to do). One call instead of two
    halves our use of Gemini's free-tier quota. The amount and date sentences are
    added by code (see app/spoken.py), so they can never be wrong.
  - explain(): write those two sentences in another language from the saved facts,
    when someone wants to hear an old document in a different language.
  - answer_question(): answer a spoken follow-up question using ONLY the facts
    extracted earlier (not the photo), again with the amount and date added by code.

GeminiProvider is the real implementation. It uses Gemini's REST "Interactions" API:
  https://ai.google.dev/gemini-api/docs/interactions
We send store=False so Google does not keep copies of people's bills.

Free-tier quotas are per model, so we keep a list of models. If one fails
(quota used up, overloaded, timeout...), we simply try the next one.
"""

import base64
import json
import logging
import re
import time
from typing import Protocol

import httpx
from pydantic import ValidationError

from app import usage
from app.config import settings
from app.schemas import AnswerReading, DocumentReading, ExtractedDocument, Language
from app.spoken import RUPEE_AMOUNT, facts_sentences

logger = logging.getLogger("odhu.llm")

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"

LANGUAGE_NAMES = {"kn-IN": "Kannada", "hi-IN": "Hindi", "en-IN": "Indian English"}
SCRIPT_NAMES = {
    "kn-IN": "Kannada script (ಕನ್ನಡ ಲಿಪಿ)",
    "hi-IN": "Devanagari script (देवनागरी)",
    "en-IN": "English (Latin letters)",
}

# How to handle names and English words, per language. Kannada and Hindi must not
# contain English letters, because TTS would then read them as English.
SCRIPT_RULES = {
    "kn-IN": "Never use English letters, even if the document is in English. Write organisation names as they sound, in Kannada script.",
    "hi-IN": "Never use English letters, even if the document is in English. Write organisation names as they sound, in Devanagari script.",
    "en-IN": "Use simple, everyday words. Keep organisation names as printed.",
}

# Letters of each language's own script, and English (Latin) letters.
SCRIPT_LETTERS = {
    "kn-IN": re.compile(r"[\u0C80-\u0CFF]"),
    "hi-IN": re.compile(r"[\u0900-\u097F]"),
    "en-IN": re.compile(r"[A-Za-z]"),
}

# A Kannada or Hindi vowel sign typed twice in a row, like "ಸರೋೋಜಮ್ಮ". Flash-Lite
# sometimes produces this glitch, and TTS would read it oddly.
DOUBLED_VOWEL_SIGN = re.compile(r"([\u0CBE-\u0CCC\u093E-\u094C])\1+")

# Any digit: Western 0-9, Kannada ೦-೯ or Devanagari ०-९. Spoken text must use words instead.
DIGIT_PATTERN = re.compile(r"[0-9೦-೯०-९]")


class LLMError(Exception):
    """Raised when the LLM call fails or returns something we can't use."""


class LLMProvider(Protocol):
    """Anything with these methods can be used as the app's LLM."""

    def read_document(self, image: bytes, mime_type: str, language: Language) -> DocumentReading: ...

    def answer_question(self, document: ExtractedDocument, question: str, language: Language) -> AnswerReading: ...

    def explain(self, document: ExtractedDocument, language: Language) -> tuple[str, str]: ...


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

READ_PROMPT = """\
You help elderly people in India understand documents. Look at the image, extract
the facts, then explain the document in simple spoken {language_name}.
Use ONLY what is printed in the image. Never guess or invent. A wrong amount or date
could make an elderly person pay the wrong money or miss a deadline, so a missing
value (null) is always better than a guessed one.

Fields:
- legibility: decide this FIRST, honestly, before reading any other field.
    "clear"            you can read the individual letters and digits of the sender,
                       the amount and the date without effort
    "partly_readable"  some parts are readable, but some important text is blurry,
                       cut off or covered
    "unreadable"       you cannot reliably read the individual letters and digits
  If it is "unreadable", set document_type to "unreadable", every other field to
  null or empty, and confidence below 0.3. Never fill fields with typical values,
  examples, or names of real companies you know.
- document_type: one of
    "electricity_bill"
    "bank_letter"      (letters from a bank, and screenshots of bank SMS messages)
    "official_notice"  (government, municipality, tax, court or similar notices)
    "other"            (a readable document that is none of the above)
    "unreadable"       (too blurry, dark, cut off, or not a document at all)
- sender: the organisation that sent it, as printed. For an SMS, use the bank's name
  if it is shown, not the sender code (like "VM-SGBANK"). null if not shown.
- amount_due: the total amount in rupees the person must pay now, as a plain number.
  Only if you can read every digit; otherwise null
  (1,179.00 -> 1179.0). If there is also a higher "after due date" amount, use the
  amount before the due date. null if nothing has to be paid or no amount is printed.
- due_date: the last date to pay or act, as YYYY-MM-DD. Indian documents usually
  write dates as DD-MM-YYYY, so 05-11-2026 means 5 November 2026. null if none, or
  if you cannot read every digit.
- account_holder_name: the person the document is addressed to, in English letters
  (transliterate if needed). null if not shown.
- key_points: 2 to 4 short facts in simple, plain English that matter to the reader,
  such as arrears, a disconnection warning, documents to bring, or a late fee. Only
  facts printed in the image. Copy any amounts and dates exactly as printed.
- confidence: a number from 0 to 1 for how sure you are that you read the important
  fields correctly. Use below 0.5 if the image is blurry, dark, cut off or hard to read.
"""

# How to write the two spoken sentences. Shared by READ_PROMPT (photo) and
# EXPLAIN_PROMPT (saved facts, another language), so both follow the same rules.
SENTENCE_RULES = """\
- intro: ONE short sentence in simple spoken {language_name} saying what the document
  is and who sent it, the way a kind grandchild would explain it to a grandparent.
- action: ONE short sentence in simple spoken {language_name} with the single most
  important thing the person should do (for example: pay at the office or online,
  visit the bank branch with the listed documents, keep enough balance).
Rules for intro and action:
  * Write them in {script_name}. {script_rule}
  * NEVER mention any amount, date or other number. The app adds the amount and the
    due date itself, in between your two sentences.
  * Plain text: no lists, markdown, emojis or greetings.
  * Don't address the listener by any name or title (no "Amma", "Ajji", "Sir", etc.).
  * Avoid first-person verbs, so the sentence fits any voice.
  * If document_type is "unreadable" or "other", use empty strings.
"""

READ_PROMPT += SENTENCE_RULES

EXPLAIN_PROMPT = """\
You help elderly people in India understand documents. Below are facts that were
read from a document earlier. Write the two spoken sentences described below.
Use ONLY these facts. Never guess or invent.

Facts:
{facts_json}

Fields:
""" + SENTENCE_RULES

EXPLAIN_SCHEMA = {
    "type": "object",
    "properties": {"intro": {"type": "string"}, "action": {"type": "string"}},
    "required": ["intro", "action"],
}

# Examples that show the model how to write numbers as words (used by the digit rewrite).
NUMBER_EXAMPLES = {
    "kn-IN": '1179 rupees -> "ಒಂದು ಸಾವಿರದ ನೂರ ಎಪ್ಪತ್ತೊಂಬತ್ತು ರೂಪಾಯಿ"; '
    '2026-11-19 -> "ನವೆಂಬರ್ ಹತ್ತೊಂಬತ್ತನೇ ತಾರೀಖು"',
    "hi-IN": '1179 rupees -> "एक हज़ार एक सौ उन्यासी रुपये"; 2026-11-19 -> "उन्नीस नवंबर"',
    "en-IN": '1179 rupees -> "one thousand one hundred and seventy-nine rupees"; 2026-11-19 -> "the nineteenth of November"',
}

# JSON Schema that Gemini must follow: ExtractedDocument's fields plus "intro" and "action".
READ_SCHEMA = {
    "type": "object",
    "properties": {
        "legibility": {"type": "string", "enum": ["clear", "partly_readable", "unreadable"]},
        "document_type": {
            "type": "string",
            "enum": ["electricity_bill", "bank_letter", "official_notice", "other", "unreadable"],
        },
        "sender": {"type": ["string", "null"]},
        "amount_due": {"type": ["number", "null"], "minimum": 0},
        "due_date": {"type": ["string", "null"], "format": "date"},
        "account_holder_name": {"type": ["string", "null"]},
        "key_points": {"type": "array", "items": {"type": "string"}, "maxItems": 4},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "intro": {"type": "string"},
        "action": {"type": "string"},
    },
    "required": [
        "legibility",
        "document_type",
        "sender",
        "amount_due",
        "due_date",
        "account_holder_name",
        "key_points",
        "confidence",
        "intro",
        "action",
    ],
}

ANSWER_PROMPT = """\
You help an elderly person in India understand a document. They asked a question
out loud. Answer it using ONLY the facts below, which were read from the document
earlier. The question was turned into text by speech recognition, so it may have
small mistakes: answer the most likely meaning.

Fields:
- answerable: false if the facts do not contain the answer. Never guess.
- answer: 0 to 2 short, kind, complete sentences in simple spoken {language_name},
  written in {script_name}. Rules:
    * Do NOT write the amount due or the due date yourself. Set say_amount_due or
      say_due_date to true instead, and the app will add exactly this sentence
      AFTER your answer:
        amount: {amount_sentence}
        date:   {date_sentence}
      Do not repeat what that sentence says. If the question is only "how much?" or
      "when?", leave answer empty: the added sentence is then the whole answer.
    * If you need another rupee amount from the facts (like a late fee or arrears),
      copy it exactly as ₹ followed by the digits in the facts, with spaces around it.
      Write any other number in {language_name} words.
    * Each sentence must be complete and end with a full stop.
    * {script_rule}
    * No lists, markdown or greetings. Avoid first-person verbs.
    * If answerable is false, use an empty string.
- say_amount_due: true if the answer needs the amount due.
- say_due_date: true if the answer needs the due date.

Facts:
{facts_json}

Question: {question}
"""

ANSWER_SCHEMA = {
    "type": "object",
    "properties": {
        "answerable": {"type": "boolean"},
        "answer": {"type": "string"},
        "say_amount_due": {"type": "boolean"},
        "say_due_date": {"type": "boolean"},
    },
    "required": ["answerable", "answer", "say_amount_due", "say_due_date"],
}

REWRITE_PROMPT = """\
Rewrite this text in simple spoken {language_name}, written in {script_name}.
{script_rule} Use no digits: write every number fully in {language_name}
words, except amounts written as ₹ followed by digits, which you must keep exactly
as they are. Keep the meaning the same. Reply with only the rewritten text.
Examples of numbers as words: {number_examples}

Text:
{text}
"""


# ---------------------------------------------------------------------------
# Gemini implementation
# ---------------------------------------------------------------------------


class GeminiProvider:
    def __init__(self, api_key: str, models: list[str], http_client: httpx.Client | None = None):
        self.api_key = api_key
        self.models = models  # tried in order until one works
        # Normal answers take 4-10 s. After 20 s, give up on this model and try the next.
        self.http = http_client or httpx.Client(timeout=20.0)

    # --- public method -------------------------------------------------------

    def read_document(self, image: bytes, mime_type: str, language: Language) -> DocumentReading:
        prompt = READ_PROMPT.format(
            language_name=LANGUAGE_NAMES[language],
            script_name=SCRIPT_NAMES[language],
            script_rule=SCRIPT_RULES[language],
        )
        inputs = [
            {"type": "text", "text": prompt},
            {"type": "image", "data": base64.b64encode(image).decode("ascii"), "mime_type": mime_type},
        ]
        text = self._generate(inputs, temperature=0.0, schema=READ_SCHEMA)

        # Split the answer into the facts and the two sentences, and validate the facts.
        try:
            data = json.loads(text)
            intro = self._clean(str(data.pop("intro", "")), language)
            action = self._clean(str(data.pop("action", "")), language)
            document = ExtractedDocument.model_validate(data)
        except (json.JSONDecodeError, AttributeError, ValidationError) as exc:
            # The model broke the schema. Better to fail than to show wrong facts.
            raise LLMError(f"Gemini returned invalid document JSON: {exc}") from exc

        return DocumentReading(document=document, intro=intro, action=action)

    def explain(self, document: ExtractedDocument, language: Language) -> tuple[str, str]:
        """Write (intro, action) in `language` from facts saved earlier. Text only: no photo needed."""
        prompt = EXPLAIN_PROMPT.format(
            language_name=LANGUAGE_NAMES[language],
            script_name=SCRIPT_NAMES[language],
            script_rule=SCRIPT_RULES[language],
            facts_json=document.model_dump_json(indent=2, exclude={"confidence", "legibility"}),
        )
        text = self._generate([{"type": "text", "text": prompt}], temperature=0.0, schema=EXPLAIN_SCHEMA)
        try:
            data = json.loads(text)
            return self._clean(str(data["intro"]), language), self._clean(str(data["action"]), language)
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise LLMError(f"Gemini returned invalid explanation JSON: {exc}") from exc

    def answer_question(self, document: ExtractedDocument, question: str, language: Language) -> AnswerReading:
        prompt = ANSWER_PROMPT.format(
            language_name=LANGUAGE_NAMES[language],
            script_name=SCRIPT_NAMES[language],
            script_rule=SCRIPT_RULES[language],
            # The answer may only use these facts. confidence/legibility don't help answer anything.
            facts_json=document.model_dump_json(indent=2, exclude={"confidence", "legibility"}),
            question=question,
            # Show the model the exact sentences the app would add, so its answer fits around them.
            amount_sentence=facts_sentences(document, language, amount=True, due_date=False) or "(no amount due)",
            date_sentence=facts_sentences(document, language, amount=False, due_date=True) or "(no due date)",
        )
        text = self._generate([{"type": "text", "text": prompt}], temperature=0.2, schema=ANSWER_SCHEMA)
        try:
            reading = AnswerReading.model_validate_json(text)
        except ValidationError as exc:
            raise LLMError(f"Gemini returned invalid answer JSON: {exc}") from exc
        reading.answer = self._clean(reading.answer, language)
        return reading

    def _clean(self, sentence: str, language: Language) -> str:
        """
        Fix the doubled-vowel-sign glitch. If the sentence has digits (TTS misreads
        them) or is mostly in the wrong script (e.g. Kannada written in English letters),
        ask the model to rewrite it. This is rare, so it rarely costs an extra call.
        "₹1,199"-style amounts are allowed: Timbre reads those correctly.
        """
        sentence = DOUBLED_VOWEL_SIGN.sub(r"\1", sentence).strip()
        without_rupees = RUPEE_AMOUNT.sub("", sentence)
        right = len(SCRIPT_LETTERS[language].findall(sentence))
        wrong = sum(len(p.findall(sentence)) for lang, p in SCRIPT_LETTERS.items() if lang != language)
        wrong_script = wrong > right
        if DIGIT_PATTERN.search(without_rupees) or wrong_script:
            logger.warning("sentence has digits or the wrong script, rewriting: %r", sentence)
            sentence = DOUBLED_VOWEL_SIGN.sub(r"\1", self._rewrite(sentence, language)).strip()
        return sentence

    def _rewrite(self, text: str, language: Language) -> str:
        prompt = REWRITE_PROMPT.format(
            language_name=LANGUAGE_NAMES[language],
            script_name=SCRIPT_NAMES[language],
            script_rule=SCRIPT_RULES[language],
            number_examples=NUMBER_EXAMPLES[language],
            text=text,
        )
        return self._generate([{"type": "text", "text": prompt}], temperature=0.0)

    # --- the actual HTTP call ------------------------------------------------

    def _generate(self, inputs: list[dict], temperature: float, schema: dict | None = None) -> str:
        """Send the request to each model in turn and return the first good text answer."""
        if not self.api_key:
            raise LLMError("GEMINI_API_KEY is not set. Add it to your .env file.")

        errors = []
        for model in self.models:
            body = {
                "model": model,
                "input": inputs,
                "store": False,  # don't keep people's documents on Google's servers
                "generation_config": {"temperature": temperature, "thinking_level": "low"},
            }
            if schema:
                body["response_format"] = {"type": "text", "mime_type": "application/json", "schema": schema}

            start = time.perf_counter()
            response = None
            try:
                response = self.http.post(GEMINI_URL, headers={"x-goog-api-key": self.api_key}, json=body)
            except httpx.HTTPError as exc:  # timeout or network problem
                errors.append(f"{model}: {type(exc).__name__}")
                logger.warning("gemini %s failed (%s), trying next model", model, type(exc).__name__)
                continue
            finally:
                duration_ms = (time.perf_counter() - start) * 1000
                ok = response is not None and response.status_code == 200
                usage.record_call("gemini", duration_ms, ok, model=model)  # to watch the daily quota
                logger.info("gemini %s call took %.0f ms", model, duration_ms)

            if response.status_code == 200:
                try:
                    return _output_text(response.json())
                except LLMError as exc:
                    errors.append(f"{model}: {exc}")
                    continue

            # 429 = quota used up, 503 = overloaded, 400 = model doesn't support a setting, ...
            # Whatever it is, another model may still work.
            errors.append(f"{model}: HTTP {response.status_code} {response.text[:200]}")
            logger.warning("gemini %s returned HTTP %d, trying next model", model, response.status_code)

        raise LLMError("All Gemini models failed. Please try again in a minute. Details: " + " | ".join(errors))


def _output_text(interaction: dict) -> str:
    """
    Pull the answer text out of an Interactions API response. The response has a
    list of "steps". We skip "thought" steps and join the text of "model_output".
    """
    parts = [
        content.get("text", "")
        for step in interaction.get("steps", [])
        if step.get("type") == "model_output"
        for content in step.get("content", [])
        if content.get("type") == "text"
    ]
    text = "".join(parts).strip()
    if not text:
        raise LLMError(f"Gemini returned no text (status={interaction.get('status')!r}).")
    return text


# One shared provider, built from settings. FastAPI routes get it through
# get_llm(), so tests can swap in a fake with app.dependency_overrides.
_provider: LLMProvider | None = None


def get_llm() -> LLMProvider:
    global _provider
    if _provider is None:
        _provider = GeminiProvider(api_key=settings.gemini_api_key, models=settings.gemini_models())
    return _provider

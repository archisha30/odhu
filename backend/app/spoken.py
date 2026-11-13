"""
Builds the sentences that say the amount and the due date out loud.

Why code and not the LLM? In testing, the LLM once turned the amount 2460 into
the words for 2260. Writing these sentences in code guarantees the spoken amount
is exactly the extracted amount.

- Amounts are written like "₹1,179". Gnani Timbre reads that correctly in
  Kannada and Hindi; we checked by speaking it and transcribing it back.
- Dates are written with words from the tables below, because Timbre misread
  Kannada dates written as digits (e.g. "31ರೊಳಗೆ").
"""

import re
from datetime import date

from app.schemas import ExtractedDocument, Language

MONTHS = {
    "kn-IN": ["ಜನವರಿ", "ಫೆಬ್ರವರಿ", "ಮಾರ್ಚ್", "ಏಪ್ರಿಲ್", "ಮೇ", "ಜೂನ್",
              "ಜುಲೈ", "ಆಗಸ್ಟ್", "ಸೆಪ್ಟೆಂಬರ್", "ಅಕ್ಟೋಬರ್", "ನವೆಂಬರ್", "ಡಿಸೆಂಬರ್"],
    "hi-IN": ["जनवरी", "फ़रवरी", "मार्च", "अप्रैल", "मई", "जून",
              "जुलाई", "अगस्त", "सितंबर", "अक्टूबर", "नवंबर", "दिसंबर"],
    "en-IN": ["January", "February", "March", "April", "May", "June",
              "July", "August", "September", "October", "November", "December"],
}

# Day of the month, 1 to 31. Kannada and English use the ordinal form
# ("nineteenth"), which is how dates are spoken; Hindi uses the plain number
# ("उन्नीस नवंबर").
DAYS = {
    "kn-IN": [
        "ಒಂದನೇ", "ಎರಡನೇ", "ಮೂರನೇ", "ನಾಲ್ಕನೇ", "ಐದನೇ", "ಆರನೇ", "ಏಳನೇ", "ಎಂಟನೇ",
        "ಒಂಬತ್ತನೇ", "ಹತ್ತನೇ", "ಹನ್ನೊಂದನೇ", "ಹನ್ನೆರಡನೇ", "ಹದಿಮೂರನೇ", "ಹದಿನಾಲ್ಕನೇ",
        "ಹದಿನೈದನೇ", "ಹದಿನಾರನೇ", "ಹದಿನೇಳನೇ", "ಹದಿನೆಂಟನೇ", "ಹತ್ತೊಂಬತ್ತನೇ", "ಇಪ್ಪತ್ತನೇ",
        "ಇಪ್ಪತ್ತೊಂದನೇ", "ಇಪ್ಪತ್ತೆರಡನೇ", "ಇಪ್ಪತ್ತಮೂರನೇ", "ಇಪ್ಪತ್ತನಾಲ್ಕನೇ", "ಇಪ್ಪತ್ತೈದನೇ",
        "ಇಪ್ಪತ್ತಾರನೇ", "ಇಪ್ಪತ್ತೇಳನೇ", "ಇಪ್ಪತ್ತೆಂಟನೇ", "ಇಪ್ಪತ್ತೊಂಬತ್ತನೇ", "ಮೂವತ್ತನೇ",
        "ಮೂವತ್ತೊಂದನೇ",
    ],
    "hi-IN": [
        "एक", "दो", "तीन", "चार", "पाँच", "छह", "सात", "आठ", "नौ", "दस",
        "ग्यारह", "बारह", "तेरह", "चौदह", "पंद्रह", "सोलह", "सत्रह", "अठारह", "उन्नीस", "बीस",
        "इक्कीस", "बाईस", "तेईस", "चौबीस", "पच्चीस", "छब्बीस", "सत्ताईस", "अट्ठाईस", "उनतीस", "तीस",
        "इकतीस",
    ],
    "en-IN": [
        "first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth", "tenth",
        "eleventh", "twelfth", "thirteenth", "fourteenth", "fifteenth", "sixteenth", "seventeenth",
        "eighteenth", "nineteenth", "twentieth", "twenty-first", "twenty-second", "twenty-third",
        "twenty-fourth", "twenty-fifth", "twenty-sixth", "twenty-seventh", "twenty-eighth",
        "twenty-ninth", "thirtieth", "thirty-first",
    ],
}

AMOUNT_SENTENCE = {
    "kn-IN": "ಪಾವತಿಸಬೇಕಾದ ಮೊತ್ತ {amount}.",
    "hi-IN": "चुकाने की रकम {amount} है।",
    "en-IN": "The amount to pay is {amount}.",
}
DATE_SENTENCE = {
    "kn-IN": "ಕೊನೆಯ ದಿನಾಂಕ {date}.",
    "hi-IN": "आख़िरी तारीख़ {date} है।",
    "en-IN": "The last date is {date}.",
}


def format_rupees(amount: float) -> str:
    """1179.0 -> "₹1,179", 123456.5 -> "₹1,23,456.50" (Indian digit grouping)."""
    rupees = int(amount)
    paise = round((amount - rupees) * 100)
    digits = str(rupees)
    # Indian grouping: the last 3 digits, then groups of 2 (1,23,45,678).
    groups = [digits[-3:]]
    rest = digits[:-3]
    while rest:
        groups.insert(0, rest[-2:])
        rest = rest[:-2]
    text = "₹" + ",".join(groups)
    return f"{text}.{paise:02d}" if paise else text


def spoken_date(day: date, language: Language) -> str:
    """date(2026, 11, 19) -> "ನವೆಂಬರ್ ಹತ್ತೊಂಬತ್ತನೇ ತಾರೀಖು", "उन्नीस नवंबर" or "the nineteenth of November"."""
    month = MONTHS[language][day.month - 1]
    day_words = DAYS[language][day.day - 1]
    if language == "kn-IN":
        return f"{month} {day_words} ತಾರೀಖು"
    if language == "en-IN":
        return f"the {day_words} of {month}"
    return f"{day_words} {month}"


def facts_sentences(
    document: ExtractedDocument, language: Language, amount: bool = True, due_date: bool = True
) -> str:
    """
    The amount and/or due date as short sentences. `amount` and `due_date` choose
    which to include. Facts the document doesn't have are skipped.
    """
    sentences = []
    if amount and document.amount_due is not None:
        sentences.append(AMOUNT_SENTENCE[language].format(amount=format_rupees(document.amount_due)))
    if due_date and document.due_date is not None:
        sentences.append(DATE_SENTENCE[language].format(date=spoken_date(document.due_date, language)))
    return " ".join(sentences)


def end_sentence(text: str, language: Language) -> str:
    """Add a full stop if the LLM forgot one, so sentences don't run into each other."""
    text = text.strip()
    if text and text[-1] not in ".?!।":
        text += "।" if language == "hi-IN" else "."
    return text


def build_answer(document: ExtractedDocument, answer: str, say_amount: bool, say_date: bool, language: Language) -> str:
    """The LLM's answer + the amount and/or date sentences built by code."""
    facts = facts_sentences(document, language, amount=say_amount, due_date=say_date)
    return " ".join(p for p in [end_sentence(answer, language), facts] if p)


def build_explanation(document: ExtractedDocument, intro: str, action: str, language: Language) -> str:
    """intro (from the LLM) + amount and date (from code) + action (from the LLM)."""
    parts = [end_sentence(intro, language), facts_sentences(document, language), end_sentence(action, language)]
    return " ".join(p for p in parts if p)


# A rupee amount written in an answer, like "₹1,199" or "₹ 350.00".
RUPEE_AMOUNT = re.compile(r"₹\s?(\d[\d,]*(?:\.\d+)?)")
# Any number written in the facts, like "1,199.00" or "350".
ANY_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _to_float(text: str) -> float:
    return float(text.replace(",", ""))


def invented_amounts(text: str, document: ExtractedDocument) -> list[str]:
    """
    Return every rupee amount in `text` that does NOT appear in the document's
    facts. An empty list means every amount the LLM mentioned is real.
    """
    known = {_to_float(n) for point in document.key_points for n in ANY_NUMBER.findall(point)}
    if document.amount_due is not None:
        known.add(document.amount_due)
    return [m for m in RUPEE_AMOUNT.findall(text) if _to_float(m) not in known]

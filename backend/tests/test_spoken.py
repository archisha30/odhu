"""Tests for the code-built amount and date sentences."""

from datetime import date

import pytest

from app import spoken
from app.schemas import ExtractedDocument
from app.spoken import DAYS, build_explanation, facts_sentences, format_rupees, spoken_date


@pytest.mark.parametrize(
    ("amount", "text"),
    [
        (0, "₹0"),
        (950, "₹950"),
        (1179.0, "₹1,179"),
        (2460, "₹2,460"),
        (123456.5, "₹1,23,456.50"),  # Indian grouping, with paise
        (12345678, "₹1,23,45,678"),
    ],
)
def test_format_rupees_uses_indian_grouping(amount, text):
    assert format_rupees(amount) == text


def test_spoken_dates():
    assert spoken_date(date(2026, 11, 19), "kn-IN") == "ನವೆಂಬರ್ ಹತ್ತೊಂಬತ್ತನೇ ತಾರೀಖು"
    assert spoken_date(date(2026, 10, 25), "hi-IN") == "पच्चीस अक्टूबर"
    assert spoken_date(date(2026, 12, 31), "kn-IN") == "ಡಿಸೆಂಬರ್ ಮೂವತ್ತೊಂದನೇ ತಾರೀಖು"


def test_every_day_of_the_month_has_a_word():
    for language in ("kn-IN", "hi-IN"):
        assert len(DAYS[language]) == 31
        assert len(set(DAYS[language])) == 31  # no copy-paste duplicates


def doc(**changes) -> ExtractedDocument:
    base = dict(document_type="electricity_bill", amount_due=1179.0, due_date=date(2026, 11, 19), confidence=1)
    return ExtractedDocument(**{**base, **changes})


def test_facts_skip_missing_amount_or_date():
    assert facts_sentences(doc(amount_due=None, due_date=None), "kn-IN") == ""
    assert "₹" not in facts_sentences(doc(amount_due=None), "hi-IN")
    assert "ತಾರೀಖು" not in facts_sentences(doc(due_date=None), "kn-IN")


def test_build_explanation_puts_facts_between_llm_sentences():
    text = build_explanation(doc(), "ಇದು ಬಿಲ್.", "ಬೇಗ ಕಟ್ಟಿ.", "kn-IN")
    assert text == "ಇದು ಬಿಲ್. ಪಾವತಿಸಬೇಕಾದ ಮೊತ್ತ ₹1,179. ಕೊನೆಯ ದಿನಾಂಕ ನವೆಂಬರ್ ಹತ್ತೊಂಬತ್ತನೇ ತಾರೀಖು. ಬೇಗ ಕಟ್ಟಿ."


def test_build_explanation_without_action():
    assert build_explanation(doc(amount_due=None, due_date=None), "ಇದು ಪತ್ರ.", "", "kn-IN") == "ಇದು ಪತ್ರ."


def test_invented_amounts_only_flags_amounts_not_in_the_facts():
    document = doc(key_points=["Amount after due date: ₹1,199.00 (incl. late fee)", "Arrears 350"])

    assert spoken.invented_amounts("ನೀವು ₹1,179 ಕಟ್ಟಬೇಕು.", document) == []  # the amount due
    assert spoken.invented_amounts("ತಡವಾದರೆ ₹1,199 ಆಗುತ್ತದೆ.", document) == []  # from key_points
    assert spoken.invented_amounts("ಬಾಕಿ ₹ 350 ಇದೆ.", document) == []
    assert spoken.invented_amounts("ನೀವು ₹5,000 ಕಟ್ಟಬೇಕು.", document) == ["5,000"]


def test_facts_sentences_can_choose_amount_or_date():
    assert facts_sentences(doc(), "kn-IN", amount=True, due_date=False) == "ಪಾವತಿಸಬೇಕಾದ ಮೊತ್ತ ₹1,179."
    assert facts_sentences(doc(), "hi-IN", amount=False, due_date=True) == "आख़िरी तारीख़ उन्नीस नवंबर है।"


def test_build_answer_adds_missing_full_stop_and_facts():
    assert spoken.build_answer(doc(), "ಬೇಗ ಕಟ್ಟಿ", False, True, "kn-IN") == "ಬೇಗ ಕಟ್ಟಿ. ಕೊನೆಯ ದಿನಾಂಕ ನವೆಂಬರ್ ಹತ್ತೊಂಬತ್ತನೇ ತಾರೀಖು."
    assert spoken.build_answer(doc(), "", True, False, "hi-IN") == "चुकाने की रकम ₹1,179 है।"
    assert spoken.build_answer(doc(), "जल्दी भरिए", False, False, "hi-IN") == "जल्दी भरिए।"


def test_english_sentences():
    assert spoken_date(date(2026, 11, 19), "en-IN") == "the nineteenth of November"
    assert facts_sentences(doc(), "en-IN") == "The amount to pay is ₹1,179. The last date is the nineteenth of November."
    assert len(DAYS["en-IN"]) == 31 and len(set(DAYS["en-IN"])) == 31


def test_every_language_has_every_table_entry():
    from typing import get_args

    from app import messages
    from app.schemas import Language

    for language in get_args(Language):
        for table in (spoken.MONTHS, spoken.DAYS, spoken.AMOUNT_SENTENCE, spoken.DATE_SENTENCE,
                      messages.UNCLEAR_PHOTO, messages.UNSUPPORTED_DOCUMENT, messages.DIDNT_HEAR,
                      messages.NOT_IN_DOCUMENT, messages.CHECK_PAPER):
            assert language in table, (language, table)

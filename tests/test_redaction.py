"""Tests for PII redaction before AI calls."""
from fixtures import STRONG_RESUME
from privacy.redact import ADDRESS_TOKEN, EMAIL_TOKEN, PHONE_TOKEN, redact


def test_redacts_contact_keeps_name_and_skills() -> None:
    out = redact(STRONG_RESUME)
    assert "priya.sharma@example.com" not in out
    assert "98765 43210" not in out
    assert "MG Road" not in out
    assert out.count(EMAIL_TOKEN) == 1 and PHONE_TOKEN in out and ADDRESS_TOKEN in out
    assert out.startswith("Priya Sharma")
    assert "Python, Django, PostgreSQL" in out
    assert "linkedin.com/in/priyasharma" in out


def test_phone_formats() -> None:
    out = redact("Call +1 (555) 123-4567 or 9876543210 or 080-2345-6789")
    assert out == f"Call {PHONE_TOKEN} or {PHONE_TOKEN} or {PHONE_TOKEN}"


def test_dates_and_metrics_survive() -> None:
    text = "EXPERIENCE\n• Jan 2019 - Dec 2021: grew revenue 25% to $1,200,000"
    assert redact(text) == text


def test_labeled_address_anywhere() -> None:
    out = redact("SKILLS\nPython\n\nAddress: 5 Elm St, Springfield, IL 62704")
    assert out.endswith(f"Address: {ADDRESS_TOKEN}")


def test_street_words_in_bullets_are_kept() -> None:
    text = "Built 3 dashboards for the road safety team"
    assert redact(text) == text


def test_header_address_and_postal_code() -> None:
    out = redact("Ravi Kumar\n221B Baker Street, London\nBengaluru 560001\n\nSKILLS\nJava 11")
    assert "Baker" not in out and "560001" not in out
    assert out.endswith("Java 11")

"""Redact contact details before resume text is sent to any AI provider.

Names, skills and LinkedIn/GitHub URLs are kept. Emails, phone numbers and
street addresses are replaced with [EMAIL], [PHONE] and [ADDRESS]. Contact
details are restored only locally, from the original text, when the DOCX is
generated.
"""
import re

from parsers.contact import EMAIL_RE, find_phones
from parsers.sections import detect_heading

EMAIL_TOKEN = "[EMAIL]"
PHONE_TOKEN = "[PHONE]"
ADDRESS_TOKEN = "[ADDRESS]"

_STREET_WORDS_LIST = (
    "street st road rd avenue ave lane ln boulevard blvd drive nagar colony marg layout sector "
    "block apartment apartments apt floor cross highway hwy way place circle enclave society phase"
).split()
# Street words must be capitalized ("MG Road", "Elm ST") so prose such as
# "3 dashboards for the road safety team" is never treated as an address.
_STREET_WORDS = "|".join(w.title() for w in _STREET_WORDS_LIST) + "|" + "|".join(w.upper() for w in _STREET_WORDS_LIST)
# "12 MG Road, Bengaluru", "221B Baker Street", "Flat 4/2, 5th Cross, Indiranagar".
STREET_RE = re.compile(
    rf"(?:\b(?i:flat|house|plot|door|no\.?)\s*)?\b\d{{1,5}}[A-Za-z]?(?:[/-]\d+)?,?\s+"
    rf"(?:[A-Za-z0-9.'-]+,?\s+){{0,4}}(?:{_STREET_WORDS})\b\.?[^\n|•]*"
)
LABELED_ADDRESS_RE = re.compile(r"(?im)^(\s*(?:address|residence|current address)\s*[:\-–]\s*).+$")
POSTAL_CODE_RE = re.compile(r"(?<![\d-])(?:\d{6}|\d{3}\s\d{3}|\d{5}(?:-\d{4})?)(?![\d-])")

HEADER_LINES = 8


def _redact_header_addresses(text: str) -> str:
    """Redact street addresses and postal codes in the resume header only.

    Restricting this to the header (lines before the first section heading,
    at most ``HEADER_LINES``) avoids touching bullets such as
    "Built 3 dashboards for the road safety team".
    """
    lines = text.splitlines(keepends=True)
    seen = 0
    for idx, line in enumerate(lines):
        if detect_heading(line):
            break
        if not line.strip():
            continue
        seen += 1
        if seen > HEADER_LINES:
            break
        new = STREET_RE.sub(ADDRESS_TOKEN, line)
        lines[idx] = POSTAL_CODE_RE.sub(ADDRESS_TOKEN, new)
    return "".join(lines)


def redact(text: str) -> str:
    """Return ``text`` with emails, phone numbers and street addresses replaced by tokens."""
    if not text:
        return text
    redacted = EMAIL_RE.sub(EMAIL_TOKEN, text)
    for phone in sorted(set(find_phones(redacted)), key=len, reverse=True):
        redacted = redacted.replace(phone, PHONE_TOKEN)
    redacted = LABELED_ADDRESS_RE.sub(lambda m: m.group(1) + ADDRESS_TOKEN, redacted)
    return _redact_header_addresses(redacted)

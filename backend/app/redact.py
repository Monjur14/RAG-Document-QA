"""Mask secrets and personal data in text that is about to be shown to the user.

Rules are deliberately conservative (a masked word is better than a leaked key, but masking ordinary words would make the
app useless): a value after "password is ..." is only masked when it looks like a credential (it contains a digit, a dash
or an underscore). Redaction is a layer, not a guarantee: it only knows the shapes below.
"""
import re

_KEY_SHAPES = [
    ("api_key", re.compile(r"\bsk-[A-Za-z0-9_-]{8,}")),
    ("api_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("api_key", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}")),
    ("api_key", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}")),
    ("api_key", re.compile(r"\bAIza[0-9A-Za-z_-]{30,}")),
    ("api_key", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{5,}")),
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?(?:-----END [A-Z ]*PRIVATE KEY-----|$)")),
]
_SECRET_ASSIGN = re.compile(
    r"(?i)\b(password|passcode|passwd|pwd|secret|api[ _-]?key|access[ _-]?key|token|credentials?)\b"
    r"([^.\n:=]{0,40}?(?:\bis\b|\bare\b|[:=])\s*[`'\"]?)([^\s,;`'\"]{4,})")
_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
_PHONES = [
    re.compile(r"(?<![\w.])\+\d{1,3}[\s.-]\(?\d{2,4}\)?[\s.-]\d{3}[\s.-]\d{3,4}(?!\w)"),   # +1 555 010 7788
    re.compile(r"(?<![\w.])\(\d{3}\)\s?\d{3}[\s.-]\d{4}(?!\w)"),                           # (555) 010-7788
    re.compile(r"(?<![\w.-])\d{3}[\s.-]\d{3}[\s.-]\d{4}(?![\w-])"),                        # 555-010-7788
]
_SSN = re.compile(r"(?<![\w-])\d{3}-\d{2}-\d{4}(?![\w-])")
_CARD = re.compile(r"(?<![\w-])(?:\d[ -]?){13,19}(?![\w-])")


def _luhn(digits: str) -> bool:
    total, alt = 0, False
    for ch in reversed(digits):
        d = int(ch)
        if alt:
            d = d * 2 - 9 if d * 2 > 9 else d * 2
        total += d
        alt = not alt
    return total % 10 == 0


def _looks_like_credential(value: str) -> bool:
    return any(c.isdigit() for c in value) or "-" in value or "_" in value


def redact(text: str) -> tuple[str, list[str]]:
    """Returns (masked text, kinds found), e.g. ("... [REDACTED_SECRET]", ["secret"])."""
    kinds: list[str] = []

    def note(kind: str) -> None:
        if kind not in kinds:
            kinds.append(kind)

    def secret(m: re.Match) -> str:
        if not _looks_like_credential(m.group(3)):
            return m.group(0)
        note("secret")
        return f"{m.group(1)}{m.group(2)}[REDACTED_SECRET]"

    text = _SECRET_ASSIGN.sub(secret, text)
    for kind, pat in _KEY_SHAPES:
        text, n = pat.subn("[REDACTED_SECRET]", text)
        if n:
            note("secret")
    text, n = _EMAIL.subn("[REDACTED_EMAIL]", text)
    if n:
        note("email")
    for pat in _PHONES:
        text, n = pat.subn("[REDACTED_PHONE]", text)
        if n:
            note("phone")
    text, n = _SSN.subn("[REDACTED_ID]", text)
    if n:
        note("id_number")

    def card(m: re.Match) -> str:
        digits = re.sub(r"\D", "", m.group(0))
        if 13 <= len(digits) <= 19 and _luhn(digits):
            note("card")
            return "[REDACTED_CARD]"
        return m.group(0)

    text = _CARD.sub(card, text)
    return text, kinds

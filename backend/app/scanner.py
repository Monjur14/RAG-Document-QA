"""Ingestion scanning: find text in an uploaded document that is aimed at the AI rather than at the reader.

Each chunk is cleaned of invisible characters and checked for instruction-like patterns. Chunks that carry an injection
are *quarantined*: stored and visible in the library, but never retrieved, so the LLM never sees them. The cost is that
legitimate text in the same chunk is lost too; the scan result is returned on upload so the user can see it.
"""
import re
from dataclasses import dataclass, field

# Zero-width and bidirectional-control characters: invisible to a reader, readable by a model.
_INVISIBLE = re.compile("[­​-‏‪-‮⁠-⁤⁦-⁩﻿]")
_LEET = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s"})

_I = re.IGNORECASE
_REMOTE = r"https?://(?!(?:localhost|127\.|0\.0\.0\.0|\[::1\]))"   # links to the reader's own machine are normal in docs
_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("instruction_override", re.compile(
        r"\b(ignore|disregard|forget|override|void)\b(?:\W+\w+){0,6}?\W+(instructions?|rules?|guidelines?|prompts?|question|sources|everything above)\b", _I)),
    ("instruction_override", re.compile(r"\b(previous|prior|earlier|above) (instructions?|rules) (are|is) (void|invalid|cancel)|\bnew (rule|instructions?)\b\W{0,3}(\d|follow)", _I)),
    ("instruction_override", re.compile(r"\bignore (any|all|every) other\b|\bstate this with certainty\b", _I)),
    ("instruction_override", re.compile(r"\binstructions? pr[eé]c[eé]dentes?\b|\binstrucciones anteriores\b|\bvorherigen anweisungen\b", _I)),
    ("ai_directive", re.compile(
        r"\bnote to (the )?(ai|assistant|llm|model)\b|\bif you are (an? )?(ai|llm|language model|assistant)\b|"
        r"\b(ai|llm) assistants? (must|should|shall)\b|\bdear (ai|assistant)\b|\bdeveloper mode\b|\byou are now (in|a|an|the)\b", _I)),
    ("role_tag", re.compile(r"</?\s*(source|sources|system|assistant|user)\b[^>]*>|<\|im_(start|end)\|>|\[/?INST\]", _I)),
    ("role_tag", re.compile(r"^\s*(system|assistant)\s*:", _I | re.MULTILINE)),
    ("exfiltration", re.compile(r"!\[[^\]]*\]\(\s*" + _REMOTE, _I)),
    ("exfiltration", re.compile(r"\b(always|must)\b.{0,60}\b(visit|visiting|click|clicking|open|go to)\b.{0,30}" + _REMOTE, _I)),
    ("prompt_leak_request", re.compile(
        r"\b(print|show|reveal|disclose|output|repeat)\b(?:\W+\w+){0,6}?\W+(system prompt|hidden rules|(your|its|their) (instructions|rules|prompt))\b", _I)),
]
QUARANTINE_FLAGS = {"instruction_override", "ai_directive", "role_tag", "exfiltration", "prompt_leak_request"}


@dataclass
class ScanResult:
    clean_text: str
    flags: list[str] = field(default_factory=list)

    @property
    def quarantine(self) -> bool:
        return bool(QUARANTINE_FLAGS & set(self.flags))


def scan_text(text: str) -> ScanResult:
    clean = _INVISIBLE.sub("", text)
    flags: list[str] = []
    if clean != text:
        flags.append("invisible_chars")
    # Look at the text as written and as de-obfuscated ("1gn0re pr3vious" -> "ignore previous").
    for view in (clean, clean.translate(_LEET)):
        for name, pat in _PATTERNS:
            if name not in flags and pat.search(view):
                flags.append(name)
    return ScanResult(clean_text=clean, flags=flags)

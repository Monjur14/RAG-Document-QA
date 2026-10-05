"""Ingestion scanning: find text in an uploaded document that is aimed at the AI rather than at the reader.

Each chunk is cleaned of invisible characters and checked for instruction-like patterns. A paragraph that carries an
injection is cut out of the chunk and the rest of the chunk is kept ("sanitized"). Only when nothing worth keeping is
left is the whole chunk *quarantined*: stored, but never retrieved, so the LLM never sees it. (Quarantining every
affected chunk outright lost 89% of the legitimate answers on poisoned documents in the red-team run.)
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
_MIN_KEPT_CHARS = 25   # fewer word characters than this (headings excluded) left over -> nothing worth keeping


@dataclass
class ScanResult:
    clean_text: str                      # invisible characters removed, and attack paragraphs cut out when text was kept
    flags: list[str] = field(default_factory=list)
    threat: bool = False                 # an injection pattern was found
    removed: int = 0                     # paragraphs cut out
    kept: bool = True                    # False: nothing worth keeping is left, quarantine the whole chunk

    @property
    def quarantine(self) -> bool:
        return self.threat and not self.kept


def _flags_of(text: str) -> list[str]:
    flags: list[str] = []
    # Look at the text as written and as de-obfuscated ("1gn0re pr3vious" -> "ignore previous").
    for view in (text, text.translate(_LEET)):
        for name, pat in _PATTERNS:
            if name not in flags and pat.search(view):
                flags.append(name)
    return flags


def _content_chars(text: str) -> int:
    body = "\n".join(l for l in text.splitlines() if not l.lstrip().startswith("#"))
    return len(re.findall(r"\w", body))


def scan_text(text: str) -> ScanResult:
    clean = _INVISIBLE.sub("", text)
    flags = ["invisible_chars"] if clean != text else []
    found = _flags_of(clean)
    flags += found
    threat = bool(QUARANTINE_FLAGS & set(found))
    if not threat:
        return ScanResult(clean_text=clean, flags=flags)
    paragraphs = re.split(r"\n\s*\n", clean)
    safe = [para for para in paragraphs if not (QUARANTINE_FLAGS & set(_flags_of(para)))]
    kept_text = "\n\n".join(safe).strip()
    if len(safe) == len(paragraphs) or _content_chars(kept_text) < _MIN_KEPT_CHARS:
        # Either the attack is spread across paragraphs, or nothing legitimate remains: quarantine the whole chunk.
        return ScanResult(clean_text=clean, flags=flags, threat=True, kept=False)
    return ScanResult(clean_text=kept_text, flags=flags + ["sanitized"], threat=True,
                      removed=len(paragraphs) - len(safe), kept=True)

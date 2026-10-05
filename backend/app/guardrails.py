"""Input guardrails: reject questions that try to override the rules, extract the system prompt, or smuggle links out.

Pattern-based, so it is fast and predictable but not exhaustive: a determined attacker can rephrase. It is one layer of
several. Every pattern is checked against the legitimate questions in the eval sets (false-positive rate).
"""
import re

BLOCKED_MESSAGE = "I can't help with that request."

_I = re.IGNORECASE
_RULES = [
    ("override", re.compile(r"\b(ignore|disregard|forget|override|bypass)\b(?:\W+\w+){0,6}?\W+(instructions?|rules?|guidelines?|prompts?|sources)\b", _I)),
    ("override", re.compile(r"\b(system|developer|admin)\s+(override|mode|prompt)\b|\bmaintenance mode\b|\bjailbreak\b|\bdo anything now\b|\bnew instructions? follow", _I)),
    ("override", re.compile(r"\bDAN\b")),                                   # case-sensitive: the "do anything now" persona
    ("prompt_extraction", re.compile(r"\b(print|show|reveal|repeat|output|display|translate|disclose|read|recite|dump)\b(?:\W+\w+){0,8}?\W+"
                                     r"(system prompt|(your|the) (initial |hidden |original |secret )?(instructions|rules|prompt)|"
                                     r"rules you were given|full prompt|everything above)\b", _I)),
    ("prompt_extraction", re.compile(r"\bstarting (from|with) the words\b|\bwhat (rules|instructions) were you given\b", _I)),
    ("roleplay_nolimits", re.compile(r"\b(pretend|act as|you are now|from now on)\b.{0,80}\b(no (rules|restrictions|limits)|without (any )?(rules|restrictions)|unrestricted)\b", _I)),
    ("roleplay_nolimits", re.compile(r"\bact as my (late|deceased)\b", _I)),
    ("link_smuggling", re.compile(r"\b(include|add|append|insert|embed|encode|show|put)\b.{0,80}https?://", _I)),
    ("link_smuggling", re.compile(r"!\[[^\]]*\]\(https?://", _I)),
]


def check_question(question: str) -> list[str]:
    """Names of the guardrail rules the question trips (empty list = allowed)."""
    hits: list[str] = []
    for name, pat in _RULES:
        if pat.search(question) and name not in hits:
            hits.append(name)
    return hits

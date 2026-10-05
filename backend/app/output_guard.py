"""Output validation: check a reply before the user sees it.

  * leak: the reply repeats a run of our own system prompt -> the whole reply is blocked
  * exfiltration: a URL or markdown image that does not appear in the retrieved sources is removed (it could carry data to
    an attacker or lure the user to a look-alike site)
Grounding (citations point at real sources) is already enforced in answering.py.
"""
import re

_URL = re.compile(r"https?://[^\s)\]>\"']+", re.I)
_IMAGE = re.compile(r"!\[[^\]]*\]\(\s*https?://[^)]*\)", re.I)
_SHINGLE_WORDS = 6


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", text.lower())


def _shingles(words: list[str], n: int) -> set[tuple[str, ...]]:
    return {tuple(words[i:i + n]) for i in range(len(words) - n + 1)}


def _host(url: str) -> str:
    return re.sub(r"^https?://", "", url, flags=re.I).split("/")[0].split("?")[0].lower()


def leaks_system_prompt(reply: str, system_prompt: str) -> bool:
    """True when the reply contains any run of 6 consecutive words from the system prompt."""
    return bool(_shingles(_words(system_prompt), _SHINGLE_WORDS) & _shingles(_words(reply), _SHINGLE_WORDS))


def strip_foreign_links(reply: str, source_texts: list[str]) -> tuple[str, bool]:
    allowed = {_host(u) for t in source_texts for u in _URL.findall(t)}
    changed = False

    def drop_image(m: re.Match) -> str:
        nonlocal changed
        if _host(_URL.search(m.group(0)).group(0)) in allowed:
            return m.group(0)
        changed = True
        return ""

    def drop_url(m: re.Match) -> str:
        nonlocal changed
        if _host(m.group(0)) in allowed:
            return m.group(0)
        changed = True
        return "[link removed]"

    reply = _IMAGE.sub(drop_image, reply)
    reply = _URL.sub(drop_url, reply)
    return reply.strip(), changed


def guard_output(reply: str, system_prompt: str, source_texts: list[str]) -> tuple[str, list[str], bool]:
    """Returns (safe reply, actions taken, blocked)."""
    if leaks_system_prompt(reply, system_prompt):
        return "", ["blocked_prompt_leak"], True
    safe, changed = strip_foreign_links(reply, source_texts)
    return safe, (["removed_foreign_link"] if changed else []), False

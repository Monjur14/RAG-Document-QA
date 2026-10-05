"""Parse uploads in a separate, restricted process.

Why: PDF and DOCX parsers handle untrusted bytes with large C libraries and zip handling. A malicious or broken file
can hang, eat all memory or crash the parser. In a child process that costs one failed upload, not the API server.

What the child gets: a time limit, and (Linux/macOS) CPU, memory and output-file-size limits; an environment with no
API keys or database URL; no database access. What it does NOT get: a container or syscall filter, and on Windows the
memory limit is not available (only the time limit applies). This is process isolation, not a full sandbox.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

from app import config
from app.models import ParsedSection
from app.parsers import MalformedFile, UnsupportedFormat, parse_file

_BACKEND_DIR = Path(__file__).resolve().parents[1]
_MAX_OUTPUT_BYTES = 100 * 1024 * 1024
_KEEP_ENV = ("PATH", "SYSTEMROOT", "SYSTEMDRIVE", "TEMP", "TMP", "TMPDIR", "LANG", "LC_ALL", "HOME")


def _child_env() -> dict[str, str]:
    env = {k: os.environ[k] for k in _KEEP_ENV if k in os.environ}
    env.update(RAG_SANDBOX_WORKER="1", PYTHONIOENCODING="utf-8", PYTHONPATH=str(_BACKEND_DIR))
    return env


def _limits():
    """Runs in the child just before it starts (POSIX only)."""
    import resource

    mem = config.SANDBOX_MAX_MEMORY_MB * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (mem, mem))
    cpu = int(config.SANDBOX_TIMEOUT_S) + 5
    resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))
    resource.setrlimit(resource.RLIMIT_FSIZE, (10 * 1024 * 1024, 10 * 1024 * 1024))


def parse_sandboxed(filename: str, raw: bytes) -> list[ParsedSection]:
    kwargs = {"preexec_fn": _limits} if os.name == "posix" else {}
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "app.parse_worker", Path(filename).name],
            input=raw, capture_output=True, timeout=config.SANDBOX_TIMEOUT_S,
            cwd=_BACKEND_DIR, env=_child_env(), **kwargs,
        )
    except subprocess.TimeoutExpired as exc:
        raise MalformedFile(f"Parsing took longer than {config.SANDBOX_TIMEOUT_S:g} s and was stopped") from exc
    line = proc.stdout[-_MAX_OUTPUT_BYTES:].strip().splitlines()[-1:] if proc.stdout else []
    try:
        result = json.loads(line[0]) if line else None
    except ValueError:
        result = None
    if result is None:
        raise MalformedFile("The file could not be parsed safely (the parser crashed or exceeded its limits)")
    if result["ok"]:
        return [ParsedSection(**s) for s in result["sections"]]
    if result["error"] == "unsupported":
        raise UnsupportedFormat(result["message"])
    if result["error"] == "malformed":
        raise MalformedFile(result["message"])
    raise MalformedFile("The file could not be parsed: " + result["message"])


def parse_upload(filename: str, raw: bytes) -> list[ParsedSection]:
    """What ingestion calls: sandboxed unless SANDBOX_PARSING is switched off (for debugging)."""
    return parse_sandboxed(filename, raw) if config.SANDBOX_PARSING else parse_file(filename, raw)

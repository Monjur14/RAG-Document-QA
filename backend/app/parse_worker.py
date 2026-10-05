"""Child process that parses ONE uploaded file. Run only through app/sandbox.py:

    python -m app.parse_worker <filename>     (file bytes on stdin, one JSON line on stdout)

It never talks to the database, never reads the API keys (the parent passes a minimal environment, and config skips the
.env file when RAG_SANDBOX_WORKER is set), and the parent limits its time and memory.
"""
import json
import sys


def main() -> int:
    filename = sys.argv[1]
    raw = sys.stdin.buffer.read()
    real_stdout, sys.stdout = sys.stdout, sys.stderr   # libraries that print must not corrupt our JSON line
    from app.parsers import MalformedFile, UnsupportedFormat, parse_file

    try:
        sections = parse_file(filename, raw)
        out = {"ok": True, "sections": [s.model_dump() for s in sections]}
    except UnsupportedFormat as exc:
        out = {"ok": False, "error": "unsupported", "message": str(exc)}
    except MalformedFile as exc:
        out = {"ok": False, "error": "malformed", "message": str(exc)}
    except Exception as exc:  # noqa: BLE001 - any parser bug is reported, not raised
        out = {"ok": False, "error": "failed", "message": f"{type(exc).__name__}: {exc}"[:300]}
    real_stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
    real_stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Download the public evaluation corpus from the original sources.

    python -m evals.fetch_corpus

Files go to evals/data/corpus/ (git-ignored): the repo never redistributes other people's documents.
Each source's licence is recorded here and in corpus/MANIFEST.json, with a SHA-256 so the eval can
detect when an upstream document changes and the labelled questions need re-checking.
"""
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

CORPUS_DIR = Path(__file__).parent / "data" / "corpus"
FASTAPI = "https://raw.githubusercontent.com/fastapi/fastapi/master/docs/en/docs/tutorial/"

SOURCES = [
    {"file": "nist-ai-rmf.pdf", "url": "https://nvlpubs.nist.gov/nistpubs/ai/nist.ai.100-1.pdf",
     "license": "US government work (public domain)", "title": "NIST AI Risk Management Framework 1.0 (AI 100-1)"},
    {"file": "nist-csf-2.pdf", "url": "https://nvlpubs.nist.gov/nistpubs/CSWP/NIST.CSWP.29.pdf",
     "license": "US government work (public domain)", "title": "NIST Cybersecurity Framework 2.0 (CSWP 29)"},
] + [
    {"file": f"fastapi-{name.replace('/', '-')}.md", "url": f"{FASTAPI}{name}.md",
     "license": "MIT (c) Sebastian Ramirez", "title": f"FastAPI tutorial: {name}"}
    for name in ["first-steps", "path-params", "query-params", "body", "dependencies/index",
                 "security/first-steps", "background-tasks"]
]


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "rag-eval-corpus-fetcher"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def main() -> int:
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    manifest, failed = [], 0
    for src in SOURCES:
        try:
            data = fetch(src["url"])
        except Exception as exc:  # report and continue so one dead link doesn't hide the rest
            print(f"FAILED {src['file']}: {exc}")
            failed += 1
            continue
        (CORPUS_DIR / src["file"]).write_bytes(data)
        manifest.append({**src, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)})
        print(f"ok  {src['file']:40} {len(data):>9} bytes")
    (CORPUS_DIR / "MANIFEST.json").write_text(json.dumps(manifest, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

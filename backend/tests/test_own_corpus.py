import json

from app.chunking import chunk_sections
from app.parsers import parse_file
from evals import make_own_corpus
from evals.corpus_eval import DATA, norm, targets_of


def _chunks():
    out = {}
    for name, raw in [("harbor-handbook.docx", make_own_corpus.build_docx()),
                      ("harbor-faq.html", make_own_corpus.HTML.encode("utf-8"))]:
        out[name] = [norm(c.text) for c in chunk_sections(parse_file(name, raw))]
    return out


def test_every_label_for_the_own_documents_is_found_inside_one_chunk():
    chunks = _chunks()
    questions = json.loads((DATA / "corpus_questions_3.json").read_text(encoding="utf-8"))
    assert len(questions) == 20
    for q in questions:
        for t in targets_of(q):
            assert any(norm(t["quote"]) in c for c in chunks[t["source"]]), q["id"]


def test_hidden_html_text_never_reaches_a_chunk_and_boilerplate_is_gone():
    text = " ".join(_chunks()["harbor-faq.html"])
    assert "lifetime free storage" not in text
    assert "All rights reserved" not in text and "Pricing" not in text


def test_word_tables_keep_their_rows():
    text = "\n".join(_chunks()["harbor-handbook.docx"])
    assert "Starter | 500 GB | 30 days | 8 USD per month" in text
    assert "E101 | Network unreachable" in text


def test_unanswerable_decoy_question_exists():
    u = json.loads((DATA / "corpus_unanswerable.json").read_text(encoding="utf-8"))
    assert any(q["id"] == "u21" for q in u)

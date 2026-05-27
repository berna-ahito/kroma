"""Deterministic smoke evals for Kroma source-card trust behavior.

Run from the repo root:
    .\\venv\\Scripts\\python.exe evals\\trust_behavior.py
"""

from pathlib import Path
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import api as kroma_api  # noqa: E402
from rag import (  # noqa: E402
    build_source_catalog,
    build_source_linked_context,
    sanitize_flashcards_source_ids,
    sanitize_quiz_source_ids,
    sanitize_summary_source_ids,
    should_show_sources,
)


SOURCE = {
    "rank": 1,
    "source": "sample.pdf",
    "page": 2,
    "chunk_id": "sample-2-1",
    "doc_chunk_id": "sample.pdf:2:1",
    "score": 91,
    "distance": 0.1,
    "preview": "Kroma is a local document-RAG assistant.",
}


CASES = [
    {
        "name": "greeting hides sources",
        "question": "hello",
        "answer": "Hi, ask me a question about your documents.",
        "context": "[Source: sample.pdf, page 2]\nKroma is a local document-RAG assistant.",
        "sources": [SOURCE],
        "expected": False,
    },
    {
        "name": "unanswerable answer hides sources",
        "question": "What is the author's favorite color?",
        "answer": "That information is not mentioned in the provided documents.",
        "context": "[Source: sample.pdf, page 2]\nKroma is a local document-RAG assistant.",
        "sources": [SOURCE],
        "expected": False,
    },
    {
        "name": "not-mentioned answer hides sources",
        "question": "What is Bernadeth's GPA?",
        "answer": "Bernadeth's GPA is not mentioned.",
        "context": "[Source: sample.pdf, page 2]\nBernadeth studied computer science.",
        "sources": [SOURCE],
        "expected": False,
    },
    {
        "name": "grounded document answer shows sources",
        "question": "What is Kroma?",
        "answer": "Kroma is a local document-RAG assistant.",
        "context": "[Source: sample.pdf, page 2]\nKroma is a local document-RAG assistant.",
        "sources": [SOURCE],
        "expected": True,
    },
    {
        "name": "no context hides sources",
        "question": "What is Kroma?",
        "answer": "No relevant information found in the documents.",
        "context": "",
        "sources": [],
        "expected": False,
    },
]


FLASHCARD_SOURCES = [
    SOURCE,
    {
        "rank": 2,
        "source": "other.pdf",
        "page": 5,
        "chunk_id": "other-5-1",
        "doc_chunk_id": "other.pdf:5:1",
        "score": 82,
        "distance": 0.22,
        "preview": "Second source preview.",
    },
]


FLASHCARD_CARDS = [
    {
        "question": "What is Kroma?",
        "answer": "A local document-RAG assistant.",
        "source_ids": ["s1", "fake.pdf", "s999", "s1", "s2"],
        "source": "model-fake.pdf",
        "page": 999,
        "preview": "model-generated preview",
    },
    {
        "question": "What is unsupported?",
        "answer": "This card has no valid source.",
        "source_ids": ["s404"],
    },
]


QUIZ_QUESTIONS = [
    {
        "question": "What is Kroma?",
        "choices": ["A. A database", "B. A local document-RAG assistant", "C. A browser", "D. A PDF"],
        "answer": "B",
        "explanation": "Kroma is described as a local document-RAG assistant.",
        "source_ids": ["s1", "sample.pdf", "s999", "s1", "s2"],
        "source": "model-fake.pdf",
        "page": 999,
        "preview": "model-generated preview",
    },
    {
        "question": "What has no valid source?",
        "choices": ["A. This item", "B. Other", "C. More", "D. None"],
        "answer": "A",
        "explanation": "This question has no valid source ID.",
        "source_ids": ["s404"],
    },
]


SUMMARY_SECTIONS = [
    {
        "heading": "Overview",
        "text": "Kroma summarizes local documents.",
        "source_ids": ["s1", "sample.pdf", "s999", "s1"],
        "source": "model-fake.pdf",
        "page": 999,
        "preview": "model-generated preview",
        "bullets": [],
    },
    {
        "heading": "Key Topics",
        "text": "",
        "source_ids": ["s404"],
        "bullets": [
            {
                "text": "Local RAG",
                "source_ids": ["s2", "other.pdf", "s404", "s2"],
                "source": "model-fake.pdf",
            },
            {
                "text": "Unsupported topic",
                "source_ids": ["s404"],
            },
        ],
    },
]


def _expect_http_error(name: str, status_code: int, func, failures: list) -> None:
    try:
        func()
    except Exception as exc:
        if getattr(exc, "status_code", None) == status_code:
            print(f"PASS: {name}")
            return
        failures.append((name, status_code, getattr(exc, "status_code", exc)))
        print(f"FAIL: {name}")
        return
    failures.append((name, status_code, "no error"))
    print(f"FAIL: {name}")


def run_delete_filename_evals(failures: list) -> None:
    original_docs_folder = kroma_api.DOCS_FOLDER
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_docs = Path(temp_dir) / "docs"
        temp_docs.mkdir()
        kroma_api.DOCS_FOLDER = temp_docs
        try:
            target = kroma_api._delete_doc_target("valid.pdf")
            if target != (temp_docs / "valid.pdf").resolve():
                failures.append(("delete target stays inside docs", temp_docs / "valid.pdf", target))
                print("FAIL: delete target stays inside docs")
            else:
                print("PASS: delete target stays inside docs")

            invalid_cases = [
                ("delete rejects forward slash traversal", "../secret.pdf", 400),
                ("delete rejects backslash traversal", r"..\secret.pdf", 400),
                ("delete rejects absolute Windows path", r"C:\secret.pdf", 400),
                ("delete rejects null byte", "bad\x00.pdf", 400),
                ("delete rejects control character", "bad\n.pdf", 400),
                ("delete rejects DEL control character", "bad\x7f.pdf", 400),
                ("delete rejects non-pdf", "notes.txt", 415),
            ]
            for name, filename, status_code in invalid_cases:
                _expect_http_error(
                    name,
                    status_code,
                    lambda filename=filename: kroma_api._delete_doc_target(filename),
                    failures,
                )

            _expect_http_error(
                "delete returns 404 for missing validated PDF",
                404,
                lambda: kroma_api.delete_doc("missing.pdf"),
                failures,
            )

            kept_outside = Path(temp_dir) / "secret.pdf"
            kept_outside.write_text("keep", encoding="utf-8")
            _expect_http_error(
                "delete does not remove outside docs",
                400,
                lambda: kroma_api._delete_doc_target("../secret.pdf"),
                failures,
            )
            if not kept_outside.exists():
                failures.append(("delete does not remove outside docs", "outside file exists", "deleted"))
                print("FAIL: delete does not remove outside docs")
        finally:
            kroma_api.DOCS_FOLDER = original_docs_folder


def main() -> int:
    failures = []
    for case in CASES:
        actual = should_show_sources(
            case["question"],
            case["answer"],
            case["context"],
            case["sources"],
        )
        status = "PASS" if actual == case["expected"] else "FAIL"
        print(f"{status}: {case['name']} -> show_sources={actual}")
        if actual != case["expected"]:
            failures.append((case["name"], case["expected"], actual))

    catalog = build_source_catalog(FLASHCARD_SOURCES)
    sanitized = sanitize_flashcards_source_ids(FLASHCARD_CARDS, catalog)
    if sanitized[0] != {
        "question": "What is Kroma?",
        "answer": "A local document-RAG assistant.",
        "source_ids": ["s1", "s2"],
    }:
        failures.append(("flashcard invalid source_ids stripped", ["s1", "s2"], sanitized[0]))
        print("FAIL: flashcard invalid source_ids stripped")
    else:
        print("PASS: flashcard invalid source_ids stripped")

    if sanitized[1]["source_ids"] != []:
        failures.append(("flashcard with no valid source stays unsourced", [], sanitized[1]["source_ids"]))
        print("FAIL: flashcard with no valid source stays unsourced")
    else:
        print("PASS: flashcard with no valid source stays unsourced")

    sanitized_quiz = sanitize_quiz_source_ids(QUIZ_QUESTIONS, catalog)
    if sanitized_quiz[0] != {
        "question": "What is Kroma?",
        "choices": ["A. A database", "B. A local document-RAG assistant", "C. A browser", "D. A PDF"],
        "answer": "B",
        "explanation": "Kroma is described as a local document-RAG assistant.",
        "source_ids": ["s1", "s2"],
    }:
        failures.append(("quiz invalid source_ids stripped", ["s1", "s2"], sanitized_quiz[0]))
        print("FAIL: quiz invalid source_ids stripped")
    else:
        print("PASS: quiz invalid source_ids stripped")

    if sanitized_quiz[1]["source_ids"] != []:
        failures.append(("quiz with no valid source stays unsourced", [], sanitized_quiz[1]["source_ids"]))
        print("FAIL: quiz with no valid source stays unsourced")
    else:
        print("PASS: quiz with no valid source stays unsourced")

    sanitized_summary = sanitize_summary_source_ids(SUMMARY_SECTIONS, catalog)
    if sanitized_summary[0] != {
        "heading": "Overview",
        "text": "Kroma summarizes local documents.",
        "source_ids": ["s1"],
        "bullets": [],
    }:
        failures.append(("summary invalid section source_ids stripped", ["s1"], sanitized_summary[0]))
        print("FAIL: summary invalid section source_ids stripped")
    else:
        print("PASS: summary invalid section source_ids stripped")

    expected_bullets = [
        {"text": "Local RAG", "source_ids": ["s2"]},
        {"text": "Unsupported topic", "source_ids": []},
    ]
    if sanitized_summary[1]["source_ids"] != [] or sanitized_summary[1]["bullets"] != expected_bullets:
        failures.append(("summary invalid bullet source_ids stripped", expected_bullets, sanitized_summary[1]))
        print("FAIL: summary invalid bullet source_ids stripped")
    else:
        print("PASS: summary invalid bullet source_ids stripped")

    linked_context = build_source_linked_context(
        "[Source: sample.pdf, page 2]\nKroma is local.\n\n[Source: other.pdf, page 5]\nOther text.",
        catalog,
    )
    if "sample.pdf" in linked_context or "page 2" in linked_context or "[Source ID: s1]" not in linked_context:
        failures.append(("flashcard context exposes only source IDs", "source IDs only", linked_context))
        print("FAIL: flashcard context exposes only source IDs")
    else:
        print("PASS: flashcard context exposes only source IDs")

    run_delete_filename_evals(failures)

    if failures:
        print("\nFailures:")
        for name, expected, actual in failures:
            print(f"- {name}: expected {expected}, got {actual}")
        return 1

    print(f"\n{len(CASES)}/{len(CASES)} trust behavior evals passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

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
    normalize_summary_sections,
    sanitize_flashcards_source_ids,
    sanitize_quiz_source_ids,
    sanitize_summary_source_ids,
    should_show_sources,
)


SOURCE = {
    "rank": 1,
    "source": "sample.pdf",
    "page": 2,
    "file_type": "pdf",
    "location_type": "page",
    "location_label": "Page 2",
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
        "file_type": "pdf",
        "location_type": "page",
        "location_label": "Page 5",
        "chunk_id": "other-5-1",
        "doc_chunk_id": "other.pdf:5:1",
        "score": 82,
        "distance": 0.22,
        "preview": "Second source preview.",
    },
    {
        "rank": 3,
        "source": "notes.txt",
        "page": None,
        "file_type": "txt",
        "location_type": "document",
        "location_label": "Text",
        "chunk_id": 3,
        "doc_chunk_id": 1,
        "score": 80,
        "distance": 0.25,
        "preview": "Text source preview.",
    },
    {
        "rank": 4,
        "source": "guide.md",
        "page": None,
        "file_type": "markdown",
        "location_type": "document",
        "location_label": "Markdown",
        "chunk_id": 4,
        "doc_chunk_id": 1,
        "score": 79,
        "distance": 0.27,
        "preview": "Markdown source preview.",
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


SUMMARY_JSON_OBJECT = {
    "sections": [
        {
            "heading": "Overview",
            "text": "Kroma summarizes local documents.",
            "source_ids": ["s1"],
            "bullets": [],
        }
    ]
}

SUMMARY_JSON_ARRAY = [
    {
        "heading": "Overview",
        "text": "Kroma summarizes local documents.",
        "source_ids": ["s1"],
        "bullets": [],
    }
]

SUMMARY_JSON_STRING = (
    '{"sections":[{"heading":"Overview","text":"Kroma summarizes local documents.",'
    '"source_ids":["s1"],"bullets":[]}]}'
)

SUMMARY_FENCED_JSON = """```json
{"sections":[{"heading":"Overview","text":"Kroma summarizes local documents.","source_ids":["s1"],"bullets":[]}]}
```"""

SUMMARY_JSON_WRAPPED = {
    "summary": {
        "sections": [
            {
                "heading": "Overview",
                "text": "Kroma summarizes local documents.",
                "source_ids": ["s1"],
                "bullets": [],
            }
        ]
    }
}

SUMMARY_TEXT_BEFORE_AFTER = (
    "Here is a summary of your documents:\n"
    '[{"heading":"Overview","text":"Kroma summarizes local documents.",'
    '"source_ids":["s1"],"bullets":[]}]\n'
    "Let me know if you need more detail."
)

SUMMARY_JSON_ARRAY_WITH_BULLETS = [
    {
        "heading": "Overview",
        "text": "Kroma is a local RAG assistant.",
        "source_ids": ["s1"],
        "bullets": [
            {"text": "Processes documents locally", "source_ids": ["s1"]},
            {"text": "Uses ChromaDB for storage", "source_ids": ["s2"]},
        ],
    },
    {
        "heading": "Key Topics",
        "text": "",
        "source_ids": [],
        "bullets": [
            {"text": "Document chunking", "source_ids": ["s2"]},
        ],
    },
]


FALLBACK_SOURCE_TEXT = (
    "[Source ID: s1]\nKroma is a local document-RAG assistant. "
    "It processes PDFs, text files, and markdown.\n\n"
    "[Source ID: s2]\nThe system uses ChromaDB for vector storage. "
    "Embeddings are generated via SentenceTransformers."
)


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

            for filename in ("notes.txt", "guide.md", "guide.markdown"):
                target = kroma_api._delete_doc_target(filename)
                if target != (temp_docs / filename).resolve():
                    failures.append((f"delete supports {filename}", temp_docs / filename, target))
                    print(f"FAIL: delete supports {filename}")
                else:
                    print(f"PASS: delete supports {filename}")

            invalid_cases = [
                ("delete rejects forward slash traversal", "../secret.pdf", 400),
                ("delete rejects backslash traversal", r"..\secret.pdf", 400),
                ("delete rejects absolute Windows path", r"C:\secret.pdf", 400),
                ("delete rejects null byte", "bad\x00.pdf", 400),
                ("delete rejects control character", "bad\n.pdf", 400),
                ("delete rejects DEL control character", "bad\x7f.pdf", 400),
                ("delete rejects doc", "notes.doc", 415),
                ("delete rejects html", "notes.html", 415),
                ("delete rejects rtf", "notes.rtf", 415),
            ]
            for name, filename, status_code in invalid_cases:
                _expect_http_error(
                    name,
                    status_code,
                    lambda filename=filename: kroma_api._delete_doc_target(filename),
                    failures,
                )

            _expect_http_error(
                "delete returns 404 for missing validated document",
                404,
                lambda: kroma_api.delete_doc("missing.pdf"),
                failures,
            )

            for filename in ("delete-me.txt", "delete-me.md"):
                target = temp_docs / filename
                target.write_text("temporary", encoding="utf-8")
                result = kroma_api.delete_doc(filename)
                if target.exists() or result != {"deleted": filename}:
                    failures.append((f"delete removes {filename}", "deleted", result))
                    print(f"FAIL: delete removes {filename}")
                else:
                    print(f"PASS: delete removes {filename}")

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


def run_upload_validation_evals(failures: list) -> None:
    original_docs_folder = kroma_api.DOCS_FOLDER
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_docs = Path(temp_dir) / "docs"
        temp_docs.mkdir()
        kroma_api.DOCS_FOLDER = temp_docs
        try:
            for filename in ("notes.txt", "guide.md", "guide.markdown", "paper.pdf"):
                safe_name = kroma_api._safe_upload_filename(filename)
                if safe_name != filename:
                    failures.append((f"upload accepts {filename}", filename, safe_name))
                    print(f"FAIL: upload accepts {filename}")
                else:
                    print(f"PASS: upload accepts {filename}")

            (temp_docs / "notes.txt").write_text("existing", encoding="utf-8")
            deduped_name = kroma_api._safe_upload_filename("notes.txt")
            if deduped_name == "notes.txt" or not deduped_name.startswith("notes-") or not deduped_name.endswith(".txt"):
                failures.append(("upload de-dupes txt filename", "notes-*.txt", deduped_name))
                print("FAIL: upload de-dupes txt filename")
            else:
                print("PASS: upload de-dupes txt filename")

            reserved_name = kroma_api._safe_upload_filename("CON.md")
            if not reserved_name.startswith("upload-") or not reserved_name.endswith(".md"):
                failures.append(("upload rejects reserved markdown stem", "upload-*.md", reserved_name))
                print("FAIL: upload rejects reserved markdown stem")
            else:
                print("PASS: upload rejects reserved markdown stem")

            for filename in ("notes.doc", "page.html", "rich.rtf"):
                _expect_http_error(
                    f"upload rejects {filename}",
                    415,
                    lambda filename=filename: kroma_api._safe_upload_filename(filename),
                    failures,
                )

            for name, filename in [
                ("upload rejects forward slash traversal", "../notes.txt"),
                ("upload rejects backslash traversal", r"..\notes.md"),
                ("upload rejects control character", "bad\n.markdown"),
            ]:
                _expect_http_error(
                    name,
                    400,
                    lambda filename=filename: kroma_api._safe_upload_filename(filename),
                    failures,
                )

            for name, payload, status_code in [
                ("text rejects empty content", b" \n\t", 400),
                ("text rejects non-utf8 content", b"\xff\xfeh\x00i\x00", 415),
                ("text rejects control-heavy content", b"hello\x01" * 20, 415),
            ]:
                _expect_http_error(
                    name,
                    status_code,
                    lambda payload=payload: kroma_api._validate_text_upload(payload),
                    failures,
                )

            try:
                kroma_api._validate_text_upload(b"\xef\xbb\xbfValid UTF-8 text.")
                print("PASS: text accepts UTF-8-SIG content")
            except Exception as exc:
                failures.append(("text accepts UTF-8-SIG content", "no error", getattr(exc, "status_code", exc)))
                print("FAIL: text accepts UTF-8-SIG content")
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
    if catalog[0].get("location_label") != "Page 2":
        failures.append(("source catalog keeps location_label", "Page 2", catalog[0]))
        print("FAIL: source catalog keeps location_label")
    else:
        print("PASS: source catalog keeps location_label")

    if catalog[2].get("location_label") != "Text" or catalog[2].get("page") is not None:
        failures.append(("source catalog keeps text location_label", "Text with no page", catalog[2]))
        print("FAIL: source catalog keeps text location_label")
    else:
        print("PASS: source catalog keeps text location_label")

    if catalog[3].get("location_label") != "Markdown" or catalog[3].get("page") is not None:
        failures.append(("source catalog keeps markdown location_label", "Markdown with no page", catalog[3]))
        print("FAIL: source catalog keeps markdown location_label")
    else:
        print("PASS: source catalog keeps markdown location_label")

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

    expected_summary = SUMMARY_JSON_ARRAY
    summary_cases = [
        ("summary JSON object wrapper parsed", SUMMARY_JSON_OBJECT, expected_summary),
        ("summary JSON array parsed", SUMMARY_JSON_ARRAY, expected_summary),
        ("summary JSON string parsed", SUMMARY_JSON_STRING, expected_summary),
        ("summary fenced JSON parsed", SUMMARY_FENCED_JSON, expected_summary),
        ("summary wrapped in summary key parsed", SUMMARY_JSON_WRAPPED, expected_summary),
        ("summary text before/after JSON parsed", SUMMARY_TEXT_BEFORE_AFTER, expected_summary),
    ]
    for name, payload, expected in summary_cases:
        parsed_summary = normalize_summary_sections(payload)
        if parsed_summary != expected:
            failures.append((name, expected, parsed_summary))
            print(f"FAIL: {name}")
        else:
            print(f"PASS: {name}")

    bullets_in = SUMMARY_JSON_ARRAY_WITH_BULLETS
    bullets_out = normalize_summary_sections(bullets_in)
    if bullets_out != bullets_in:
        failures.append(("summary JSON array with bullets parsed", bullets_in, bullets_out))
        print("FAIL: summary JSON array with bullets parsed")
    else:
        print("PASS: summary JSON array with bullets parsed")

    fallback_result = normalize_summary_sections("not valid json at all", FALLBACK_SOURCE_TEXT)
    fallback_has_text = (
        isinstance(fallback_result, list)
        and len(fallback_result) == 1
        and "Kroma" in fallback_result[0].get("text", "")
    )
    if not fallback_has_text:
        failures.append(("summary fallback uses source snippets", "text contains Kroma", fallback_result))
        print("FAIL: summary fallback uses source snippets")
    else:
        print("PASS: summary fallback uses source snippets")

    empty_fallback = normalize_summary_sections("")
    empty_has_fallback = (
        isinstance(empty_fallback, list)
        and len(empty_fallback) == 1
        and "could not be parsed" in empty_fallback[0].get("text", "")
    )
    if not empty_has_fallback:
        failures.append(("summary empty fallback shows guidance", "could not be parsed", empty_fallback))
        print("FAIL: summary empty fallback shows guidance")
    else:
        print("PASS: summary empty fallback shows guidance")

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
    run_upload_validation_evals(failures)

    if failures:
        print("\nFailures:")
        for name, expected, actual in failures:
            print(f"- {name}: expected {expected}, got {actual}")
        return 1

    print(f"\n{len(CASES)}/{len(CASES)} trust behavior evals passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

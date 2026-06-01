"""Deterministic smoke evals for Kroma source-card trust behavior.

Run from the repo root:
    .\\venv\\Scripts\\python.exe evals\\trust_behavior.py
"""

import json
import gc
import io
import os
from pathlib import Path
import sys
import tempfile

import chromadb
from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import api as kroma_api  # noqa: E402
import ingest as kroma_ingest  # noqa: E402
import rag as kroma_rag  # noqa: E402
from rag import (  # noqa: E402
    build_source_catalog,
    build_source_linked_context,
    business_context_is_relevant,
    business_needs_human_review,
    normalize_business_copilot_output,
    normalize_summary_sections,
    retrieve_chunks,
    sanitize_business_copilot_source_ids,
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


JSON_PARSER_CASES = [
    ("valid raw JSON array", '["a", "b", "c"]', ["a", "b", "c"]),
    ("fenced JSON array", '```json\n["a", "b"]\n```', ["a", "b"]),
    ("text before/after array", 'Result:\n[42, 43]\nDone.', [42, 43]),
    ("malformed returns []", "not json at all", []),
]

SOURCE_IDS_CATALOG = [
    {"id": "s1", "source": "doc1.pdf"},
    {"id": "s2", "source": "doc2.pdf"},
    {"id": "s3", "source": "doc3.pdf"},
]


FALLBACK_SOURCE_TEXT = (
    "[Source ID: s1]\nKroma is a local document-RAG assistant. "
    "It processes PDFs, text files, and markdown.\n\n"
    "[Source ID: s2]\nThe system uses ChromaDB for vector storage. "
    "Embeddings are generated via SentenceTransformers."
)

JOBDESCRIPTION_CONTEXT = (
    "[Source: jobdescription_18.txt]\n"
    "Job Description: We need an AI engineer for a remote contract role. "
    "Required skills include Python, FastAPI, LangChain, vector databases, and RAG evaluation. "
    "Bonus qualifications include React experience and familiarity with Groq or OpenAI APIs. "
    "Proposal questions: Describe your RAG experience and explain how you evaluate answer quality. "
    "The role is hourly for a 3-month duration. Candidates without Python or RAG experience are not a fit."
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


def _clear_rate_limit_buckets() -> None:
    with kroma_api._groq_rate_limit_lock:
        kroma_api._groq_rate_limit_buckets.clear()


def run_api_docs_evals(failures: list) -> None:
    original_app_env = os.environ.get("APP_ENV")
    original_env = os.environ.get("ENV")
    try:
        os.environ["APP_ENV"] = "production"
        os.environ.pop("ENV", None)
        production_client = TestClient(FastAPI(**kroma_api._fastapi_docs_config()), raise_server_exceptions=False)
        production_statuses = {
            "/docs": production_client.get("/docs").status_code,
            "/redoc": production_client.get("/redoc").status_code,
            "/openapi.json": production_client.get("/openapi.json").status_code,
        }
        if production_statuses != {"/docs": 404, "/redoc": 404, "/openapi.json": 404}:
            failures.append(("production docs disabled", "all 404", production_statuses))
            print("FAIL: production docs disabled")
        else:
            print("PASS: production docs disabled")

        os.environ.pop("APP_ENV", None)
        os.environ.pop("ENV", None)
        local_client = TestClient(FastAPI(**kroma_api._fastapi_docs_config()), raise_server_exceptions=False)
        local_statuses = {
            "/docs": local_client.get("/docs").status_code,
            "/redoc": local_client.get("/redoc").status_code,
            "/openapi.json": local_client.get("/openapi.json").status_code,
        }
        if local_statuses != {"/docs": 200, "/redoc": 200, "/openapi.json": 200}:
            failures.append(("non-production docs enabled", "all 200", local_statuses))
            print("FAIL: non-production docs enabled")
        else:
            print("PASS: non-production docs enabled")
    finally:
        if original_app_env is None:
            os.environ.pop("APP_ENV", None)
        else:
            os.environ["APP_ENV"] = original_app_env
        if original_env is None:
            os.environ.pop("ENV", None)
        else:
            os.environ["ENV"] = original_env


def run_groq_rate_limit_evals(failures: list) -> None:
    original_retrieve = kroma_api.retrieve_chunks
    original_generate = kroma_api.generate_answer
    original_key = os.environ.get("KROMA_DEMO_KEY")
    original_limit = os.environ.get("KROMA_RATE_LIMIT_REQUESTS")
    original_window = os.environ.get("KROMA_RATE_LIMIT_WINDOW_SECONDS")
    client = TestClient(kroma_api.app, raise_server_exceptions=False)
    try:
        os.environ["KROMA_DEMO_KEY"] = "rate-secret"
        os.environ["KROMA_RATE_LIMIT_REQUESTS"] = "1"
        os.environ["KROMA_RATE_LIMIT_WINDOW_SECONDS"] = "600"
        _clear_rate_limit_buckets()

        kroma_api.retrieve_chunks = lambda *args, **kwargs: (
            "[Source: sample.pdf, page 2]\nKroma is a local document-RAG assistant.",
            [SOURCE],
        )
        kroma_api.generate_answer = lambda *args, **kwargs: "Kroma is a local document-RAG assistant."
        first = client.post("/api/chat", headers={"X-Kroma-Demo-Key": "rate-secret"}, json={"question": "What is Kroma?"})

        def fail_retrieve(*args, **kwargs):
            raise AssertionError("Rate-limited request should stop before retrieval.")

        kroma_api.retrieve_chunks = fail_retrieve
        limited = client.post("/api/chat", headers={"X-Kroma-Demo-Key": "rate-secret"}, json={"question": "What is Kroma?"})
        retry_after = limited.headers.get("Retry-After")
        rate_limited_ok = (
            first.status_code == 200
            and limited.status_code == 429
            and limited.json().get("detail") == kroma_api.GROQ_RATE_LIMIT_DETAIL
            and retry_after is not None
            and int(retry_after) > 0
        )
        if not rate_limited_ok:
            failures.append(("valid demo key is rate-limited before retrieval", "200 then 429 with Retry-After", {
                "first": first.status_code,
                "limited": limited.status_code,
                "limited_body": limited.json() if limited.headers.get("content-type", "").startswith("application/json") else limited.text,
                "retry_after": retry_after,
            }))
            print("FAIL: valid demo key is rate-limited before retrieval")
        else:
            print("PASS: valid demo key is rate-limited before retrieval")

        missing = client.post("/api/chat", json={"question": "What is Kroma?"})
        wrong = client.post("/api/chat", headers={"X-Kroma-Demo-Key": "wrong"}, json={"question": "What is Kroma?"})
        if missing.status_code != 401 or wrong.status_code != 401:
            failures.append(("missing/wrong demo key returns 401 before rate limiting", "401/401", (missing.status_code, wrong.status_code)))
            print("FAIL: missing/wrong demo key returns 401 before rate limiting")
        else:
            print("PASS: missing/wrong demo key returns 401 before rate limiting")

        public_demo = client.post("/api/demo/chat", json={"question": kroma_api.PUBLIC_DEMO_QUESTIONS[0]})
        if public_demo.status_code != 200 or public_demo.json().get("answer") != kroma_api.PUBLIC_DEMO_ANSWERS[kroma_api._normalize_demo_question(kroma_api.PUBLIC_DEMO_QUESTIONS[0])]["answer"]:
            failures.append(("public demo remains available outside Groq limiter", "200 public demo answer", public_demo.status_code))
            print("FAIL: public demo remains available outside Groq limiter")
        else:
            print("PASS: public demo remains available outside Groq limiter")
    finally:
        kroma_api.retrieve_chunks = original_retrieve
        kroma_api.generate_answer = original_generate
        if original_key is None:
            os.environ.pop("KROMA_DEMO_KEY", None)
        else:
            os.environ["KROMA_DEMO_KEY"] = original_key
        if original_limit is None:
            os.environ.pop("KROMA_RATE_LIMIT_REQUESTS", None)
        else:
            os.environ["KROMA_RATE_LIMIT_REQUESTS"] = original_limit
        if original_window is None:
            os.environ.pop("KROMA_RATE_LIMIT_WINDOW_SECONDS", None)
        else:
            os.environ["KROMA_RATE_LIMIT_WINDOW_SECONDS"] = original_window
        _clear_rate_limit_buckets()


def run_delete_filename_evals(failures: list) -> None:
    original_docs_folder = kroma_api.DOCS_FOLDER
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
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


def run_no_context_chat_eval(failures: list) -> None:
    original_retrieve = kroma_api.retrieve_chunks
    original_generate = kroma_api.generate_answer
    try:
        kroma_api.retrieve_chunks = lambda *args, **kwargs: ("", [])

        def fail_generate(*args, **kwargs):
            raise AssertionError("Groq generation should not run without retrieved context.")

        kroma_api.generate_answer = fail_generate
        result = kroma_api.chat(kroma_api.ChatRequest(question="What is only in missing docs?"))
        expected_answer = "That information was not found in the uploaded documents."
        if result != {"answer": expected_answer, "sources": [], "show_sources": False}:
            failures.append(("no-context chat returns deterministic missing-info answer", expected_answer, result))
            print("FAIL: no-context chat returns deterministic missing-info answer")
        else:
            print("PASS: no-context chat returns deterministic missing-info answer")
    except Exception as exc:
        failures.append(("no-context chat does not call Groq", "no generation call", repr(exc)))
        print("FAIL: no-context chat does not call Groq")
    finally:
        kroma_api.retrieve_chunks = original_retrieve
        kroma_api.generate_answer = original_generate


def run_delete_index_evals(failures: list) -> None:
    original_docs_folder = kroma_api.DOCS_FOLDER
    original_chroma_path = kroma_ingest.CHROMA_PATH
    original_stats_file = kroma_ingest.STATS_FILE
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        temp_docs = root / "docs"
        temp_docs.mkdir()
        temp_chroma = root / "chroma_db"
        temp_stats = root / "index_stats.json"
        (temp_docs / "delete-me.txt").write_text("deleted-only-token", encoding="utf-8")
        (temp_docs / "keep.txt").write_text("keep-only-token", encoding="utf-8")
        temp_stats.write_text(
            json.dumps(
                {
                    "total_chunks": 2,
                    "total_pages": 0,
                    "docs": [
                        {"name": "delete-me.txt", "file_type": "txt", "pages": 0, "chunks": 1},
                        {"name": "keep.txt", "file_type": "txt", "pages": 0, "chunks": 1},
                    ],
                    "processed_at": "2026-01-01T00:00:00",
                }
            ),
            encoding="utf-8",
        )
        client = chromadb.PersistentClient(path=str(temp_chroma))
        collection = client.get_or_create_collection("langchain")
        collection.add(
            ids=["delete-me-1", "keep-1"],
            embeddings=[[0.1, 0.2], [0.2, 0.1]],
            documents=["deleted-only-token", "keep-only-token"],
            metadatas=[{"source": "delete-me.txt"}, {"source": "keep.txt"}],
        )

        kroma_api.DOCS_FOLDER = temp_docs
        kroma_ingest.CHROMA_PATH = temp_chroma
        kroma_ingest.STATS_FILE = temp_stats
        try:
            result = kroma_api.delete_doc("delete-me.txt")
            deleted_records = collection.get(where={"source": "delete-me.txt"})
            kept_records = collection.get(where={"source": "keep.txt"})
            stats = json.loads(temp_stats.read_text(encoding="utf-8"))
            deleted_ok = (
                result == {"deleted": "delete-me.txt"}
                and not (temp_docs / "delete-me.txt").exists()
                and deleted_records.get("ids") == []
                and kept_records.get("ids") == ["keep-1"]
                and [doc["name"] for doc in stats.get("docs", [])] == ["keep.txt"]
                and stats.get("total_chunks") == 1
            )
            if not deleted_ok:
                failures.append(("deleted document removed from retrieval index", "only keep.txt remains", {
                    "result": result,
                    "deleted_records": deleted_records.get("ids"),
                    "kept_records": kept_records.get("ids"),
                    "stats": stats,
                }))
                print("FAIL: deleted document removed from retrieval index")
            else:
                print("PASS: deleted document removed from retrieval index")
        finally:
            try:
                client.clear_system_cache()
            except Exception:
                pass
            del collection
            del client
            gc.collect()
            kroma_api.DOCS_FOLDER = original_docs_folder
            kroma_ingest.CHROMA_PATH = original_chroma_path
            kroma_ingest.STATS_FILE = original_stats_file


def run_deleted_only_query_eval(failures: list) -> None:
    original_chroma_path = kroma_rag.CHROMA_PATH
    original_load_index_stats = kroma_rag.load_index_stats
    original_embeddings = kroma_rag.SentenceTransformerEmbeddings
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_chroma = Path(temp_dir) / "chroma_db"
        temp_chroma.mkdir()
        try:
            kroma_rag.CHROMA_PATH = temp_chroma
            kroma_rag.load_index_stats = lambda: {
                "total_chunks": 1,
                "docs": [{"name": "keep.txt", "file_type": "txt", "pages": 0, "chunks": 1}],
            }

            def fail_embeddings(*args, **kwargs):
                raise AssertionError("Deleted-only query should stop before embedding.")

            kroma_rag.SentenceTransformerEmbeddings = fail_embeddings
            context, sources = retrieve_chunks("deleted-only-token", selected_docs=["delete-me.txt"])
            if context != "" or sources != []:
                failures.append(("deleted-only document cannot be queried", ("", []), (context, sources)))
                print("FAIL: deleted-only document cannot be queried")
            else:
                print("PASS: deleted-only document cannot be queried")
        except Exception as exc:
            failures.append(("deleted-only document cannot be queried", "no retrieval/embedding", repr(exc)))
            print("FAIL: deleted-only document cannot be queried")
        finally:
            kroma_rag.CHROMA_PATH = original_chroma_path
            kroma_rag.load_index_stats = original_load_index_stats
            kroma_rag.SentenceTransformerEmbeddings = original_embeddings


def run_demo_key_evals(failures: list) -> None:
    original_retrieve = kroma_api.retrieve_chunks
    original_generate = kroma_api.generate_answer
    original_load_index_stats = kroma_api.load_index_stats
    original_docs_folder = kroma_api.DOCS_FOLDER
    original_chroma_path = kroma_api.CHROMA_PATH
    original_key = os.environ.get("KROMA_DEMO_KEY")
    client = TestClient(kroma_api.app, raise_server_exceptions=False)
    try:
        def fail_retrieve(*args, **kwargs):
            raise AssertionError("Protected endpoint ran without a valid demo key.")

        kroma_api.retrieve_chunks = fail_retrieve
        os.environ["KROMA_DEMO_KEY"] = "demo-secret"
        missing = client.post("/api/chat", json={"question": "hello"})
        wrong = client.post("/api/chat", headers={"X-Kroma-Demo-Key": "wrong"}, json={"question": "hello"})
        health = client.get("/health")
        if missing.status_code != 401 or wrong.status_code != 401 or health.status_code != 200:
            failures.append(("demo key required when configured", "401/401/200", (missing.status_code, wrong.status_code, health.status_code)))
            print("FAIL: demo key required when configured")
        else:
            print("PASS: demo key required when configured")

        kroma_api.generate_answer = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Public demo should not call Groq generation."))
        public_demo = client.post("/api/demo/chat", json={"question": kroma_api.PUBLIC_DEMO_QUESTIONS[0]})
        unsupported_public_question = client.post("/api/demo/chat", json={"question": "Tell me anything you want about Kroma."})
        status_response = client.get("/api/status")
        status_payload = status_response.json()
        public_demo_ok = (
            public_demo.status_code == 200
            and public_demo.json().get("show_sources") is True
            and public_demo.json().get("sources", [{}])[0].get("source") == kroma_api.PUBLIC_DEMO_DOCUMENT
            and unsupported_public_question.status_code == 400
            and status_payload.get("demo_key_required") is True
            and status_payload.get("public_demo", {}).get("note") == kroma_api.PUBLIC_DEMO_NOTE
        )
        if not public_demo_ok:
            failures.append(("public demo available without key when demo key is configured", "200 demo/400 unsupported/status metadata", {
                "demo_status": public_demo.status_code,
                "demo_body": public_demo.json() if public_demo.headers.get("content-type", "").startswith("application/json") else public_demo.text,
                "unsupported_status": unsupported_public_question.status_code,
                "status": status_payload,
            }))
            print("FAIL: public demo available without key when demo key is configured")
        else:
            print("PASS: public demo available without key when demo key is configured")

        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            docs_dir = temp_root / "docs"
            chroma_dir = temp_root / "chroma"
            docs_dir.mkdir()
            chroma_dir.mkdir()
            (docs_dir / "private.pdf").write_bytes(b"%PDF-1.4\n")
            kroma_api.DOCS_FOLDER = docs_dir
            kroma_api.CHROMA_PATH = chroma_dir
            kroma_api.load_index_stats = lambda: {
                "total_chunks": 12,
                "total_pages": 3,
                "documents": {"private.pdf": {"chunks": 12, "pages": 3}},
            }

            locked_status_response = client.get("/api/status")
            locked_status = locked_status_response.json()
            unlocked_status_response = client.get("/api/status", headers={"X-Kroma-Demo-Key": "demo-secret"})
            unlocked_status = unlocked_status_response.json()
            status_metadata_ok = (
                locked_status_response.status_code == 200
                and locked_status.get("demo_key_required") is True
                and locked_status.get("indexed") is False
                and locked_status.get("stats") is None
                and locked_status.get("docs") == []
                and locked_status.get("public_demo", {}).get("document") == kroma_api.PUBLIC_DEMO_DOCUMENT
                and unlocked_status_response.status_code == 200
                and unlocked_status.get("stats", {}).get("total_chunks") == 12
                and unlocked_status.get("docs") == ["private.pdf"]
                and unlocked_status.get("indexed") is True
            )
            if not status_metadata_ok:
                failures.append(("status metadata protected by demo key", "safe locked status/full unlocked status", {
                    "locked_status_code": locked_status_response.status_code,
                    "locked_status": locked_status,
                    "unlocked_status_code": unlocked_status_response.status_code,
                    "unlocked_status": unlocked_status,
                }))
                print("FAIL: status metadata protected by demo key")
            else:
                print("PASS: status metadata protected by demo key")

            kroma_api.load_index_stats = original_load_index_stats
            kroma_api.DOCS_FOLDER = original_docs_folder
            kroma_api.CHROMA_PATH = original_chroma_path

        blocked_cases = [
            ("upload requires demo key", lambda: client.post("/api/upload", files={"file": ("notes.txt", io.BytesIO(b"hello"), "text/plain")})),
            ("process requires demo key", lambda: client.post("/api/process")),
            ("delete requires demo key", lambda: client.delete("/api/docs/notes.txt")),
            ("clear library requires demo key", lambda: client.delete("/api/library")),
            ("flashcards require demo key", lambda: client.post("/api/flashcards", json={"selected_docs": ["notes.txt"], "count": 8})),
            ("quiz requires demo key", lambda: client.post("/api/quiz", json={"selected_docs": ["notes.txt"], "difficulty": "easy", "count": 8})),
            ("summary requires demo key", lambda: client.post("/api/summary", json={"selected_docs": ["notes.txt"]})),
            ("suggestions require demo key", lambda: client.post("/api/suggest", json={"selected_docs": ["notes.txt"]})),
        ]
        blocked_statuses = [(name, call().status_code) for name, call in blocked_cases]
        if any(status != 401 for _, status in blocked_statuses):
            failures.append(("no-key custom document actions remain blocked", "all 401", blocked_statuses))
            print("FAIL: no-key custom document actions remain blocked")
        else:
            print("PASS: no-key custom document actions remain blocked")

        kroma_api.retrieve_chunks = lambda *args, **kwargs: ("", [])
        kroma_api.generate_answer = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Groq should not run."))
        allowed = client.post("/api/chat", headers={"X-Kroma-Demo-Key": "demo-secret"}, json={"question": "missing topic"})
        if allowed.status_code != 200:
            failures.append(("correct demo key allows protected endpoint", 200, allowed.status_code))
            print("FAIL: correct demo key allows protected endpoint")
        else:
            print("PASS: correct demo key allows protected endpoint")

        os.environ.pop("KROMA_DEMO_KEY", None)
        no_key_required = client.post("/api/chat", json={"question": "missing topic"})
        if no_key_required.status_code != 200:
            failures.append(("demo key not required when unset", 200, no_key_required.status_code))
            print("FAIL: demo key not required when unset")
        else:
            print("PASS: demo key not required when unset")
    finally:
        kroma_api.retrieve_chunks = original_retrieve
        kroma_api.generate_answer = original_generate
        kroma_api.load_index_stats = original_load_index_stats
        kroma_api.DOCS_FOLDER = original_docs_folder
        kroma_api.CHROMA_PATH = original_chroma_path
        if original_key is None:
            os.environ.pop("KROMA_DEMO_KEY", None)
        else:
            os.environ["KROMA_DEMO_KEY"] = original_key


def run_request_bound_evals(failures: list) -> None:
    original_retrieve = kroma_api.retrieve_chunks
    client = TestClient(kroma_api.app, raise_server_exceptions=False)
    try:
        kroma_api.retrieve_chunks = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Invalid input should fail before retrieval."))
        cases = [
            ("oversized chat question rejected", "/api/chat", {"question": "x" * 2001}),
            ("oversized history rejected", "/api/chat", {"question": "hello", "history": [{"role": "user", "content": "x"}] * 17}),
            ("too many selected docs rejected", "/api/chat", {"question": "hello", "selected_docs": [f"doc{i}.txt" for i in range(26)]}),
            ("invalid flashcard count rejected", "/api/flashcards", {"selected_docs": ["notes.txt"], "count": 31}),
            ("invalid quiz difficulty rejected", "/api/quiz", {"selected_docs": ["notes.txt"], "difficulty": "expert", "count": 8}),
            ("summary selected doc bound rejected", "/api/summary", {"selected_docs": [f"doc{i}.txt" for i in range(26)]}),
        ]
        for name, path, payload in cases:
            response = client.post(path, json=payload)
            if response.status_code != 400:
                failures.append((name, 400, response.status_code))
                print(f"FAIL: {name}")
            else:
                print(f"PASS: {name}")
    finally:
        kroma_api.retrieve_chunks = original_retrieve


def run_suggestion_grounding_evals(failures: list) -> None:
    original_client = kroma_rag._groq_client
    original_retrieve = kroma_api.retrieve_chunks
    original_generate = kroma_api.generate_suggestions
    original_key = os.environ.get("KROMA_DEMO_KEY")
    original_limit = os.environ.get("KROMA_RATE_LIMIT_REQUESTS")

    class FakeGroqClient:
        class Chat:
            class Completions:
                @staticmethod
                def create(*args, **kwargs):
                    class Message:
                        content = json.dumps(
                            [
                                "Can you provide an example of a recent AI research project the team has worked on?",
                                "How does the company approach model deployment and MLOps, and what tools or workflows are currently in use?",
                                "What required skills and experience does this role list?",
                            ]
                        )

                    class Choice:
                        message = Message()

                    class Response:
                        choices = [Choice()]

                    return Response()

            completions = Completions()

        chat = Chat()

    try:
        kroma_rag._groq_client = lambda: FakeGroqClient()
        suggestions = kroma_rag.generate_suggestions(JOBDESCRIPTION_CONTEXT)
        joined = " ".join(suggestions).lower()
        banned_absent = (
            "team has worked on" not in joined
            and "recent project" not in joined
            and "mlops" not in joined
            and "currently in use" not in joined
        )
        has_answerable_theme = any("required skills" in item.lower() for item in suggestions)
        has_bonus_or_proposal = any(
            "bonus qualifications" in item.lower() or "proposal" in item.lower()
            for item in suggestions
        )
        has_candidate_fit = any("fit" in item.lower() or "candidate profile" in item.lower() for item in suggestions)

        if not banned_absent:
            failures.append(("suggestions reject ungrounded project-history prompts", "no banned text", suggestions))
            print("FAIL: suggestions reject ungrounded project-history prompts")
        else:
            print("PASS: suggestions reject ungrounded project-history prompts")

        if not (has_answerable_theme and has_bonus_or_proposal and has_candidate_fit):
            failures.append(("suggestions include answerable job-post themes", "skills/bonus-or-proposal/fit", suggestions))
            print("FAIL: suggestions include answerable job-post themes")
        else:
            print("PASS: suggestions include answerable job-post themes")

        os.environ.pop("KROMA_DEMO_KEY", None)
        os.environ["KROMA_RATE_LIMIT_REQUESTS"] = "100"
        _clear_rate_limit_buckets()
        captured = {}

        def fake_retrieve(query, n_results=10, progress_callback=None, selected_docs=None):
            captured["query"] = query
            captured["n_results"] = n_results
            captured["selected_docs"] = selected_docs
            return (JOBDESCRIPTION_CONTEXT, [SOURCE])

        kroma_api.retrieve_chunks = fake_retrieve
        kroma_api.generate_suggestions = lambda context: ["What required skills and experience does this role list?"]

        client = TestClient(kroma_api.app, raise_server_exceptions=False)
        response = client.post("/api/suggest", json={"selected_docs": ["jobdescription_18.txt"]})
        if response.status_code != 200 or captured.get("selected_docs") != ["jobdescription_18.txt"]:
            failures.append(("suggest endpoint preserves selected_docs filter", ["jobdescription_18.txt"], captured))
            print("FAIL: suggest endpoint preserves selected_docs filter")
        else:
            print("PASS: suggest endpoint preserves selected_docs filter")

        response_all = client.post("/api/suggest", json={"selected_docs": []})
        if response_all.status_code != 200 or captured.get("selected_docs") != []:
            failures.append(("suggest endpoint keeps empty selected_docs as all docs", [], captured))
            print("FAIL: suggest endpoint keeps empty selected_docs as all docs")
        else:
            print("PASS: suggest endpoint keeps empty selected_docs as all docs")
    finally:
        kroma_rag._groq_client = original_client
        kroma_api.retrieve_chunks = original_retrieve
        kroma_api.generate_suggestions = original_generate
        _clear_rate_limit_buckets()
        if original_key is None:
            os.environ.pop("KROMA_DEMO_KEY", None)
        else:
            os.environ["KROMA_DEMO_KEY"] = original_key
        if original_limit is None:
            os.environ.pop("KROMA_RATE_LIMIT_REQUESTS", None)
        else:
            os.environ["KROMA_RATE_LIMIT_REQUESTS"] = original_limit


def run_json_parser_evals(failures: list) -> None:
    for name, raw, expected in JSON_PARSER_CASES:
        result = kroma_rag._parse_json_array_response(raw)
        if result != expected:
            failures.append((f"json parser: {name}", expected, result))
            print(f"FAIL: json parser: {name}")
        else:
            print(f"PASS: json parser: {name}")

    cards_str = [{"question": "Q?", "answer": "A.", "source_ids": "s1"}]
    result = sanitize_flashcards_source_ids(cards_str, SOURCE_IDS_CATALOG)
    expected = [{"question": "Q?", "answer": "A.", "source_ids": ["s1"]}]
    if result != expected:
        failures.append(("flashcard source_ids string becomes ['s1']", expected, result))
        print("FAIL: flashcard source_ids string becomes ['s1']")
    else:
        print("PASS: flashcard source_ids string becomes ['s1']")

    questions_bad = [{
        "question": "Q?", "choices": ["A. a", "B. b", "C. c", "D. d"],
        "answer": "A", "explanation": "Because.", "source_ids": 123,
    }]
    result = sanitize_quiz_source_ids(questions_bad, SOURCE_IDS_CATALOG)
    if result[0]["source_ids"] != []:
        failures.append(("quiz source_ids non-list/non-string becomes []", [], result[0]["source_ids"]))
        print("FAIL: quiz source_ids non-list/non-string becomes []")
    else:
        print("PASS: quiz source_ids non-list/non-string becomes []")

    cards_dup = [{"question": "Q?", "answer": "A.", "source_ids": ["s2", "s1", "s2", "s3", "s1"]}]
    result = sanitize_flashcards_source_ids(cards_dup, SOURCE_IDS_CATALOG)
    if result[0]["source_ids"] != ["s2", "s1", "s3"]:
        failures.append(("duplicate source_ids preserve first occurrence", ["s2", "s1", "s3"], result[0]["source_ids"]))
        print("FAIL: duplicate source_ids preserve first occurrence")
    else:
        print("PASS: duplicate source_ids preserve first occurrence")

    sections_str = [{
        "heading": "Key Topics",
        "text": "",
        "source_ids": [],
        "bullets": [{"text": "Test bullet", "source_ids": "nonexistent"}],
    }]
    result = sanitize_summary_source_ids(sections_str, SOURCE_IDS_CATALOG)
    expected_bullets = [{"text": "Test bullet", "source_ids": []}]
    if result[0]["bullets"] != expected_bullets:
        failures.append(("summary string bullet becomes []", expected_bullets, result[0]["bullets"]))
        print("FAIL: summary string bullet becomes []")
    else:
        print("PASS: summary string bullet becomes []")


BUSINESS_COPILOT_SOURCES = [
    {"id": "s1", "source": "doc1.pdf", "score": 91},
    {"id": "s2", "source": "doc2.pdf", "score": 82},
]


BUSINESS_COPILOT_NORMALIZED = {
    "verified_facts": [
        {"text": "Kroma is a document assistant.", "source_ids": ["s1", "s2"]},
        {"text": "Made up fact.", "source_ids": ["s999", "invented"]},
    ],
    "suggested_draft": "Based on our documents, Kroma is a document assistant.",
    "missing_information": ["Revenue figures not available."],
    "sources_used": ["s1", "s999"],
}


BUSINESS_COPILOT_SANITIZED = {
    "verified_facts": [
        {"text": "Kroma is a document assistant.", "source_ids": ["s1", "s2"]},
    ],
    "suggested_draft": "Based on our documents, Kroma is a document assistant.",
    "missing_information": ["Revenue figures not available.", "Made up fact."],
    "sources_used": ["s1"],
}


def run_business_copilot_evals(failures: list) -> None:
    result = sanitize_business_copilot_source_ids(BUSINESS_COPILOT_NORMALIZED, BUSINESS_COPILOT_SOURCES)
    if result != BUSINESS_COPILOT_SANITIZED:
        failures.append(("business copilot invalid source IDs removed", BUSINESS_COPILOT_SANITIZED, result))
        print("FAIL: business copilot invalid source IDs removed")
    else:
        print("PASS: business copilot invalid source IDs removed")

    if "Made up fact." not in result.get("missing_information", []):
        failures.append(("business copilot unsourced facts moved to missing_information", "Made up fact. in missing_information", result))
        print("FAIL: business copilot unsourced facts moved to missing_information")
    else:
        print("PASS: business copilot unsourced facts moved to missing_information")

    hr = business_needs_human_review("draft_reply", "customer", "What are our terms?", [])
    if hr["required"] is not True or not hr["reasons"]:
        failures.append(("customer + draft_reply requires human review", "required with reasons", hr))
        print("FAIL: customer + draft_reply requires human review")
    else:
        print("PASS: customer + draft_reply requires human review")

    hr = business_needs_human_review("answer_from_sources", "internal_team", "What does Kroma do?", [])
    if hr["required"] is not False or hr["reasons"]:
        failures.append(("internal_team + answer_from_sources can avoid human review", "not required", hr))
        print("FAIL: internal_team + answer_from_sources can avoid human review")
    else:
        print("PASS: internal_team + answer_from_sources can avoid human review")

    hr = business_needs_human_review("answer_from_sources", "internal_team", "What does Kroma do?", ["No relevant information"])
    if hr["required"] is not True:
        failures.append(("missing context always requires human review", "required", hr))
        print("FAIL: missing context always requires human review")
    else:
        print("PASS: missing context always requires human review")

    sensitive_texts = [
        "What is our pricing for enterprise?",
        "What are the legal terms?",
        "Share financial projections.",
        "Draft a reply about the complaint.",
        "What is the refund policy?",
        "Summarize contract terms.",
        "What is the employee salary range?",
    ]
    for text in sensitive_texts:
        hr = business_needs_human_review("answer_from_sources", "internal_team", text, [])
        if hr["required"] is not True:
            failures.append((f"business copilot sensitive keyword triggers review: '{text}'", "required", hr))
            print(f"FAIL: business copilot sensitive keyword triggers review: '{text}'")
        else:
            print(f"PASS: business copilot sensitive keyword triggers review: '{text}'")

    original_retrieve = kroma_api.retrieve_chunks
    client = TestClient(kroma_api.app, raise_server_exceptions=False)
    try:
        kroma_api.retrieve_chunks = lambda *args, **kwargs: ("", [])

        os.environ["KROMA_DEMO_KEY"] = "bc-noctx"
        try:
            response = client.post(
                "/api/business-copilot",
                headers={"X-Kroma-Demo-Key": "bc-noctx"},
                json={
                    "task_type": "answer_from_sources",
                    "audience": "internal_team",
                    "request": "What is the revenue?",
                    "selected_docs": ["doc1.pdf"],
                },
            )
            expected_noctx = {
                "result": {
                    "verified_facts": [],
                    "suggested_draft": "",
                    "missing_information": ["No relevant information was found in the selected documents."],
                    "needs_human_review": {"required": True, "reasons": ["No source-grounded context available"]},
                    "sources_used": [],
                },
                "sources": [],
            }
            if response.status_code != 200 or response.json() != expected_noctx:
                failures.append(("business copilot no-context returns deterministic JSON", expected_noctx, (response.status_code, response.json())))
                print("FAIL: business copilot no-context returns deterministic JSON")
            else:
                print("PASS: business copilot no-context returns deterministic JSON")
        finally:
            os.environ.pop("KROMA_DEMO_KEY", None)
    finally:
        kroma_api.retrieve_chunks = original_retrieve

    client2 = TestClient(kroma_api.app, raise_server_exceptions=False)
    original_retrieve2 = kroma_api.retrieve_chunks
    try:
        kroma_api.retrieve_chunks = lambda *args, **kwargs: ("", [])
        os.environ["KROMA_DEMO_KEY"] = "bc-demo-protect"
        try:
            missing = client2.post("/api/business-copilot", json={
                "task_type": "answer_from_sources", "audience": "internal_team",
                "request": "test", "selected_docs": [],
            })
            wrong = client2.post("/api/business-copilot", headers={"X-Kroma-Demo-Key": "wrong"}, json={
                "task_type": "answer_from_sources", "audience": "internal_team",
                "request": "test", "selected_docs": [],
            })
            correct = client2.post("/api/business-copilot", headers={"X-Kroma-Demo-Key": "bc-demo-protect"}, json={
                "task_type": "answer_from_sources", "audience": "internal_team",
                "request": "test", "selected_docs": [],
            })
            if missing.status_code != 401 or wrong.status_code != 401:
                failures.append(("business copilot requires demo key when configured", "401/401", (missing.status_code, wrong.status_code)))
                print("FAIL: business copilot requires demo key when configured")
            else:
                print("PASS: business copilot requires demo key when configured")
            if correct.status_code == 401:
                failures.append(("business copilot correct demo key allowed", "non-401", correct.status_code))
                print("FAIL: business copilot correct demo key allowed")
            else:
                body = correct.json()
                if "result" not in body or "needs_human_review" not in body.get("result", {}):
                    failures.append(("business copilot correct demo key returns expected body", "result with needs_human_review", body))
                    print("FAIL: business copilot correct demo key returns expected body")
                else:
                    print("PASS: business copilot correct demo key allowed and returns expected body")
        finally:
            os.environ.pop("KROMA_DEMO_KEY", None)

        no_key = client2.post("/api/business-copilot", json={
            "task_type": "answer_from_sources", "audience": "internal_team",
            "request": "test", "selected_docs": [],
        })
        if no_key.status_code == 401:
            failures.append(("business copilot no key required when unset", "200", no_key.status_code))
            print("FAIL: business copilot no key required when unset")
        else:
            print("PASS: business copilot no key required when unset")
    finally:
        kroma_api.retrieve_chunks = original_retrieve2

    hr_deleg = business_needs_human_review("summarize_for_team", "internal_team", "Summarize the key points.", [])
    if hr_deleg["required"] is not False:
        failures.append(("internal_team + summarize_for_team can avoid human review", "not required", hr_deleg))
        print("FAIL: internal_team + summarize_for_team can avoid human review")
    else:
        print("PASS: internal_team + summarize_for_team can avoid human review")

    for aud in ("customer", "partner", "investor", "distributor", "other"):
        hr_aud = business_needs_human_review("answer_from_sources", aud, "What does Kroma do?", [])
        if hr_aud["required"] is not True:
            failures.append((f"audience '{aud}' always requires human review", "required", hr_aud))
            print(f"FAIL: audience '{aud}' always requires human review")
        else:
            print(f"PASS: audience '{aud}' always requires human review")

    for ttype in ("draft_reply", "risk_check"):
        hr_task = business_needs_human_review(ttype, "internal_team", "What does Kroma do?", [])
        if hr_task["required"] is not True:
            failures.append((f"task_type '{ttype}' always requires human review", "required", hr_task))
            print(f"FAIL: task_type '{ttype}' always requires human review")
        else:
            print(f"PASS: task_type '{ttype}' always requires human review")

    hr_extract = business_needs_human_review("extract_action_items", "internal_team", "Extract action items from meeting notes.", [])
    if hr_extract["required"] is not True:
        failures.append(("extract_action_items + internal_team requires human review", "required", hr_extract))
        print("FAIL: extract_action_items + internal_team requires human review")
    else:
        print("PASS: extract_action_items + internal_team requires human review")

    plural_sensitive = ["product claims", "complaints", "refunds", "negotiations"]
    for text in plural_sensitive:
        hr_plural = business_needs_human_review("answer_from_sources", "internal_team", f"What about {text}?", [])
        if hr_plural["required"] is not True:
            failures.append((f"plural sensitive term triggers review: '{text}'", "required", hr_plural))
            print(f"FAIL: plural sensitive term triggers review: '{text}'")
        else:
            print(f"PASS: plural sensitive term triggers review: '{text}'")

    # ── Malformed / empty model output evals ──
    client3 = TestClient(kroma_api.app, raise_server_exceptions=False)
    original_retrieve3 = kroma_api.retrieve_chunks
    original_generate3 = kroma_api.generate_business_copilot_output
    try:
        kroma_api.retrieve_chunks = lambda *args, **kwargs: (
            "[Source: doc1.pdf, Page 1]\nKroma is a document assistant.",
            [{"rank": 1, "source": "doc1.pdf", "page": 1, "file_type": "pdf", "location_type": "page", "location_label": "Page 1", "chunk_id": "doc1-1-1", "doc_chunk_id": "doc1.pdf:1:1", "score": 90, "distance": 0.11, "preview": "Kroma is a document assistant."}],
        )

        os.environ["KROMA_DEMO_KEY"] = "bc-malformed"

        kroma_api.generate_business_copilot_output = lambda *args, **kwargs: "not valid json at all"
        resp = client3.post("/api/business-copilot", headers={"X-Kroma-Demo-Key": "bc-malformed"}, json={
            "task_type": "answer_from_sources", "audience": "internal_team",
            "request": "What is Kroma?", "selected_docs": [],
        })
        result = resp.json()["result"]
        required_ok = result["needs_human_review"]["required"] is True
        reason_ok = any("Model output could not be verified" in r for r in result["needs_human_review"].get("reasons", []))
        if not required_ok or not reason_ok:
            failures.append(("malformed model JSON requires human review", "required with 'Model output could not be verified'", result["needs_human_review"]))
            print("FAIL: malformed model JSON requires human review")
        else:
            print("PASS: malformed model JSON requires human review")

        kroma_api.generate_business_copilot_output = lambda *args, **kwargs: "{}"
        resp = client3.post("/api/business-copilot", headers={"X-Kroma-Demo-Key": "bc-malformed"}, json={
            "task_type": "answer_from_sources", "audience": "internal_team",
            "request": "What is Kroma?", "selected_docs": [],
        })
        result = resp.json()["result"]
        if result["needs_human_review"]["required"] is not True or not result.get("missing_information"):
            failures.append(("empty model JSON requires human review", "required with fallback missing_information", result))
            print("FAIL: empty model JSON requires human review")
        else:
            print("PASS: empty model JSON requires human review")

        kroma_api.generate_business_copilot_output = lambda *args, **kwargs: '{"verified_facts":[],"suggested_draft":"","missing_information":[]}'
        resp = client3.post("/api/business-copilot", headers={"X-Kroma-Demo-Key": "bc-malformed"}, json={
            "task_type": "answer_from_sources", "audience": "internal_team",
            "request": "What is Kroma?", "selected_docs": [],
        })
        result = resp.json()["result"]
        if result["needs_human_review"]["required"] is not True or not result.get("missing_information"):
            failures.append(("empty normalized output requires human review", "required with fallback missing_information", result))
            print("FAIL: empty normalized output requires human review")
        else:
            print("PASS: empty normalized output requires human review")
    finally:
        kroma_api.retrieve_chunks = original_retrieve3
        kroma_api.generate_business_copilot_output = original_generate3
        os.environ.pop("KROMA_DEMO_KEY", None)


def run_knowledge_audit_evals(failures: list) -> None:
    from rag import (
        sanitize_knowledge_audit_source_ids,
        normalize_knowledge_audit_output,
        compute_readiness_verdict
    )
    ka_sources = [{"id": "s1", "source": "doc1.pdf", "score": 91}]
    ka_payload = {
        "coverage_summary": [{"area": "A", "source_ids": ["s1", "bad"]}, {"area": "B", "source_ids": ["bad"]}],
        "risk_areas": [{"area": "R", "detail": "D", "source_ids": ["s1", "bad"]}],
        "sources_used": ["s1", "bad"]
    }
    sanitized = sanitize_knowledge_audit_source_ids(ka_payload, ka_sources)
    if sanitized["coverage_summary"] != [{"area": "A", "source_ids": ["s1"]}]:
        failures.append(("knowledge audit invalid source IDs removed from coverage & without valid sources removed", "A with s1", sanitized["coverage_summary"]))
        print("FAIL: knowledge audit invalid source IDs removed from coverage")
    else:
        print("PASS: knowledge audit invalid source IDs removed from coverage")

    if sanitized["risk_areas"] != [{"area": "R", "detail": "D", "source_ids": ["s1"]}]:
        failures.append(("knowledge audit invalid source IDs removed from risk_areas", "R with s1", sanitized["risk_areas"]))
        print("FAIL: knowledge audit invalid source IDs removed from risk_areas")
    else:
        print("PASS: knowledge audit invalid source IDs removed from risk_areas")

    if sanitized["sources_used"] != ["s1"]:
        failures.append(("knowledge audit invalid sources_used stripped", ["s1"], sanitized["sources_used"]))
        print("FAIL: knowledge audit invalid sources_used stripped")
    else:
        print("PASS: knowledge audit invalid sources_used stripped")

    v_low_coverage = compute_readiness_verdict({"coverage_summary": [{"area": "A"}], "risk_areas": [], "missing_knowledge": []})
    if v_low_coverage["level"] != "Low":
        failures.append(("knowledge audit readiness verdict Low when no coverage", "Low", v_low_coverage))
        print("FAIL: knowledge audit readiness verdict Low when no coverage")
    else:
        print("PASS: knowledge audit readiness verdict Low when no coverage")

    v_low_risks = compute_readiness_verdict({"coverage_summary": [{"area": "A"}, {"area": "B"}], "risk_areas": [1,2,3], "missing_knowledge": []})
    if v_low_risks["level"] != "Low":
        failures.append(("knowledge audit readiness verdict Low when many risks", "Low", v_low_risks))
        print("FAIL: knowledge audit readiness verdict Low when many risks")
    else:
        print("PASS: knowledge audit readiness verdict Low when many risks")

    v_low_missing = compute_readiness_verdict({"coverage_summary": [{"area": "A"}, {"area": "B"}], "risk_areas": [], "missing_knowledge": [1,2,3]})
    if v_low_missing["level"] != "Low":
        failures.append(("knowledge audit readiness verdict Low when many missing items", "Low", v_low_missing))
        print("FAIL: knowledge audit readiness verdict Low when many missing items")
    else:
        print("PASS: knowledge audit readiness verdict Low when many missing items")

    v_high = compute_readiness_verdict({"coverage_summary": [1,2,3,4], "risk_areas": [], "missing_knowledge": [1]})
    if v_high["level"] != "High":
        failures.append(("knowledge audit readiness verdict High when good coverage", "High", v_high))
        print("FAIL: knowledge audit readiness verdict High when good coverage")
    else:
        print("PASS: knowledge audit readiness verdict High when good coverage")

    v_med = compute_readiness_verdict({"coverage_summary": [1,2,3], "risk_areas": [1], "missing_knowledge": [1]})
    if v_med["level"] != "Medium":
        failures.append(("knowledge audit readiness verdict Medium otherwise", "Medium", v_med))
        print("FAIL: knowledge audit readiness verdict Medium otherwise")
    else:
        print("PASS: knowledge audit readiness verdict Medium otherwise")

    norm_empty = normalize_knowledge_audit_output({})
    if "coverage_summary" not in norm_empty:
        failures.append(("knowledge audit normalize handles empty payload", "valid structure", norm_empty))
        print("FAIL: knowledge audit normalize handles empty payload")
    else:
        print("PASS: knowledge audit normalize handles empty payload")

    norm_malf = normalize_knowledge_audit_output("bad string")
    if "coverage_summary" not in norm_malf:
        failures.append(("knowledge audit normalize handles malformed/string payload", "valid structure", norm_malf))
        print("FAIL: knowledge audit normalize handles malformed/string payload")
    else:
        print("PASS: knowledge audit normalize handles malformed/string payload")

    original_retrieve = kroma_api.retrieve_chunks
    original_generate = getattr(kroma_api, "generate_knowledge_audit", None)
    client = TestClient(kroma_api.app, raise_server_exceptions=False)

    try:
        kroma_api.retrieve_chunks = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Invalid input should fail before retrieval."))
        resp = client.post("/api/knowledge-audit", json={"selected_docs": [f"doc{i}.pdf" for i in range(30)]})
        if resp.status_code != 400:
            failures.append(("knowledge audit selected_docs validation rejects too many docs", 400, resp.status_code))
            print("FAIL: knowledge audit selected_docs validation rejects too many docs")
        else:
            print("PASS: knowledge audit selected_docs validation rejects too many docs")

        kroma_api.retrieve_chunks = lambda *args, **kwargs: ("", [])
        kroma_api.generate_knowledge_audit = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Should not call Groq"))
        resp = client.post("/api/knowledge-audit", json={"selected_docs": []})
        expected_no_ctx = kroma_api.KNOWLEDGE_AUDIT_NO_CONTEXT_RESPONSE
        if resp.status_code != 200 or resp.json() != expected_no_ctx:
            failures.append(("knowledge audit no-context returns deterministic JSON", expected_no_ctx, resp.json()))
            print("FAIL: knowledge audit no-context returns deterministic JSON")
        else:
            print("PASS: knowledge audit no-context returns deterministic JSON")

        os.environ["KROMA_DEMO_KEY"] = "ka-key"
        resp_missing = client.post("/api/knowledge-audit", json={})
        if resp_missing.status_code != 401:
            failures.append(("knowledge audit requires demo key when configured", 401, resp_missing.status_code))
            print("FAIL: knowledge audit requires demo key when configured")
        else:
            print("PASS: knowledge audit requires demo key when configured")

        resp_correct = client.post("/api/knowledge-audit", headers={"X-Kroma-Demo-Key": "ka-key"}, json={})
        if resp_correct.status_code != 200:
            failures.append(("knowledge audit correct demo key allowed", 200, resp_correct.status_code))
            print("FAIL: knowledge audit correct demo key allowed")
        else:
            print("PASS: knowledge audit correct demo key allowed")

        os.environ.pop("KROMA_DEMO_KEY", None)
        resp_nokey = client.post("/api/knowledge-audit", json={})
        if resp_nokey.status_code != 200:
            failures.append(("knowledge audit no key required when unset", 200, resp_nokey.status_code))
            print("FAIL: knowledge audit no key required when unset")
        else:
            print("PASS: knowledge audit no key required when unset")
    except Exception as e:
        failures.append(("knowledge audit execution exception", "success", str(e)))
        print(f"FAIL: knowledge audit execution exception - {str(e)}")
    finally:
        kroma_api.retrieve_chunks = original_retrieve
        if original_generate:
            kroma_api.generate_knowledge_audit = original_generate
        os.environ.pop("KROMA_DEMO_KEY", None)


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

    run_json_parser_evals(failures)
    run_api_docs_evals(failures)
    run_delete_filename_evals(failures)
    run_upload_validation_evals(failures)
    run_no_context_chat_eval(failures)
    run_delete_index_evals(failures)
    run_deleted_only_query_eval(failures)
    run_demo_key_evals(failures)
    run_groq_rate_limit_evals(failures)
    run_request_bound_evals(failures)
    run_suggestion_grounding_evals(failures)
    run_business_copilot_evals(failures)
    run_knowledge_audit_evals(failures)

    if failures:
        print("\nFailures:")
        for name, expected, actual in failures:
            print(f"- {name}: expected {expected}, got {actual}")
        return 1

    print("\nAll trust behavior evals passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

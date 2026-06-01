import gc
import json
import hmac
import os
import re
import shutil
import threading
import time
import uuid
from pathlib import Path, PurePosixPath, PureWindowsPath

from fastapi import FastAPI, File, UploadFile, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel

from ingest import (
    CHROMA_PATH,
    DOCS_FOLDER,
    STATS_FILE,
    SUPPORTED_DOCUMENT_EXTENSIONS,
    SUPPORTED_TEXT_EXTENSIONS,
    delete_document_from_index,
    ingest_documents,
    is_control_heavy_text,
    is_supported_document,
    load_index_stats,
)
from rag import (
    build_source_catalog,
    build_source_linked_context,
    business_context_is_relevant,
    business_needs_human_review,
    compute_readiness_verdict,
    generate_answer,
    generate_business_copilot_output,
    generate_flashcards,
    generate_knowledge_audit,
    generate_quiz,
    generate_suggestions,
    generate_summary,
    normalize_business_copilot_output,
    normalize_knowledge_audit_output,
    normalize_summary_sections,
    retrieve_chunks,
    sanitize_business_copilot_source_ids,
    sanitize_flashcards_source_ids,
    sanitize_knowledge_audit_source_ids,
    sanitize_quiz_source_ids,
    sanitize_summary_source_ids,
    should_show_sources,
)


def _is_production() -> bool:
    return os.getenv("APP_ENV", "").lower() == "production" or os.getenv("ENV", "").lower() == "production"


def _fastapi_docs_config() -> dict:
    if _is_production():
        return {"docs_url": None, "redoc_url": None, "openapi_url": None}
    return {}


app = FastAPI(**_fastapi_docs_config())

DOCS_FOLDER.mkdir(exist_ok=True)
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MAX_QUESTION_CHARS = 2000
MAX_HISTORY_ITEMS = 16
MAX_HISTORY_CONTENT_CHARS = 4000
MAX_SELECTED_DOCS = 25
MIN_STUDY_COUNT = 3
MAX_STUDY_COUNT = 30
VALID_QUIZ_DIFFICULTIES = {"easy", "medium", "hard"}
VALID_BUSINESS_TASK_TYPES = {"answer_from_sources", "draft_reply", "summarize_for_team", "extract_action_items", "risk_check"}
VALID_BUSINESS_AUDIENCES = {"internal_team", "customer", "partner", "investor", "distributor", "other"}
DEMO_KEY_HEADER = "x-kroma-demo-key"
DEFAULT_GROQ_RATE_LIMIT_REQUESTS = 30
DEFAULT_GROQ_RATE_LIMIT_WINDOW_SECONDS = 10 * 60
GROQ_RATE_LIMIT_DETAIL = "Too many requests. Please try again later."
MISSING_CONTEXT_ANSWER = "That information was not found in the uploaded documents."
PUBLIC_DEMO_MAX_QUESTION_CHARS = 180
PUBLIC_DEMO_NOTE = "Public demo uses a sample document. Enter demo key to test your own files."
PUBLIC_DEMO_DOCUMENT = "kroma-public-demo.md"
PUBLIC_DEMO_QUESTIONS = [
    "What can Kroma help students and small teams do?",
    "How does Kroma show evidence for answers?",
    "Does the demo support DOCX uploads or billing workflows?",
]
PUBLIC_DEMO_SECTIONS = [
    {
        "location_label": "Overview",
        "text": (
            "Kroma is a source-grounded study assistant for students, researchers, and small teams. "
            "It helps people upload course notes, project briefs, research PDFs, text files, and Markdown notes, "
            "then ask questions, create summaries, and review study material from those sources."
        ),
    },
    {
        "location_label": "Evidence model",
        "text": (
            "Kroma is designed around trust. Answers should be based only on retrieved document context, "
            "and the interface keeps source previews, locations, and relevance scores visible so users can inspect "
            "the evidence behind a response."
        ),
    },
    {
        "location_label": "Demo limits",
        "text": (
            "This public portfolio demo uses a bundled sample document for unauthenticated visitors. "
            "Custom PDF, TXT, and Markdown upload, processing, deletion, clearing, unrestricted chat, flashcards, "
            "quiz, and summary generation require the demo key. The public demo does not support DOCX uploads, "
            "billing workflows, user accounts, or team workspaces."
        ),
    },
]
PUBLIC_DEMO_ANSWERS = {
    "what can kroma help students and small teams do?": {
        "answer": (
            "Kroma helps students, researchers, and small teams turn their own notes, briefs, PDFs, text files, "
            "and Markdown documents into grounded answers, summaries, and study material they can trace back to sources."
        ),
        "sections": [0],
    },
    "how does kroma show evidence for answers?": {
        "answer": (
            "Kroma keeps source previews, document locations, and relevance scores visible so users can inspect the "
            "evidence behind an answer instead of trusting a response blindly."
        ),
        "sections": [1],
    },
    "does the demo support docx uploads or billing workflows?": {
        "answer": (
            "No. The public sample says DOCX uploads, billing workflows, user accounts, and team workspaces are not "
            "part of this demo; custom PDF, TXT, and Markdown usage requires the demo key."
        ),
        "sections": [2],
    },
}
PDF_HEADER = b"%PDF-"
SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")
SUPPORTED_UPLOAD_LABEL = "PDF, TXT, and Markdown files"
WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
}
_groq_rate_limit_lock = threading.Lock()
_groq_rate_limit_buckets: dict[str, dict[str, float | int]] = {}


# ── Models ──────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    question: str
    history: list = []
    selected_docs: list = []


class DemoChatRequest(BaseModel):
    question: str


@app.exception_handler(RequestValidationError)
async def request_validation_error_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=400, content={"detail": "Invalid request body."})


def _demo_key_expected() -> str:
    return os.getenv("KROMA_DEMO_KEY") or ""


def _demo_key_configured() -> bool:
    return bool(_demo_key_expected())


def _has_valid_demo_key(request: Request) -> bool:
    expected = _demo_key_expected()
    if not expected:
        return True
    supplied = request.headers.get(DEMO_KEY_HEADER, "")
    return hmac.compare_digest(supplied, expected)


def _require_demo_key(request: Request) -> None:
    if not _demo_key_configured():
        return
    if not _has_valid_demo_key(request):
        raise HTTPException(status_code=401, detail="Demo key required.")


def _positive_int_env(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def _groq_rate_limit_config() -> tuple[int, int]:
    return (
        _positive_int_env("KROMA_RATE_LIMIT_REQUESTS", DEFAULT_GROQ_RATE_LIMIT_REQUESTS),
        _positive_int_env("KROMA_RATE_LIMIT_WINDOW_SECONDS", DEFAULT_GROQ_RATE_LIMIT_WINDOW_SECONDS),
    )


def _client_ip(request: Request) -> str:
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _retry_after_seconds(reset_at: float, now: float) -> int:
    remaining = reset_at - now
    if remaining <= 1:
        return 1
    retry_after = int(remaining)
    if remaining > retry_after:
        retry_after += 1
    return retry_after


def _prune_expired_rate_limit_buckets(now: float) -> None:
    for identity, bucket in list(_groq_rate_limit_buckets.items()):
        if now >= float(bucket["reset_at"]):
            _groq_rate_limit_buckets.pop(identity, None)


def _enforce_groq_rate_limit(request: Request) -> None:
    limit, window_seconds = _groq_rate_limit_config()
    now = time.monotonic()
    identity = _client_ip(request)
    with _groq_rate_limit_lock:
        _prune_expired_rate_limit_buckets(now)
        bucket = _groq_rate_limit_buckets.get(identity)
        if not bucket:
            _groq_rate_limit_buckets[identity] = {"count": 1, "reset_at": now + window_seconds}
            return

        if int(bucket["count"]) >= limit:
            retry_after = _retry_after_seconds(float(bucket["reset_at"]), now)
            raise HTTPException(
                status_code=429,
                detail=GROQ_RATE_LIMIT_DETAIL,
                headers={"Retry-After": str(retry_after)},
            )

        bucket["count"] = int(bucket["count"]) + 1


def _normalize_demo_question(question: str) -> str:
    return re.sub(r"\s+", " ", question.strip().lower())


def _public_demo_payload() -> dict:
    return {
        "available": True,
        "document": PUBLIC_DEMO_DOCUMENT,
        "note": PUBLIC_DEMO_NOTE,
        "question_limit": PUBLIC_DEMO_MAX_QUESTION_CHARS,
        "questions": PUBLIC_DEMO_QUESTIONS,
    }


def _validate_public_demo_question(question: str) -> str:
    cleaned = question.strip()
    if not cleaned:
        raise HTTPException(400, "Question is required.")
    if len(cleaned) > PUBLIC_DEMO_MAX_QUESTION_CHARS:
        raise HTTPException(400, f"Public demo questions are limited to {PUBLIC_DEMO_MAX_QUESTION_CHARS} characters.")
    allowed = {_normalize_demo_question(item) for item in PUBLIC_DEMO_QUESTIONS}
    if _normalize_demo_question(cleaned) not in allowed:
        raise HTTPException(400, "Use one of the suggested public demo questions.")
    return cleaned


def _public_demo_context_and_sources() -> tuple[str, list]:
    context_parts = []
    sources = []
    for index, section in enumerate(PUBLIC_DEMO_SECTIONS, start=1):
        label = section["location_label"]
        text = section["text"]
        context_parts.append(f"[Source: {PUBLIC_DEMO_DOCUMENT}, {label}]\n{text}")
        sources.append(
            {
                "rank": index,
                "source": PUBLIC_DEMO_DOCUMENT,
                "page": None,
                "file_type": "markdown",
                "location_type": "section",
                "location_label": label,
                "chunk_id": f"public-demo-{index}",
                "doc_chunk_id": f"{PUBLIC_DEMO_DOCUMENT}:{index}",
                "score": 100,
                "distance": 0.0,
                "preview": text[:320].replace("\n", " "),
            }
        )
    return "\n\n".join(context_parts), sources


def _upload_error(status_code: int, message: str):
    raise HTTPException(status_code=status_code, detail=message)


def _safe_upload_filename(filename: str) -> str:
    if not filename:
        _upload_error(400, "Upload must include a filename.")
    if "\x00" in filename or any(ord(ch) < 32 or ord(ch) == 127 for ch in filename):
        _upload_error(400, "Filename contains invalid characters.")
    # Reject client-supplied paths before deriving a storage name.
    if filename != PurePosixPath(filename).name or filename != PureWindowsPath(filename).name:
        _upload_error(400, "Filename must not include path separators.")
    suffix = PurePosixPath(filename).suffix.lower()
    if suffix not in SUPPORTED_DOCUMENT_EXTENSIONS:
        _upload_error(415, f"Only {SUPPORTED_UPLOAD_LABEL} are supported.")

    stem = filename[: -len(PurePosixPath(filename).suffix)].strip(" ._-")
    if not stem:
        _upload_error(400, "Filename must include a valid name before the extension.")

    safe_stem = SAFE_FILENAME_RE.sub("_", stem).strip("._-")[:80] or "upload"
    if safe_stem.upper() in WINDOWS_RESERVED_NAMES:
        safe_stem = f"upload-{uuid.uuid4().hex[:8]}"
    safe_name = f"{safe_stem}{suffix}"
    dest = DOCS_FOLDER / safe_name
    if dest.exists():
        safe_name = f"{safe_stem}-{uuid.uuid4().hex[:8]}{suffix}"
    return safe_name


def _delete_doc_target(filename: str) -> Path:
    if not filename:
        raise HTTPException(400, "Document filename is required.")
    if "\x00" in filename or any(ord(ch) < 32 or ord(ch) == 127 for ch in filename):
        raise HTTPException(400, "Filename contains invalid characters.")
    if filename != PurePosixPath(filename).name or filename != PureWindowsPath(filename).name:
        raise HTTPException(400, "Filename must not include path separators.")
    if PurePosixPath(filename).is_absolute() or PureWindowsPath(filename).is_absolute():
        raise HTTPException(400, "Filename must not be an absolute path.")
    if PurePosixPath(filename).suffix.lower() not in SUPPORTED_DOCUMENT_EXTENSIONS:
        raise HTTPException(415, f"Only {SUPPORTED_UPLOAD_LABEL} can be deleted.")

    docs_root = DOCS_FOLDER.resolve()
    target = (DOCS_FOLDER / filename).resolve()
    try:
        target.relative_to(docs_root)
    except ValueError:
        raise HTTPException(400, "Invalid document path.")
    return target


def _validate_selected_docs(selected_docs: list | None) -> list:
    if selected_docs is None:
        return []
    if not isinstance(selected_docs, list):
        raise HTTPException(400, "selected_docs must be a list.")
    if len(selected_docs) > MAX_SELECTED_DOCS:
        raise HTTPException(400, f"Select at most {MAX_SELECTED_DOCS} documents.")

    validated = []
    seen = set()
    for item in selected_docs:
        if not isinstance(item, str) or not item.strip():
            raise HTTPException(400, "selected_docs must contain document filenames.")
        name = item.strip()
        _delete_doc_target(name)
        if name not in seen:
            validated.append(name)
            seen.add(name)
    return validated


def _validate_history(history: list | None) -> list:
    if history is None:
        return []
    if not isinstance(history, list):
        raise HTTPException(400, "history must be a list.")
    if len(history) > MAX_HISTORY_ITEMS:
        raise HTTPException(400, f"Chat history is limited to {MAX_HISTORY_ITEMS} messages.")

    cleaned = []
    for msg in history:
        if not isinstance(msg, dict):
            raise HTTPException(400, "history entries must be objects.")
        role = msg.get("role")
        content = msg.get("content")
        if role not in {"user", "assistant"} or not isinstance(content, str):
            raise HTTPException(400, "history entries must include a valid role and content.")
        if len(content) > MAX_HISTORY_CONTENT_CHARS:
            raise HTTPException(400, f"history content is limited to {MAX_HISTORY_CONTENT_CHARS} characters.")
        cleaned.append({"role": role, "content": content})
    return cleaned


def _validate_chat_request(req: ChatRequest) -> tuple[str, list, list]:
    question = req.question.strip()
    if not question:
        raise HTTPException(400, "Question is required.")
    if len(question) > MAX_QUESTION_CHARS:
        raise HTTPException(400, f"Question is limited to {MAX_QUESTION_CHARS} characters.")
    return question, _validate_history(req.history), _validate_selected_docs(req.selected_docs)


def _validate_study_count(count: int, label: str) -> int:
    if isinstance(count, bool) or not isinstance(count, int):
        raise HTTPException(400, f"{label} count must be an integer.")
    if count < MIN_STUDY_COUNT or count > MAX_STUDY_COUNT:
        raise HTTPException(400, f"{label} count must be between {MIN_STUDY_COUNT} and {MAX_STUDY_COUNT}.")
    return count


def _validate_text_upload(data: bytes) -> None:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        _upload_error(415, "Uploaded text file must be UTF-8 encoded.")
    if not text.strip():
        _upload_error(400, "Uploaded text file is empty.")
    if is_control_heavy_text(text):
        _upload_error(415, "Uploaded text file appears to be binary or control-heavy.")


async def _read_supported_upload(file: UploadFile, suffix: str) -> bytes:
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if not data:
        _upload_error(400, "Uploaded file is empty.")
    if len(data) > MAX_UPLOAD_BYTES:
        _upload_error(413, "Upload exceeds the 25 MB limit.")
    if suffix == ".pdf" and not data.startswith(PDF_HEADER):
        _upload_error(415, "Uploaded file content is not a PDF.")
    if suffix in SUPPORTED_TEXT_EXTENSIONS:
        _validate_text_upload(data)
    return data
    
# ── Routes ──────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/status")
def status(request: Request):
    if _demo_key_configured() and not _has_valid_demo_key(request):
        return {
            "demo_key_required": True,
            "indexed": False,
            "stats": None,
            "docs": [],
            "public_demo": _public_demo_payload(),
        }

    stats = load_index_stats()
    return {
        "indexed": bool(stats and int(stats.get("total_chunks") or 0) > 0 and CHROMA_PATH.exists()),
        "stats": stats,
        "docs": [f.name for f in sorted(DOCS_FOLDER.iterdir()) if is_supported_document(f)],
        "demo_key_required": _demo_key_configured(),
        "public_demo": _public_demo_payload(),
    }


@app.get("/api/demo")
def public_demo_status():
    return _public_demo_payload()


@app.post("/api/demo/chat")
def public_demo_chat(req: DemoChatRequest):
    question = _validate_public_demo_question(req.question)
    context, sources = _public_demo_context_and_sources()
    demo_answer = PUBLIC_DEMO_ANSWERS[_normalize_demo_question(question)]
    answer = demo_answer["answer"]
    sources = [sources[index] for index in demo_answer["sections"]]
    show_sources = should_show_sources(question, answer, context, sources)
    return {"answer": answer, "sources": sources if show_sources else [], "show_sources": show_sources}


@app.post("/api/upload")
async def upload(request: Request, file: UploadFile = File(...)):
    _require_demo_key(request)
    safe_name = _safe_upload_filename(file.filename or "")
    suffix = PurePosixPath(safe_name).suffix.lower()
    data = await _read_supported_upload(file, suffix)
    dest = (DOCS_FOLDER / safe_name).resolve()
    docs_root = DOCS_FOLDER.resolve()
    # Defense-in-depth guard: stored uploads must remain inside docs/.
    if docs_root not in [dest, *dest.parents]:
        _upload_error(400, "Invalid upload destination.")
    try:
        with dest.open("wb") as f:
            f.write(data)
    except OSError:
        _upload_error(500, "Could not save uploaded file.")
    return {"filename": safe_name, "saved": True}


@app.post("/api/process")
def process(request: Request):
    _require_demo_key(request)
    docs = [path for path in DOCS_FOLDER.iterdir() if is_supported_document(path)]
    if not docs:
        raise HTTPException(400, "No supported documents to process.")
    try:
        stats = ingest_documents()
        return {"success": True, "stats": stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Document processing failed.")


class FlashcardRequest(BaseModel):
    selected_docs: list = []
    count: int = 8

@app.post("/api/flashcards")
def flashcards(req: FlashcardRequest, request: Request):
    _require_demo_key(request)
    _enforce_groq_rate_limit(request)
    selected_docs = _validate_selected_docs(req.selected_docs)
    count = _validate_study_count(req.count, "Flashcard")
    context, sources = retrieve_chunks("generate flashcards summary overview key concepts", n_results=15, selected_docs=selected_docs)
    if not context:
        raise HTTPException(400, "No content to generate flashcards from.")
    source_catalog = build_source_catalog(sources)
    source_context = build_source_linked_context(context, source_catalog)
    cards = generate_flashcards(
        source_context,
        count=count,
        source_ids=[source["id"] for source in source_catalog],
    )
    cards = sanitize_flashcards_source_ids(cards, source_catalog)
    return {"flashcards": cards, "sources": source_catalog}

class QuizRequest(BaseModel):
    selected_docs: list = []
    difficulty: str = "medium"
    count: int = 8

@app.post("/api/quiz")
def quiz(req: QuizRequest, request: Request):
    _require_demo_key(request)
    _enforce_groq_rate_limit(request)
    selected_docs = _validate_selected_docs(req.selected_docs)
    count = _validate_study_count(req.count, "Quiz")
    difficulty = req.difficulty.strip().lower()
    if difficulty not in VALID_QUIZ_DIFFICULTIES:
        raise HTTPException(400, "Quiz difficulty must be easy, medium, or hard.")
    context, sources = retrieve_chunks("key concepts definitions commands processes", n_results=15, selected_docs=selected_docs)
    if not context:
        raise HTTPException(400, "No content to generate quiz from.")
    source_catalog = build_source_catalog(sources)
    source_context = build_source_linked_context(context, source_catalog)
    questions = generate_quiz(
        source_context,
        difficulty=difficulty,
        count=count,
        source_ids=[source["id"] for source in source_catalog],
    )
    questions = sanitize_quiz_source_ids(questions, source_catalog)
    return {"questions": questions, "sources": source_catalog}

class SuggestRequest(BaseModel):
    selected_docs: list = []

class SummaryRequest(BaseModel):
    selected_docs: list = []

class BusinessCopilotRequest(BaseModel):
    task_type: str
    audience: str
    request: str
    selected_docs: list = []

@app.post("/api/summary")
def summary(req: SummaryRequest, request: Request):
    _require_demo_key(request)
    _enforce_groq_rate_limit(request)
    selected_docs = _validate_selected_docs(req.selected_docs)
    context, sources = retrieve_chunks("main topics overview summary key points introduction", n_results=20, selected_docs=selected_docs)
    if not context:
        raise HTTPException(400, "No content to summarize.")
    source_catalog = build_source_catalog(sources)
    source_context = build_source_linked_context(context, source_catalog)
    sections = generate_summary(
        source_context,
        source_ids=[source["id"] for source in source_catalog],
    )
    sections = sanitize_summary_source_ids(sections, source_catalog)
    if not sections:
        sections = sanitize_summary_source_ids(normalize_summary_sections("", source_context), source_catalog)
    return {"summary": {"sections": sections}, "sources": source_catalog}

@app.post("/api/suggest")
def suggest(req: SuggestRequest, request: Request):
    _require_demo_key(request)
    _enforce_groq_rate_limit(request)
    selected_docs = _validate_selected_docs(req.selected_docs)
    context, _ = retrieve_chunks(
        "main topics key concepts overview summary required skills qualifications tools frameworks bonus proposal interview rate duration job type location candidate fit",
        n_results=10,
        selected_docs=selected_docs,
    )
    if not context:
        raise HTTPException(400, "No content to generate suggestions from.")
    questions = generate_suggestions(context)
    return {"questions": questions}

@app.post("/api/chat")
def chat(req: ChatRequest, request: Request = None):
    if request is not None:
        _require_demo_key(request)
        _enforce_groq_rate_limit(request)
    question, history, selected_docs = _validate_chat_request(req)
    context, sources = retrieve_chunks(question, selected_docs=selected_docs)
    if not context.strip():
        return {"answer": MISSING_CONTEXT_ANSWER, "sources": [], "show_sources": False}
    answer = generate_answer(question, context, history)
    show_sources = should_show_sources(question, answer, context, sources)
    return {"answer": answer, "sources": sources, "show_sources": show_sources}


@app.delete("/api/docs/{filename}")
def delete_doc(filename: str, request: Request = None):
    if request is not None:
        _require_demo_key(request)
    target = _delete_doc_target(filename)
    if not target.is_file():
        raise HTTPException(404, "File not found.")
    delete_document_from_index(filename)
    target.unlink()
    return {"deleted": filename}


@app.delete("/api/library")
def clear_library(request: Request):
    _require_demo_key(request)
    gc.collect()
    for path in (CHROMA_PATH, STATS_FILE):
        try:
            if path.is_dir():
                shutil.rmtree(path)
            elif path.is_file():
                path.unlink(missing_ok=True)
        except Exception:
            continue
    for pdf in [path for path in DOCS_FOLDER.iterdir() if is_supported_document(path)]:
        try:
            pdf.unlink(missing_ok=True)
        except Exception:
            pass
    return {"cleared": True}

BUSINESS_NO_CONTEXT_RESPONSE = {
    "result": {
        "verified_facts": [],
        "suggested_draft": "",
        "missing_information": ["No relevant information was found in the selected documents."],
        "needs_human_review": {"required": True, "reasons": ["No source-grounded context available"]},
        "sources_used": [],
    },
    "sources": [],
}


@app.post("/api/business-copilot")
def business_copilot(req: BusinessCopilotRequest, request: Request):
    _require_demo_key(request)
    _enforce_groq_rate_limit(request)

    task_type = req.task_type.strip().lower()
    if task_type not in VALID_BUSINESS_TASK_TYPES:
        raise HTTPException(400, f"task_type must be one of: {', '.join(sorted(VALID_BUSINESS_TASK_TYPES))}")

    audience = req.audience.strip().lower()
    if audience not in VALID_BUSINESS_AUDIENCES:
        raise HTTPException(400, f"audience must be one of: {', '.join(sorted(VALID_BUSINESS_AUDIENCES))}")

    request_text = req.request.strip()
    if not request_text:
        raise HTTPException(400, "request is required.")
    if len(request_text) > 2000:
        raise HTTPException(400, "request is limited to 2000 characters.")

    selected_docs = _validate_selected_docs(req.selected_docs)
    context, sources = retrieve_chunks(request_text, n_results=15, selected_docs=selected_docs)
    source_catalog = build_source_catalog(sources) if sources else []
    source_context = build_source_linked_context(context, source_catalog) if context and source_catalog else ""

    if not business_context_is_relevant(sources):
        return BUSINESS_NO_CONTEXT_RESPONSE

    raw = generate_business_copilot_output(task_type, audience, request_text, source_context, source_catalog)
    normalized = normalize_business_copilot_output(raw)
    sanitized = sanitize_business_copilot_source_ids(normalized, source_catalog)

    is_empty_output = (
        not sanitized.get("verified_facts")
        and not sanitized.get("suggested_draft", "").strip()
        and not sanitized.get("missing_information")
    )
    if is_empty_output:
        sanitized["missing_information"] = ["The model response could not be verified. Please review the request manually."]
        hr = {"required": True, "reasons": ["Model output could not be verified"]}
    else:
        hr = business_needs_human_review(
            task_type, audience, request_text,
            sanitized.get("missing_information", []),
        )
    sanitized["needs_human_review"] = hr

    return {"result": sanitized, "sources": source_catalog}


class KnowledgeAuditRequest(BaseModel):
    selected_docs: list = []


KNOWLEDGE_AUDIT_NO_CONTEXT_RESPONSE = {
    "result": {
        "coverage_summary": [],
        "missing_knowledge": ["No relevant information was found in the selected documents."],
        "risk_areas": [],
        "suggested_next_documents": [],
        "automation_readiness": [
            {"category": "Keep manual", "items": ["All tasks — no source context available"]}
        ],
        "readiness_verdict": {
            "level": "Low",
            "reasons": ["No source-grounded context available"]
        },
        "sources_used": []
    },
    "sources": []
}


@app.post("/api/knowledge-audit")
def knowledge_audit(req: KnowledgeAuditRequest, request: Request):
    _require_demo_key(request)
    _enforce_groq_rate_limit(request)
    selected_docs = _validate_selected_docs(req.selected_docs)
    context, sources = retrieve_chunks("overview summary key topics policies terms procedures guidelines", n_results=20, selected_docs=selected_docs)

    source_catalog = build_source_catalog(sources) if sources else []
    source_context = build_source_linked_context(context, source_catalog) if context and source_catalog else ""

    if not business_context_is_relevant(sources):
        return KNOWLEDGE_AUDIT_NO_CONTEXT_RESPONSE

    raw = generate_knowledge_audit(source_context, source_catalog)
    normalized = normalize_knowledge_audit_output(raw)
    sanitized = sanitize_knowledge_audit_source_ids(normalized, source_catalog)
    verdict = compute_readiness_verdict(sanitized, source_context)
    sanitized["readiness_verdict"] = verdict

    return {"result": sanitized, "sources": source_catalog}


# ── Serve frontend ───────────────────────────────────────────────────────────

@app.get("/")
def landing():
    return FileResponse("static/landing.html")


def react_index_response():
    index_path = Path("frontend/dist/index.html")
    if not index_path.exists():
        return JSONResponse(
            status_code=503,
            content={"detail": "React build not found. Please run 'npm run build' in the frontend directory."}
        )
    return FileResponse(index_path)


@app.get("/app")
def app_page():
    return RedirectResponse(url="/dashboard")

@app.get("/next")
def next_page():
    return RedirectResponse(url="/dashboard")

@app.get("/dashboard")
def dashboard_page():
    return react_index_response()


assets_dir = Path("frontend/dist/assets")
if assets_dir.exists():
    app.mount("/assets", StaticFiles(directory="frontend/dist/assets"), name="assets")


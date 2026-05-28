import json
import re
import shutil
import uuid
from pathlib import Path, PurePosixPath, PureWindowsPath

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from ingest import (
    CHROMA_PATH,
    DOCS_FOLDER,
    STATS_FILE,
    SUPPORTED_DOCUMENT_EXTENSIONS,
    SUPPORTED_TEXT_EXTENSIONS,
    ingest_documents,
    is_control_heavy_text,
    is_supported_document,
    load_index_stats,
)
from rag import (
    build_source_catalog,
    build_source_linked_context,
    generate_answer,
    generate_flashcards,
    generate_quiz,
    generate_suggestions,
    generate_summary,
    normalize_summary_sections,
    retrieve_chunks,
    sanitize_flashcards_source_ids,
    sanitize_quiz_source_ids,
    sanitize_summary_source_ids,
    should_show_sources,
)

app = FastAPI()

DOCS_FOLDER.mkdir(exist_ok=True)
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
PDF_HEADER = b"%PDF-"
SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]+")
SUPPORTED_UPLOAD_LABEL = "PDF, TXT, and Markdown files"
WINDOWS_RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
}


# ── Models ──────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    question: str
    history: list = []
    selected_docs: list = []


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

@app.get("/api/status")
def status():
    stats = load_index_stats()
    return {
        "indexed": CHROMA_PATH.exists() and any(CHROMA_PATH.iterdir()) if CHROMA_PATH.exists() else False,
        "stats": stats,
        "docs": [f.name for f in sorted(DOCS_FOLDER.iterdir()) if is_supported_document(f)]
    }


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
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
def process():
    docs = [path for path in DOCS_FOLDER.iterdir() if is_supported_document(path)]
    if not docs:
        raise HTTPException(400, "No supported documents to process.")
    try:
        stats = ingest_documents()
        return {"success": True, "stats": stats}
    except Exception as e:
        raise HTTPException(500, str(e))


class FlashcardRequest(BaseModel):
    selected_docs: list = []
    count: int = 8

@app.post("/api/flashcards")
def flashcards(req: FlashcardRequest):
    context, sources = retrieve_chunks("generate flashcards summary overview key concepts", n_results=15, selected_docs=req.selected_docs)
    if not context:
        raise HTTPException(400, "No content to generate flashcards from.")
    source_catalog = build_source_catalog(sources)
    source_context = build_source_linked_context(context, source_catalog)
    cards = generate_flashcards(
        source_context,
        count=req.count,
        source_ids=[source["id"] for source in source_catalog],
    )
    cards = sanitize_flashcards_source_ids(cards, source_catalog)
    return {"flashcards": cards, "sources": source_catalog}

class QuizRequest(BaseModel):
    selected_docs: list = []
    difficulty: str = "medium"
    count: int = 8

@app.post("/api/quiz")
def quiz(req: QuizRequest):
    context, sources = retrieve_chunks("key concepts definitions commands processes", n_results=15, selected_docs=req.selected_docs)
    if not context:
        raise HTTPException(400, "No content to generate quiz from.")
    source_catalog = build_source_catalog(sources)
    source_context = build_source_linked_context(context, source_catalog)
    questions = generate_quiz(
        source_context,
        difficulty=req.difficulty,
        count=req.count,
        source_ids=[source["id"] for source in source_catalog],
    )
    questions = sanitize_quiz_source_ids(questions, source_catalog)
    return {"questions": questions, "sources": source_catalog}

class SuggestRequest(BaseModel):
    selected_docs: list = []

class SummaryRequest(BaseModel):
    selected_docs: list = []

@app.post("/api/summary")
def summary(req: SummaryRequest):
    context, sources = retrieve_chunks("main topics overview summary key points introduction", n_results=20, selected_docs=req.selected_docs)
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
def suggest(req: SuggestRequest):
    context, _ = retrieve_chunks("main topics key concepts overview summary", n_results=10, selected_docs=req.selected_docs)
    if not context:
        raise HTTPException(400, "No content to generate suggestions from.")
    questions = generate_suggestions(context)
    return {"questions": questions}

@app.post("/api/chat")
def chat(req: ChatRequest):
    context, sources = retrieve_chunks(req.question, selected_docs=req.selected_docs)
    answer = generate_answer(req.question, context, req.history)
    show_sources = should_show_sources(req.question, answer, context, sources)
    return {"answer": answer, "sources": sources, "show_sources": show_sources}


@app.delete("/api/docs/{filename}")
def delete_doc(filename: str):
    target = _delete_doc_target(filename)
    if not target.is_file():
        raise HTTPException(404, "File not found.")
    target.unlink()
    return {"deleted": filename}


@app.delete("/api/library")
def clear_library():
    import gc
    gc.collect()
    for path in (CHROMA_PATH, STATS_FILE):
        try:
            if path.is_dir():
                shutil.rmtree(path)
            elif path.is_file():
                path.unlink(missing_ok=True)
        except Exception as e:
            print(f"Could not delete {path}: {e}")
    for pdf in [path for path in DOCS_FOLDER.iterdir() if is_supported_document(path)]:
        try:
            pdf.unlink(missing_ok=True)
        except Exception:
            pass
    return {"cleared": True}

# ── Serve frontend ───────────────────────────────────────────────────────────

@app.get("/")
def landing():
    return FileResponse("static/landing.html")

@app.get("/app")
def app_page():
    return FileResponse("static/index.html")

app.mount("/static", StaticFiles(directory="static"), name="static")

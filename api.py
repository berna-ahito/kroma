import json
import shutil
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from ingest import CHROMA_PATH, DOCS_FOLDER, STATS_FILE, ingest_documents, load_index_stats
from rag import generate_answer, retrieve_chunks, generate_flashcards, generate_quiz, generate_suggestions, generate_summary

app = FastAPI()

DOCS_FOLDER.mkdir(exist_ok=True)
HISTORY_FILE = Path("chat_history.json")


# ── Models ──────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    question: str
    history: list = []
    selected_docs: list = []
    
# ── Routes ──────────────────────────────────────────────────────────────────

@app.get("/api/status")
def status():
    stats = load_index_stats()
    return {
        "indexed": CHROMA_PATH.exists() and any(CHROMA_PATH.iterdir()) if CHROMA_PATH.exists() else False,
        "stats": stats,
        "docs": [f.name for f in DOCS_FOLDER.glob("*.pdf")]
    }


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are supported.")
    dest = DOCS_FOLDER / file.filename
    with dest.open("wb") as f:
        f.write(await file.read())
    return {"filename": file.filename, "saved": True}


@app.post("/api/process")
def process():
    pdfs = list(DOCS_FOLDER.glob("*.pdf"))
    if not pdfs:
        raise HTTPException(400, "No PDFs to process.")
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
    context, _ = retrieve_chunks("generate flashcards summary overview key concepts", n_results=15, selected_docs=req.selected_docs)
    if not context:
        raise HTTPException(400, "No content to generate flashcards from.")
    cards = generate_flashcards(context, count=req.count)
    return {"flashcards": cards}

class QuizRequest(BaseModel):
    selected_docs: list = []
    difficulty: str = "medium"
    count: int = 8

@app.post("/api/quiz")
def quiz(req: QuizRequest):
    context, _ = retrieve_chunks("key concepts definitions commands processes", n_results=15, selected_docs=req.selected_docs)
    if not context:
        raise HTTPException(400, "No content to generate quiz from.")
    questions = generate_quiz(context, difficulty=req.difficulty, count=req.count)
    return {"questions": questions}

class SuggestRequest(BaseModel):
    selected_docs: list = []

class SummaryRequest(BaseModel):
    selected_docs: list = []

@app.post("/api/summary")
def summary(req: SummaryRequest):
    context, _ = retrieve_chunks("main topics overview summary key points introduction", n_results=20, selected_docs=req.selected_docs)
    if not context:
        raise HTTPException(400, "No content to summarize.")
    result = generate_summary(context)
    return {"summary": result}

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
    return {"answer": answer, "sources": sources}


@app.delete("/api/docs/{filename}")
def delete_doc(filename: str):
    target = DOCS_FOLDER / filename
    if not target.exists():
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
    for pdf in DOCS_FOLDER.glob("*.pdf"):
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
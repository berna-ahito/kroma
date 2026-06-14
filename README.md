<div align="center">

<img src="assets/kroma-logo.svg" alt="Kroma" width="340">

### Ask your documents questions. Get answers with sources.

Kroma turns PDF, TXT, and Markdown files into answers, summaries, flashcards, quizzes, and document audits. It shows the source context behind answers so you can check where the information came from.

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.136-009688?logo=fastapi&logoColor=white)
![LangChain RAG](https://img.shields.io/badge/LangChain%20%2F%20RAG-retrieval--grounded-1C3C3C)
![ChromaDB](https://img.shields.io/badge/ChromaDB-vector%20store-5B5BD6)
![Groq](https://img.shields.io/badge/Groq-LLM%20inference-F55036)
![Status](https://img.shields.io/badge/status-active%20build-2563EB)

**Built by:** [Claire Ahito](https://github.com/berna-ahito) · 2026

[Live Demo](https://kroma-knyd.onrender.com) · [Features](#features) · [Architecture](#architecture) · [Run Locally](#run-locally)

</div>

---

## Live demo

**[https://kroma-knyd.onrender.com](https://kroma-knyd.onrender.com)**

The public demo includes a bundled sample document you can query immediately. Custom uploads and LLM-backed document actions require a demo key.

> **Note:** Hosted on Render Free. First request after inactivity may take a few seconds due to a cold start. Uploaded files and indexes are ephemeral — not persisted between restarts.

## What is Kroma?

Kroma is a document intelligence app for working with your own files. Upload notes, readings, research files, briefs, or Markdown documents, then ask questions in plain language.

You can use Kroma to summarize key points, make study materials, generate flashcards and quizzes, or run an audit that shows what your document library does and does not cover.

Kroma focuses on inspectable, source-backed answers. Instead of hiding the evidence, it shows source cards and context so you can review the passages behind an answer.

Supported uploads: **PDF, TXT, Markdown (`.md`, `.markdown`)** — UTF-8 or UTF-8-SIG encoded.

## Preview

| Chat with sources |
|---|
| ![Kroma chat answer with source cards](assets/kroma-chat-sources.png) |

## Features

| Feature | What it does |
|---|---|
| Ask your documents | Upload your own files and ask questions across them. Kroma answers using retrieved context from your document library. |
| Check the source | Source cards show document location, passage previews, and relevance scores so you can inspect the evidence behind an answer. |
| Make study materials | Generate summaries, flashcards, quizzes, and study suggestions from your uploaded sources. Export study output to PDF from the browser. |
| Use Knowledge Copilot | Draft replies, summarize for a team, extract action items, or run a risk check with outputs grounded in your documents. |
| Run a Knowledge Audit | Review coverage gaps, missing knowledge areas, risk zones, next document suggestions, and AI-readiness scoring for your library. |
| Safer demo mode | Custom uploads and LLM-backed actions can be gated by `KROMA_DEMO_KEY`; the bundled sample document and suggested questions remain public. |

## Architecture

```mermaid
flowchart LR
    A[PDF / TXT / Markdown upload] --> B[FastAPI upload validation]
    B --> C[Text extraction]
    C --> D[Chunking]
    D --> E[SentenceTransformers embeddings]
    E --> F[(ChromaDB local vector store)]

    G[Question / study request / Knowledge Copilot task / Knowledge Audit] --> H[FastAPI API routes]
    H --> I[Hybrid retrieval: vector + keyword + RRF]
    F --> I
    I --> J[Retrieved context + source catalog]
    J --> K[Groq-hosted Llama model]
    K --> L[Answer / study tools / knowledge output / audit report]
    J --> M[Source cards and source-linked UI]
    L --> M
```

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Python · FastAPI |
| AI / LLM | Groq (current); adaptable to other LangChain-compatible chat model providers |
| RAG pipeline | LangChain · ChromaDB · hybrid semantic + keyword retrieval with RRF |
| Embeddings | BAAI/bge-small-en-v1.5 · SentenceTransformers |
| Document processing | PyPDF · UTF-8 text/Markdown |
| Frontend | React 18 · Vite |
| Evals | Deterministic Python smoke evals |

## Routes

| Route | Behavior |
|---|---|
| `/` | Landing page |
| `/dashboard` | React app |
| `/app`, `/next` | Redirect to `/dashboard` |
| `/api/*` | Backend endpoints |
| `/assets/*` | Built Vite assets |
| `/docs`, `/redoc`, `/openapi.json` | Disabled in production (`APP_ENV=production`) |

## Run locally

Prerequisites: Python 3.10+, Node.js, and a Groq API key.

```powershell
git clone https://github.com/berna-ahito/kroma.git
cd kroma

py -m venv venv
.\venv\Scripts\Activate.ps1
.\venv\Scripts\python.exe -m pip install -r requirements.txt

Copy-Item .env.example .env
notepad .env
```

Set `GROQ_API_KEY` in `.env`, then start the backend:

```powershell
.\venv\Scripts\python.exe -m uvicorn backend.api:app --reload --port 8000
```

For frontend development (Vite dev server):

```powershell
cd frontend
npm install
npm run dev
```

For production-like local routing through FastAPI:

```powershell
cd frontend
npm run build
cd ..
.\venv\Scripts\python.exe -m uvicorn backend.api:app --reload --port 8000
```

Visit `http://localhost:8000` for the landing page and `http://localhost:8000/dashboard` for the app.

## Running evals

```powershell
.\venv\Scripts\python.exe evals\trust_behavior.py
```

Checks source display behavior, upload/delete validation, source ID sanitization, no-context responses, Knowledge Copilot safeguards, and Knowledge Audit readiness scoring.

## Project structure

```text
kroma/
├── backend/
│   ├── __init__.py
│   ├── api.py          # FastAPI routes, upload handling, chat, study, Copilot, and Audit APIs
│   ├── rag.py          # Retrieval, source handling, Groq generation
│   └── ingest.py       # Document loading, chunking, embeddings, ChromaDB writes
├── frontend/
│   ├── src/            # React dashboard source
│   └── dist/           # Generated by build; ignored by git
├── static/
│   └── landing.html    # Landing page served at /
├── assets/             # Logo and screenshots
├── evals/
│   └── trust_behavior.py
├── Dockerfile
├── render.yaml
├── requirements.txt
└── README.md
```

## Deployment notes

Kroma deploys to Render as a Docker Web Service. The Docker image builds `frontend/dist` in a Node stage, copies assets into the Python runtime image, and runs:

```
uvicorn backend.api:app --host 0.0.0.0 --port ${PORT:-8000}
```

No `--reload` in production.

### Environment variables

| Variable | Purpose |
|---|---|
| `GROQ_API_KEY` | Required for LLM-backed chat, study tools, Knowledge Copilot, and Knowledge Audit. |
| `KROMA_DEMO_KEY` | Optional key for protected custom-document demo actions. |
| `APP_ENV` | Set to `production` to disable `/docs`, `/redoc`, and `/openapi.json`. `render.yaml` sets this automatically. |
| `KROMA_RATE_LIMIT_REQUESTS` | Optional request cap for Groq-backed endpoints. |
| `KROMA_RATE_LIMIT_WINDOW_SECONDS` | Optional rate-limit window (seconds). |

### Render Free caveats

- Uploaded files, Chroma indexes, index metadata, and embedding model cache are ephemeral. For persistent use, mount `docs/`, `chroma_db/`, `chroma_db_next/`, and `index_stats.json` on a disk or external service.
- Cold starts can delay the first request after inactivity.
- The embedding model (`BAAI/bge-small-en-v1.5`) may download on the first `/api/process` call.
- `GET /health` returns `{"status": "ok"}` and is always public.

### Demo key behavior

When `KROMA_DEMO_KEY` is set, uploads, processing, deletion, library clearing, unrestricted chat, study generation, Knowledge Copilot, and Knowledge Audit all require the `X-Kroma-Demo-Key` header. The landing page, dashboard, health check, and bundled sample document remain publicly accessible.

## Product direction

Kroma is built around a simple idea: AI answers from your own documents should be easy to inspect.

The current version supports document chat, study tools, knowledge workflows, and coverage audits. The roadmap focuses on making Kroma more useful for real teams: persistent document libraries, richer audit reports, shareable knowledge bases, and integrations with tools that organizations already use.

## Contact

**GitHub:** [berna-ahito](https://github.com/berna-ahito)  
**LinkedIn:** [bernadeth-ahito](https://www.linkedin.com/in/bernadeth-ahito/)  
**Location:** Cebu, Philippines

# RAG Knowledge Agent

## What this project is

A RAG (Retrieval-Augmented Generation) system that lets users upload documents and ask questions about them. Answers are grounded in retrieved document chunks, with sources shown in the UI.

## Stack

- Python 3.12.5
- FastAPI — backend API and static file serving
- React 18 + Vite — active frontend dashboard
- LangChain — document loading, chunking, embeddings, and vector-store integration
- ChromaDB — vector database (stores document embeddings locally)
- Groq API (default model: meta-llama/llama-4-scout-17b-16e-instruct) — LLM for answering questions
- sentence-transformers — local embeddings (free, no API needed)
- pypdf — PDF reading

## Routes

- `/` — landing page
- `/dashboard` — React dashboard app
- `/app` — redirects to `/dashboard`
- `/next` — redirects to `/dashboard`
- `/api/*` — backend endpoints
- `/assets/*` — built React assets from `frontend/dist`

## Project structure

- api.py — FastAPI backend, upload/chat/process routes, static pages
- ingest.py — loads documents, creates embeddings, stores in ChromaDB
- rag.py — handles querying ChromaDB and sending to Groq
- frontend/src/ — active React dashboard source
- frontend/dist/ — generated Vite build output; ignored by git
- static/ — legacy static app files; unrouted and not the active app
- docs/ — folder where user puts their documents
- .env — stores environment variables; never print values
- chroma_db/ — auto-created, stores the vector database
- chroma_db_next/ — alternate/new vector database path used during index transitions
- index_stats.json — local index metadata

## How it works

1. User uploads a PDF, TXT, or Markdown file through the React dashboard.
2. ingest.py splits it into chunks, converts to embeddings, stores in ChromaDB
3. User asks a question in the React UI served by FastAPI from `/dashboard`
4. rag.py finds relevant chunks from ChromaDB
5. Groq answers the question using those chunks as context, and the UI shows sources

## Local development

Backend:

```powershell
.\venv\Scripts\python.exe -m uvicorn api:app --reload --port 8000
```

Frontend Vite dev server:

```powershell
cd frontend
npm run dev
```

Production-like local FastAPI route:

```powershell
cd frontend
npm run build
cd ..
.\venv\Scripts\python.exe -m uvicorn api:app --reload --port 8000
```

## Deployment

- Docker builds `frontend/dist` automatically in a frontend builder stage.
- `frontend/dist` is generated during build and ignored by git.
- Production Uvicorn command does not use `--reload`.
- Persist `docs/`, `chroma_db/`, `chroma_db_next/`, and `index_stats.json` on a disk/volume for real deployed use.

## Environment

- `GROQ_API_KEY` is required for LLM-backed features.
- `KROMA_DEMO_KEY` is optional for protected demo/custom document actions.
- `APP_ENV=production` disables `/docs`, `/redoc`, and `/openapi.json`.
- `KROMA_RATE_LIMIT_REQUESTS` and `KROMA_RATE_LIMIT_WINDOW_SECONDS` optionally tune Groq-backed endpoint rate limits.

## Key decisions

- Using sentence-transformers for embeddings (free, runs locally, no API cost)
- ChromaDB persists to disk so documents don't need re-ingesting every run
- Groq model: meta-llama/llama-4-scout-17b-16e-instruct by default, configurable with `GROQ_MODEL`

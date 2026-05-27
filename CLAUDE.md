# RAG Knowledge Agent

## What this project is

A RAG (Retrieval-Augmented Generation) system that lets users upload documents and ask questions about them. Answers are grounded in retrieved document chunks, with sources shown in the UI.

## Stack

- Python 3.12.5
- FastAPI — backend API and static file serving
- Vanilla HTML/CSS/JS — frontend
- LangChain — document loading, chunking, embeddings, and vector-store integration
- ChromaDB — vector database (stores document embeddings locally)
- Groq API (default model: meta-llama/llama-4-scout-17b-16e-instruct) — LLM for answering questions
- sentence-transformers — local embeddings (free, no API needed)
- pypdf — PDF reading

## Project structure

- api.py — FastAPI backend, upload/chat/process routes, static pages
- ingest.py — loads documents, creates embeddings, stores in ChromaDB
- rag.py — handles querying ChromaDB and sending to Groq
- static/index.html — main app UI
- static/landing.html — landing page
- docs/ — folder where user puts their documents
- .env — stores GROQ_API_KEY
- chroma_db/ — auto-created, stores the vector database

## How it works

1. User drops a PDF into docs/
2. ingest.py splits it into chunks, converts to embeddings, stores in ChromaDB
3. User asks a question in the static web UI served by FastAPI
4. rag.py finds relevant chunks from ChromaDB
5. Groq answers the question using those chunks as context, and the UI shows sources

## Key decisions

- Using sentence-transformers for embeddings (free, runs locally, no API cost)
- ChromaDB persists to disk so documents don't need re-ingesting every run
- Groq model: meta-llama/llama-4-scout-17b-16e-instruct by default, configurable with `GROQ_MODEL`

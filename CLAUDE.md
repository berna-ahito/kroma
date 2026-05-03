# RAG Knowledge Agent

## What this project is

A RAG (Retrieval-Augmented Generation) system that lets users upload documents and ask questions about them. The AI answers based only on the document content, not from general knowledge.

## Stack

- Python 3.12.5
- LangChain — document loading and chaining
- ChromaDB — vector database (stores document embeddings locally)
- Groq API (llama-3.3-70b-versatile) — LLM for answering questions
- sentence-transformers — local embeddings (free, no API needed)
- Streamlit — web UI
- pypdf — PDF reading

## Project structure

- app.py — main Streamlit UI
- ingest.py — loads documents, creates embeddings, stores in ChromaDB
- rag.py — handles querying ChromaDB and sending to Groq
- docs/ — folder where user puts their documents
- .env — stores GROQ_API_KEY
- chroma_db/ — auto-created, stores the vector database

## How it works

1. User drops a PDF into docs/
2. ingest.py splits it into chunks, converts to embeddings, stores in ChromaDB
3. User asks a question in Streamlit UI
4. rag.py finds relevant chunks from ChromaDB
5. Groq answers the question using those chunks as context

## Key decisions

- Using sentence-transformers for embeddings (free, runs locally, no API cost)
- ChromaDB persists to disk so documents don't need re-ingesting every run
- Groq model: llama-3.3-70b-versatile (stable production model)

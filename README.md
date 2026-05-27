# Kroma — Ask. Learn. Know.

AI that reads your documents, not the internet. Ask questions, generate flashcards, and quiz yourself from your own PDFs. Built with FastAPI, LangChain, Groq, and RAG.

**Live demo:** coming soon  
**Built by:** [Claire Ahito](https://github.com/berna-ahito) · CIT-U Cebu · 2026

---

## What it does

Most people drown in documents — reports, lecture slides, research papers. They highlight. They re-read. They still miss things.

Kroma flips that. Upload your files, ask your question, and get an answer grounded in retrieved chunks from your actual documents, with sources shown in the app.

| Feature | Description |
|---|---|
| 💬 Document Chat | Ask questions and get answers grounded in retrieved chunks from uploaded files |
| ⚡ Flashcard Generator | Auto-generate Q&A cards with source links when available |
| 🧠 Quiz Mode | AI-generated multiple choice questions — Easy, Medium, or Hard |
| 📋 Smart Summary | One-click structured summary with key topics and takeaways |
| 🎯 Source Cards | See retrieved chunks, pages, and relevance scores behind answers |
| 🎯 Source Filtering | Choose exactly which documents to query |
| ↓ Export to PDF | Save your full chat session as a clean PDF |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python · FastAPI |
| AI / LLM | Groq API · Llama 4 Scout |
| RAG Pipeline | LangChain · ChromaDB |
| Embeddings | BAAI/bge-small-en-v1.5 · SentenceTransformers |
| PDF Processing | PyPDF |
| Frontend | Vanilla HTML · CSS · JS |

---

## How it works

```
PDF Upload → Text Extraction → Chunking → Vector Embeddings → ChromaDB
                                                                    ↓
User Question → Semantic Search → Top K Chunks → Groq (Llama 4 Scout) → Answer
```

1. PDFs are split into chunks and converted into vector embeddings
2. Embeddings are stored in ChromaDB (local vector database)
3. When you ask a question, ChromaDB finds the most semantically similar chunks
4. Those chunks are sent to Groq as context
5. Groq answers from the retrieved context, and the app shows the source chunks used

Uploads are limited to PDF files up to 25 MB each.

---

## Running locally

**Prerequisites:** Python 3.10+, Groq API key

```powershell
# Clone the repo
git clone https://github.com/berna-ahito/kroma.git
cd kroma

# Create virtual environment
py -m venv venv
.\venv\Scripts\Activate.ps1

# Install dependencies
.\venv\Scripts\python.exe -m pip install -r requirements.txt

# Create .env from the example, then add your Groq API key
Copy-Item .env.example .env
notepad .env

# Run the app
.\venv\Scripts\python.exe -m uvicorn api:app --reload --port 8000
```

Visit `http://localhost:8000` for the landing page and `http://localhost:8000/app` for the app.

Hosted demos on free tiers may take a short cold start after inactivity.

## Running evals

```powershell
.\venv\Scripts\python.exe evals\trust_behavior.py
```

---

## Project structure

```
kroma/
├── api.py            # FastAPI backend — routes, upload, chat, process
├── rag.py            # RAG pipeline — retrieval, Groq integration
├── ingest.py         # PDF ingestion — chunking, embeddings, ChromaDB
├── static/
│   ├── index.html    # Main app UI
│   └── landing.html  # Landing page
├── requirements.txt
└── CLAUDE.md         # Claude Code context file
```

---

## Why I built this

This is Build 1 of my AI engineering portfolio. I am a 4th-year BSIT student at CIT-U Cebu targeting AI and automation roles.

Kroma demonstrates:
- End-to-end RAG pipeline implementation from scratch
- FastAPI backend with PDF file handling and JSON API responses
- Vector database integration with ChromaDB
- LLM integration via Groq API
- Clean product thinking — landing page, features, UX

**Next builds:** Lead Qualification Agent (n8n + Groq) · Content Repurposing Pipeline · Voice AI Agent (VAPI) · Multi-Agent Research Writer (LangGraph)

---

## Contact

**GitHub:** [berna-ahito](https://github.com/berna-ahito)  
**LinkedIn:** [bernadeth-ahito](https://www.linkedin.com/in/bernadeth-ahito/)  
**Location:** Cebu, Philippines

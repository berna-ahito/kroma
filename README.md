# Kroma — Ask. Learn. Know.

AI that reads your documents, not the internet. Ask questions, generate flashcards, and quiz yourself from your own PDFs. Built with FastAPI, LangChain, Groq, and RAG.

**Live demo:** coming soon  
**Built by:** [Claire Ahito](https://github.com/berna-ahito) · CIT-U Cebu · 2026

---

## What it does

Most people drown in documents — reports, lecture slides, research papers. They highlight. They re-read. They still miss things.

Kroma flips that. Upload your files, ask your question, get a direct answer sourced from your actual documents. No hallucination. No internet noise.

| Feature | Description |
|---|---|
| 💬 Document Chat | Ask anything. Answers sourced only from your uploaded files |
| ⚡ Flashcard Generator | Auto-generate Q&A cards from any document |
| 🧠 Quiz Mode | AI-generated multiple choice questions — Easy, Medium, or Hard |
| 📋 Smart Summary | One-click structured summary with key topics and takeaways |
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
5. Groq answers based only on your document content

---

## Running locally

**Prerequisites:** Python 3.10+, Groq API key

```bash
# Clone the repo
git clone https://github.com/berna-ahito/kroma.git
cd kroma

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Mac/Linux

# Install dependencies
pip install -r requirements.txt

# Create .env file and add your Groq API key
# GROQ_API_KEY=your_key_here

# Run the app
uvicorn api:app --reload --port 8000
```

Visit `http://localhost:8000` for the landing page and `http://localhost:8000/app` for the app.

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
- FastAPI backend with file handling and streaming
- Vector database integration with ChromaDB
- LLM integration via Groq API
- Clean product thinking — landing page, features, UX

**Next builds:** Lead Qualification Agent (n8n + Groq) · Content Repurposing Pipeline · Voice AI Agent (VAPI) · Multi-Agent Research Writer (LangGraph)

---

## Contact

**GitHub:** [berna-ahito](https://github.com/berna-ahito)  
**LinkedIn:** [bernadeth-ahito](https://www.linkedin.com/in/bernadeth-ahito/)  
**Location:** Cebu, Philippines

import os
from pathlib import Path
from typing import Callable

from dotenv import load_dotenv
from groq import Groq
from langchain_community.embeddings import SentenceTransformerEmbeddings
from langchain_community.vectorstores import Chroma

import json
import re
from ingest import EMBEDDING_MODEL, load_index_stats


load_dotenv()
os.environ.setdefault("HF_HUB_OFFLINE", "0")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "0")

BASE_DIR = Path(__file__).resolve().parent
CHROMA_PATH = BASE_DIR / "chroma_db"
GROQ_MODEL = os.getenv("GROQ_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")


def _emit(progress_callback: Callable | None, event: str, payload: dict | None = None) -> None:
    if progress_callback:
        progress_callback(event, payload or {})


def _confidence_from_distance(distance: float) -> int:
    try:
        value = float(distance)
    except (TypeError, ValueError):
        return 0
    if value < 0:
        return 0
    # Chroma returns a distance, where lower is better. This maps it to an
    # intuitive relevance percentage while preserving useful separation.
    return max(0, min(100, round(100 / (1 + value))))


def retrieve_chunks(question: str, n_results: int = 10, progress_callback: Callable | None = None, selected_docs: list | None = None):
    """
    Search the vector store for relevant chunks.

    Returns (context_str, sources). Each source has source, page, chunk ids,
    score, distance, and preview fields for UI display.
    """
    if not CHROMA_PATH.exists():
        _emit(progress_callback, "missing_index", {"message": "No local vector index found."})
        return "", []

    stats = load_index_stats() or {}
    _emit(
        progress_callback,
        "prepare",
        {
            "doc_count": len(stats.get("docs", [])),
            "total_chunks": stats.get("total_chunks", 0),
            "n_results": n_results,
        },
    )

    embeddings = SentenceTransformerEmbeddings(model_name=EMBEDDING_MODEL)
    vectorstore = Chroma(persist_directory=str(CHROMA_PATH), embedding_function=embeddings)

    _emit(progress_callback, "search", {"message": "Query embedded. Searching nearest chunks."})
    try:
        if selected_docs:
            results = vectorstore.similarity_search_with_score(
                question, k=n_results,
                filter={"source": {"$in": selected_docs}}
            )
        else:
            results = vectorstore.similarity_search_with_score(question, k=n_results)
    except Exception as exc:
        _emit(progress_callback, "error", {"message": str(exc)})
        return "", []

    if not results:
        _emit(progress_callback, "empty", {"message": "No chunks matched the question."})
        return "", []

    context_parts = []
    sources = []
    for rank, (doc, distance) in enumerate(results, start=1):
        src = Path(doc.metadata.get("source", "unknown")).name
        page = int(doc.metadata.get("page", 0)) + 1
        chunk_id = doc.metadata.get("chunk_id")
        doc_chunk_id = doc.metadata.get("doc_chunk_id")
        score = _confidence_from_distance(float(distance))

        context_parts.append(
            f"[Source: {src}, page {page}]\n"
            f"{doc.page_content}"
        )

        source = {
            "rank": rank,
            "source": src,
            "page": page,
            "chunk_id": chunk_id,
            "doc_chunk_id": doc_chunk_id,
            "score": score,
            "distance": round(float(distance), 4),
            "preview": doc.page_content[:320].replace("\n", " "),
        }
        sources.append(source)
        _emit(progress_callback, "candidate", source)

    _emit(progress_callback, "complete", {"matches": len(sources)})
    return "\n\n".join(context_parts), sources


def _groq_client() -> Groq:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is missing. Add it to .env before asking questions.")
    return Groq(api_key=api_key)


def generate_answer(
    question: str,
    context: str,
    chat_history: list | None = None,
) -> str:
    """
    Call Groq with retrieved context and prior conversation history.
    Returns the answer string.
    """
    messages = [
        {
            "role": "system",
            "content": (
                "You are Kroma, a document intelligence assistant. "
                "Answer questions directly and concisely using only the supplied document context. "
                "Never mention filenames, document names, page numbers, chunk numbers, or any technical retrieval details in your response. "
                "If someone greets you or asks something unrelated, reply in one short sentence and invite them to ask a question. "
                "If the answer is not in the documents, say so in one sentence. "
                "Never list or reference the names of uploaded files."
            ),
        }
    ]

    if chat_history:
        for msg in chat_history[-16:]:
            role = msg.get("role")
            content = msg.get("content")
            if role in {"user", "assistant"} and content:
                messages.append({"role": role, "content": content})

    if context:
        messages.append(
            {
                "role": "user",
                "content": f"[Document context]\n{context}\n\n[Question]\n{question}",
            }
        )
    else:
        messages.append({"role": "user", "content": question})

    response = _groq_client().chat.completions.create(
        model=GROQ_MODEL,
        messages=messages,
        temperature=0.1,
    )
    return response.choices[0].message.content


def query_documents(question: str, chat_history: list | None = None, n_results: int = 5):
    context, sources = retrieve_chunks(question, n_results)
    if not context and not chat_history:
        return "No relevant information found in the documents.", []
    answer = generate_answer(question, context, chat_history)
    return answer, sources


def generate_quiz(context: str, difficulty: str = "medium", count: int = 8) -> list:
    difficulty_instruction = {
        "easy": "Questions must be simple recall — 'What is X?' or 'What does X do?' format. Wrong answer choices must be obviously incorrect.",
        "medium": "Questions must require understanding — 'Why would you use X?' or 'What happens when Y?'. Wrong choices must be plausible but clearly incorrect on reflection.",
        "hard": "Questions must require inference and cross-concept reasoning — combining two or more ideas, edge cases, or 'what would happen if' scenarios. All wrong choices must be believable and tricky."
    }.get(difficulty, "medium")

    messages = [
        {
            "role": "system",
            "content": (
                f"You are a quiz generator. Given document context, generate exactly {count} multiple choice questions. "
                "Respond ONLY with a valid JSON array, no markdown, no explanation, no backticks. "
                "Format: [{\"question\": \"...\", \"choices\": [\"A. ...\", \"B. ...\", \"C. ...\", \"D. ...\"], \"answer\": \"A\", \"explanation\": \"...\"}, ...] "
                "The answer field must be just the letter A, B, C, or D. "
                f"Difficulty level: {difficulty}. {difficulty_instruction}"
            )
        },
        {
            "role": "user",
            "content": f"[Document context]\n{context}\n\nGenerate {count} quiz questions from this content."
        }
    ]
    response = _groq_client().chat.completions.create(
        model=GROQ_MODEL,
        messages=messages,
        temperature=0.4,
    )
    raw = response.choices[0].message.content.strip()
    raw = re.sub(r'```json|```', '', raw).strip()
    try:
        return json.loads(raw)
    except Exception:
        match = re.search(r'\[.*\]', raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except Exception:
                pass
        return []

def generate_summary(context: str) -> str:
    messages = [
        {
            "role": "system",
            "content": (
                "You are a document summarizer. Given document context, produce a clean structured summary. "
                "Format your response in markdown with these sections: "
                "## Overview (2-3 sentences), "
                "## Key Topics (bullet points), "
                "## Main Takeaways (3-5 bullet points). "
                "Be concise and professional. Never mention filenames or technical details."
            )
        },
        {
            "role": "user",
            "content": f"[Document context]\n{context}\n\nSummarize this content."
        }
    ]
    response = _groq_client().chat.completions.create(
        model=GROQ_MODEL,
        messages=messages,
        temperature=0.2,
    )
    return response.choices[0].message.content

def generate_suggestions(context: str) -> list:
    messages = [
        {
            "role": "system",
            "content": (
                "You are a document assistant. Given document context, generate exactly 3 interesting questions a user might want to ask. "
                "Respond ONLY with a valid JSON array of strings, no markdown, no explanation, no backticks. "
                "Format: [\"Question 1?\", \"Question 2?\", \"Question 3?\"] "
                "Make questions specific, useful, and varied — one factual, one analytical, one practical."
            )
        },
        {
            "role": "user",
            "content": f"[Document context]\n{context}\n\nGenerate 3 suggested questions."
        }
    ]
    response = _groq_client().chat.completions.create(
        model=GROQ_MODEL,
        messages=messages,
        temperature=0.4,
    )
    raw = response.choices[0].message.content.strip()
    raw = re.sub(r'```json|```', '', raw).strip()
    try:
        return json.loads(raw)
    except Exception:
        match = re.search(r'\[.*\]', raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except Exception:
                pass
        return []

def generate_flashcards(context: str, count: int = 8) -> list:
    messages = [
        {
            "role": "system",
            "content": (
                f"You are a flashcard generator. Given document context, generate exactly {count} flashcards. "
                "Respond ONLY with a valid JSON array, no markdown, no explanation, no backticks, no trailing commas. "
                "Format: [{\"question\": \"...\", \"answer\": \"...\"}, ...] "
                "Questions should test understanding, not just recall. Keep answers concise under 2 sentences. "
                "Ensure all strings are properly escaped and the JSON is valid."
            )
        },
        {
            "role": "user",
            "content": f"[Document context]\n{context}\n\nGenerate {count} flashcards from this content."
        }
    ]
    response = _groq_client().chat.completions.create(
        model=GROQ_MODEL,
        messages=messages,
        temperature=0.1,
    )
    raw = response.choices[0].message.content.strip()
    raw = re.sub(r'```json|```', '', raw).strip()
    try:
        return json.loads(raw)
    except Exception:
        match = re.search(r'\[.*\]', raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except Exception:
                pass
        return []

if __name__ == "__main__":
    q = input("Ask a question: ")
    answer, srcs = query_documents(q)
    print(f"\nAnswer: {answer}")
    print(f"Sources: {srcs}")

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


SMALL_TALK_RE = re.compile(
    r"^\s*("
    r"hi|hello|hey|yo|howdy|good\s+(morning|afternoon|evening)|"
    r"thanks|thank\s+you|thx|ok|okay|cool|great|nice|bye|goodbye|"
    r"how\s+are\s+you|who\s+are\s+you|what\s+can\s+you\s+do"
    r")\s*[.!?]*\s*$",
    re.IGNORECASE,
)

UNGROUNDED_ANSWER_RE = re.compile(
    r"("
    r"not\s+(mentioned|provided|contained|included|stated|specified|found|available)\s+in\s+(the\s+)?((provided|supplied)\s+)?(documents?|context)|"
    r"(documents?|context)\s+(does\s+not|doesn.?t|do\s+not|don.?t)\s+(mention|provide|contain|include|state|specify)|"
    r"(provided|supplied)\s+(documents?|context)\s+(does\s+not|doesn.?t|do\s+not|don.?t)\s+(mention|provide|contain|include|state|specify)|"
    r"answer\s+is\s+not\s+in\s+(the\s+)?documents?|"
    r"no\s+relevant\s+information|"
    r"i\s+(do\s+not|don.?t|cannot|can.?t)\s+(see|find)\s+"
    r")",
    re.IGNORECASE,
)


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


def should_show_sources(question: str, answer: str, context: str, sources: list) -> bool:
    """
    Lightweight display guard for source cards.

    This is a deterministic UI safety check, not a full faithfulness evaluator
    or hallucination-prevention system.
    """
    if not context.strip() or not sources:
        return False
    if SMALL_TALK_RE.search(question or ""):
        return False
    if UNGROUNDED_ANSWER_RE.search(answer or ""):
        return False
    return True


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


def generate_quiz(context: str, difficulty: str = "medium", count: int = 8, source_ids: list | None = None) -> list:
    difficulty_instruction = {
        "easy": "Questions must be simple recall — 'What is X?' or 'What does X do?' format. Wrong answer choices must be obviously incorrect.",
        "medium": "Questions must require understanding — 'Why would you use X?' or 'What happens when Y?'. Wrong choices must be plausible but clearly incorrect on reflection.",
        "hard": "Questions must require inference and cross-concept reasoning — combining two or more ideas, edge cases, or 'what would happen if' scenarios. All wrong choices must be believable and tricky."
    }.get(difficulty, "medium")
    allowed_source_ids = source_ids or []
    source_instruction = ""
    if allowed_source_ids:
        source_instruction = (
            f" Each question may include source_ids using only these IDs: {', '.join(allowed_source_ids)}. "
            "Use an empty source_ids array if no supplied source directly supports the explanation. "
            "Do not include filenames, page numbers, previews, or any source metadata."
        )

    messages = [
        {
            "role": "system",
            "content": (
                f"You are a quiz generator. Given document context, generate exactly {count} multiple choice questions. "
                "Respond ONLY with a valid JSON array, no markdown, no explanation, no backticks. "
                "Format: [{\"question\": \"...\", \"choices\": [\"A. ...\", \"B. ...\", \"C. ...\", \"D. ...\"], \"answer\": \"A\", \"explanation\": \"...\", \"source_ids\": [\"s1\"]}, ...] "
                "The answer field must be just the letter A, B, C, or D. "
                f"Difficulty level: {difficulty}. {difficulty_instruction}"
                f"{source_instruction}"
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

def generate_summary(context: str, source_ids: list | None = None) -> list:
    allowed_source_ids = source_ids or []
    source_instruction = ""
    if allowed_source_ids:
        source_instruction = (
            f"Use source_ids only from this list: {', '.join(allowed_source_ids)}. "
            "Use an empty source_ids array when a section or bullet is not directly supported by a supplied source. "
            "Do not include filenames, page numbers, previews, or any source metadata."
        )

    messages = [
        {
            "role": "system",
            "content": (
                "You are a document summarizer. Given document context, produce a clean structured summary. "
                "Respond ONLY with a valid JSON array, no markdown, no explanation, no backticks. "
                "Format: [{\"heading\":\"Overview\",\"text\":\"2-3 concise sentences\",\"source_ids\":[\"s1\"],\"bullets\":[]},"
                "{\"heading\":\"Key Topics\",\"text\":\"\",\"source_ids\":[],\"bullets\":[{\"text\":\"...\",\"source_ids\":[\"s1\"]}]},"
                "{\"heading\":\"Main Takeaways\",\"text\":\"\",\"source_ids\":[],\"bullets\":[{\"text\":\"...\",\"source_ids\":[\"s1\"]}]}]. "
                "Use exactly these three headings: Overview, Key Topics, Main Takeaways. "
                "Key Topics and Main Takeaways should use concise bullets. "
                "Be concise and professional. Never mention filenames or technical details. "
                f"{source_instruction}"
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
    raw = response.choices[0].message.content.strip()
    raw = re.sub(r'```json|```', '', raw).strip()
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict) and isinstance(parsed.get("sections"), list):
            return parsed["sections"]
        return parsed
    except Exception:
        match = re.search(r'\[.*\]', raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except Exception:
                pass
        return [
            {
                "heading": "Overview",
                "text": raw,
                "source_ids": [],
                "bullets": [],
            }
        ]

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

def build_source_catalog(sources: list) -> list:
    catalog = []
    for index, source in enumerate(sources, start=1):
        catalog.append(
            {
                "id": f"s{index}",
                "source": source.get("source", "unknown"),
                "page": source.get("page"),
                "score": source.get("score"),
                "preview": source.get("preview", ""),
            }
        )
    return catalog


def build_source_linked_context(context: str, source_catalog: list) -> str:
    chunks = re.split(r"\n\n(?=\[Source: )", context)
    linked_parts = []
    for source, chunk in zip(source_catalog, chunks):
        body = re.sub(r"^\[Source:[^\n]*\]\n", "", chunk, count=1)
        linked_parts.append(f"[Source ID: {source['id']}]\n{body}")
    return "\n\n".join(linked_parts)


def sanitize_flashcards_source_ids(cards: list, source_catalog: list) -> list:
    valid_ids = {source["id"] for source in source_catalog}
    sanitized = []
    if not isinstance(cards, list):
        return sanitized

    for card in cards:
        if not isinstance(card, dict):
            continue
        question = card.get("question")
        answer = card.get("answer")
        if not isinstance(question, str) or not isinstance(answer, str):
            continue

        raw_source_ids = card.get("source_ids", [])
        if isinstance(raw_source_ids, str):
            raw_source_ids = [raw_source_ids]
        if not isinstance(raw_source_ids, list):
            raw_source_ids = []

        source_ids = []
        for source_id in raw_source_ids:
            if isinstance(source_id, str) and source_id in valid_ids and source_id not in source_ids:
                source_ids.append(source_id)

        sanitized.append(
            {
                "question": question,
                "answer": answer,
                "source_ids": source_ids,
            }
        )
    return sanitized


def sanitize_quiz_source_ids(questions: list, source_catalog: list) -> list:
    valid_ids = {source["id"] for source in source_catalog}
    sanitized = []
    if not isinstance(questions, list):
        return sanitized

    for question in questions:
        if not isinstance(question, dict):
            continue
        question_text = question.get("question")
        choices = question.get("choices")
        answer = question.get("answer")
        explanation = question.get("explanation")
        if (
            not isinstance(question_text, str)
            or not isinstance(choices, list)
            or not all(isinstance(choice, str) for choice in choices)
            or not isinstance(answer, str)
            or not isinstance(explanation, str)
        ):
            continue

        raw_source_ids = question.get("source_ids", [])
        if isinstance(raw_source_ids, str):
            raw_source_ids = [raw_source_ids]
        if not isinstance(raw_source_ids, list):
            raw_source_ids = []

        source_ids = []
        for source_id in raw_source_ids:
            if isinstance(source_id, str) and source_id in valid_ids and source_id not in source_ids:
                source_ids.append(source_id)

        sanitized.append(
            {
                "question": question_text,
                "choices": choices,
                "answer": answer,
                "explanation": explanation,
                "source_ids": source_ids,
            }
        )
    return sanitized


def sanitize_summary_source_ids(sections: list, source_catalog: list) -> list:
    valid_ids = {source["id"] for source in source_catalog}
    sanitized = []
    if not isinstance(sections, list):
        return sanitized

    for section in sections:
        if not isinstance(section, dict):
            continue
        heading = section.get("heading")
        if not isinstance(heading, str):
            continue

        text = section.get("text", "")
        if not isinstance(text, str):
            text = ""

        raw_source_ids = section.get("source_ids", [])
        if isinstance(raw_source_ids, str):
            raw_source_ids = [raw_source_ids]
        if not isinstance(raw_source_ids, list):
            raw_source_ids = []

        source_ids = []
        for source_id in raw_source_ids:
            if isinstance(source_id, str) and source_id in valid_ids and source_id not in source_ids:
                source_ids.append(source_id)

        bullets = []
        raw_bullets = section.get("bullets", [])
        if isinstance(raw_bullets, list):
            for bullet in raw_bullets:
                if isinstance(bullet, str):
                    bullet_text = bullet
                    bullet_raw_source_ids = []
                elif isinstance(bullet, dict):
                    bullet_text = bullet.get("text")
                    bullet_raw_source_ids = bullet.get("source_ids", [])
                else:
                    continue

                if not isinstance(bullet_text, str):
                    continue
                if isinstance(bullet_raw_source_ids, str):
                    bullet_raw_source_ids = [bullet_raw_source_ids]
                if not isinstance(bullet_raw_source_ids, list):
                    bullet_raw_source_ids = []

                bullet_source_ids = []
                for source_id in bullet_raw_source_ids:
                    if isinstance(source_id, str) and source_id in valid_ids and source_id not in bullet_source_ids:
                        bullet_source_ids.append(source_id)

                bullets.append(
                    {
                        "text": bullet_text,
                        "source_ids": bullet_source_ids,
                    }
                )

        sanitized.append(
            {
                "heading": heading,
                "text": text,
                "source_ids": source_ids,
                "bullets": bullets,
            }
        )
    return sanitized


def generate_flashcards(context: str, count: int = 8, source_ids: list | None = None) -> list:
    allowed_source_ids = source_ids or []
    source_instruction = ""
    if allowed_source_ids:
        source_instruction = (
            f" Each flashcard may include source_ids using only these IDs: {', '.join(allowed_source_ids)}. "
            "Use an empty source_ids array if no supplied source directly supports the flashcard. "
            "Do not include filenames, page numbers, previews, or any source metadata."
        )

    messages = [
        {
            "role": "system",
            "content": (
                f"You are a flashcard generator. Given document context, generate exactly {count} flashcards. "
                "Respond ONLY with a valid JSON array, no markdown, no explanation, no backticks, no trailing commas. "
                "Format: [{\"question\": \"...\", \"answer\": \"...\", \"source_ids\": [\"s1\"]}, ...] "
                "Questions should test understanding, not just recall. Keep answers concise under 2 sentences. "
                "Ensure all strings are properly escaped and the JSON is valid."
                f"{source_instruction}"
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

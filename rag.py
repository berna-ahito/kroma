import gc
import os
from pathlib import Path
from typing import Callable

# pyrefly: ignore [missing-import]
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
MISSING_CONTEXT_ANSWER = "That information was not found in the uploaded documents."


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
    r"\bnot\s+(mentioned|provided|available|stated)\b|"
    r"\b(does\s+not|doesn.?t|do\s+not|don.?t)\s+mention\b|"
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

    Returns (context_str, sources). Each source has source, location labels,
    chunk ids, score, distance, and preview fields for UI display.
    """
    if not CHROMA_PATH.exists():
        _emit(progress_callback, "missing_index", {"message": "No local vector index found."})
        return "", []

    stats = load_index_stats() or {}
    indexed_docs = {
        doc.get("name")
        for doc in stats.get("docs", [])
        if isinstance(doc, dict) and doc.get("name")
    }
    _emit(
        progress_callback,
        "prepare",
        {
            "doc_count": len(stats.get("docs", [])),
            "total_chunks": stats.get("total_chunks", 0),
            "n_results": n_results,
        },
    )

    search_filter = None
    if selected_docs:
        requested_docs = {Path(name).name for name in selected_docs}
        filtered_docs = sorted(requested_docs & indexed_docs) if indexed_docs else sorted(requested_docs)
        if not filtered_docs:
            _emit(progress_callback, "empty", {"message": "No selected documents are indexed."})
            return "", []
        search_filter = {"source": {"$in": filtered_docs}}
    elif indexed_docs:
        search_filter = {"source": {"$in": sorted(indexed_docs)}}

    embeddings = SentenceTransformerEmbeddings(model_name=EMBEDDING_MODEL)
    vectorstore = Chroma(persist_directory=str(CHROMA_PATH), embedding_function=embeddings)

    _emit(progress_callback, "search", {"message": "Query embedded. Searching nearest chunks."})
    try:
        if search_filter:
            results = vectorstore.similarity_search_with_score(
                question, k=n_results,
                filter=search_filter,
            )
        else:
            results = vectorstore.similarity_search_with_score(question, k=n_results)
    except Exception as exc:
        _emit(progress_callback, "error", {"message": str(exc)})
        return "", []
    finally:
        try:
            vectorstore._client.clear_system_cache()
        except Exception:
            pass
        del vectorstore
        gc.collect()

    if not results:
        _emit(progress_callback, "empty", {"message": "No chunks matched the question."})
        return "", []

    context_parts = []
    sources = []
    for rank, (doc, distance) in enumerate(results, start=1):
        src = Path(doc.metadata.get("source", "unknown")).name
        if indexed_docs and src not in indexed_docs:
            continue
        file_type = doc.metadata.get("file_type")
        location_type = doc.metadata.get("location_type")
        location_label = doc.metadata.get("location_label")
        page = None
        if doc.metadata.get("page") is not None:
            page = int(doc.metadata.get("page")) + 1
            location_label = location_label or f"Page {page}"
            location_type = location_type or "page"
        location_label = location_label or "Document"
        location_type = location_type or "document"
        chunk_id = doc.metadata.get("chunk_id")
        doc_chunk_id = doc.metadata.get("doc_chunk_id")
        score = _confidence_from_distance(float(distance))

        context_parts.append(
            f"[Source: {src}, {location_label}]\n"
            f"{doc.page_content}"
        )

        source = {
            "rank": rank,
            "source": src,
            "page": page,
            "file_type": file_type,
            "location_type": location_type,
            "location_label": location_label,
            "chunk_id": chunk_id,
            "doc_chunk_id": doc_chunk_id,
            "score": score,
            "distance": round(float(distance), 4),
            "preview": doc.page_content[:320].replace("\n", " "),
        }
        sources.append(source)
        _emit(progress_callback, "candidate", source)

    if not context_parts:
        _emit(progress_callback, "empty", {"message": "No usable chunks matched the question."})
        return "", []

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
    if not context.strip():
        return MISSING_CONTEXT_ANSWER

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
    if not context:
        return MISSING_CONTEXT_ANSWER, []
    answer = generate_answer(question, context, chat_history)
    return answer, sources


def _parse_json_array_response(raw: str) -> list:
    stripped = raw.strip()
    stripped = re.sub(r'```json|```', '', stripped).strip()
    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, list):
            return parsed
    except Exception:
        pass
    match = re.search(r'\[.*\]', stripped, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except Exception:
            pass
    return []


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
    return _parse_json_array_response(response.choices[0].message.content)


def _strip_json_fence(text: str) -> str:
    stripped = text.strip()
    match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", stripped, flags=re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip()
    return stripped


def _summary_json_candidates(text: str) -> list:
    stripped = _strip_json_fence(text)
    candidates = [stripped]

    for match in re.finditer(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.IGNORECASE | re.DOTALL):
        candidate = match.group(1).strip()
        if candidate not in candidates:
            candidates.append(candidate)

    for opener, closer in (("{", "}"), ("[", "]")):
        start = stripped.find(opener)
        end = stripped.rfind(closer)
        if start != -1 and end != -1 and start < end:
            candidate = stripped[start : end + 1].strip()
            if candidate not in candidates:
                candidates.append(candidate)

    return candidates


def _summary_sections_from_payload(payload, depth: int = 0):
    if depth > 3:
        return None
    if isinstance(payload, dict):
        sections = payload.get("sections")
        if isinstance(sections, list):
            return sections
        inner = payload.get("summary")
        if isinstance(inner, dict):
            inner_sections = inner.get("sections")
            if isinstance(inner_sections, list):
                return inner_sections
        if "heading" in payload:
            return [payload]
        return None
    if isinstance(payload, list):
        return payload
    if isinstance(payload, str):
        for candidate in _summary_json_candidates(payload):
            try:
                parsed = json.loads(candidate)
            except Exception:
                continue
            sections = _summary_sections_from_payload(parsed, depth + 1)
            if isinstance(sections, list):
                return sections
    return None


def _summary_fallback_sections(raw="", source_text="") -> list:
    if source_text:
        parts = re.split(r"\[Source ID: [^\]]+\]\s*", source_text.strip())
        useful = [
            re.split(r"(?<=[.!])\s+", p.strip(), maxsplit=1)[0][:200]
            for p in parts if p.strip()
        ]
        if useful:
            return [
                {
                    "heading": "Overview",
                    "text": " ".join(useful[:3]),
                    "source_ids": [],
                    "bullets": [],
                }
            ]
    return [
        {
            "heading": "Overview",
            "text": "Summary could not be parsed into readable sections. Try summarizing again.",
            "source_ids": [],
            "bullets": [],
        }
    ]


def normalize_summary_sections(payload, source_text="") -> list:
    sections = _summary_sections_from_payload(payload)
    if isinstance(sections, list) and sections:
        return sections
    return _summary_fallback_sections(payload, source_text)


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
    return normalize_summary_sections(raw, context)

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
    return _parse_json_array_response(response.choices[0].message.content)


def build_source_catalog(sources: list) -> list:
    catalog = []
    for index, source in enumerate(sources, start=1):
        catalog.append(
            {
                "id": f"s{index}",
                "source": source.get("source", "unknown"),
                "page": source.get("page"),
                "file_type": source.get("file_type"),
                "location_type": source.get("location_type"),
                "location_label": source.get("location_label"),
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


def _valid_source_ids(source_catalog) -> set:
    return {source["id"] for source in source_catalog}


def _sanitize_source_ids(raw_source_ids, valid_ids: set) -> list:
    if isinstance(raw_source_ids, str):
        raw_source_ids = [raw_source_ids]
    if not isinstance(raw_source_ids, list):
        return []
    result = []
    for sid in raw_source_ids:
        if isinstance(sid, str) and sid in valid_ids and sid not in result:
            result.append(sid)
    return result


def sanitize_flashcards_source_ids(cards: list, source_catalog: list) -> list:
    valid_ids = _valid_source_ids(source_catalog)
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

        sanitized.append(
            {
                "question": question,
                "answer": answer,
                "source_ids": _sanitize_source_ids(card.get("source_ids", []), valid_ids),
            }
        )
    return sanitized


def sanitize_quiz_source_ids(questions: list, source_catalog: list) -> list:
    valid_ids = _valid_source_ids(source_catalog)
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

        sanitized.append(
            {
                "question": question_text,
                "choices": choices,
                "answer": answer,
                "explanation": explanation,
                "source_ids": _sanitize_source_ids(question.get("source_ids", []), valid_ids),
            }
        )
    return sanitized


def sanitize_summary_source_ids(sections: list, source_catalog: list) -> list:
    valid_ids = _valid_source_ids(source_catalog)
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

        source_ids = _sanitize_source_ids(section.get("source_ids", []), valid_ids)

        bullets = []
        raw_bullets = section.get("bullets", [])
        if isinstance(raw_bullets, list):
            for bullet in raw_bullets:
                if isinstance(bullet, str):
                    bullet_text = bullet
                    bullet_source_ids = []
                elif isinstance(bullet, dict):
                    bullet_text = bullet.get("text")
                    bullet_source_ids = _sanitize_source_ids(bullet.get("source_ids", []), valid_ids)
                else:
                    continue

                if not isinstance(bullet_text, str):
                    continue

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


BUSINESS_SENSITIVE_RE = re.compile(
    r"\b("
    r"pricing?|price|cost|budget|"
    r"legal|liability|compliance|regulatory|regulation|"
    r"finance|financial|investor|investment|valuation|revenue|profit|"
    r"scientific|clinical|"
    r"medical|treatment|diagnosis|patient|"
    r"product\s*claims?|warranty|guarantee|"
    r"commercial\s*terms?|terms?\s*of\s*service|"
    r"hr|hiring|personnel|employee|salary|compensation|"
    r"complaints?|dispute|grievance|"
    r"refunds?|cancel|cancellation|return\s*policy|"
    r"negotiations?|negotiate|contract|"
    r"confidential|nda|proprietary|"
    r"lawsuit|litigation|settlement"
    r")\b",
    re.IGNORECASE,
)


def business_context_is_relevant(sources, min_top_score=35):
    if not sources or not isinstance(sources, list):
        return False
    scores = [s.get("score", 0) for s in sources if isinstance(s, dict)]
    if not scores:
        return False
    return max(scores) >= min_top_score


def business_needs_human_review(task_type, audience, request_text, missing_info):
    reasons = []
    external_audiences = {"customer", "partner", "investor", "distributor", "other"}
    if audience in external_audiences:
        reasons.append("External audience requires human review")
    if task_type not in ("answer_from_sources", "summarize_for_team"):
        reasons.append(f"Task type '{task_type}' requires human review")
    if missing_info:
        reasons.append("Missing information identified")
    if BUSINESS_SENSITIVE_RE.search(request_text or ""):
        reasons.append("Request contains potentially sensitive terms")
    if not reasons:
        return {"required": False, "reasons": []}
    return {"required": True, "reasons": reasons}


def _parse_business_copilot_response(raw: str) -> dict:
    stripped = _strip_json_fence(raw)
    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass
    match = re.search(r"\{.*\}", stripped, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except Exception:
            pass
    return {}


def generate_business_copilot_output(task_type, audience, request_text, source_context, source_catalog):
    allowed_ids = [s["id"] for s in source_catalog] if source_catalog else []
    messages = [
        {
            "role": "system",
            "content": (
                "You are a Business Copilot assistant. Given document context, produce structured business output. "
                "Respond ONLY with a valid JSON object, no markdown, no explanation, no backticks. "
                f"Allowed source IDs: {', '.join(allowed_ids)}. "
                "Use ONLY these source IDs in your response. Never invent source IDs. "
                "Format: {\"verified_facts\": [{\"text\": \"...\", \"source_ids\": [\"s1\"]}], "
                "\"suggested_draft\": \"...\", "
                "\"missing_information\": [\"...\"], "
                "\"sources_used\": [\"s1\"]} "
                "verified_facts must cite at least one valid source ID per fact. "
                "If a point is not directly supported by a source, put it in missing_information, not verified_facts. "
                "suggested_draft should be a professional draft based on the verified facts. "
                "sources_used should list all source IDs that were actually used."
            ),
        },
        {
            "role": "user",
            "content": (
                f"[Task type] {task_type}\n"
                f"[Audience] {audience}\n"
                f"[Request] {request_text}\n\n"
                f"[Document context]\n{source_context}\n\n"
                "Generate business copilot output for this task."
            ),
        },
    ]
    response = _groq_client().chat.completions.create(
        model=GROQ_MODEL,
        messages=messages,
        temperature=0.3,
    )
    return _parse_business_copilot_response(response.choices[0].message.content)


def normalize_business_copilot_output(payload):
    if not isinstance(payload, dict):
        payload = {}
    result = {
        "verified_facts": [],
        "suggested_draft": "",
        "missing_information": [],
        "sources_used": [],
    }
    vf = payload.get("verified_facts", [])
    if isinstance(vf, list):
        cleaned = []
        for f in vf:
            if not isinstance(f, dict):
                continue
            text = f.get("text", "")
            if not isinstance(text, str) or not text.strip():
                continue
            raw_ids = f.get("source_ids", [])
            if isinstance(raw_ids, str):
                raw_ids = [raw_ids]
            if not isinstance(raw_ids, list):
                raw_ids = []
            cleaned.append({"text": text, "source_ids": [str(s) for s in raw_ids if isinstance(s, str)]})
        result["verified_facts"] = cleaned
    draft = payload.get("suggested_draft")
    if isinstance(draft, str):
        result["suggested_draft"] = draft
    mi = payload.get("missing_information")
    if isinstance(mi, list):
        result["missing_information"] = [str(m) for m in mi if isinstance(m, str) and m.strip()]
    su = payload.get("sources_used")
    if isinstance(su, list):
        result["sources_used"] = [str(s) for s in su if isinstance(s, str)]
    return result


def sanitize_business_copilot_source_ids(result, source_catalog):
    valid_ids = _valid_source_ids(source_catalog) if source_catalog else set()
    sanitized = {
        "verified_facts": [],
        "suggested_draft": result.get("suggested_draft", ""),
        "missing_information": list(result.get("missing_information", [])),
        "sources_used": _sanitize_source_ids(result.get("sources_used", []), valid_ids),
    }
    for fact in result.get("verified_facts", []):
        if not isinstance(fact, dict):
            continue
        text = fact.get("text", "")
        if not isinstance(text, str) or not text.strip():
            continue
        clean_ids = _sanitize_source_ids(fact.get("source_ids", []), valid_ids)
        if clean_ids:
            sanitized["verified_facts"].append({"text": text, "source_ids": clean_ids})
        else:
            sanitized["missing_information"].append(text)
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
    return _parse_json_array_response(response.choices[0].message.content)


def compute_readiness_verdict(result: dict, source_context: str = "") -> dict:
    coverage = len(result.get("coverage_summary", []))
    risks = len(result.get("risk_areas", []))
    missing = len(result.get("missing_knowledge", []))

    if coverage < 2:
        return {"level": "Low", "reasons": ["Insufficient knowledge coverage"]}
    if risks >= 3:
        return {"level": "Low", "reasons": ["Too many risk areas identified"]}
    if missing >= 3:
        return {"level": "Low", "reasons": ["Too much missing knowledge"]}

    if coverage >= 4 and risks == 0 and missing <= 1:
        return {"level": "High", "reasons": ["Excellent coverage with minimal risks and gaps"]}

    return {"level": "Medium", "reasons": ["Adequate knowledge coverage but some gaps or risks exist"]}


def generate_knowledge_audit(source_context: str, source_catalog: list) -> dict:
    allowed_ids = [s["id"] for s in source_catalog] if source_catalog else []
    messages = [
        {
            "role": "system",
            "content": (
                "You are a Knowledge Audit assistant. Given document context, produce a structured audit of the knowledge. "
                "Respond ONLY with a valid JSON object, no markdown, no explanation, no backticks. "
                f"Allowed source IDs: {', '.join(allowed_ids)}. "
                "Use ONLY these source IDs in your response. Never invent source IDs. "
                "Format: {"
                "\"coverage_summary\": [{\"area\": \"...\", \"source_ids\": [\"s1\"]}], "
                "\"missing_knowledge\": [\"...\"], "
                "\"risk_areas\": [{\"area\": \"...\", \"detail\": \"...\", \"source_ids\": [\"s1\"]}], "
                "\"suggested_next_documents\": [\"...\"], "
                "\"automation_readiness\": [{\"category\": \"Safe to answer from sources\", \"items\": [\"...\"]}], "
                "\"sources_used\": [\"s1\"]"
                "} "
                "Avoid claiming coverage unless supported by source IDs. "
                "Include missing information when docs are weak. "
                "Flag risk areas: pricing, legal, finance, investor claims, scientific claims, medical claims, product claims, commercial terms, HR, complaints, refunds, negotiations. "
                "sources_used should list all source IDs that were actually used."
            ),
        },
        {
            "role": "user",
            "content": (
                f"[Document context]\n{source_context}\n\n"
                "Generate a knowledge audit based on this context."
            ),
        },
    ]
    response = _groq_client().chat.completions.create(
        model=GROQ_MODEL,
        messages=messages,
        temperature=0.3,
    )
    return _parse_business_copilot_response(response.choices[0].message.content)


def normalize_knowledge_audit_output(payload) -> dict:
    if not isinstance(payload, dict):
        payload = {}
    result = {
        "coverage_summary": [],
        "missing_knowledge": [],
        "risk_areas": [],
        "suggested_next_documents": [],
        "automation_readiness": [],
        "sources_used": [],
    }

    cs = payload.get("coverage_summary", [])
    if isinstance(cs, list):
        cleaned = []
        for c in cs:
            if not isinstance(c, dict):
                continue
            area = c.get("area", "")
            if not isinstance(area, str) or not area.strip():
                continue
            raw_ids = c.get("source_ids", [])
            if isinstance(raw_ids, str):
                raw_ids = [raw_ids]
            if not isinstance(raw_ids, list):
                raw_ids = []
            cleaned.append({"area": area, "source_ids": [str(s) for s in raw_ids if isinstance(s, str)]})
        result["coverage_summary"] = cleaned

    mk = payload.get("missing_knowledge")
    if isinstance(mk, list):
        result["missing_knowledge"] = [str(m) for m in mk if isinstance(m, str) and m.strip()]

    ra = payload.get("risk_areas", [])
    if isinstance(ra, list):
        cleaned = []
        for r in ra:
            if not isinstance(r, dict):
                continue
            area = r.get("area", "")
            detail = r.get("detail", "")
            if not isinstance(area, str) or not area.strip():
                continue
            raw_ids = r.get("source_ids", [])
            if isinstance(raw_ids, str):
                raw_ids = [raw_ids]
            if not isinstance(raw_ids, list):
                raw_ids = []
            cleaned.append({"area": area, "detail": str(detail), "source_ids": [str(s) for s in raw_ids if isinstance(s, str)]})
        result["risk_areas"] = cleaned

    snd = payload.get("suggested_next_documents")
    if isinstance(snd, list):
        result["suggested_next_documents"] = [str(m) for m in snd if isinstance(m, str) and m.strip()]

    ar = payload.get("automation_readiness", [])
    canonical_cats = {"Safe to answer from sources", "AI draft + human review", "Keep manual"}
    auto_buckets = {c: [] for c in canonical_cats}
    if isinstance(ar, list):
        for a in ar:
            if not isinstance(a, dict):
                continue
            cat = a.get("category", "")
            if cat in auto_buckets:
                items = a.get("items", [])
                if isinstance(items, list):
                    auto_buckets[cat].extend([str(i) for i in items if isinstance(i, str) and str(i).strip()])

    result["automation_readiness"] = [{"category": k, "items": v} for k, v in auto_buckets.items()]

    su = payload.get("sources_used")
    if isinstance(su, list):
        result["sources_used"] = [str(s) for s in su if isinstance(s, str)]

    return result


def sanitize_knowledge_audit_source_ids(result: dict, source_catalog: list) -> dict:
    valid_ids = _valid_source_ids(source_catalog) if source_catalog else set()
    sanitized = {
        "coverage_summary": [],
        "missing_knowledge": list(result.get("missing_knowledge", [])),
        "risk_areas": [],
        "suggested_next_documents": list(result.get("suggested_next_documents", [])),
        "automation_readiness": list(result.get("automation_readiness", [])),
        "sources_used": _sanitize_source_ids(result.get("sources_used", []), valid_ids),
    }
    for cov in result.get("coverage_summary", []):
        if not isinstance(cov, dict):
            continue
        area = cov.get("area", "")
        if not isinstance(area, str) or not area.strip():
            continue
        clean_ids = _sanitize_source_ids(cov.get("source_ids", []), valid_ids)
        if clean_ids:
            sanitized["coverage_summary"].append({"area": area, "source_ids": clean_ids})

    for risk in result.get("risk_areas", []):
        if not isinstance(risk, dict):
            continue
        area = risk.get("area", "")
        detail = risk.get("detail", "")
        if not isinstance(area, str) or not area.strip():
            continue
        clean_ids = _sanitize_source_ids(risk.get("source_ids", []), valid_ids)
        sanitized["risk_areas"].append({"area": area, "detail": detail, "source_ids": clean_ids})

    return sanitized


if __name__ == "__main__":
    q = input("Ask a question: ")
    answer, srcs = query_documents(q)
    print(f"\nAnswer: {answer}")
    print(f"Sources: {srcs}")

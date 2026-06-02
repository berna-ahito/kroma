import gc
import hashlib
import os
import time
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Callable

# pyrefly: ignore [missing-import]
from dotenv import load_dotenv
from groq import Groq
from langchain_community.embeddings import SentenceTransformerEmbeddings
from langchain_community.vectorstores import Chroma

import json
import re
from .ingest import EMBEDDING_MODEL, load_index_stats


load_dotenv()
os.environ.setdefault("HF_HUB_OFFLINE", "0")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "0")

ROOT_DIR = Path(__file__).resolve().parents[1]
CHROMA_PATH = ROOT_DIR / "chroma_db"
GROQ_MODEL = os.getenv("GROQ_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")
MISSING_CONTEXT_ANSWER = "That information was not found in the uploaded documents."
RRF_K = 60
KEYWORD_CANDIDATE_FLOOR = 20
TOKEN_RE = re.compile(r"[A-Za-z0-9$][A-Za-z0-9._$:/-]*")
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "did", "do",
    "does", "each", "for", "from", "has", "have", "how", "in", "is", "it",
    "its", "of", "on", "or", "say", "says", "the", "to", "what", "when",
    "where", "which", "who", "why", "with",
}
EXTERNAL_RISK_TERMS_RE = re.compile(
    r"\b("
    r"pricing?|refunds?|legal|compliance|finance|medical|clinical|claims?|"
    r"contract|warranty|guarantee|customer|external|public|policy|terms?"
    r")\b",
    re.IGNORECASE,
)
PRICE_RE = re.compile(r"(?:\$|usd\s*)\s*\d[\d,]*(?:\.\d{1,2})?|\d[\d,]*(?:\.\d{1,2})?\s*(?:usd|dollars?)", re.IGNORECASE)
DATE_RE = re.compile(
    r"\b(?:\d{4}-\d{1,2}-\d{1,2}|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\s+\d{1,2}(?:,\s*\d{4})?|\d{1,2}/\d{1,2}/\d{2,4})\b",
    re.IGNORECASE,
)
STATUS_GROUPS = {
    "available": {"available", "enabled", "active", "open", "approved", "included", "supported", "allowed"},
    "unavailable": {"unavailable", "disabled", "inactive", "closed", "rejected", "excluded", "unsupported", "not allowed"},
}
STATUS_RE = re.compile(
    r"\b(available|unavailable|enabled|disabled|active|inactive|open|closed|approved|rejected|included|excluded|supported|unsupported|allowed|not allowed)\b",
    re.IGNORECASE,
)


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


def _safe_trace_text(value, max_chars: int = 120) -> str:
    text = str(value or "").replace("\x00", "")
    text = re.sub(r"[\r\n\t]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= max_chars:
        return text
    digest = hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()[:10]
    return f"{text[:max_chars]}...#{digest}"


def _safe_trace_filename(value) -> str:
    return _safe_trace_text(Path(str(value or "unknown")).name, 96)


def _new_retrieval_trace(
    question: str,
    selected_docs: list | None,
    indexed_docs: set[str] | None,
    endpoint: str | None = None,
    request_id: str | None = None,
) -> dict:
    trace_id = uuid.uuid4().hex
    selected_doc_names = [Path(str(name)).name for name in selected_docs] if selected_docs else []
    return {
        "trace_id": trace_id,
        "request_id": _safe_trace_text(request_id, 128) if request_id else trace_id,
        "endpoint": _safe_trace_text(endpoint, 128) if endpoint else None,
        "query_redacted": "[redacted]",
        "query_length": len(question or ""),
        "selected_doc_count": len(selected_doc_names),
        "selected_docs_redacted": [_safe_trace_filename(name) for name in selected_doc_names],
        "indexed_doc_count": len(indexed_docs or set()),
        "vector_candidate_count": 0,
        "keyword_candidate_count": 0,
        "final_candidate_count": 0,
        "final_candidates": [],
        "vector_latency_ms": 0.0,
        "keyword_latency_ms": 0.0,
        "fusion_latency_ms": 0.0,
        "total_retrieval_latency_ms": 0.0,
        "no_context_reason": None,
        "retrieval_mode": "none",
        "safe_for_client": False,
    }


def _trace_source_id(source: dict, rank: int) -> str:
    source_id = source.get("doc_chunk_id") or source.get("chunk_id") or f"{source.get('source', 'unknown')}:{rank}"
    return _safe_trace_text(source_id, 140)


def _trace_candidate(source: dict) -> dict:
    return {
        "source_id": _trace_source_id(source, source.get("rank", 0)),
        "filename": _safe_trace_filename(source.get("source")),
        "location_label": _safe_trace_text(source.get("location_label"), 80),
        "vector_rank": source.get("vector_rank"),
        "keyword_rank": source.get("keyword_rank"),
        "fused_score": source.get("fused_score"),
        "retrieval_methods": list(source.get("retrieval_methods") or []),
        "score": source.get("score"),
        "exact_terms": [_safe_trace_text(term, 60) for term in (source.get("exact_terms") or [])],
    }


def _retrieval_mode(trace: dict) -> str:
    final_candidates = trace.get("final_candidates") or []
    if not final_candidates:
        return "none"
    methods = {
        method
        for candidate in final_candidates
        for method in candidate.get("retrieval_methods", [])
    }
    if "vector" in methods and "keyword" in methods:
        return "hybrid"
    if "vector" in methods:
        return "vector"
    if "keyword" in methods:
        return "keyword"
    return "none"


def _finish_retrieval_trace(
    trace: dict,
    started_at: float,
    progress_callback: Callable | None,
    no_context_reason: str | None = None,
) -> dict:
    if no_context_reason:
        trace["no_context_reason"] = no_context_reason
        trace.setdefault("model_called", False)
    trace["final_candidate_count"] = len(trace.get("final_candidates") or [])
    trace["retrieval_mode"] = _retrieval_mode(trace)
    trace["total_retrieval_latency_ms"] = round((time.perf_counter() - started_at) * 1000, 2)
    # Deprecated compatibility only. Endpoint logic must use the request-scoped
    # trace returned from retrieve_chunks(..., return_trace=True).
    retrieve_chunks.last_trace = trace
    _emit(progress_callback, "trace", trace)
    return trace


def _retrieval_return(context: str, sources: list, trace: dict, return_trace: bool):
    if return_trace:
        return context, sources, trace
    return context, sources


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


def _tokenize(text: str) -> list[str]:
    return [match.group(0).lower() for match in TOKEN_RE.finditer(text or "")]


def _query_terms(query: str) -> list[str]:
    terms = []
    seen = set()
    for term in _tokenize(query):
        if term in seen:
            continue
        if term in STOPWORDS:
            continue
        seen.add(term)
        terms.append(term)
    return terms


def _rare_looking_term(term: str) -> bool:
    return any(ch.isdigit() for ch in term) or any(ch in term for ch in "$._:/-") or len(term) <= 4


def _keyword_score(query: str, content: str) -> tuple[float, list[str]]:
    terms = _query_terms(query)
    if not terms or not content:
        return 0.0, []

    content_terms = _tokenize(content)
    if not content_terms:
        return 0.0, []

    frequencies = {}
    for term in content_terms:
        frequencies[term] = frequencies.get(term, 0) + 1

    score = 0.0
    exact_terms = []
    for term in terms:
        count = frequencies.get(term, 0)
        if not count:
            continue
        exact_terms.append(term)
        weight = 3.0 if _rare_looking_term(term) else 1.0
        score += min(count, 8) * weight

    normalized_query = " ".join(terms)
    normalized_content = " ".join(content_terms)
    if len(terms) >= 2 and normalized_query in normalized_content:
        score += 8.0

    return score, exact_terms


def _candidate_key(doc) -> tuple:
    metadata = getattr(doc, "metadata", {}) or {}
    source = Path(metadata.get("source", "unknown")).name
    return (
        source,
        metadata.get("chunk_id"),
        metadata.get("doc_chunk_id"),
        metadata.get("page"),
        (getattr(doc, "page_content", "") or "")[:80],
    )


def _keyword_candidates(vectorstore, question: str, search_filter: dict | None, indexed_docs: set[str], limit: int) -> list[dict]:
    try:
        if search_filter:
            raw = vectorstore.get(where=search_filter, include=["documents", "metadatas"])
        else:
            raw = vectorstore.get(include=["documents", "metadatas"])
    except Exception:
        return []

    documents = raw.get("documents") or []
    metadatas = raw.get("metadatas") or []
    candidates = []
    for order, content in enumerate(documents):
        metadata = metadatas[order] if order < len(metadatas) and isinstance(metadatas[order], dict) else {}
        src = Path(metadata.get("source", "unknown")).name
        if indexed_docs and src not in indexed_docs:
            continue
        score, exact_terms = _keyword_score(question, content or "")
        if score <= 0:
            continue
        doc = SimpleNamespace(page_content=content or "", metadata=metadata)
        candidates.append(
            {
                "doc": doc,
                "keyword_score": score,
                "exact_terms": exact_terms,
                "keyword_order": order,
            }
        )

    candidates.sort(key=lambda item: (-item["keyword_score"], item["keyword_order"]))
    return candidates[:limit]


def _fuse_candidates(vector_results: list, keyword_results: list, limit: int) -> list[dict]:
    fused = {}
    first_seen = 0

    for rank, (doc, distance) in enumerate(vector_results, start=1):
        key = _candidate_key(doc)
        if key not in fused:
            fused[key] = {"doc": doc, "first_seen": first_seen, "fused_score": 0.0}
            first_seen += 1
        fused[key]["vector_rank"] = rank
        fused[key]["vector_distance"] = float(distance)
        fused[key]["fused_score"] += 1 / (RRF_K + rank)

    for rank, item in enumerate(keyword_results, start=1):
        doc = item["doc"]
        key = _candidate_key(doc)
        if key not in fused:
            fused[key] = {"doc": doc, "first_seen": first_seen, "fused_score": 0.0}
            first_seen += 1
        fused[key]["keyword_rank"] = rank
        fused[key]["keyword_score"] = item["keyword_score"]
        fused[key]["exact_terms"] = item["exact_terms"]
        fused[key]["fused_score"] += 1 / (RRF_K + rank)

    return sorted(
        fused.values(),
        key=lambda item: (
            -item["fused_score"],
            min(item.get("vector_rank", 10**9), item.get("keyword_rank", 10**9)),
            item["first_seen"],
        ),
    )[:limit]


def _source_from_fused_candidate(candidate: dict, rank: int) -> dict | None:
    doc = candidate["doc"]
    src = Path(doc.metadata.get("source", "unknown")).name
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

    if "vector_distance" in candidate:
        distance = round(float(candidate["vector_distance"]), 4)
        score = _confidence_from_distance(candidate["vector_distance"])
    else:
        distance = 0.0
        score = max(1, min(100, round(float(candidate.get("keyword_score", 0)) * 8)))

    methods = []
    if candidate.get("vector_rank") is not None:
        methods.append("vector")
    if candidate.get("keyword_rank") is not None:
        methods.append("keyword")

    return {
        "rank": rank,
        "source": src,
        "page": page,
        "file_type": file_type,
        "location_type": location_type,
        "location_label": location_label,
        "chunk_id": chunk_id,
        "doc_chunk_id": doc_chunk_id,
        "score": score,
        "distance": distance,
        "preview": doc.page_content[:320].replace("\n", " "),
        "retrieval_methods": methods,
        "retrieval_method": "+".join(methods) if methods else "unknown",
        "vector_rank": candidate.get("vector_rank"),
        "keyword_rank": candidate.get("keyword_rank"),
        "fused_score": round(float(candidate.get("fused_score", 0.0)), 6),
        "exact_terms": candidate.get("exact_terms", []),
    }


def retrieve_chunks(
    question: str,
    n_results: int = 10,
    progress_callback: Callable | None = None,
    selected_docs: list | None = None,
    return_trace: bool = False,
    request_id: str | None = None,
    endpoint: str | None = None,
):
    """
    Search the vector store for relevant chunks.

    Returns (context_str, sources). Each source has source, location labels,
    chunk ids, score, distance, and preview fields for UI display.
    """
    started_at = time.perf_counter()
    stats = load_index_stats() or {}
    indexed_docs = {
        doc.get("name")
        for doc in stats.get("docs", [])
        if isinstance(doc, dict) and doc.get("name")
    }
    trace = _new_retrieval_trace(question, selected_docs, indexed_docs, endpoint=endpoint, request_id=request_id)

    if not CHROMA_PATH.exists():
        _emit(progress_callback, "missing_index", {"message": "No local vector index found."})
        _finish_retrieval_trace(trace, started_at, progress_callback, "missing_index")
        return _retrieval_return("", [], trace, return_trace)

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
            _finish_retrieval_trace(trace, started_at, progress_callback, "no_selected_documents_indexed")
            return _retrieval_return("", [], trace, return_trace)
        search_filter = {"source": {"$in": filtered_docs}}
    elif indexed_docs:
        search_filter = {"source": {"$in": sorted(indexed_docs)}}

    embeddings = SentenceTransformerEmbeddings(model_name=EMBEDDING_MODEL)
    vectorstore = Chroma(persist_directory=str(CHROMA_PATH), embedding_function=embeddings)

    candidate_limit = max(n_results * 4, KEYWORD_CANDIDATE_FLOOR)
    _emit(progress_callback, "search", {"message": "Query embedded. Searching nearest chunks."})
    try:
        vector_started_at = time.perf_counter()
        if search_filter:
            vector_results = vectorstore.similarity_search_with_score(
                question, k=candidate_limit,
                filter=search_filter,
            )
        else:
            vector_results = vectorstore.similarity_search_with_score(question, k=candidate_limit)
        trace["vector_latency_ms"] = round((time.perf_counter() - vector_started_at) * 1000, 2)
        trace["vector_candidate_count"] = len(vector_results)
        keyword_started_at = time.perf_counter()
        keyword_results = _keyword_candidates(vectorstore, question, search_filter, indexed_docs, candidate_limit)
        trace["keyword_latency_ms"] = round((time.perf_counter() - keyword_started_at) * 1000, 2)
        trace["keyword_candidate_count"] = len(keyword_results)
    except Exception as exc:
        _emit(progress_callback, "error", {"message": str(exc)})
        _finish_retrieval_trace(trace, started_at, progress_callback, "retrieval_error")
        return _retrieval_return("", [], trace, return_trace)
    finally:
        try:
            vectorstore._client.clear_system_cache()
        except Exception:
            pass
        del vectorstore
        gc.collect()

    fusion_started_at = time.perf_counter()
    fused_results = _fuse_candidates(vector_results, keyword_results, n_results)
    trace["fusion_latency_ms"] = round((time.perf_counter() - fusion_started_at) * 1000, 2)

    if not fused_results:
        _emit(progress_callback, "empty", {"message": "No chunks matched the question."})
        _finish_retrieval_trace(trace, started_at, progress_callback, "no_matching_chunks")
        return _retrieval_return("", [], trace, return_trace)

    context_parts = []
    sources = []
    for rank, candidate in enumerate(fused_results, start=1):
        doc = candidate["doc"]
        src = Path(doc.metadata.get("source", "unknown")).name
        if indexed_docs and src not in indexed_docs:
            continue
        source = _source_from_fused_candidate(candidate, rank)
        if not source:
            continue
        context_parts.append(
            f"[Source: {src}, {source['location_label']}]\n"
            f"{doc.page_content}"
        )

        sources.append(source)
        trace["final_candidates"].append(_trace_candidate(source))
        _emit(progress_callback, "candidate", source)

    if not context_parts:
        _emit(progress_callback, "empty", {"message": "No usable chunks matched the question."})
        _finish_retrieval_trace(trace, started_at, progress_callback, "no_usable_chunks")
        return _retrieval_return("", [], trace, return_trace)

    _finish_retrieval_trace(trace, started_at, progress_callback)
    _emit(progress_callback, "complete", {"matches": len(sources)})
    return _retrieval_return("\n\n".join(context_parts), sources, trace, return_trace)


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

SUGGESTION_BLOCKED_TOPICS = [
    (
        re.compile(r"\b(team|company|organization)\b.*\b(worked on|built|delivered)\b|\brecent\s+(ai\s+)?(research\s+)?projects?\b", re.IGNORECASE),
        re.compile(r"\b(worked on|recent\s+(ai\s+)?(research\s+)?projects?|case stud(y|ies)|portfolio)\b", re.IGNORECASE),
    ),
    (
        re.compile(r"\b(internal\s+)?(workflow|workflows|mlops|deployment|deployments|tooling|processes)\b", re.IGNORECASE),
        re.compile(r"\b(workflow|workflows|mlops|deployment|deployments|tooling|processes)\b", re.IGNORECASE),
    ),
    (
        re.compile(r"\bhiring manager\b.*\b(prefer|preference|want|looking for)\b", re.IGNORECASE),
        re.compile(r"\bhiring manager\b|\bpreference(s)?\b", re.IGNORECASE),
    ),
    (
        re.compile(r"\b(culture|values|team dynamics|work environment)\b", re.IGNORECASE),
        re.compile(r"\b(culture|values|team dynamics|work environment)\b", re.IGNORECASE),
    ),
    (
        re.compile(r"\b(future plans?|roadmap|upcoming|next steps|plans to)\b", re.IGNORECASE),
        re.compile(r"\b(future plans?|roadmap|upcoming|next steps|plans to)\b", re.IGNORECASE),
    ),
]


def _looks_like_job_context(context: str) -> bool:
    lower = context.lower()
    markers = [
        "job description",
        "required skills",
        "requirements",
        "qualifications",
        "proposal",
        "candidate",
        "hourly",
        "duration",
        "job type",
        "location",
        "interview",
    ]
    return sum(1 for marker in markers if marker in lower) >= 2


def _is_grounded_suggestion(question: object, context: str) -> bool:
    if not isinstance(question, str):
        return False
    cleaned = question.strip()
    if not cleaned or len(cleaned) > 180:
        return False
    lower_question = cleaned.lower()
    lower_context = context.lower()
    sensitive_terms = {
        "mlops": ("mlops",),
        "deployment": ("deployment", "deployments", "deploy", "deployed"),
        "workflow": ("workflow", "workflows"),
    }
    for term, context_terms in sensitive_terms.items():
        if term in lower_question and not any(context_term in lower_context for context_term in context_terms):
            return False
    approach_phrases = (
        "how does the company approach",
        "how does the team approach",
        "how does the organization approach",
    )
    explicit_approach_phrases = (
        "company approach",
        "company approaches",
        "team approach",
        "team approaches",
        "organization approach",
        "organization approaches",
        "approach to model deployment",
        "approach to mlops",
    )
    if any(phrase in lower_question for phrase in approach_phrases) and not any(
        phrase in lower_context for phrase in explicit_approach_phrases
    ):
        return False
    if "currently in use" in lower_question and "currently in use" not in lower_context:
        return False
    for question_pattern, context_pattern in SUGGESTION_BLOCKED_TOPICS:
        if question_pattern.search(cleaned) and not context_pattern.search(context):
            return False
    return True


def _fallback_suggestions(context: str) -> list:
    lower = context.lower()
    if _looks_like_job_context(context):
        questions = ["What required skills and experience does this role list?"]
        has_bonus = re.search(r"\b(bonus|preferred|nice[- ]to[- ]have|plus)\b", lower)
        has_screening = re.search(r"\b(proposal|interview|screening)\b.*\b(question|answer|ask)\b|\bquestions?\b", lower)
        if has_bonus and has_screening:
            questions.append("What bonus qualifications and proposal or interview questions are listed?")
        elif has_bonus:
            questions.append("What bonus qualifications or preferred skills are mentioned?")
        elif has_screening:
            questions.append("What proposal or interview questions does the job post ask candidates to answer?")
        questions.append("What candidate profile would be the best fit for the stated role?")
        if re.search(r"\b(rate|hourly|salary|duration|job type|contract|location|remote|onsite|hybrid)\b", lower):
            questions.append("What rate, duration, job type, or location details are stated?")
        questions.append("Which candidates would be rejected or not a fit based on the stated requirements?")
        return questions

    return [
        "What are the main topics covered in this document?",
        "What key facts or requirements are explicitly stated?",
        "What practical next steps does the document support?",
    ]


def _ground_suggestions(questions: list, context: str, limit: int = 3) -> list:
    grounded = []
    seen = set()
    for question in list(questions or []) + _fallback_suggestions(context):
        if not _is_grounded_suggestion(question, context):
            continue
        cleaned = re.sub(r"\s+", " ", question.strip())
        key = cleaned.lower()
        if key in seen:
            continue
        grounded.append(cleaned)
        seen.add(key)
        if len(grounded) == limit:
            break
    return grounded


def generate_suggestions(context: str) -> list:
    messages = [
        {
            "role": "system",
            "content": (
                "You are a document assistant. Given document context, generate exactly 3 source-answerable questions a user might want to ask. "
                "Respond ONLY with a valid JSON array of strings, no markdown, no explanation, no backticks. "
                "Format: [\"Question 1?\", \"Question 2?\", \"Question 3?\"] "
                "Use only explicit facts in the supplied context. Do not ask about company/team past projects, internal workflows, "
                "hiring manager preferences, culture details, or future plans unless the context explicitly states that information. "
                "For job posts, prefer questions about required skills, rejected or not-fit candidates, mentioned tools/frameworks, "
                "bonus qualifications, proposal or interview questions, rate, duration, job type, location, and candidate fit. "
                "Do not include questions to ask the employer in the normal suggested questions. "
                "Do not invent document facts. Make questions specific, useful, and varied."
            )
        },
        {
            "role": "user",
            "content": f"[Document context]\n{context}\n\nGenerate 3 suggested questions that can be answered from this context."
        }
    ]
    response = _groq_client().chat.completions.create(
        model=GROQ_MODEL,
        messages=messages,
        temperature=0.4,
    )
    questions = _parse_json_array_response(response.choices[0].message.content)
    return _ground_suggestions(questions, context)


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


def _knowledge_audit_source_blocks(source_context: str) -> list[dict]:
    blocks = []
    pattern = re.compile(r"\[Source ID: ([^\]]+)\]\s*(.*?)(?=\n\n\[Source ID: |\Z)", re.DOTALL)
    for match in pattern.finditer(source_context or ""):
        sid = match.group(1).strip()
        text = match.group(2).strip()
        if sid and text:
            blocks.append({"source_id": sid, "text": text})
    return blocks


def _sentence_parts(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text or "")
    return [part.strip() for part in parts if part and part.strip()]


def _fact_key_terms(sentence: str) -> set[str]:
    label_match = re.match(r"^\s*([A-Za-z][A-Za-z0-9 /_-]{1,60})\s*[:=-]\s*", sentence or "")
    source = label_match.group(1) if label_match else sentence
    terms = []
    for term in _tokenize(source):
        if term in STOPWORDS or len(term) < 3:
            continue
        if PRICE_RE.fullmatch(term) or DATE_RE.fullmatch(term):
            continue
        if term in {"usd", "dollar", "dollars"}:
            continue
        terms.append(term)
    return set(terms[:8])


def _normalize_price(value: str) -> str:
    number = re.sub(r"[^\d.]", "", value or "")
    return number.rstrip("0").rstrip(".") if "." in number else number


def _normalize_date(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def _normalize_status(value: str) -> str:
    normalized = (value or "").strip().lower()
    for group, terms in STATUS_GROUPS.items():
        if normalized in terms:
            return group
    return normalized


def _extract_comparable_facts(source_context: str) -> list[dict]:
    facts = []
    for block in _knowledge_audit_source_blocks(source_context):
        sid = block["source_id"]
        for sentence in _sentence_parts(block["text"]):
            terms = _fact_key_terms(sentence)
            if len(terms) < 2:
                continue
            for match in PRICE_RE.finditer(sentence):
                facts.append({"type": "price", "value": _normalize_price(match.group(0)), "terms": terms, "source_id": sid, "text": sentence})
            for match in DATE_RE.finditer(sentence):
                facts.append({"type": "date", "value": _normalize_date(match.group(0)), "terms": terms, "source_id": sid, "text": sentence})
            for match in STATUS_RE.finditer(sentence):
                facts.append({"type": "status", "value": _normalize_status(match.group(0)), "terms": terms, "source_id": sid, "text": sentence})
    return facts


def detect_possible_contradictions(source_context: str, source_catalog: list | None = None, limit: int = 5) -> list[dict]:
    valid_ids = _valid_source_ids(source_catalog) if source_catalog else None
    facts = _extract_comparable_facts(source_context)
    contradictions = []
    seen = set()
    for idx, left in enumerate(facts):
        for right in facts[idx + 1:]:
            if left["source_id"] == right["source_id"]:
                continue
            if valid_ids is not None and (left["source_id"] not in valid_ids or right["source_id"] not in valid_ids):
                continue
            if left["type"] != right["type"] or left["value"] == right["value"]:
                continue
            shared = sorted(left["terms"] & right["terms"])
            if len(shared) < 2:
                continue
            key = (left["type"], tuple(sorted((left["source_id"], right["source_id"]))), tuple(shared[:4]))
            if key in seen:
                continue
            seen.add(key)
            topic = " ".join(shared[:4])
            contradictions.append(
                {
                    "status": "possible",
                    "type": left["type"],
                    "area": topic.title() if topic else left["type"].title(),
                    "detail": f"Possible conflicting {left['type']} values found for similar terms.",
                    "source_ids": [left["source_id"], right["source_id"]],
                }
            )
            if len(contradictions) >= limit:
                return contradictions
    return contradictions


def infer_missing_required_documents(source_context: str) -> list[str]:
    text = (source_context or "").lower()
    suggestions = []

    def missing_any(terms: tuple[str, ...]) -> bool:
        return not any(term in text for term in terms)

    job_like = re.search(r"\b(job|role|candidate|hire|hiring|qualification|interview|resume|portfolio)\b", text)
    if job_like:
        if missing_any(("company", "mission", "culture", "team", "department")):
            suggestions.append("Company and team context")
        if missing_any(("project example", "sample project", "portfolio", "case study", "work sample")):
            suggestions.append("Project examples or work-sample expectations")
        if missing_any(("evaluation", "criteria", "rubric", "scorecard")):
            suggestions.append("Evaluation criteria or interview scorecard")
        if missing_any(("interview process", "interview stage", "timeline", "next steps")):
            suggestions.append("Interview process and hiring timeline")

    support_like = re.search(r"\b(customer|support|service|refund|pricing|price|subscription|escalation)\b", text)
    if support_like:
        if missing_any(("price", "pricing", "$", "cost", "subscription")):
            suggestions.append("Pricing or plan details")
        if missing_any(("refund", "return", "cancellation", "cancel")):
            suggestions.append("Refund, return, or cancellation policy")
        if missing_any(("scope", "service includes", "included", "not included")):
            suggestions.append("Service scope and exclusions")
        if missing_any(("escalation", "manager", "priority", "urgent")):
            suggestions.append("Escalation process")

    study_like = re.search(r"\b(study|lesson|course|chapter|student|learning|exam|quiz|assessment)\b", text)
    if study_like:
        if missing_any(("example", "sample", "case study")):
            suggestions.append("Worked examples")
        if missing_any(("definition", "glossary", "terms")):
            suggestions.append("Definitions or glossary")
        if missing_any(("question", "quiz", "assessment", "exercise")):
            suggestions.append("Assessment questions or practice exercises")

    result = []
    for item in suggestions:
        if item not in result:
            result.append(item)
    return result


def compute_retrieval_confidence(sources: list | None, trace: dict | None = None) -> dict:
    sources = sources if isinstance(sources, list) else []
    final_count = len(sources)
    source_names = {source.get("source") for source in sources if isinstance(source, dict) and source.get("source")}
    keyword_hits = sum(
        1 for source in sources
        if isinstance(source, dict) and (
            "keyword" in (source.get("retrieval_methods") or [])
            or source.get("retrieval_method") == "keyword"
            or source.get("exact_terms")
        )
    )
    scores = [int(source.get("score", 0)) for source in sources if isinstance(source, dict)]
    avg_score = sum(scores) / len(scores) if scores else 0

    score = min(100, round((final_count * 4) + (len(source_names) * 10) + (keyword_hits * 4) + (avg_score * 0.45)))
    if final_count == 0:
        score = 0
    level = "High" if score >= 75 else "Medium" if score >= 45 else "Low"

    notes = []
    if final_count:
        notes.append(f"{final_count} retrieved chunks across {len(source_names)} source document(s)")
    else:
        notes.append("No retrieved source chunks")
    if keyword_hits:
        notes.append("Exact-term retrieval contributed to the result")
    if trace and isinstance(trace, dict):
        notes.append(f"Hybrid retrieval returned {trace.get('final_candidate_count', final_count)} final candidate(s)")
    return {"level": level, "score": score, "notes": notes}


def _readiness_level(score: int) -> str:
    if score >= 75:
        return "High"
    if score >= 45:
        return "Medium"
    return "Low"


def _unique_text_count(*values) -> int:
    seen = set()
    for value in values:
        if not isinstance(value, list):
            continue
        for item in value:
            normalized = re.sub(r"\s+", " ", str(item).strip().lower())
            if normalized:
                seen.add(normalized)
    return len(seen)


def compute_readiness_verdict(
    result: dict,
    source_context: str = "",
    source_catalog: list | None = None,
    retrieval_confidence: dict | None = None,
) -> dict:
    coverage = len(result.get("coverage_summary", []))
    risks = len(result.get("risk_areas", []))
    missing = _unique_text_count(result.get("missing_knowledge", []), result.get("missing_information", []))
    missing_required = len(result.get("missing_required_documents", []))
    contradictions = len(result.get("contradictions", []))
    sources_used = result.get("sources_used", [])
    valid_source_context = source_context.strip() if isinstance(source_context, str) else ""
    referenced_source_ids = set(sources_used if isinstance(sources_used, list) else [])
    for field in ("coverage_summary", "risk_areas", "contradictions"):
        for item in result.get(field, []):
            if isinstance(item, dict):
                referenced_source_ids.update(item.get("source_ids", []))
    if source_catalog is not None:
        valid_ids = _valid_source_ids(source_catalog)
        has_valid_sources = bool(referenced_source_ids & valid_ids)
    else:
        has_valid_sources = bool(valid_source_context or referenced_source_ids or coverage)

    reasons = []
    if coverage < 2:
        reasons.append("Insufficient knowledge coverage")
    if not has_valid_sources:
        reasons.append("No source-grounded context available")
    if risks >= 3:
        reasons.append("Too many risk areas identified")
    if missing >= 3:
        reasons.append("Too much missing knowledge")
    if missing_required >= 3:
        reasons.append("Several required supporting documents appear to be missing")
    if contradictions:
        reasons.append("Possible contradictions need review")

    score = 55 + min(25, coverage * 6)
    score -= min(35, risks * 10)
    score -= min(30, missing * 7)
    score -= min(25, missing_required * 6)
    score -= min(30, contradictions * 12)
    if retrieval_confidence and isinstance(retrieval_confidence, dict):
        confidence_score = int(retrieval_confidence.get("score", 0) or 0)
        if confidence_score < 45:
            score -= 15
        elif confidence_score >= 75:
            score += 5
    if coverage < 2 or not has_valid_sources:
        score = min(score, 35)

    score = max(0, min(100, round(score)))
    level = _readiness_level(score)
    if coverage < 2 or not has_valid_sources or risks >= 3 or missing >= 3:
        level = "Low"
        score = min(score, 44)
    elif coverage >= 4 and risks == 0 and missing <= 1 and missing_required <= 1 and contradictions == 0:
        level = "High"
        score = max(score, 75)

    if not reasons:
        reasons.append("Adequate knowledge coverage with limited known gaps")

    external_penalty = 15 if (risks or contradictions or EXTERNAL_RISK_TERMS_RE.search(source_context or "")) else 5
    external_score = max(0, score - external_penalty)
    automation_score = max(0, score - (20 if risks or missing or missing_required or contradictions else 5))

    return {
        "level": level,
        "score": score,
        "reasons": reasons,
        "internal_use": {"level": _readiness_level(score), "score": score},
        "external_customer_facing": {"level": _readiness_level(external_score), "score": external_score},
        "automation": {"level": _readiness_level(automation_score), "score": automation_score},
    }


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
                "\"coverage\": [{\"area\": \"...\", \"source_ids\": [\"s1\"]}], "
                "\"missing_knowledge\": [\"...\"], "
                "\"missing_information\": [\"...\"], "
                "\"missing_required_documents\": [\"...\"], "
                "\"risk_areas\": [{\"area\": \"...\", \"detail\": \"...\", \"source_ids\": [\"s1\"]}], "
                "\"contradictions\": [{\"status\": \"possible\", \"area\": \"...\", \"detail\": \"...\", \"source_ids\": [\"s1\", \"s2\"]}], "
                "\"suggested_next_documents\": [\"...\"], "
                "\"recommended_next_documents\": [\"...\"], "
                "\"automation_readiness\": [{\"category\": \"Safe to answer from sources\", \"items\": [\"...\"]}], "
                "\"sources_used\": [\"s1\"]"
                "} "
                "Avoid claiming coverage unless supported by source IDs. "
                "Include missing information when docs are weak. "
                "Keep contradiction claims conservative and label uncertain conflicts as possible. "
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
        "coverage": [],
        "missing_knowledge": [],
        "missing_information": [],
        "missing_required_documents": [],
        "risk_areas": [],
        "contradictions": [],
        "suggested_next_documents": [],
        "recommended_next_documents": [],
        "automation_readiness": [],
        "sources_used": [],
    }

    cs = payload.get("coverage_summary", payload.get("coverage", []))
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
        result["coverage"] = list(cleaned)

    mk = payload.get("missing_knowledge", payload.get("missing_information"))
    if isinstance(mk, list):
        missing_items = [str(m) for m in mk if isinstance(m, str) and m.strip()]
        result["missing_knowledge"] = missing_items
        result["missing_information"] = list(missing_items)

    mrd = payload.get("missing_required_documents")
    if isinstance(mrd, list):
        result["missing_required_documents"] = [str(m) for m in mrd if isinstance(m, str) and m.strip()]

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

    contradictions = payload.get("contradictions", [])
    if isinstance(contradictions, list):
        cleaned = []
        for item in contradictions:
            if not isinstance(item, dict):
                continue
            area = item.get("area", "")
            detail = item.get("detail", "")
            status = item.get("status", "possible")
            if not isinstance(area, str) or not area.strip():
                continue
            raw_ids = item.get("source_ids", [])
            if isinstance(raw_ids, str):
                raw_ids = [raw_ids]
            if not isinstance(raw_ids, list):
                raw_ids = []
            cleaned.append(
                {
                    "status": str(status) if str(status).lower() == "certain" else "possible",
                    "area": area,
                    "detail": str(detail),
                    "source_ids": [str(s) for s in raw_ids if isinstance(s, str)],
                }
            )
        result["contradictions"] = cleaned

    snd = payload.get("suggested_next_documents", payload.get("recommended_next_documents"))
    if isinstance(snd, list):
        next_docs = [str(m) for m in snd if isinstance(m, str) and m.strip()]
        result["suggested_next_documents"] = next_docs
        result["recommended_next_documents"] = list(next_docs)

    ar = payload.get("automation_readiness", [])
    canonical_cats = ("Safe to answer from sources", "AI draft + human review", "Keep manual")
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
        "coverage": [],
        "missing_knowledge": list(result.get("missing_knowledge", [])),
        "missing_information": list(result.get("missing_information", result.get("missing_knowledge", []))),
        "missing_required_documents": list(result.get("missing_required_documents", [])),
        "risk_areas": [],
        "contradictions": [],
        "suggested_next_documents": list(result.get("suggested_next_documents", [])),
        "recommended_next_documents": list(result.get("recommended_next_documents", result.get("suggested_next_documents", []))),
        "automation_readiness": list(result.get("automation_readiness", [])),
        "sources_used": _sanitize_source_ids(result.get("sources_used", []), valid_ids),
    }
    for cov in result.get("coverage_summary", result.get("coverage", [])):
        if not isinstance(cov, dict):
            continue
        area = cov.get("area", "")
        if not isinstance(area, str) or not area.strip():
            continue
        clean_ids = _sanitize_source_ids(cov.get("source_ids", []), valid_ids)
        if clean_ids:
            sanitized["coverage_summary"].append({"area": area, "source_ids": clean_ids})
    sanitized["coverage"] = list(sanitized["coverage_summary"])

    for risk in result.get("risk_areas", []):
        if not isinstance(risk, dict):
            continue
        area = risk.get("area", "")
        detail = risk.get("detail", "")
        if not isinstance(area, str) or not area.strip():
            continue
        clean_ids = _sanitize_source_ids(risk.get("source_ids", []), valid_ids)
        sanitized["risk_areas"].append({"area": area, "detail": detail, "source_ids": clean_ids})

    for item in result.get("contradictions", []):
        if not isinstance(item, dict):
            continue
        area = item.get("area", "")
        detail = item.get("detail", "")
        if not isinstance(area, str) or not area.strip():
            continue
        clean_ids = _sanitize_source_ids(item.get("source_ids", []), valid_ids)
        if clean_ids:
            status = str(item.get("status", "possible")).lower()
            sanitized["contradictions"].append(
                {
                    "status": "certain" if status == "certain" else "possible",
                    "area": area,
                    "detail": str(detail),
                    "source_ids": clean_ids,
                }
            )

    return sanitized


def finalize_knowledge_audit(
    result: dict,
    source_context: str,
    source_catalog: list,
    sources: list | None = None,
    retrieval_trace: dict | None = None,
) -> dict:
    sanitized = sanitize_knowledge_audit_source_ids(result, source_catalog)
    valid_ids = _valid_source_ids(source_catalog) if source_catalog else set()

    heuristic_contradictions = detect_possible_contradictions(source_context, source_catalog)
    existing_keys = {
        (item.get("area"), tuple(item.get("source_ids", [])))
        for item in sanitized.get("contradictions", [])
        if isinstance(item, dict)
    }
    for item in heuristic_contradictions:
        clean_ids = _sanitize_source_ids(item.get("source_ids", []), valid_ids)
        key = (item.get("area"), tuple(clean_ids))
        if clean_ids and key not in existing_keys:
            sanitized["contradictions"].append({**item, "source_ids": clean_ids})
            existing_keys.add(key)

    inferred_missing_docs = infer_missing_required_documents(source_context)
    for item in inferred_missing_docs:
        if item not in sanitized["missing_required_documents"]:
            sanitized["missing_required_documents"].append(item)

    next_docs = list(sanitized.get("recommended_next_documents") or sanitized.get("suggested_next_documents") or [])
    for item in sanitized["missing_required_documents"]:
        if item not in next_docs:
            next_docs.append(item)
    sanitized["suggested_next_documents"] = next_docs
    sanitized["recommended_next_documents"] = list(next_docs)

    if not sanitized.get("missing_information"):
        sanitized["missing_information"] = list(sanitized.get("missing_knowledge", []))
    if not sanitized.get("missing_knowledge"):
        sanitized["missing_knowledge"] = list(sanitized.get("missing_information", []))

    used = list(sanitized.get("sources_used", []))
    for field in ("coverage_summary", "risk_areas", "contradictions"):
        for item in sanitized.get(field, []):
            if not isinstance(item, dict):
                continue
            for sid in item.get("source_ids", []):
                if sid in valid_ids and sid not in used:
                    used.append(sid)
    sanitized["sources_used"] = used

    retrieval_confidence = compute_retrieval_confidence(sources or source_catalog, retrieval_trace)
    sanitized["retrieval_confidence"] = retrieval_confidence
    verdict = compute_readiness_verdict(sanitized, source_context, source_catalog, retrieval_confidence)
    sanitized["readiness_verdict"] = verdict
    sanitized["readiness_score"] = verdict["score"]
    sanitized["readiness_level"] = verdict["level"]
    sanitized["coverage"] = list(sanitized.get("coverage_summary", []))
    return sanitized


if __name__ == "__main__":
    q = input("Ask a question: ")
    answer, srcs = query_documents(q)
    print(f"\nAnswer: {answer}")
    print(f"Sources: {srcs}")

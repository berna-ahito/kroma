import html
import json
import os
import shutil
from datetime import datetime
from pathlib import Path

import streamlit as st

from ingest import CHROMA_PATH, DOCS_FOLDER, STATS_FILE, ingest_documents, load_index_stats
from rag import generate_answer, retrieve_chunks


BASE_DIR = Path(__file__).resolve().parent
HISTORY_FILE = BASE_DIR / "chat_history.json"


st.set_page_config(
    page_title="Kroma",
    page_icon=":briefcase:",
    layout="centered",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

:root {
  --navy: #0f172a;
  --navy-2: #1e293b;
  --navy-3: #334155;
  --blue: #2563eb;
  --blue-soft: #eff6ff;
  --blue-border: #bfdbfe;
  --bg: #f1f5f9;
  --white: #ffffff;
  --text: #0f172a;
  --text-2: #64748b;
  --text-3: #94a3b8;
  --border: #e2e8f0;
  --radius: 8px;
}

[data-testid="stSidebar"] {
  background: #0f172a !important;
}
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] small,
[data-testid="stSidebar"] caption,
[data-testid="stSidebar"] .stCaption > div,
[data-testid="stSidebarContent"] > section > div > div > div > p {
  color: #e2e8f0 !important;
  font-size: 1rem !important;
}
[data-testid="stSidebar"] h2,
[data-testid="stSidebar"] h3 {
  color: #94a3b8 !important;
  font-size: 0.85rem !important;
  font-weight: 600 !important;
  text-transform: uppercase !important;
  letter-spacing: 0.07em !important;
}

[data-testid="stSidebar"] [data-testid="stFileUploader"] {
  background: #1e293b !important;
  border: 1px dashed #334155 !important;
  border-radius: 8px !important;
  padding: 0.5rem !important;
}

[data-testid="stSidebar"] [data-testid="stFileUploader"] button {
  background: #1e293b !important;
  color: #e2e8f0 !important;
  border: 1px solid #475569 !important;
  border-radius: 6px !important;
  font-weight: 500 !important;
}

[data-testid="stSidebar"] [data-testid="stFileUploader"] button * {
  color: #e2e8f0 !important;
  -webkit-text-fill-color: #e2e8f0 !important;
}

[data-testid="stSidebar"] [data-testid="stFileUploader"] small {
  color: #94a3b8 !important;
}

div.stButton > button[kind="primary"] {
  background: #f59e0b !important;
  color: #1a1a2e !important;
  border: none !important;
  font-weight: 700 !important;
}
div.stButton > button[kind="primary"]:hover {
  background: #d97706 !important;
}

html, body,
.main,
[data-testid="stAppViewContainer"],
[data-testid="stMain"] {
  font-family: 'Inter', -apple-system, sans-serif !important;
  background: var(--bg);
  color: var(--text);
}

[class*="material-symbols"],
[class*="material-icons"],
.material-symbols-rounded,
.material-icons {
  font-family: 'Material Symbols Rounded', 'Material Icons' !important;
}

#MainMenu, footer, [data-testid="stToolbar"] { visibility: hidden; }

header[data-testid="stHeader"] { background: transparent; height: 0; }

.main .block-container {
  max-width: 750px;
  padding: 1.5rem 1.5rem 7rem;
  margin: 0 auto;
}

[data-testid="stAppViewContainer"]::before {
  content: "";
  position: fixed;
  top: 0; left: 0; right: 0;
  height: 3px;
  background: linear-gradient(90deg, #2563eb, #f59e0b);
  z-index: 9999;
}

/* BUTTONS */
div.stButton > button[kind="primary"] {
  background: #f59e0b !important;
  color: #1a1a2e !important;
  border: none !important;
  border-radius: 6px !important;
  font-weight: 600 !important;
  font-size: 0.85rem !important;
  padding: 0.4rem 0.9rem !important;
}
div.stButton > button[kind="primary"]:hover { background: #d97706 !important; }
div.stButton > button {
  border-radius: 6px !important;
  font-weight: 500 !important;
  font-size: 0.8rem !important;
  border: 1px solid #334155 !important;
  background: #1e293b !important;
  color: #e2e8f0 !important;
  padding: 0.35rem 0.75rem !important;
}

/* HEADER */
.app-header { text-align: center; margin-bottom: 1.5rem; }
.header-panel h1 {
  font-size: 3.5rem;
  font-weight: 700;
  color: var(--navy);
  letter-spacing: -0.02em;
  margin: 0 0 0.35rem;
}
.header-panel p {
  font-size: 1.3rem;
  color: var(--text-2);
  margin: 0;
}

/* METRICS */
.metric-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.6rem;
  margin: 0 auto 1.25rem;
  max-width: 480px;
}
.metric-card {
  background: var(--white);
  border: 1px solid var(--border);
  border-top: 2px solid var(--blue);
  border-radius: var(--radius);
  padding: 0.7rem 0.85rem;
}
.metric-card span {
  font-size: 1rem;
  font-weight: 600;
  letter-spacing: 0.07em;
  text-transform: uppercase;
  color: var(--text-3);
  display: block;
  margin-bottom: 0.2rem;
}
.metric-card strong {
  font-size: 2rem;
  font-weight: 700;
  color: var(--navy);
  display: block;
  line-height: 1;
}

/* DOC CARDS */
.doc-card {
  background: var(--white);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 0.6rem 0.75rem;
  margin-bottom: 0.4rem;
}
.doc-card.sidebar {
  background: var(--navy-2);
  border-color: var(--navy-3);
}
.doc-card.sidebar .doc-name { color: #f1f5f9 !important; }
.doc-card.sidebar .doc-meta { color: var(--text-3) !important; }
.doc-name { font-size: 0.95rem; font-weight: 600; color: var(--text); margin-bottom: 0.2rem; overflow-wrap: anywhere; }
.doc-meta { font-size: 0.8rem; color: var(--text-3); }

/* SOURCE CARDS */
.source-card {
  background: var(--white);
  border: 1px solid var(--border);
  border-left: 3px solid var(--blue);
  border-radius: var(--radius);
  padding: 0.65rem 0.8rem;
  margin: 0.4rem 0;
}
.source-head { display: flex; align-items: center; justify-content: space-between; gap: 0.5rem; margin-bottom: 0.25rem; flex-wrap: wrap; }
.source-title { font-size: 0.78rem; font-weight: 600; color: var(--navy); }
.source-preview { font-size: 0.76rem; color: var(--text-2); line-height: 1.5; margin: 0; }

/* BADGES */
.score { border-radius: 999px; padding: 0.12rem 0.45rem; font-size: 0.67rem; font-weight: 600; white-space: nowrap; }
.score-high { color: #166534; background: #dcfce7; border: 1px solid #bbf7d0; }
.score-med  { color: #92400e; background: #fef3c7; border: 1px solid #fde68a; }
.score-low  { color: #991b1b; background: #fee2e2; border: 1px solid #fecaca; }

/* THINKING CHIPS */
.thinking-chip {
  display: inline-flex; align-items: center;
  border-radius: 999px;
  border: 1px solid var(--blue-border);
  background: var(--blue-soft);
  color: #1d4ed8;
  padding: 0.12rem 0.45rem;
  margin: 0.1rem;
  font-size: 0.7rem; font-weight: 500;
}

/* EMPTY STATE */
.empty-state {
  background: var(--white);
  border: 1.5px dashed var(--border);
  border-radius: 10px;
  text-align: center;
  padding: 2.5rem 1.5rem;
  margin: 1.5rem auto;
  max-width: 480px;
}
.empty-state h3 { font-size: 1rem; font-weight: 600; color: var(--navy); margin: 0 0 0.4rem; }
.empty-state p { font-size: 0.85rem; color: var(--text-2); margin: 0; line-height: 1.6; }

/* CHAT */
[data-testid="stChatMessage"] {
  background: var(--white) !important;
  border: 1px solid var(--border) !important;
  border-radius: var(--radius) !important;
  padding: 0.6rem 0.85rem !important;
  margin-bottom: 0.6rem !important;
}
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {
  background: var(--blue-soft) !important;
  border-color: var(--blue-border) !important;
}

/* CHAT INPUT */
[data-testid="stBottomBlockContainer"],
[data-testid="stBottom"] {
  background: #f1f5f9 !important;
  border-top: 1px solid var(--border);
}
[data-testid="stChatInput"] textarea {
  font-family: 'Inter', sans-serif !important;
  border-radius: 8px !important;
  border: 1.5px solid var(--border) !important;
  background: var(--white) !important;
  color: var(--text) !important;
  font-size: 0.9rem !important;
}
[data-testid="stChatInput"] textarea:focus {
  border-color: var(--blue) !important;
  box-shadow: 0 0 0 3px rgba(37,99,235,0.1) !important;
}

/* EXPANDER */
[data-testid="stExpander"] {
  border: 1px solid var(--border) !important;
  border-radius: var(--radius) !important;
  background: var(--white) !important;
  margin-bottom: 0.75rem;
}
[data-testid="stExpander"] summary {
  background: #f8fafc !important;
  border-radius: var(--radius) var(--radius) 0 0 !important;
  font-size: 0.8rem !important;
}

.history-note {
  background: var(--blue-soft);
  border: 1px solid var(--blue-border);
  border-radius: var(--radius);
  padding: 0.55rem 0.75rem;
  color: #1d4ed8;
  font-size: 0.78rem;
  margin-bottom: 0.75rem;
}

.notice {
  background: #fffbeb;
  border: 1px solid #fde68a;
  color: #92400e;
  border-radius: var(--radius);
  padding: 0.55rem 0.75rem;
  font-size: 0.78rem;
  margin-bottom: 0.75rem;
}
</style>
""",
    unsafe_allow_html=True,
)

def load_history() -> list:
    try:
        with HISTORY_FILE.open(encoding="utf-8") as fh:
            data = json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return []

    if not isinstance(data, list):
        return []

    messages = []
    for item in data:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        content = item.get("content")
        if role in {"user", "assistant"} and isinstance(content, str):
            messages.append(
                {
                    "role": role,
                    "content": content,
                    "sources": item.get("sources", []),
                    "timestamp": item.get("timestamp"),
                }
            )
    return messages


def save_history(messages: list) -> None:
    serializable = []
    for message in messages:
        serializable.append(
            {
                "role": message.get("role"),
                "content": message.get("content"),
                "sources": message.get("sources", []),
                "timestamp": message.get("timestamp") or datetime.now().isoformat(timespec="seconds"),
            }
        )

    temp_path = HISTORY_FILE.with_suffix(".json.tmp")
    with temp_path.open("w", encoding="utf-8") as fh:
        json.dump(serializable, fh, indent=2, ensure_ascii=False)
    temp_path.replace(HISTORY_FILE)


def compact_pages(pages: list[int]) -> str:
    if not pages:
        return "No indexed pages"

    sorted_pages = sorted(set(int(p) for p in pages))
    ranges = []
    start = prev = sorted_pages[0]
    for page in sorted_pages[1:]:
        if page == prev + 1:
            prev = page
            continue
        ranges.append(f"{start}-{prev}" if start != prev else str(start))
        start = prev = page
    ranges.append(f"{start}-{prev}" if start != prev else str(start))
    return ", ".join(ranges)


def format_bytes(size: int | None) -> str:
    if not size:
        return "Unknown size"
    units = ["B", "KB", "MB", "GB"]
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{size} B"


def score_class(score: int) -> str:
    if score >= 72:
        return "score-high"
    if score >= 48:
        return "score-med"
    return "score-low"


def confidence_label(score: int) -> str:
    if score >= 72:
        return "High"
    if score >= 48:
        return "Medium"
    return "Low"


def score_badge(score: int) -> str:
    safe_score = max(0, min(100, int(score or 0)))
    return (
        f'<span class="score {score_class(safe_score)}">'
        f'{safe_score}% {confidence_label(safe_score)}</span>'
    )


def page_pills(doc: dict, limit: int = 14) -> str:
    page_chunks = doc.get("page_chunks") or []
    if not page_chunks:
        return ""

    pills = []
    for item in page_chunks[:limit]:
        page = html.escape(str(item.get("page", "?")))
        chunks = html.escape(str(item.get("chunks", 0)))
        pills.append(f'<span class="page-pill">p{page}: {chunks}</span>')
    remaining = len(page_chunks) - limit
    if remaining > 0:
        pills.append(f'<span class="page-pill">+{remaining} pages</span>')
    return f'<div class="page-pills">{"".join(pills)}</div>'


def doc_card(doc: dict, sidebar: bool = False, active: bool = False) -> str:
    name = html.escape(doc.get("name", "Unknown document"))
    pages = int(doc.get("pages", 0) or 0)
    chunks = int(doc.get("chunks", 0) or 0)
    css_class = "doc-card sidebar" if sidebar else "doc-card"
    if sidebar and active:
        css_class += " active"
    if sidebar:
        return f"""
<div class="{css_class}">
  <div class="doc-name">{name}</div>
  <div class="doc-meta">{pages} pages</div>
</div>
"""

    return f"""
<div class="{css_class}">
  <div class="doc-name">{name}</div>
  <div class="doc-meta">{pages} pages - {chunks} chunks</div>
</div>
"""


def source_card(source: dict, compact: bool = False) -> str:
    score = int(source.get("score", 0) or 0)
    name = html.escape(Path(source.get("source", "Unknown document")).name)
    page = html.escape(str(source.get("page", "?")))
    chunk = source.get("doc_chunk_id") or source.get("chunk_id")
    rank = source.get("rank")
    rank_text = f"Match {html.escape(str(rank))} - " if rank else ""
    chunk_text = ""
    preview = html.escape(source.get("preview", "").strip())
    if compact and len(preview) > 145:
        preview = preview[:145] + "..."
    return f"""
<div class="source-card">
  <div class="source-head">
    <span class="source-title">{rank_text}{name} - page {page}{chunk_text}</span>
    {score_badge(score)}
  </div>
  <p class="source-preview">{preview}</p>
</div>
"""


def thinking_chip(source: dict) -> str:
    name = html.escape(Path(source.get("source", "Unknown document")).name)
    page = html.escape(str(source.get("page", "?")))
    chunk = html.escape(str(source.get("doc_chunk_id") or source.get("chunk_id") or "?"))
    score = html.escape(str(source.get("score", 0)))
    return f'<span class="thinking-chip">{name} p{page} chunk {chunk} - {score}%</span>'


def render_sources(sources: list, expanded: bool = False) -> None:
    if not sources:
        return
    avg = round(sum(int(s.get("score", 0) or 0) for s in sources) / len(sources))
    with st.expander(
        f"Retrieved evidence: {len(sources)} chunks - average relevance {avg}%",
        expanded=expanded,
    ):
        for source in sources:
            st.markdown(source_card(source), unsafe_allow_html=True)


def format_updated_date(value: str | None) -> str:
    if not value:
        return "Not recorded"
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return str(value)
    return f"{parsed.strftime('%B')} {parsed.day}, {parsed.year}"


def render_summary(stats: dict, expanded: bool = False) -> None:
    docs = stats.get("docs", [])
    total_pages = int(stats.get("total_pages") or sum(doc.get("pages", 0) for doc in docs))
    total_chunks = int(stats.get("total_chunks", 0) or 0)
    processed_at = format_updated_date(stats.get("processed_at"))

    st.markdown(
        f"""
<div class="metric-grid">
  <div class="metric-card"><span>Documents</span><strong>{len(docs)}</strong></div>
  <div class="metric-card"><span>Pages</span><strong>{total_pages}</strong></div>
  <div class="metric-card"><span>Chunks</span><strong>{total_chunks}</strong></div>
</div>
""",
        unsafe_allow_html=True,
    )

    with st.expander(f"Last updated: {processed_at}", expanded=expanded):
        if not docs:
            st.caption("No documents have been processed yet.")
        for doc in docs:
            st.markdown(doc_card(doc), unsafe_allow_html=True)


def render_header(stats: dict | None) -> None:
    docs = stats.get("docs", []) if stats else []
    subtitle = (
        "Ask reliable questions across your document library."
        if docs
        else "Add documents to create a searchable workspace."
    )

    st.markdown(
        f"""
<div class="app-header">
  <div class="header-panel">
    <h1>Kroma</h1>
    <p>{html.escape(subtitle)}</p>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )


def save_uploads(uploads) -> int:
    saved = 0
    DOCS_FOLDER.mkdir(exist_ok=True)
    for upload in uploads:
        filename = Path(upload.name).name
        if not filename.lower().endswith(".pdf"):
            continue
        destination = DOCS_FOLDER / filename
        with destination.open("wb") as fh:
            fh.write(upload.getbuffer())
        saved += 1
    return saved


DOCS_FOLDER.mkdir(exist_ok=True)

if "messages" not in st.session_state:
    st.session_state.messages = load_history()
    st.session_state.history_restored = bool(st.session_state.messages)

if "ingest_stats" not in st.session_state:
    st.session_state.ingest_stats = load_index_stats()

if "ingested" not in st.session_state:
    st.session_state.ingested = CHROMA_PATH.exists()

if "show_ingest_summary" not in st.session_state:
    st.session_state.show_ingest_summary = False
    
if "delete_doc" not in st.session_state:
    st.session_state.delete_doc = None
    
if "upload_key" not in st.session_state:
    st.session_state.upload_key = 0

if st.session_state.delete_doc:
    target = DOCS_FOLDER / st.session_state.delete_doc
    if target.exists():
        target.unlink()
    st.session_state.delete_doc = None
    remaining_pdfs = list(DOCS_FOLDER.glob("*.pdf"))
    if remaining_pdfs:
        try:
            st.session_state.ingest_stats = ingest_documents()
            st.session_state.ingested = True
        except Exception:
            st.session_state.ingest_stats = None
            st.session_state.ingested = False
    else:
        st.session_state.ingest_stats = None
        st.session_state.ingested = False
    st.rerun()

current_stats = st.session_state.ingest_stats or load_index_stats()
render_header(current_stats)

with st.sidebar:
    st.markdown("## Documents")
    st.caption("Upload PDFs and keep your library ready for questions.")

    uploads = st.file_uploader(
        "Upload PDFs",
        type=["pdf"],
        accept_multiple_files=True,
        label_visibility="collapsed",
        key=f"uploader_{st.session_state.get('upload_key', 0)}",
    )
    if uploads:
        saved_count = save_uploads(uploads)
        if saved_count:
            st.success(f"Added {saved_count} PDF file(s).")

    if st.button("Process Documents", use_container_width=True, type="primary"):
        pdfs = sorted(path for path in DOCS_FOLDER.iterdir() if path.suffix.lower() == ".pdf")
        if not pdfs:
            st.warning("Add at least one PDF first.")
        else:
            with st.spinner("Updating your library..."):
                try:
                    st.session_state.ingest_stats = ingest_documents()
                    st.session_state.ingested = True
                    st.session_state.show_ingest_summary = True
                    st.session_state.upload_key = st.session_state.get("upload_key", 0) + 1
                    st.rerun()
                except Exception as exc:
                    st.error(f"Indexing failed: {exc}")

    sidebar_stats = st.session_state.ingest_stats or load_index_stats()
    if sidebar_stats and sidebar_stats.get("docs"):
        st.markdown("### Library")
        for index, document in enumerate(sidebar_stats["docs"]):
            doc_name = document.get("name", "")
            col1, col2 = st.columns([5, 1])
            with col1:
                st.markdown(f"""<div class="doc-card sidebar">
  <div class="doc-name">{doc_name}</div>
  <div class="doc-meta">{document.get('pages', 0)} pages</div>
</div>""", unsafe_allow_html=True)
            with col2:
                st.markdown("<div style='margin-top:0.4rem'></div>", unsafe_allow_html=True)
                if st.button("🗑", key=f"del_{index}"):
                    st.session_state.delete_doc = doc_name
                    st.rerun()
    else:
        pending_pdfs = sorted(path.name for path in DOCS_FOLDER.iterdir() if path.suffix.lower() == ".pdf")
        if pending_pdfs:
            st.markdown("### Ready to index")
            for pdf in pending_pdfs:
                st.caption(pdf)
        else:
            st.caption("No PDFs have been added yet.")

    st.divider()

    left, right = st.columns(2)
    with left:
        if st.button("Clear library", use_container_width=True):
            import gc
            gc.collect()
            for path in (CHROMA_PATH, STATS_FILE):
                if path.is_dir():
                    shutil.rmtree(path, ignore_errors=True)
                elif path.is_file():
                    try:
                        path.unlink()
                    except Exception:
                        pass
            for pdf in DOCS_FOLDER.glob("*.pdf"):
                try:
                    pdf.unlink()
                except Exception:
                    pass
            st.session_state.ingested = False
            st.session_state.ingest_stats = None
            st.session_state.show_ingest_summary = False
            st.rerun()
    with right:
        if st.button("New chat", use_container_width=True):
            st.session_state.messages = []
            if HISTORY_FILE.exists():
                HISTORY_FILE.unlink()
            st.session_state.history_restored = False
            st.rerun()

    st.divider()


if st.session_state.get("history_restored"):
    st.markdown(
        f'<div class="history-note">Restored {len(st.session_state.messages)} saved message(s) from chat_history.json.</div>',
        unsafe_allow_html=True,
    )
    st.session_state.history_restored = False


if current_stats and current_stats.get("docs"):
    render_summary(current_stats, expanded=st.session_state.get("show_ingest_summary", False))
    st.session_state.show_ingest_summary = False
elif st.session_state.ingested:
    st.markdown(
        '<div class="notice">Existing search index found. Reprocess documents once to refresh the executive library summary.</div>',
        unsafe_allow_html=True,
    )


if not st.session_state.ingested:
    st.markdown(
        """
<div class="empty-state">
  <h3 style="font-size:1.4rem;">Get started in 2 steps</h3>
  <p style="margin-bottom:1rem; font-size:1rem;">Upload your documents and ask questions — answers come directly from your files.</p>
  <div style="text-align:left; max-width:320px; margin:0 auto;">
    <div style="display:flex; align-items:flex-start; gap:0.75rem; margin-bottom:0.75rem;">
      <span style="background:#2563eb; color:white; border-radius:999px; width:22px; height:22px; display:flex; align-items:center; justify-content:center; font-size:0.75rem; font-weight:700; flex-shrink:0;">1</span>
      <span style="font-size:0.9rem; color:#374151;">Upload a PDF using the <strong>Upload</strong> button in the sidebar</span>
    </div>
    <div style="display:flex; align-items:flex-start; gap:0.75rem;">
      <span style="background:#2563eb; color:white; border-radius:999px; width:22px; height:22px; display:flex; align-items:center; justify-content:center; font-size:0.75rem; font-weight:700; flex-shrink:0;">2</span>
      <span style="font-size:0.9rem; color:#374151;">Click <strong>Process Documents</strong> to make it searchable</span>
    </div>
  </div>
</div>
""",
        unsafe_allow_html=True,
    )
    st.stop()


for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message["role"] == "assistant":
            render_sources(message.get("sources", []), expanded=False)


if prompt := st.chat_input("Ask anything about your documents..."):
    previous_messages = list(st.session_state.messages)
    user_message = {
        "role": "user",
        "content": prompt,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }
    st.session_state.messages.append(user_message)
    save_history(st.session_state.messages)

    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        try:
            seen_chunks = []

            with st.status("Thinking through the document library...", expanded=True) as status:
                st.write("Preparing semantic search across the indexed PDFs.")

                def progress(event: str, payload: dict) -> None:
                    if event == "prepare":
                        st.write(
                            f"Searching {payload.get('total_chunks', 0)} chunks "
                            f"across {payload.get('doc_count', 0)} document(s)."
                        )
                    elif event == "search":
                        st.write("Query embedded. Ranking the nearest document chunks.")
                    elif event == "candidate":
                        seen_chunks.append(payload)
                        st.markdown(thinking_chip(payload), unsafe_allow_html=True)
                    elif event == "empty":
                        st.write("No matching chunks were returned.")
                    elif event == "error":
                        st.write(f"Retrieval error: {payload.get('message', 'Unknown error')}")

                context, sources = retrieve_chunks(prompt, progress_callback=progress)

                if sources:
                    status.update(
                        label=f"Found {len(sources)} relevant chunks. Generating answer...",
                        state="running",
                        expanded=True,
                    )
                    for source in sources[:3]:
                        st.markdown(source_card(source, compact=True), unsafe_allow_html=True)
                else:
                    status.update(
                        label="No close chunks found. Generating from chat history only...",
                        state="running",
                        expanded=True,
                    )

                answer = generate_answer(prompt, context, previous_messages)
                status.update(label="Answer ready", state="complete", expanded=False)

            st.markdown(answer)
            render_sources(sources, expanded=True)

            assistant_message = {
                "role": "assistant",
                "content": answer,
                "sources": sources,
                "timestamp": datetime.now().isoformat(timespec="seconds"),
            }
            st.session_state.messages.append(assistant_message)
            save_history(st.session_state.messages)
        except Exception as exc:
            st.error(f"Error: {exc}")

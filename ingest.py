import gc
import json
import os
import shutil
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader
from langchain_community.embeddings import SentenceTransformerEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter


os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

BASE_DIR = Path(__file__).resolve().parent
DOCS_FOLDER = BASE_DIR / "docs"
CHROMA_PATH = BASE_DIR / "chroma_db"
NEXT_CHROMA_PATH = BASE_DIR / "chroma_db_next"
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
STATS_FILE = BASE_DIR / "index_stats.json"
CHUNK_SIZE = 600
CHUNK_OVERLAP = 120


def _write_json(path: Path, data: dict) -> None:
    temp_path = path.with_suffix(f"{path.suffix}.tmp")
    with temp_path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
    temp_path.replace(path)


def _file_metadata(path: Path) -> dict:
    stat = path.stat()
    return {
        "size_bytes": stat.st_size,
        "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
    }


def ingest_documents():
    DOCS_FOLDER.mkdir(exist_ok=True)
    pdf_files = sorted(path for path in DOCS_FOLDER.iterdir() if path.suffix.lower() == ".pdf")
    if not pdf_files:
        stats = {"total_chunks": 0, "total_pages": 0, "docs": [], "processed_at": None}
        _write_json(STATS_FILE, stats)
        return stats

    build_path = NEXT_CHROMA_PATH if CHROMA_PATH.exists() else CHROMA_PATH
    if build_path.exists():
        shutil.rmtree(build_path)

    all_documents = []
    doc_page_counts = {}
    doc_file_meta = {}

    for pdf_path in pdf_files:
        pages = PyPDFLoader(str(pdf_path)).load()
        doc_page_counts[pdf_path.name] = len(pages)
        doc_file_meta[pdf_path.name] = _file_metadata(pdf_path)
        all_documents.extend(pages)

    splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    chunks = splitter.split_documents(all_documents)

    doc_chunk_counts = defaultdict(int)
    doc_indexed_pages = defaultdict(set)
    doc_page_chunk_counts = defaultdict(lambda: defaultdict(int))

    for global_idx, chunk in enumerate(chunks, start=1):
        name = Path(chunk.metadata.get("source", "unknown")).name
        page_zero_based = int(chunk.metadata.get("page", 0))
        page_display = page_zero_based + 1

        doc_chunk_counts[name] += 1
        doc_indexed_pages[name].add(page_display)
        doc_page_chunk_counts[name][page_display] += 1

        chunk.metadata["source"] = name
        chunk.metadata["doc_name"] = name
        chunk.metadata["page"] = page_zero_based
        chunk.metadata["page_label"] = page_display
        chunk.metadata["chunk_id"] = global_idx
        chunk.metadata["doc_chunk_id"] = doc_chunk_counts[name]

    embeddings = SentenceTransformerEmbeddings(model_name=EMBEDDING_MODEL)
    try:
        vectorstore = Chroma.from_documents(
            documents=chunks,
            embedding=embeddings,
            persist_directory=str(build_path),
        )
    except Exception:
        if build_path.exists() and build_path != CHROMA_PATH:
            shutil.rmtree(build_path)
        raise
    else:
        try:
            vectorstore._client.clear_system_cache()
        except Exception:
            pass
        del vectorstore
        gc.collect()

    docs_info = []
    for pdf_path in pdf_files:
        name = pdf_path.name
        page_chunks = [
            {"page": page, "chunks": count}
            for page, count in sorted(doc_page_chunk_counts.get(name, {}).items())
        ]
        docs_info.append(
            {
                "name": name,
                "pages": doc_page_counts.get(name, 0),
                "chunks": doc_chunk_counts.get(name, 0),
                "indexed_pages": sorted(doc_indexed_pages.get(name, set())),
                "page_chunks": page_chunks,
                **doc_file_meta.get(name, {}),
            }
        )

    stats = {
        "total_chunks": len(chunks),
        "total_pages": sum(doc_page_counts.values()),
        "docs": docs_info,
        "embedding_model": EMBEDDING_MODEL,
        "chunk_size": CHUNK_SIZE,
        "chunk_overlap": CHUNK_OVERLAP,
        "processed_at": datetime.now().isoformat(timespec="seconds"),
    }

    if build_path != CHROMA_PATH and CHROMA_PATH.exists():
        shutil.rmtree(CHROMA_PATH)
    if build_path != CHROMA_PATH:
        build_path.rename(CHROMA_PATH)
    _write_json(STATS_FILE, stats)
    return stats


def load_index_stats():
    try:
        with STATS_FILE.open(encoding="utf-8") as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


if __name__ == "__main__":
    result = ingest_documents()
    print(f"Done. {result['total_chunks']} chunks from {len(result['docs'])} document(s).")

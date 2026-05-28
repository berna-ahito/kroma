import gc
import json
import os
import shutil
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import chromadb
from langchain_core.documents import Document
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.embeddings import SentenceTransformerEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter


os.environ.setdefault("HF_HUB_OFFLINE", "0")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "0")

BASE_DIR = Path(__file__).resolve().parent
DOCS_FOLDER = BASE_DIR / "docs"
CHROMA_PATH = BASE_DIR / "chroma_db"
NEXT_CHROMA_PATH = BASE_DIR / "chroma_db_next"
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
STATS_FILE = BASE_DIR / "index_stats.json"
CHUNK_SIZE = 600
CHUNK_OVERLAP = 120
SUPPORTED_TEXT_EXTENSIONS = {".txt", ".md", ".markdown"}
SUPPORTED_DOCUMENT_EXTENSIONS = {".pdf", *SUPPORTED_TEXT_EXTENSIONS}
TEXT_EXTENSION_LABELS = {
    ".txt": ("txt", "Text"),
    ".md": ("markdown", "Markdown"),
    ".markdown": ("markdown", "Markdown"),
}


def is_supported_document(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in SUPPORTED_DOCUMENT_EXTENSIONS


def _decode_text_bytes(data: bytes) -> str:
    return data.decode("utf-8-sig")


def is_control_heavy_text(text: str) -> bool:
    if "\x00" in text:
        return True
    if not text:
        return False
    control_chars = sum(
        1
        for ch in text
        if (ord(ch) < 32 and ch not in "\t\n\r") or ord(ch) == 127
    )
    return control_chars / len(text) > 0.01


def load_text_document(path: Path) -> Document:
    text = _decode_text_bytes(path.read_bytes())
    if not text.strip():
        raise ValueError(f"{path.name} is empty.")
    if is_control_heavy_text(text):
        raise ValueError(f"{path.name} contains too many control characters.")

    file_type, location_label = TEXT_EXTENSION_LABELS[path.suffix.lower()]
    return Document(
        page_content=text,
        metadata={
            "source": path.name,
            "doc_name": path.name,
            "file_type": file_type,
            "location_type": "document",
            "location_label": location_label,
        },
    )


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
    source_files = sorted(path for path in DOCS_FOLDER.iterdir() if is_supported_document(path))
    if not source_files:
        stats = {"total_chunks": 0, "total_pages": 0, "docs": [], "processed_at": None}
        _write_json(STATS_FILE, stats)
        return stats

    build_path = NEXT_CHROMA_PATH if CHROMA_PATH.exists() else CHROMA_PATH
    if build_path.exists():
        shutil.rmtree(build_path)

    all_documents = []
    doc_page_counts = {}
    doc_file_meta = {}
    text_document_names = set()

    for source_path in source_files:
        doc_file_meta[source_path.name] = _file_metadata(source_path)
        if source_path.suffix.lower() == ".pdf":
            pages = PyPDFLoader(str(source_path)).load()
            doc_page_counts[source_path.name] = len(pages)
            all_documents.extend(pages)
        else:
            all_documents.append(load_text_document(source_path))
            doc_page_counts[source_path.name] = 0
            text_document_names.add(source_path.name)

    splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    chunks = splitter.split_documents(all_documents)

    doc_chunk_counts = defaultdict(int)
    doc_indexed_pages = defaultdict(set)
    doc_page_chunk_counts = defaultdict(lambda: defaultdict(int))

    for global_idx, chunk in enumerate(chunks, start=1):
        name = Path(chunk.metadata.get("source", "unknown")).name
        doc_chunk_counts[name] += 1

        chunk.metadata["source"] = name
        chunk.metadata["doc_name"] = name
        chunk.metadata["chunk_id"] = global_idx
        chunk.metadata["doc_chunk_id"] = doc_chunk_counts[name]

        if name in text_document_names:
            file_type, location_label = TEXT_EXTENSION_LABELS[Path(name).suffix.lower()]
            chunk.metadata["file_type"] = file_type
            chunk.metadata["location_type"] = "document"
            chunk.metadata["location_label"] = location_label
            continue

        page_zero_based = int(chunk.metadata.get("page", 0))
        page_display = page_zero_based + 1
        doc_indexed_pages[name].add(page_display)
        doc_page_chunk_counts[name][page_display] += 1

        chunk.metadata["page"] = page_zero_based
        chunk.metadata["page_label"] = page_display
        chunk.metadata["file_type"] = "pdf"
        chunk.metadata["location_type"] = "page"
        chunk.metadata["location_label"] = f"Page {page_display}"

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
    for source_path in source_files:
        name = source_path.name
        suffix = source_path.suffix.lower()
        page_chunks = [
            {"page": page, "chunks": count}
            for page, count in sorted(doc_page_chunk_counts.get(name, {}).items())
        ]
        docs_info.append(
            {
                "name": name,
                "file_type": "pdf" if suffix == ".pdf" else TEXT_EXTENSION_LABELS[suffix][0],
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


def _empty_index_stats() -> dict:
    return {
        "total_chunks": 0,
        "total_pages": 0,
        "docs": [],
        "embedding_model": EMBEDDING_MODEL,
        "chunk_size": CHUNK_SIZE,
        "chunk_overlap": CHUNK_OVERLAP,
        "processed_at": None,
    }


def _stats_without_document(filename: str) -> dict:
    stats = load_index_stats() or _empty_index_stats()
    docs = [
        doc
        for doc in stats.get("docs", [])
        if isinstance(doc, dict) and doc.get("name") != filename
    ]
    updated = {
        **stats,
        "docs": docs,
        "total_chunks": sum(int(doc.get("chunks") or 0) for doc in docs),
        "total_pages": sum(int(doc.get("pages") or 0) for doc in docs),
    }
    if not docs:
        updated = _empty_index_stats()
    return updated


def delete_document_from_index(filename: str) -> dict:
    """Remove one document's chunks from Chroma and update index stats."""
    if CHROMA_PATH.exists():
        client = None
        try:
            client = chromadb.PersistentClient(path=str(CHROMA_PATH))
            collection = client.get_collection("langchain")
            collection.delete(where={"source": filename})
        except Exception as exc:
            if "does not exist" not in str(exc).lower():
                raise
        finally:
            if client is not None:
                try:
                    client.clear_system_cache()
                except Exception:
                    pass
            gc.collect()

    updated_stats = _stats_without_document(filename)
    _write_json(STATS_FILE, updated_stats)
    return updated_stats


if __name__ == "__main__":
    result = ingest_documents()
    print(f"Done. {result['total_chunks']} chunks from {len(result['docs'])} document(s).")

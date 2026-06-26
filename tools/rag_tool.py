import os
import re
import uuid
import json
from typing import Any, Dict, List, Optional

import chromadb
from chromadb.config import Settings
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

_RAG_BASE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")

CHUNK_SIZE = 600
CHUNK_OVERLAP = 80

_EMBED_FN = DefaultEmbeddingFunction()


def _get_embedding(text: str) -> List[float]:
    return _EMBED_FN([text])[0].tolist()


def _rag_dir(username: str = "") -> str:
    d = os.path.join(_RAG_BASE, username.strip().lower(), "rag") if username.strip() else os.path.join(_RAG_BASE, "shared", "rag")
    os.makedirs(d, exist_ok=True)
    return d


def _chroma_path(username: str = "") -> str:
    return os.path.join(_rag_dir(username), "chroma")


def _docs_dir(username: str = "") -> str:
    return os.path.join(_rag_dir(username), "files")


def _get_client(username: str = "") -> chromadb.PersistentClient:
    path = _chroma_path(username)
    os.makedirs(path, exist_ok=True)
    return chromadb.PersistentClient(path=path, settings=Settings(anonymized_telemetry=False))


def _get_collection(client: chromadb.PersistentClient):
    try:
        return client.get_collection("docs")
    except Exception:
        return client.create_collection("docs", metadata={"hnsw:space": "cosine"})


def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[Dict[str, Any]]:
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks = []
    current = ""
    for s in sentences:
        if len(current) + len(s) > chunk_size and current:
            chunks.append(current.strip())
            words = current.split()
            overlap_words = words[-overlap:] if len(words) > overlap else words
            current = " ".join(overlap_words) + " " + s
        else:
            current += " " + s
    if current.strip():
        chunks.append(current.strip())
    result = []
    for i, c in enumerate(chunks):
        result.append({"index": i, "text": c, "char_count": len(c)})
    return result


def _extract_text_from_pdf(path: str) -> str:
    import fitz
    doc = fitz.open(path)
    text = ""
    for page in doc:
        text += page.get_text() + "\n"
    doc.close()
    return text


def _extract_text(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        return _extract_text_from_pdf(path)
    elif ext in (".txt", ".md", ".csv"):
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    elif ext in (".json",):
        with open(path, encoding="utf-8", errors="replace") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return json.dumps(data, indent=2)
            elif isinstance(data, list):
                return "\n".join(json.dumps(item) for item in data)
            return str(data)
    else:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()


def upload_document(file_path: str, filename: str, username: str = "") -> Dict[str, Any]:
    try:
        doc_id = str(uuid.uuid4())[:8]
        dd = _docs_dir(username)
        os.makedirs(dd, exist_ok=True)
        import shutil
        dest = os.path.join(dd, f"{doc_id}_{filename}")
        shutil.copy2(file_path, dest)

        raw_text = _extract_text(dest)
        if not raw_text.strip():
            return {"success": False, "error": "No extractable text found."}

        chunks = _chunk_text(raw_text)

        client = _get_client(username)
        collection = _get_collection(client)

        ids = []
        texts = []
        metadatas = []
        for ch in chunks:
            ids.append(f"{doc_id}_{ch['index']}")
            texts.append(ch["text"])
            metadatas.append({"doc_id": doc_id, "filename": filename, "chunk_index": ch["index"]})

        for i in range(0, len(texts), 20):
            batch = texts[i:i+20]
            embeds = []
            for t in batch:
                embeds.append(_get_embedding(t))
            collection.add(ids=ids[i:i+20], embeddings=embeds, documents=batch, metadatas=metadatas[i:i+20])

        return {
            "success": True,
            "doc_id": doc_id,
            "filename": filename,
            "chunks": len(chunks),
            "char_count": len(raw_text),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def retrieve_context(query: str, username: str = "", top_k: int = 5) -> Dict[str, Any]:
    try:
        client = _get_client(username)
        collection = _get_collection(client)
        count = collection.count()
        if count == 0:
            return {"success": True, "results": [], "total_chunks": 0}

        query_embedding = _get_embedding(query)
        results = collection.query(query_embeddings=[query_embedding], n_results=min(top_k, count))

        passages = []
        seen_docs = set()
        for i in range(len(results["ids"][0])):
            doc_id = results["metadatas"][0][i]["doc_id"]
            seen_docs.add(doc_id)
            passages.append({
                "doc_id": doc_id,
                "filename": results["metadatas"][0][i]["filename"],
                "chunk_index": results["metadatas"][0][i]["chunk_index"],
                "text": results["documents"][0][i],
                "score": round(results["distances"][0][i], 4) if "distances" in results else 0,
            })

        return {
            "success": True,
            "results": passages,
            "total_chunks": count,
            "source_docs": list(seen_docs),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def list_documents(username: str = "") -> Dict[str, Any]:
    try:
        dd = _docs_dir(username)
        if not os.path.isdir(dd):
            return {"success": True, "documents": []}
        files = []
        for f in sorted(os.listdir(dd), reverse=True):
            fp = os.path.join(dd, f)
            if os.path.isfile(fp):
                files.append({
                    "id": f.split("_")[0] if "_" in f else f,
                    "filename": "_".join(f.split("_")[1:]) if "_" in f else f,
                    "path": fp,
                    "size_kb": round(os.path.getsize(fp) / 1024, 1),
                })
        return {"success": True, "documents": files}
    except Exception as e:
        return {"success": False, "error": str(e)}


def delete_document(doc_id: str, username: str = "") -> Dict[str, Any]:
    try:
        dd = _docs_dir(username)
        for f in os.listdir(dd):
            if f.startswith(doc_id):
                os.remove(os.path.join(dd, f))
        client = _get_client(username)
        collection = _get_collection(client)
        collection.delete(where={"doc_id": doc_id})
        return {"success": True, "doc_id": doc_id}
    except Exception as e:
        return {"success": False, "error": str(e)}


def clear_documents(username: str = ""):
    try:
        dd = _docs_dir(username)
        if os.path.isdir(dd):
            import shutil
            shutil.rmtree(dd)
        cp = _chroma_path(username)
        if os.path.isdir(cp):
            import shutil
            shutil.rmtree(cp)
    except Exception:
        pass


def get_chunks_for_doc(doc_id: str, username: str = "") -> List[Dict[str, Any]]:
    try:
        client = _get_client(username)
        collection = _get_collection(client)
        results = collection.get(where={"doc_id": doc_id})
        chunks = []
        for i in range(len(results["ids"])):
            chunks.append({
                "index": results["metadatas"][i]["chunk_index"],
                "text": results["documents"][i],
            })
        chunks.sort(key=lambda x: x["index"])
        return chunks
    except Exception:
        return []

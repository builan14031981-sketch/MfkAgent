import os
import hashlib
from typing import List, Dict
from app.core.database import SessionLocal
from app.models.agent import Project


CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
TEXT_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".md", ".txt", ".json",
    ".yaml", ".yml", ".toml", ".cfg", ".ini", ".env",
    ".html", ".css", ".scss", ".less",
    ".java", ".go", ".rs", ".c", ".cpp", ".h",
}


def _is_text_file(file_path: str) -> bool:
    ext = os.path.splitext(file_path)[1].lower()
    return ext in TEXT_EXTENSIONS


def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        if chunk.strip():
            chunks.append(chunk)
        start = end - overlap
    return chunks


def _file_hash(file_path: str) -> str:
    with open(file_path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


class KnowledgeService:
    def __init__(self):
        self._index: Dict[str, List[Dict]] = {}

    def index_project(self, project_id: int, force: bool = False) -> Dict:
        db = SessionLocal()
        try:
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                return {"error": "Project not found"}
        finally:
            db.close()

        base_path = project.path
        if not os.path.exists(base_path):
            return {"error": "Project path not found"}

        indexed = 0
        skipped = 0
        errors = 0

        for root, dirs, files in os.walk(base_path):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d != "node_modules" and d != "__pycache__"]

            for file_name in files:
                if file_name.startswith("."):
                    continue

                file_path = os.path.join(root, file_name)
                rel_path = os.path.relpath(file_path, base_path)

                if not _is_text_file(file_path):
                    skipped += 1
                    continue

                try:
                    file_size = os.path.getsize(file_path)
                    if file_size > 100 * 1024:
                        skipped += 1
                        continue

                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()

                    chunks = _chunk_text(content)

                    key = f"{project_id}:{rel_path}"
                    self._index[key] = [
                        {
                            "project_id": project_id,
                            "file_path": rel_path,
                            "chunk_index": i,
                            "content": chunk,
                            "hash": _file_hash(file_path),
                        }
                        for i, chunk in enumerate(chunks)
                    ]

                    indexed += 1
                except Exception:
                    errors += 1

        return {
            "project_id": project_id,
            "indexed": indexed,
            "skipped": skipped,
            "errors": errors,
            "total_chunks": sum(len(chunks) for chunks in self._index.values()),
        }

    def search(self, project_id: int, query: str, limit: int = 5) -> List[Dict]:
        query_lower = query.lower()
        results = []

        for key, chunks in self._index.items():
            if not key.startswith(f"{project_id}:"):
                continue

            for chunk in chunks:
                content_lower = chunk["content"].lower()
                if query_lower in content_lower:
                    score = content_lower.count(query_lower)
                    results.append({
                        "file_path": chunk["file_path"],
                        "chunk_index": chunk["chunk_index"],
                        "content": chunk["content"][:200],
                        "score": score,
                    })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:limit]

    def get_context(self, project_id: int, query: str, max_tokens: int = 2000) -> str:
        results = self.search(project_id, query, limit=3)
        if not results:
            return ""

        context_parts = ["相关项目文件内容：\n"]
        total_len = 0

        for r in results:
            part = f"\n--- {r['file_path']} (chunk {r['chunk_index']}) ---\n{r['content']}\n"
            if total_len + len(part) > max_tokens * 2:
                break
            context_parts.append(part)
            total_len += len(part)

        return "".join(context_parts)

    def get_stats(self) -> Dict:
        total_files = len(self._index)
        total_chunks = sum(len(chunks) for chunks in self._index.values())
        return {
            "total_files": total_files,
            "total_chunks": total_chunks,
        }


knowledge_service = KnowledgeService()

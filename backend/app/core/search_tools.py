"""项目内代码搜索工具 —— 供 LLM Function Calling 使用。

基于 project_path 直接遍历项目做关键字检索，无需预索引（区别于 RAG 时代的
KnowledgeService：后者按 project_id + 显式 index 调用，且存内存易过期）。
本模块与 core/tools.py（文件）、core/git_tools.py（git）同一模式：
接收 project_path + 相对路径，realpath 沙箱校验，返回文本结果。
"""
import os
from typing import Dict, List

from app.core.tools import ToolExecutionError
from app.core.sandbox import resolve_sandbox_path

# 检索时跳过的大型/隐藏/构建目录（与 KnowledgeService.index_project 保持一致并扩展）
SKIP_DIRS = {".git", ".idea", ".vscode", "node_modules", "__pycache__", "dist", "build", ".venv", "venv", ".next", ".nuxt"}

TEXT_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".vue", ".md", ".txt", ".json",
    ".yaml", ".yml", ".toml", ".cfg", ".ini", ".env",
    ".html", ".css", ".scss", ".less",
    ".java", ".go", ".rs", ".c", ".cpp", ".h", ".hpp", ".cs",
    ".sh", ".bat", ".ps1", ".sql", ".xml",
}

MAX_FILE_SIZE = 200 * 1024  # 超过此大小的文件跳过（避免读入二进制/大文件）
MAX_RESULTS = 20            # 最多返回多少条命中
LINE_TRIM = 160             # 单行内容截断长度


def _is_text_file(file_path: str) -> bool:
    ext = os.path.splitext(file_path)[1].lower()
    return ext in TEXT_EXTENSIONS


def _search_dir(base: str, query_lower: str, max_results: int) -> List[str]:
    """在 base 目录内递归搜索 query（不区分大小写），返回 [path:line: content] 文本行。

    支持 `|` 分隔的多关键词（任一命中即算命中），兼容模型以 `keyword1|keyword2`
    形式一次搜索多个同义词的习惯（此前字面量匹配会把 `|` 当普通字符而搜不到）。
    """
    queries = [q for q in (p.strip() for p in query_lower.split("|")) if q]
    if not queries:
        queries = [query_lower]
    hits: List[str] = []
    for root, dirs, files in os.walk(base):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        for file_name in files:
            if file_name.startswith("."):
                continue
            file_path = os.path.join(root, file_name)
            if not _is_text_file(file_path):
                continue
            try:
                if os.path.getsize(file_path) > MAX_FILE_SIZE:
                    continue
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()
            except OSError:
                continue

            rel = os.path.relpath(file_path, base).replace("\\", "/")
            for i, line in enumerate(lines, 1):
                low = line.lower()
                if any(q in low for q in queries):
                    content = line.strip()[:LINE_TRIM]
                    hits.append(f"{rel}:{i}: {content}")
                    if len(hits) >= max_results:
                        return hits
    return hits


def search_files(project_path: Optional[str], query: str, relative_path: str = ".", max_results: int = MAX_RESULTS) -> str:
    """在项目或指定目录内搜索关键字（大小写不敏感），返回 文件:行号: 内容 列表。"""
    query = (query or "").strip()
    if not query:
        return "错误: query 不能为空"
    try:
        target = resolve_sandbox_path(relative_path, project_path, allow_outside=True)
    except (ToolExecutionError, PermissionError, Exception) as e:
        return f"错误: {e}"
    if not os.path.isdir(target):
        return f"错误: 目录不存在: {relative_path}"

    max_results = max(1, min(int(max_results or MAX_RESULTS), 100))
    hits = _search_dir(target, query.lower(), max_results)
    if not hits:
        return f"项目内未找到匹配: {query}"
    return "\n".join(hits)


SEARCH_TOOLS_DEFINITIONS: List[Dict] = [
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": (
                "在本地项目内搜索关键字（大小写不敏感，支持文件名/代码/注释内容），"
                "返回 文件:行号: 内容 列表。适合定位函数定义、调用处、错误关键词等，"
                "通常先 search_files 定位再 read_file 读取全文。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "要搜索的关键字或代码片段（无需正则）",
                    },
                    "relative_path": {
                        "type": "string",
                        "description": "限定搜索的子目录（相对项目根），默认整个项目",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "最多返回的命中条数，默认 20",
                    },
                },
                "required": ["query"],
            },
        },
    },
]

SEARCH_TOOLS = {
    "search_files": search_files,
}


def execute_search_tool(name: str, project_path: str, **kwargs) -> str:
    """执行搜索工具并返回文本结果（失败返回错误说明）。"""
    fn = SEARCH_TOOLS.get(name)
    if fn is None:
        return f"错误: 未知工具 {name}"
    try:
        return fn(project_path=project_path, **kwargs)
    except (ToolExecutionError, PermissionError) as e:
        return f"错误: {e}"
    except Exception as e:
        return f"错误: {e}"

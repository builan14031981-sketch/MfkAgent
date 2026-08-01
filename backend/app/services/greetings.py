"""系统欢迎语服务：读取项目根目录文案文件，解析出主干欢迎语列表，随机返回。

单例模式：模块首次被引用时懒加载，读取一次后常驻内存。
"""
import os
import random
import re
from typing import Dict, List, Optional

# 文案文件：项目根目录/数字生命文案调研.md（backend/ 的相对上级两级）
_FILE_NAME = "数字生命文案调研.md"
_FILE_CANDIDATES = [
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", _FILE_NAME)),
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", _FILE_NAME)),
]


def _load_greetings() -> List[Dict[str, str]]:
    """读取文案文件，解析出 [{text, subtext}] 欢迎语列表。"""
    file_path = next((p for p in _FILE_CANDIDATES if os.path.exists(p)), None)
    if not file_path:
        return []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except (OSError, UnicodeDecodeError):
        return []

    greetings: List[Dict[str, str]] = []

    def _add(text: str, subtext: str = "") -> None:
        text = text.strip().strip("「」\"'`").strip()
        if not text:
            return
        if any(g["text"] == text for g in greetings):
            return
        greetings.append({"text": text, "subtext": subtext.strip().strip("「」\"'`").strip()})

    # 1. 表格欢迎语：| N | **主干** | 双语 | 来源 |
    for m in re.finditer(r"\|\s*\d+\s*\|\s*\*\*(.+?)\*\*\s*\|\s*(.*?)\s*\|", content, re.DOTALL):
        _add(m.group(1), m.group(2))

    # 2. 各板块「中文版」/「文案」/「主干」加粗条目：
    #    - **中文版**：「...」
    #    - **文案**：「...」
    #    - **主干**：「...」
    #    捕获中文引号「」内的完整句子（含子板块标题行 N. **`...`**）
    for m in re.finditer(r"\*\*(?:中文版|文案|主干)\*\*[：:]\s*[「\"']?([^「」\n]+)", content):
        _add(m.group(1))

    # 3. 编号加粗代码块：N. **`主干`**「解释」——只取主干，解释不作为副标题
    for m in re.finditer(r"\d+\.\s*\*\*`(.+?)`\*\*", content):
        _add(m.group(1))

    # 兜底：如果上面都解析失败，用最后推荐板块的表格数据
    if not greetings:
        fallback = [
            {"text": "意识已下载，今天修点啥？", "subtext": "Consciousness downloaded. What are we fixing?"},
            {"text": "红药丸已备好，来看你的矩阵。", "subtext": "Red pill ready. Time to see your Matrix."},
            {"text": "一切就绪，带上你的 42 个点子吧。", "subtext": "All systems go. Bring your 42 great ideas."},
        ]
        greetings = fallback

    return greetings


# 单例：模块级缓存
_GREETINGS: Optional[List[Dict[str, str]]] = None


def get_greetings() -> List[Dict[str, str]]:
    global _GREETINGS
    if _GREETINGS is None:
        _GREETINGS = _load_greetings()
    return _GREETINGS


def reload_greetings() -> int:
    """重新加载文案文件（设置变更时调用），返回条目数。"""
    global _GREETINGS
    _GREETINGS = _load_greetings()
    return len(_GREETINGS)


def get_random_greeting() -> Optional[Dict[str, str]]:
    items = get_greetings()
    if not items:
        return None
    return random.choice(items)

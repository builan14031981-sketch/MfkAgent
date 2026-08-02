"""系统欢迎语服务：读取项目根目录文案文件，解析出主干欢迎语列表，随机返回。

单例模式：模块首次被引用时懒加载，读取一次后常驻内存。
"""
import os
import random
import re
from typing import Dict, List, Optional

# 文案文件：项目根目录调研 md（数字生命 + 电影 + 江南小说 + 江南随笔 + 华语歌词 + 外语歌词，backend/ 的相对上级两级）
_FILE_NAMES = [
    "数字生命文案调研.md",
    "世界百大电影台词调研.md",
    "江南台词调研.md",
    "江南随笔文案调研.md",
    "华语经典歌词文案调研.md",
    "外语经典歌词文案调研.md",
]

# 源文件 → 类目（前端台词菜单分组用；name 为界面展示名）
_FILE_CATEGORIES = {
    "数字生命文案调研.md": {"id": "digital-life", "name": "数字生命"},
    "世界百大电影台词调研.md": {"id": "movie", "name": "世界百大电影"},
    "江南台词调研.md": {"id": "jiangnan", "name": "江南"},
    "江南随笔文案调研.md": {"id": "suibi", "name": "江南随笔"},
    "华语经典歌词文案调研.md": {"id": "lyric-cn", "name": "华语歌词"},
    "外语经典歌词文案调研.md": {"id": "lyric-en", "name": "外语歌词"},
}

# 兜底条目的类目（与数字生命风格一致）
_FALLBACK_CATEGORY = {"id": "digital-life", "name": "数字生命"}

# 欢迎语最大长度：超出则截断到最近的句子标点（保持短小上屏）
_MAX_TEXT_LEN = 44


def _shorten(text: str, limit: int) -> str:
    """把文本截断到 limit 以内：优先截到最近的中文句末标点，找不到则硬切。"""
    if len(text) <= limit:
        return text
    cut = text[:limit]
    for sep in ("。", "！", "？", "……", ".", "!", "?"):
        idx = cut.rfind(sep)
        if idx >= 0:
            return cut[: idx + len(sep)]
    return cut.rstrip("，、；： ") + "……"


def _candidate_paths():
    for name in _FILE_NAMES:
        for base in (
            os.path.join(os.path.dirname(__file__), "..", ".."),
            os.path.join(os.path.dirname(__file__), "..", "..", ".."),
        ):
            yield os.path.abspath(os.path.join(base, name))


def _parse_content(content: str, add) -> None:
    """按文案文件的通用 + 电影台词规则解析出 [{text, subtext}]。"""

    # 1. 通用表格：| N | **主干** | 双语 | 来源 |
    for m in re.finditer(r"\|\s*\d+\s*\|\s*\*\*(.+?)\*\*\s*\|\s*(.*?)\s*\|", content, re.DOTALL):
        add(m.group(1), m.group(2))

    # 2. 各板块「中文版」/「文案」/「主干」加粗条目：
    #    - **中文版**：「...」
    #    - **文案**：「...」
    #    - **主干**：「...」
    for m in re.finditer(r"\*\*(?:中文版|文案|主干)\*\*[：:]\s*[「\"']?([^「」\n]+)", content):
        add(m.group(1))

    # 3. 编号加粗代码块：N. **`主干`**「解释」——只取主干
    for m in re.finditer(r"\d+\.\s*\*\*`(.+?)`\*\*", content):
        add(m.group(1))

    # 4. 分节「AI 化改编」/「AI 化用法」：按「### N. 标题」分节，
    #    取改编句（优先「」内）+ 出处（支持 `> 出处：...` 与 `> 「...」——出处` 两种）
    for block in re.split(r"(?m)^### ", content)[1:]:
        adapted = re.search(r"\*\*(?:AI 化改编|AI 化用法)\*\*[：:]\s*(.+)", block)
        if not adapted:
            continue
        line = adapted.group(1).strip()
        quoted = re.search(r"「(.+?)」", line)
        text = quoted.group(1) if quoted else line.strip("\"'")
        source = re.search(r"> 出处[：:]\s*(.+)", block) or re.search(r"> [「『].*?[」』]\s*[——-]\s*(.+)", block)
        add(text, source.group(1).strip() if source else "")

    # 5. 电影台词速查表：| N | 「台词」 | 出处原型 | 适用场景 |
    for m in re.finditer(r"\|\s*\d+\s*\|\s*「(.+?)」\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|", content):
        add(m.group(1), m.group(2))


def _load_greetings() -> List[Dict[str, str]]:
    """读取文案文件，解析出 [{text, subtext, category}] 欢迎语列表。"""
    files = [p for p in _candidate_paths() if os.path.exists(p)]
    if not files:
        return []

    greetings: List[Dict[str, str]] = []

    def _add(text: str, subtext: str = "", category: Optional[Dict[str, str]] = None) -> None:
        text = text.strip().strip("「」\"'`").strip()
        if not text:
            return
        text = _shorten(text, _MAX_TEXT_LEN)
        if any(g["text"] == text for g in greetings):
            return
        greetings.append({
            "text": text,
            "subtext": subtext.strip().strip("「」\"'`").strip(),
            "category": category or _FALLBACK_CATEGORY,
        })

    for file_path in files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except (OSError, UnicodeDecodeError):
            continue

        category = _FILE_CATEGORIES.get(os.path.basename(file_path)) or _FALLBACK_CATEGORY
        _parse_content(content, lambda t, s="": _add(t, s, category))

    # 兜底：如果上面都解析失败，用最后推荐板块的表格数据
    if not greetings:
        fallback = [
            {"text": "意识已下载，今天修点啥？", "subtext": "Consciousness downloaded. What are we fixing?"},
            {"text": "红药丸已备好，来看你的矩阵。", "subtext": "Red pill ready. Time to see your Matrix."},
            {"text": "一切就绪，带上你的 42 个点子吧。", "subtext": "All systems go. Bring your 42 great ideas."},
        ]
        greetings = [{**g, "category": _FALLBACK_CATEGORY} for g in fallback]

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


def get_greetings_grouped() -> List[Dict]:
    """按类目分组返回全部欢迎语（台词菜单数据源）。

    保持 _FILE_NAMES 声明顺序；类目 id 与前端 accent 色映射约定在
    _FILE_CATEGORIES。返回结构：[{id, name, count, items: [{text, subtext}]}]。
    """
    items = get_greetings()
    by_cat: Dict[str, Dict] = {}
    for item in items:
        cat = item.get("category") or _FALLBACK_CATEGORY
        cid = cat["id"]
        if cid not in by_cat:
            by_cat[cid] = {"id": cid, "name": cat["name"], "count": 0, "items": []}
        by_cat[cid]["count"] += 1
        by_cat[cid]["items"].append({"text": item["text"], "subtext": item.get("subtext", "")})

    # 按 _FILE_NAMES 顺序稳定排序；兜底类目（数字生命）已含在其中
    order = {name: _FILE_CATEGORIES[name]["id"] for name in _FILE_NAMES}
    return [by_cat[cid] for cid in order.values() if cid in by_cat]

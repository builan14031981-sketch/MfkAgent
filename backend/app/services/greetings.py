"""系统欢迎语服务：读取 backend/app/data/greetings.json 欢迎语库，随机返回。

单例模式：模块首次被引用时懒加载，读取一次后常驻内存。
数据来源：scripts/build_greetings.py 从 文案素材/ 一次性提取生成（不依赖原始 .md 文件）。
"""
import json
import os
import random
from typing import Dict, List, Optional

# 数据文件：后端自带欢迎语库（类目分组结构）
_DATA_FILE = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "data", "greetings.json")
)

# 类目顺序（前端台词菜单分组用；name 为界面展示名）——与数据文件的 key 对应
_CATEGORY_ORDER = [
    {"id": "digital-life", "name": "数字生命"},
    {"id": "movie", "name": "世界百大电影"},
    {"id": "jiangnan", "name": "江南"},
    {"id": "suibi", "name": "江南随笔"},
    {"id": "lyric-cn", "name": "华语歌词"},
    {"id": "lyric-en", "name": "外语歌词"},
]

# 类目 id → 展示名
_CATEGORY_NAMES = {c["id"]: c["name"] for c in _CATEGORY_ORDER}

# 兜底条目的类目（与数字生命风格一致）
_FALLBACK_CATEGORY = {"id": "digital-life", "name": "数字生命"}


def _load_greetings() -> List[Dict[str, str]]:
    """读取 greetings.json，组装出 [{text, subtext, category}] 欢迎语列表。"""
    try:
        with open(_DATA_FILE, "r", encoding="utf-8") as f:
            grouped = json.load(f)
    except (OSError, ValueError):
        grouped = {}

    greetings: List[Dict[str, str]] = []
    for cid, items in grouped.items():
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            text = str(item.get("text", "")).strip()
            if not text:
                continue
            greetings.append({
                "text": text,
                "subtext": str(item.get("subtext", "")).strip(),
                "category": {"id": cid, "name": _CATEGORY_NAMES.get(cid, cid)},
            })

    # 兜底：数据文件缺失 / 损坏 / 为空时，用内置文案
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

    # 按类目声明顺序稳定排序；兜底类目（数字生命）已含在其中
    order = [c["id"] for c in _CATEGORY_ORDER]
    return [by_cat[cid] for cid in order if cid in by_cat]

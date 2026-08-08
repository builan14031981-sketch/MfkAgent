"""从 文案素材/ 提取欢迎语，生成 backend/app/data/greetings.json（类目分组）。

用法（在仓库根目录执行）：
    python scripts/build_greetings.py

说明：
    - 本脚本独立实现文案解析（不依赖运行时 greetings.py，避免运行时残留 md 依赖）。
    - 输出 JSON 按类目分组：{"类目id": [{text, subtext}, ...], ...}，
      供 backend/app/services/greetings.py 运行时读取。
    - 更新了 .md 素材后可重跑本脚本刷新欢迎语库。
"""
import json
import os
import re
import sys
from typing import Dict, List, Optional

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SOURCE_DIR = os.path.join(REPO_ROOT, "文案素材")
OUTPUT_PATH = os.path.join(REPO_ROOT, "backend", "app", "data", "greetings.json")

# 文案源文件 → 类目（与运行时 greetings.py 的 _CATEGORY_ORDER 保持一致）
_FILE_CATEGORIES: Dict[str, Dict[str, str]] = {
    "数字生命文案调研.md": {"id": "digital-life", "name": "数字生命"},
    "世界百大电影台词调研.md": {"id": "movie", "name": "世界百大电影"},
    "江南台词调研.md": {"id": "jiangnan", "name": "江南"},
    "江南随笔文案调研.md": {"id": "suibi", "name": "江南随笔"},
    "华语经典歌词文案调研.md": {"id": "lyric-cn", "name": "华语歌词"},
    "外语经典歌词文案调研.md": {"id": "lyric-en", "name": "外语歌词"},
}

_FALLBACK_CATEGORY_ID = "digital-life"

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


def _load_items() -> List[Dict[str, str]]:
    """读取 文案素材/ 下各文件，返回 [{text, subtext, category_id}] 列表。"""
    items: List[Dict[str, str]] = []

    def _add(text: str, subtext: str = "", category_id: Optional[str] = None) -> None:
        text = text.strip().strip("「」\"'`").strip()
        if not text:
            return
        text = _shorten(text, _MAX_TEXT_LEN)
        if any(i["text"] == text for i in items):
            return
        items.append({
            "text": text,
            "subtext": subtext.strip().strip("「」\"'`").strip(),
            "category_id": category_id or _FALLBACK_CATEGORY_ID,
        })

    for name, cat in _FILE_CATEGORIES.items():
        path = os.path.join(SOURCE_DIR, name)
        if not os.path.exists(path):
            print(f"[build_greetings] 缺失源文件，跳过: {name}")
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        except (OSError, UnicodeDecodeError) as e:
            print(f"[build_greetings] 读取失败: {name} ({e})")
            continue
        _parse_content(content, lambda t, s="", cid=cat["id"]: _add(t, s, cid))

    if not items:
        items = [
            {"text": "意识已下载，今天修点啥？", "subtext": "Consciousness downloaded. What are we fixing?", "category_id": _FALLBACK_CATEGORY_ID},
            {"text": "红药丸已备好，来看你的矩阵。", "subtext": "Red pill ready. Time to see your Matrix.", "category_id": _FALLBACK_CATEGORY_ID},
            {"text": "一切就绪，带上你的 42 个点子吧。", "subtext": "All systems go. Bring your 42 great ideas.", "category_id": _FALLBACK_CATEGORY_ID},
        ]
    return items


def main() -> int:
    if not os.path.isdir(SOURCE_DIR):
        print(f"[build_greetings] 源目录不存在: {SOURCE_DIR}")
        return 1

    items = _load_items()
    if not items:
        print("[build_greetings] 提取结果为空，中止（不覆盖已有 JSON）。")
        return 1

    # 按类目分组，保持声明顺序
    grouped: Dict[str, List[Dict[str, str]]] = {}
    for item in items:
        grouped.setdefault(item["category_id"], []).append(
            {"text": item["text"], "subtext": item.get("subtext", "")}
        )

    ordered: Dict[str, List[Dict[str, str]]] = {}
    for cid in _FILE_CATEGORIES.values():
        if cid["id"] in grouped:
            ordered[cid["id"]] = grouped[cid["id"]]

    # 合并已有 JSON：手写类目（如 meme）整体保留；被提取类目中，
    # 人工补过的 subtext（出处）按 text 匹配保留，未被提取的新增条目也保留
    if os.path.exists(OUTPUT_PATH):
        try:
            with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
                existing = json.load(f)
            for key, val in existing.items():
                if not isinstance(val, list):
                    continue
                if key not in ordered:
                    ordered[key] = val
                    continue
                cur = ordered[key]
                merged: List[Dict[str, str]] = []
                seen: set = set()
                old_by_text = {it["text"]: it for it in val}
                for it in cur:
                    # 已存在的条目：人工 subtext（出处）优先于本次提取
                    old = old_by_text.get(it["text"])
                    if old and old.get("subtext"):
                        it = {"text": it["text"], "subtext": old["subtext"]}
                    merged.append(it)
                    seen.add(it["text"])
                for old in val:
                    if old["text"] not in seen:
                        merged.append({"text": old["text"], "subtext": old.get("subtext", "")})
                ordered[key] = merged
        except (OSError, ValueError):
            pass

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(ordered, f, ensure_ascii=False, indent=2)
        f.write("\n")

    total = sum(len(v) for v in ordered.values())
    print(f"[build_greetings] 已生成 {OUTPUT_PATH}")
    print(f"[build_greetings] 类目: {json.dumps({k: len(v) for k, v in ordered.items()}, ensure_ascii=False)}")
    print(f"[build_greetings] 共 {total} 条欢迎语")
    return 0


if __name__ == "__main__":
    sys.exit(main())

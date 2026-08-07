"""工具调用归一化层（Phase C-1）

解决模型偶发输出非标准工具调用（XML invoke / 纯文本调用）导致的静默失败。

只识别三种明确格式（宁缺毋滥，不猜测）：
  1. Anthropic 风格: <invoke name="tool_name">JSON参数</invoke>
  2. 通用 XML:      <tool_call><name>X</name><arguments>JSON</arguments></tool_call>
  3. 明确文本:      "调用 run_command:\nipconfig"（块）或 "调用 run_command: ipconfig"（行内）

原则：
  - 宁可返回解析失败（issue），让模型重新生成；
  - 不要误识别并执行。

返回: {"calls": [...], "issues": [{"reason","raw"}]}
  calls 的元素为标准 OpenAI tool_call: {"id","type":"function","function":{"name","arguments"}}
  任何失败都不会静默，都会记入 issues 供上层回馈模型。
"""
import json
import re
from typing import Dict, List

_AVAILABLE_NAME_RE = re.compile(r"^\w+$")

# 1) <invoke name="X">...</invoke>（Anthropic 风格；name 允许空以便记录解析失败）
_INVOKE_RE = re.compile(
    r"<invoke\s+name\s*=\s*[\"']([^\"']*)[\"']\s*>([\s\S]*?)</invoke\s*>",
    re.IGNORECASE,
)

# 2) <tool_call>...</tool_call> 或 <tool>...</tool>
_TOOL_CALL_RE = re.compile(
    r"<(?:tool_call|tool)\s*>([\s\S]*?)</(?:tool_call|tool)\s*>",
    re.IGNORECASE,
)
_NAME_TAG_RE = re.compile(r"<name\s*>([\s\S]*?)</name\s*>", re.IGNORECASE)
_ARGS_TAG_RE = re.compile(
    r"<(?:arguments|parameters|args)\s*>([\s\S]*?)</(?:arguments|parameters|args)\s*>",
    re.IGNORECASE,
)

# 3) 明确文本调用：块状 "调用 run_command:" 或行内 "调用 run_command: ipconfig"
_TEXT_BLOCK_RE = re.compile(r"^\s*调用\s+([a-zA-Z_]\w*)\s*[:：]\s*$")
_TEXT_INLINE_RE = re.compile(r"^\s*调用\s+([a-zA-Z_]\w*)\s*[:：]\s*(.+?)\s*$")

# 仅供 run_command 接受裸文本参数（把整段文本当作 command）
_TEXT_PARAM_TOOLS = {"run_command"}

_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*([\s\S]*?)\s*```$")


def _parse_args(text: str):
    """尝试把工具参数文本解析为 JSON 对象。

    Returns:
        (args_dict, None) 成功；或 (None, issue_reason) 失败。
    """
    text = (text or "").strip()
    if not text:
        return None, "参数为空"

    m = _JSON_FENCE_RE.match(text)
    if m:
        text = m.group(1).strip()

    try:
        obj = json.loads(text)
    except json.JSONDecodeError as e:
        return None, f"参数不是合法 JSON: {e.msg}"
    except Exception as e:  # noqa: BLE001
        return None, f"参数解析异常: {e}"
    if not isinstance(obj, dict):
        return None, f"参数必须是 JSON 对象，收到 {type(obj).__name__}"
    return obj, None


def normalize_tool_call_text(content: str, available_tools) -> Dict:
    """从纯文本/XML 内容中识别非标准工具调用。

    Args:
        content: 模型某一轮的纯文本输出（不含 thinking）
        available_tools: 当前会话可用工具名集合（迭代器/集合）

    Returns:
        {"calls": List[Dict], "issues": List[Dict]}
    """
    content = content or ""
    avail = set(available_tools or [])
    calls: List[Dict] = []
    issues: List[Dict] = []

    def handle(name: str, args_text: str, raw: str) -> None:
        name = (name or "").strip()
        if not name or not _AVAILABLE_NAME_RE.match(name):
            issues.append({"reason": "工具名缺失或非法", "raw": raw})
            return
        if name not in avail:
            issues.append({"reason": f"工具 {name} 不在当前可用列表", "raw": raw})
            return

        args, err = _parse_args(args_text)
        if err is not None:
            if name in _TEXT_PARAM_TOOLS:
                args = {"command": (args_text or "").strip()}
            else:
                issues.append({"reason": err, "raw": raw})
                return
        if not args:
            issues.append({"reason": "参数为空", "raw": raw})
            return

        calls.append({
            "id": f"call_txt_{len(calls) + 1}",
            "type": "function",
            "function": {"name": name, "arguments": json.dumps(args, ensure_ascii=False)},
        })

    # 1) <invoke name="X">...</invoke>
    for m in _INVOKE_RE.finditer(content):
        handle(m.group(1), m.group(2), m.group(0))

    # 2) <tool_call>/<tool> 包裹
    for m in _TOOL_CALL_RE.finditer(content):
        body = m.group(1)
        name_m = _NAME_TAG_RE.search(body)
        args_m = _ARGS_TAG_RE.search(body)
        name = name_m.group(1).strip() if name_m else None
        if args_m:
            args_text = args_m.group(1)
        elif name_m:
            args_text = _NAME_TAG_RE.sub("", body).strip()
        else:
            args_text = body
        handle(name, args_text, m.group(0))

    # 3) 明确文本调用（逐行）
    lines = content.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        bm = _TEXT_BLOCK_RE.match(line)
        im = _TEXT_INLINE_RE.match(line)
        if bm:
            name = bm.group(1)
            args_lines: List[str] = []
            j = i + 1
            while j < len(lines) and lines[j].strip():
                nxt = lines[j].strip()
                if _TEXT_BLOCK_RE.match(nxt) or _TEXT_INLINE_RE.match(nxt):
                    break
                args_lines.append(nxt)
                j += 1
            handle(name, "\n".join(args_lines), "\n".join(lines[i:j]))
            i = j
            continue
        if im:
            handle(im.group(1), im.group(2), line)
        i += 1

    return {"calls": calls, "issues": issues}

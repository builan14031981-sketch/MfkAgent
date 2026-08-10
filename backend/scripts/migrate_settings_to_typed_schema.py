"""settings 表数据清洗与强类型 Schema 迁移脚本（Dry-run 模式）

用途：
  从旧 SQLite settings 表读取全 Text 类型数据，按预设强类型 Schema 校验，
  并格式化输出清洗结果。为下一阶段真正迁移到强类型 schema 做推演。

约束（严格遵守）：
  - Dry-run 模式：仅读取、校验、输出报告，绝不执行 INSERT/UPDATE/CREATE
  - 不在当前数据库中创建新表
  - 不修改任何业务代码

强类型 Schema 定义（基于 DEFAULT_SETTINGS 的真实数据样本推断）：
  - str 类型：theme, language, font_family, default_model, default_agent...
  - int 类型：font_size, default_personality, hero_entry, hero_random
  - bool 类型：（hero_random/hero_entry 当前用 "0"/"1"，需转 bool）
  - JSON-array 类型：hero_favorites, custom_greetings
  - JSON-object 类型：enabled_models
  - secret 类型：api_key_*, vision_api_key, stt_api_key（脱敏处理，不输出明文）

真实脏数据样本（来自当前数据库）：
  font_size = '12'              ← 字符串数字
  default_personality = '0'     ← 字符串数字
  hero_random = '0'             ← 字符串布尔
  hero_entry = '1'              ← 字符串布尔
  hero_favorites = '["a","b"]'  ← 字符串 JSON 数组
  enabled_models = '{"x":[]}'   ← 字符串 JSON 对象
  api_key_qwen = 'sk-xxx'       ← 明文敏感数据

用法：
  python scripts/migrate_settings_to_typed_schema.py
  python scripts/migrate_settings_to_typed_schema.py --db path/to/db.sqlite
  python scripts/migrate_settings_to_typed_schema.py --report-only
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

# 确保能导入 app 模块
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


# ──── 强类型 Schema 定义 ────

class FieldType(Enum):
    """字段目标类型"""
    STRING = "str"
    INTEGER = "int"
    BOOLEAN = "bool"
    JSON_ARRAY = "json_array"
    JSON_OBJECT = "json_object"
    SECRET = "secret"          # 敏感数据（API Key 等），脱敏输出
    ENUM = "enum"


@dataclass
class FieldSchema:
    """单个字段的强类型定义"""
    key: str
    field_type: FieldType
    default: Any = None
    enum_values: Optional[Tuple[str, ...]] = None
    description: str = ""


# 基于真实 settings 表数据推断的 Schema（覆盖 DEFAULT_SETTINGS + 运行时新增字段）
TYPED_SCHEMA: Dict[str, FieldSchema] = {
    # ── 字符串类型 ──
    "theme": FieldSchema("theme", FieldType.STRING, "system", description="主题"),
    "language": FieldSchema("language", FieldType.STRING, "zh-CN", description="语言"),
    "font_family": FieldSchema("font_family", FieldType.STRING, "system", description="字体族"),
    "default_model": FieldSchema("default_model", FieldType.STRING, "qwen-flash", description="默认模型"),
    "default_agent": FieldSchema("default_agent", FieldType.STRING, "general", description="默认 Agent"),
    "default_reasoning_effort": FieldSchema("default_reasoning_effort", FieldType.STRING, "none",
                                            description="默认推理强度"),
    "hero_random_scope": FieldSchema("hero_random_scope", FieldType.STRING, "all", description="随机主题范围"),
    "greeting_mode": FieldSchema("greeting_mode", FieldType.STRING, "builtin", description="问候语模式"),
    "accent_theme": FieldSchema("accent_theme", FieldType.STRING, "default", description="强调色主题"),

    # ── 整数类型（当前存为字符串数字）──
    "font_size": FieldSchema("font_size", FieldType.INTEGER, 14, description="字体大小"),
    "default_personality": FieldSchema("default_personality", FieldType.INTEGER, 50, description="默认人格等级"),
    "hero_entry": FieldSchema("hero_entry", FieldType.INTEGER, 1, description="Hero 入口"),
    "hero_random": FieldSchema("hero_random", FieldType.INTEGER, 1, description="Hero 随机开关（0/1）"),

    # ── JSON 数组类型 ──
    "hero_favorites": FieldSchema("hero_favorites", FieldType.JSON_ARRAY, [], description="收藏主题列表"),
    "custom_greetings": FieldSchema("custom_greetings", FieldType.JSON_ARRAY, [], description="自定义问候语"),

    # ── JSON 对象类型 ──
    "enabled_models": FieldSchema("enabled_models", FieldType.JSON_OBJECT, {}, description="各 provider 启用模型"),

    # ── 敏感数据（API Key，脱敏输出）──
    # 动态匹配 api_key_* 前缀，这里列出已知字段
    "vision_api_key": FieldSchema("vision_api_key", FieldType.SECRET, "", description="备用识图 API Key"),
    "stt_api_key": FieldSchema("stt_api_key", FieldType.SECRET, "", description="语音转写 API Key"),

    # ── BYOK 配置（字符串）──
    "vision_provider": FieldSchema("vision_provider", FieldType.STRING, "", description="备用识图 Provider"),
    "vision_model": FieldSchema("vision_model", FieldType.STRING, "", description="备用识图模型"),
    "vision_base_url": FieldSchema("vision_base_url", FieldType.STRING, "", description="备用识图端点"),
    "stt_provider": FieldSchema("stt_provider", FieldType.STRING, "", description="语音转写 Provider"),
    "stt_model": FieldSchema("stt_model", FieldType.STRING, "whisper-1", description="语音转写模型"),
    "stt_base_url": FieldSchema("stt_base_url", FieldType.STRING, "", description="语音转写端点"),
}


# ──── 清洗结果数据结构 ────

class CleanStatus(Enum):
    """单字段清洗状态"""
    OK = "ok"                    # 类型正确或成功转换
    CONVERTED = "converted"      # 从脏数据转换而来
    DEFAULTED = "defaulted"      # 值缺失或无效，用默认值填充
    INVALID = "invalid"          # 无法转换，保留原值并标记
    SECRET_MASKED = "masked"     # 敏感数据脱敏


@dataclass
class FieldCleanResult:
    """单字段清洗结果"""
    key: str
    raw_value: str
    typed_value: Any
    target_type: FieldType
    status: CleanStatus
    detail: str = ""


@dataclass
class CleanReport:
    """完整清洗报告"""
    total: int = 0
    ok: int = 0
    converted: int = 0
    defaulted: int = 0
    invalid: int = 0
    masked: int = 0
    fields: List[FieldCleanResult] = field(default_factory=list)
    unknown_keys: List[str] = field(default_factory=list)  # Schema 中未定义的 key

    def summary(self) -> str:
        return (
            f"总计 {self.total} 字段 | "
            f"OK={self.ok} 转换={self.converted} 默认填充={self.defaulted} "
            f"无效={self.invalid} 脱敏={self.masked} | "
            f"未定义 key={len(self.unknown_keys)}"
        )


# ──── 类型转换器 ────

def _mask_secret(value: str) -> str:
    """脱敏 API Key"""
    if not value:
        return ""
    if len(value) <= 8:
        return "****"
    return f"{value[:3]}****{value[-4:]}"


def _to_int(raw: str, default: int) -> Tuple[int, CleanStatus, str]:
    """字符串转 int"""
    if raw is None or raw == "":
        return default, CleanStatus.DEFAULTED, "空值，用默认值填充"
    try:
        return int(raw), CleanStatus.CONVERTED, f"'{raw}' → {int(raw)}"
    except ValueError:
        # 尝试提取数字
        match = re.search(r"\d+", str(raw))
        if match:
            val = int(match.group())
            return val, CleanStatus.CONVERTED, f"从 '{raw}' 提取数字 {val}"
        return default, CleanStatus.INVALID, f"无法解析为整数: '{raw}'"


def _to_bool(raw: str) -> Tuple[bool, CleanStatus, str]:
    """字符串转 bool（兼容 'true'/'false'/'0'/'1'）"""
    if raw is None:
        return False, CleanStatus.DEFAULTED, "空值 → False"
    low = str(raw).strip().lower()
    if low in ("true", "1", "yes", "on"):
        return True, CleanStatus.CONVERTED, f"'{raw}' → True"
    if low in ("false", "0", "no", "off", ""):
        return False, CleanStatus.CONVERTED, f"'{raw}' → False"
    return False, CleanStatus.INVALID, f"无法识别的布尔值: '{raw}'"


def _to_json_array(raw: str) -> Tuple[List, CleanStatus, str]:
    """字符串转 JSON 数组"""
    if raw is None or raw == "":
        return [], CleanStatus.DEFAULTED, "空值 → []"
    try:
        val = json.loads(raw)
        if isinstance(val, list):
            return val, CleanStatus.OK, f"合法 JSON 数组（{len(val)} 项）"
        # 是 JSON 但不是数组
        return [val], CleanStatus.CONVERTED, f"JSON 非数组，包装为单元素列表"
    except json.JSONDecodeError as e:
        return [], CleanStatus.INVALID, f"JSON 解析失败: {e}"


def _to_json_object(raw: str) -> Tuple[Dict, CleanStatus, str]:
    """字符串转 JSON 对象"""
    if raw is None or raw == "":
        return {}, CleanStatus.DEFAULTED, "空值 → {}"
    try:
        val = json.loads(raw)
        if isinstance(val, dict):
            return val, CleanStatus.OK, f"合法 JSON 对象（{len(val)} 键）"
        return {}, CleanStatus.INVALID, f"JSON 非 object 类型: {type(val).__name__}"
    except json.JSONDecodeError as e:
        return {}, CleanStatus.INVALID, f"JSON 解析失败: {e}"


# ──── 核心清洗逻辑 ────

def resolve_field_schema(key: str) -> FieldSchema:
    """解析字段的 Schema 定义。

    对动态 key（api_key_* 前缀）按 SECRET 类型处理。
    """
    if key in TYPED_SCHEMA:
        return TYPED_SCHEMA[key]
    # 动态匹配：api_key_{provider} → SECRET
    if key.startswith("api_key_"):
        return FieldSchema(key, FieldType.SECRET, "", description=f"Provider API Key ({key})")
    if key.startswith("api_base_"):
        return FieldSchema(key, FieldType.STRING, "", description=f"Provider API Base ({key})")
    # 未知 key → 默认 STRING
    return FieldSchema(key, FieldType.STRING, "", description="未定义字段（按字符串处理）")


def clean_field(key: str, raw_value: str) -> FieldCleanResult:
    """清洗单个字段

    Args:
        key: setting key
        raw_value: 原始 Text 值

    Returns:
        FieldCleanResult 清洗结果
    """
    schema = resolve_field_schema(key)
    ft = schema.field_type

    if ft == FieldType.STRING:
        # 字符串类型：原值即正确类型
        status = CleanStatus.OK if raw_value else CleanStatus.DEFAULTED
        val = raw_value if raw_value else (schema.default or "")
        detail = "" if raw_value else "空值，用默认值填充"
        return FieldCleanResult(key, raw_value, val, ft, status, detail)

    if ft == FieldType.INTEGER:
        val, status, detail = _to_int(raw_value, schema.default)
        return FieldCleanResult(key, raw_value, val, ft, status, detail)

    if ft == FieldType.BOOLEAN:
        val, status, detail = _to_bool(raw_value)
        return FieldCleanResult(key, raw_value, val, ft, status, detail)

    if ft == FieldType.JSON_ARRAY:
        val, status, detail = _to_json_array(raw_value)
        return FieldCleanResult(key, raw_value, val, ft, status, detail)

    if ft == FieldType.JSON_OBJECT:
        val, status, detail = _to_json_object(raw_value)
        return FieldCleanResult(key, raw_value, val, ft, status, detail)

    if ft == FieldType.SECRET:
        # 敏感数据：脱敏输出，不保留明文
        masked = _mask_secret(raw_value)
        status = CleanStatus.SECRET_MASKED if raw_value else CleanStatus.DEFAULTED
        detail = "已脱敏" if raw_value else "空值"
        return FieldCleanResult(key, "[REDACTED]", masked, ft, status, detail)

    # 兜底
    return FieldCleanResult(key, raw_value, raw_value, ft, CleanStatus.OK, "")


def clean_all_settings(raw_settings: Dict[str, str]) -> CleanReport:
    """清洗全部 settings

    Args:
        raw_settings: {key: value} 原始数据

    Returns:
        CleanReport 完整报告
    """
    report = CleanReport(total=len(raw_settings))

    for key, raw_value in raw_settings.items():
        result = clean_field(key, raw_value)
        report.fields.append(result)

        if result.status == CleanStatus.OK:
            report.ok += 1
        elif result.status == CleanStatus.CONVERTED:
            report.converted += 1
        elif result.status == CleanStatus.DEFAULTED:
            report.defaulted += 1
        elif result.status == CleanStatus.INVALID:
            report.invalid += 1
        elif result.status == CleanStatus.SECRET_MASKED:
            report.masked += 1

        # 检查是否为 Schema 未定义的 key
        if key not in TYPED_SCHEMA and not key.startswith("api_key_") and not key.startswith("api_base_"):
            report.unknown_keys.append(key)

    return report


# ──── 数据读取（Dry-run：仅 SELECT）───

def read_settings_from_db(db_path: str) -> Dict[str, str]:
    """从 SQLite 读取 settings 表（只读）

    Args:
        db_path: SQLite 数据库路径

    Returns:
        {key: value} 字典
    """
    import sqlite3
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.execute("SELECT key, value FROM settings")
        return {row["key"]: (row["value"] or "") for row in cursor.fetchall()}
    finally:
        conn.close()


def find_db_path() -> str:
    """自动定位数据库路径"""
    from app.core.config import settings as app_settings
    db_url = getattr(app_settings, "DATABASE_URL", "")
    if db_url.startswith("sqlite:///"):
        path = db_url.replace("sqlite:///", "")
        if os.path.isabs(path):
            return path
        return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", path))
    # 默认位置
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "mfkagent.db"))


# ──── 报告输出 ────

def print_report(report: CleanReport, verbose: bool = False) -> None:
    """打印清洗报告"""
    print("=" * 70)
    print("settings 表强类型 Schema 迁移 Dry-run 报告")
    print("=" * 70)
    print()
    print(f"【汇总】{report.summary()}")
    print()

    # 分类统计
    print("【按类型统计】")
    type_counts: Dict[str, int] = {}
    for f in report.fields:
        t = f.target_type.value
        type_counts[t] = type_counts.get(t, 0) + 1
    for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"  {t:15} {c} 字段")
    print()

    # 需要转换的字段（重点）
    needs_action = [f for f in report.fields
                    if f.status in (CleanStatus.CONVERTED, CleanStatus.INVALID, CleanStatus.DEFAULTED)]
    if needs_action:
        print(f"【需处理的字段（{len(needs_action)}）】")
        for f in needs_action:
            raw_display = f.raw_value[:60] + "..." if len(str(f.raw_value)) > 60 else f.raw_value
            print(f"  [{f.status.value:9}] {f.key:30} "
                  f"raw={raw_display!r:40} → typed={f.typed_value!r}")
            if f.detail:
                print(f"            └─ {f.detail}")
        print()

    # 脱敏字段
    masked = [f for f in report.fields if f.status == CleanStatus.SECRET_MASKED]
    if masked:
        print(f"【敏感字段脱敏（{len(masked)}）】")
        for f in masked:
            print(f"  {f.key:30} → {f.typed_value}")
        print()

    # 未定义 key
    if report.unknown_keys:
        print(f"【Schema 未定义的 key（{len(report.unknown_keys)}）】")
        for k in report.unknown_keys:
            print(f"  {k}")
        print()

    # 完整清洗结果（verbose 模式）
    if verbose:
        print("【完整清洗结果】")
        for f in report.fields:
            raw_display = str(f.raw_value)[:60]
            print(f"  {f.key:30} [{f.target_type.value:10}] "
                  f"{f.status.value:9} = {f.typed_value!r}")
        print()

    # 输出强类型化后的 JSON（供下一阶段迁移参考）
    print("【强类型化后的目标数据（JSON 预览）】")
    typed_output: Dict[str, Any] = {}
    for f in report.fields:
        typed_output[f.key] = f.typed_value
    print(json.dumps(typed_output, ensure_ascii=False, indent=2, default=str)[:2000])
    if len(json.dumps(typed_output, ensure_ascii=False, default=str)) > 2000:
        print("... [输出已截断]")
    print()
    print("=" * 70)
    print("Dry-run 完成。未对数据库执行任何写入操作。")
    print("=" * 70)


# ──── 主入口 ────

def main():
    parser = argparse.ArgumentParser(description="settings 表强类型 Schema 迁移 Dry-run")
    parser.add_argument("--db", default=None, help="SQLite 数据库路径（默认自动定位）")
    parser.add_argument("--verbose", action="store_true", help="输出完整清洗结果")
    parser.add_argument("--report-only", action="store_true", help="仅输出报告，不读数据库（用模拟数据）")
    args = parser.parse_args()

    if args.report_only:
        # 模拟脏数据（不读数据库）
        raw_settings = {
            "font_size": "12",                    # 字符串数字
            "default_personality": "0",           # 字符串数字
            "hero_random": "0",                   # 字符串布尔
            "hero_entry": "1",                    # 字符串布尔
            "hero_favorites": '["a","b","c"]',    # JSON 数组
            "custom_greetings": "[]",             # 空 JSON 数组
            "enabled_models": '{"deepseek":[],"qwen":["m1"]}',  # JSON 对象
            "api_key_qwen": "sk-xxxxxxxxxxxx",    # 明文 Key
            "vision_api_key": "sk-secret-yyy",    # 明文 Key
            "theme": "system",                    # 正常字符串
            "language": "zh-CN",
            "default_model": "qwen-flash",
            "unknown_new_key": "some-value",      # 未定义 key
            "empty_value": "",                    # 空值
        }
        print("[模式] report-only：使用模拟脏数据\n")
    else:
        db_path = args.db or find_db_path()
        print(f"[数据库] {db_path}\n")
        if not os.path.exists(db_path):
            print(f"[错误] 数据库不存在: {db_path}")
            sys.exit(1)
        raw_settings = read_settings_from_db(db_path)

    report = clean_all_settings(raw_settings)
    print_report(report, verbose=args.verbose)


if __name__ == "__main__":
    main()

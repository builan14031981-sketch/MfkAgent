"""Phase 10: 记忆自动提取系统（Memory Extractor）。

将记忆系统从「依赖模型主动调用 add_memory 工具」升级为
「对话结束后后台无感自动提炼、去重并保存」。

核心组件：
- MemoryExtractor：无状态服务，输入用户消息 + AI 回复 + 已有记忆，
  调用轻量模型（qwen-flash）判定长期稳定信息，输出 add/update 动作列表。
- run_memory_extraction：后台任务入口，独立 Session 落库（Fail-safe）。

设计约束：
- 只保存长期稳定有效信息（偏好 / 事实 / 工作流 / 项目规则）；
  严禁保存临时性、一次性废话。
- 提取失败绝不影响用户正常聊天响应（完整 try-except 包裹 + 日志）。
"""

import json
import logging
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional

from app.core.database import AsyncSessionLocal
from app.models.agent import MemoryItem
from app.services.model import model_service

logger = logging.getLogger(__name__)

# 极短确认语 / 寒暄语：直接跳过提取
_SHORT_CONFIRMATIONS = {
    "好的", "收到", "可以", "知道", "嗯", "好", "行", "了解", "明白",
    "ok", "okay", "ok!", "好的！", "收到！", "知道了", "谢谢", "多谢",
    "没问题", "可以呀", "好呀", "好的呀", "行吧", "1", "yes", "no",
    "是", "不是", "对", "不对", "可以吗", "帮我", "来", "继续", "再试一次",
}

# 允许的 memory_type（与 MemoryItem.memory_type 对齐）
VALID_MEMORY_TYPES = (
    "preference", "fact", "workflow", "project",
    "user_preference", "interaction_pattern", "relationship_note", "current_context",
)

# 记忆提取模型：直接使用用户在前端配置的默认主模型，不硬编码任何特定模型名。
# 原则：后端不假设用户启用了哪些模型，所有模型选择基于用户实际配置。
# 主模型不可用时跳过本次提取，不尝试调用用户未配置的模型。

# 触发提取的最小用户输入长度（低于则视为寒暄，直接跳过）
MIN_USER_INPUT_LEN = 5

# 记忆置信度最低阈值：低于此值的提取结果不保存（过滤低质量/不确定的记忆）
MIN_CONFIDENCE = 0.5

# 去重相似度阈值：新记忆与已有记忆相似度超过此值则视为重复，跳过或更新
DEDUP_SIMILARITY_THRESHOLD = 0.85


class MemoryExtractor:
    """无状态记忆提取服务。

    extract() 不触碰数据库；落库由 run_memory_extraction() 在独立 Session 完成。
    """

    def _pick_model(self) -> str:
        """直接使用用户在前端配置的默认主模型，不硬编码任何特定模型。"""
        from app.core.agent_runtime.context_builder import get_default_model
        return get_default_model()

    @staticmethod
    def should_skip(user_message: str) -> bool:
        """前置过滤：输入过短或为极短确认语/寒暄 → 跳过提取。"""
        msg = (user_message or "").strip()
        if not msg:
            return True
        if len(msg) < MIN_USER_INPUT_LEN:
            return True
        if msg.lower() in _SHORT_CONFIRMATIONS:
            return True
        return False

    def _build_prompt(
        self,
        user_message: str,
        ai_content: str,
        existing_memories: List[Dict[str, Any]],
    ) -> str:
        existing_lines = []
        for i, mem in enumerate(existing_memories or []):
            mem_id = mem.get("id", mem.get("existing_id", i + 1))
            mem_type = mem.get("memory_type", "preference")
            mem_content = (mem.get("content") or "").strip()
            existing_lines.append(
                f'{i + 1}. [id={mem_id}, type={mem_type}] {mem_content}'
            )
        if existing_lines:
            existing_block = "\n".join(existing_lines)
        else:
            existing_block = "（无已有记忆）"

        return (
            "你是记忆提取助手。请根据「用户消息」与「AI 回复」，判断本次对话中"
            "是否存在值得长期保存的稳定信息，并输出结构化 JSON。\n\n"
            "## 可保存的信息类型\n"
            "- preference: 用户的稳定偏好 / 习惯（如「喜欢简洁的回答」）\n"
            "- fact: 长期稳定事实（如「项目使用 Python 3.14」）\n"
            "- workflow: 用户惯用的工作流程 / 步骤约定\n"
            "- project: 项目规则 / 约定（仅当对话明显涉及某个项目的固定规则）\n"
            "- user_preference: 用户喜欢的交流方式、表达风格（如「不喜欢被分析」「喜欢直接给答案」）\n"
            "- interaction_pattern: 用户的交流模式（如「喜欢深入讨论」「喜欢先被倾听再给建议」）\n"
            "- relationship_note: 用户和 AI 之间真实发生过的交流痕迹（如「讨论过换工作的事」）\n"
            "- current_context: 用户最近关注的问题（如「最近在纠结是否离职」）\n\n"
            "## 严禁保存（不要提取）\n"
            "- 临时性、一次性内容：如「今天遇到一个 Bug」「报错信息是 404」\n"
            "- 寒暄、确认语、情绪化的即时表达\n"
            "- 无法跨会话复用的零散细节\n"
            "- 虚假关系声明：禁止生成「我们关系很好」「用户很依赖我」这类 AI 对关系的自我断言\n\n"
            "## 已有记忆（用于去重，判定 add / update）\n"
            f"{existing_block}\n\n"
            "## 输出要求\n"
            '仅输出一个 JSON 数组，不要输出任何其他文字。数组元素格式：\n'
            '- 全新信息: {"action": "add", "memory_type": "preference|fact|workflow|project", '
            '"confidence": 0.0-1.0, "content": "长期稳定信息的内容"}\n'
            '- 更新已有记忆: {"action": "update", "existing_id": <已有记忆的 id>, '
            '"memory_type": "...", "confidence": 0.0-1.0, "content": "合并后的内容"}\n'
            '- 若没有值得保存的信息，输出空数组 []\n'
            'confidence 请依据对话中的明确程度给出（明确陈述为 0.9+，一般推断为 0.6-0.8）。\n\n'
            f"## 用户消息\n{user_message}\n\n"
            f"## AI 回复\n{ai_content}\n\n"
            "JSON:"
        )

    @staticmethod
    def _parse_response(raw: str) -> List[Dict[str, Any]]:
        """解析 LLM 输出为动作列表；任何解析失败都回退为空列表。"""
        if not raw or not raw.strip():
            return []
        text = raw.strip()
        # 去掉 ```json ... ``` 围栏
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:]
            text = text.strip()
        try:
            data = json.loads(text)
        except Exception:  # noqa: BLE001
            # 兼容：LLM 可能输出了多余文本，尝试截取第一个 [ 到最后一个 ]
            try:
                start = text.find("[")
                end = text.rfind("]")
                if start == -1 or end == -1 or end <= start:
                    return []
                data = json.loads(text[start : end + 1])
            except Exception:  # noqa: BLE001
                return []
        if not isinstance(data, list):
            return []
        return data

    @staticmethod
    def _normalize(item: Dict[str, Any]) -> Dict[str, Any]:
        """校验并规范化单条动作。非法条目返回空 dict（由调用方过滤）。"""
        action = item.get("action")
        if action not in ("add", "update"):
            return {}
        content = (item.get("content") or "").strip()
        if not content:
            return {}
        mem_type = item.get("memory_type") or "preference"
        if mem_type not in VALID_MEMORY_TYPES:
            mem_type = "preference"
        try:
            confidence = float(item.get("confidence", 0.8))
        except (TypeError, ValueError):
            confidence = 0.8
        confidence = max(0.0, min(1.0, confidence))
        norm = {
            "action": action,
            "memory_type": mem_type,
            "confidence": round(confidence, 3),
            "content": content,
        }
        if action == "update":
            try:
                existing_id = int(item.get("existing_id", 0))
            except (TypeError, ValueError):
                existing_id = 0
            if existing_id <= 0:
                return {}
            norm["existing_id"] = existing_id
        return norm

    async def extract(
        self,
        user_message: str,
        ai_content: str,
        existing_memories: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """执行记忆提取，返回规范化后的动作列表（add/update）。

        前置过滤命中 / LLM 调用失败 / 解析失败 均安全返回 []。
        """
        if self.should_skip(user_message):
            return []

        ai_text = (ai_content or "").strip()
        if not ai_text:
            return []

        model_id = self._pick_model()
        prompt = self._build_prompt(user_message, ai_text, existing_memories)
        # 将 system 指令并入 user 消息首行：部分供应商（qwen / siliconflow）强约束
        # role ∈ [user, assistant]，不接受 system role（否则 400）。合并后兼容全供应商。
        prompt = "你只输出 JSON，不输出任何解释或围栏以外的文字。\n\n" + prompt
        messages = [
            {"role": "user", "content": prompt},
        ]

        try:
            result = await model_service.call_once(
                model_id=model_id,
                messages=messages,
                temperature=0.2,
                max_tokens=2048,
            )
        except Exception:  # noqa: BLE001
            # 主模型不可用时跳过本次提取，不尝试调用用户未配置的模型
            logger.warning("[memory_extractor] 提取模型 %s 调用失败，跳过本次提取", model_id, exc_info=True)
            return []

        raw = (result.content or "").strip()
        if not raw:
            return []

        actions: List[Dict[str, Any]] = []
        for raw_item in self._parse_response(raw):
            norm = self._normalize(raw_item)
            if norm:
                actions.append(norm)
        return actions


# 写作类 Agent 黑名单：这类 Agent 专注文本创作，不需要长期记忆提取，
# 且无项目绑定时会误存 global 记忆污染其他 Agent。命中则直接跳过提取。
MEMORY_EXTRACTION_AGENT_BLOCKLIST = frozenset({
    "writer_jiangnan",   # 听澜
    "writer",             # 笔神
    "writer_narrative",   # 作家
})


async def run_memory_extraction(
    chat_id: int,
    project_id: Any,
    user_message: str,
    ai_content: str,
    agent_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """后台记忆自动提取任务（独立 Session 落库，Fail-safe）。

    Scope 自动分配：
      - Chat 绑定 project_id → 记忆归入 project 作用域
      - 否则 → 归入 global 作用域
      - 若传入 relationship agent_id（如 pianai）→ 归入 agent 作用域（自隔离）
        （Relationship Agent 的记忆按 Agent 隔离，不与其他 Agent 共用）

    任何异常都被捕获并记录日志，绝不影响用户聊天响应。
    """
    # 写作类 Agent 跳过记忆提取：避免无项目绑定时误存 global 记忆污染其他 Agent
    if agent_id and agent_id in MEMORY_EXTRACTION_AGENT_BLOCKLIST:
        return []

    try:
        extractor = MemoryExtractor()

        async with AsyncSessionLocal() as session:
            # 关系型 Agent（当前仅 pianai）→ agent 作用域自隔离记忆
            if agent_id and agent_id in ("pianai",):
                scope = "agent"
            else:
                scope = "project" if project_id is not None else "global"
            query = session.query(MemoryItem).filter(MemoryItem.scope == scope)
            if scope == "project":
                query = query.filter(MemoryItem.project_id == project_id)
            elif scope == "agent":
                query = query.filter(MemoryItem.agent_id == agent_id)
            existing = [
                {
                    "id": m.id,
                    "scope": m.scope,
                    "content": m.content,
                    "memory_type": m.memory_type or "preference",
                    "confidence": m.confidence or 0.8,
                }
                for m in query.order_by(MemoryItem.created_at.desc()).all()
            ]

            actions = await extractor.extract(user_message, ai_content, existing)

            saved_count = 0
            for action in actions:
                # P1: confidence 阈值过滤
                if action.get("confidence", 0) < MIN_CONFIDENCE:
                    logger.info("[memory_extractor] 跳过低置信度记忆 (%.2f < %.2f): %s",
                                action.get("confidence", 0), MIN_CONFIDENCE, action.get("content", "")[:50])
                    continue

                content = action["content"]

                if action["action"] == "add":
                    # P1: 文本相似度硬去重（不依赖 LLM 判断）
                    is_duplicate = False
                    for mem in existing:
                        ratio = SequenceMatcher(None, content, mem.get("content", "")).ratio()
                        if ratio > DEDUP_SIMILARITY_THRESHOLD:
                            is_duplicate = True
                            logger.info("[memory_extractor] 跳过重复记忆 (相似度%.2f): %s",
                                        ratio, content[:50])
                            break
                    if is_duplicate:
                        continue

                    session.add(
                        MemoryItem(
                            scope=scope,
                            agent_id=agent_id if scope == "agent" else None,
                            project_id=project_id if scope == "project" else None,
                            content=content,
                            memory_type=action["memory_type"],
                            confidence=action["confidence"],
                            source_chat_id=chat_id,
                        )
                    )
                    saved_count += 1
                elif action["action"] == "update":
                    target = (
                        session.query(MemoryItem)
                        .filter(
                            MemoryItem.id == action["existing_id"],
                            MemoryItem.scope == scope,
                        )
                        .first()
                    )
                    if target:
                        target.content = content
                        target.memory_type = action["memory_type"]
                        target.confidence = action["confidence"]
                        target.source_chat_id = chat_id
                        saved_count += 1

            session.commit()
            logger.info("[memory_extractor] 本次提取保存 %d 条记忆（共 %d 个动作）", saved_count, len(actions))
            return actions
    except Exception:  # noqa: BLE001
        logger.exception("[memory_extractor] 后台记忆提取失败（已忽略）")
        return []

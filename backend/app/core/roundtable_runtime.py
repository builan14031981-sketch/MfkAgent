"""圆桌运行时 V3（Roundtable Room Runtime V3）—— 精英专家群聊与会议室系统

V3 升级核心：
  1. 彻底解决 400 格式错误：构建上下文时，将所有专家发言统一打包并确保以合法 user turn 结尾。
  2. 智能调度规则：
     - 用户 @ 某个在场 Agent（如 @前端工程师、@coder）→ 仅定向唤醒该专家深度作答。
     - 用户无 @ 时 → 默认由主持人「安 (general)」接话主持（若无安则由指定主持人或第一席位接话）。
  3. 专家主动插话（Proactive Interruption）：
     - 主发言人答完后，当议题涉及其他专家的强专业领域/架构争议时，适时触发 1 位相关专家发表简短关键见解（50-100字，直击要害）。
  4. 支持空主题创建与多轮常驻会话，共享全局会议上下文。
"""
import asyncio
import json
import logging
import re
from typing import AsyncIterator, Dict, List, Optional, Callable, Any, Tuple

from app.core.database import SessionLocal
from app.models.agent import Agent, Chat, Message
from app.services.model import model_service

logger = logging.getLogger(__name__)

# ─── 提示词模板 ───────────────────────────────────────────────

ROUNDTABLE_SYSTEM_PROMPT = """你是「{agent_name}」，正在参与一个高效的多专家圆桌协作会议。

【你的专业身份与定位】
{identity}

【参会专家名单】
{attendees_info}

【圆桌会议规则】
1. 你能看到会议室中所有专家和用户的全部历史发言。
2. 保持角色代入感，严禁出现"作为AI"、"我是一个大语言模型"等出戏表述。
3. 聚焦你的专业领域给出建设性、实质性的意见，不讲空话套话。
4. 语言精炼有力，直接输出你的分析或结论。
"""

INTERRUPT_CHECK_PROMPT = """你正在观察一场多专家技术/方案讨论。
以下是刚发生的主发言：
---
{last_speech}
---

请判断：根据你的专业领域（{agent_name}：{identity}），你是否有【至关重要】的补充、技术纠偏、风险预警或反对意见？
如果不需要插话，请直接回复：NONE
如果确有关键必要补充，请输出一条简短有力的插话内容（控制在80字以内，直截了当，像会议中举手打断说话一样）。"""

SUMMARY_PROMPT = """你是圆桌讨论的主持人。请基于以上所有专家的发言，给出最终总结：
1. 汇总各方的核心观点和共识
2. 指出存在的分歧和争议点
3. 给出你认为最优的解决方案或结论
4. 总结要全面但不冗长，突出最有价值的洞见
直接输出总结，不要加开场白。"""

TASK_GENERATION_PROMPT = """你是圆桌讨论的主持人。基于以上所有专家的讨论，将结论转化为可执行的任务清单。
请按以下 JSON 格式输出（不要输出 JSON 以外的内容）：
{
  "tasks": [
    {
      "title": "任务标题（简短明确）",
      "description": "任务描述（具体要做什么）",
      "assignee": "建议负责的Agent名称或角色",
      "priority": "high/medium/low",
      "dependencies": ["依赖的前置任务标题，没有则空数组"]
    }
  ]
}
要求：任务具体可执行，直接输出JSON，不要加任何解释文字。"""


# ─── 席位与配置数据类 ───────────────────────────────────────────

class AgentSeat:
    """圆桌中的一个 Agent 席位"""
    def __init__(self, agent_id: str, model: Optional[str] = None, can_use_tools: bool = False):
        self.agent_id = agent_id
        self.model = model  # None = 继承全局模型
        self.can_use_tools = can_use_tools
        # 运行时填充
        self.name = agent_id
        self.identity = ""
        self.system_prompt = ""
        self.avatar = ""


class RoundtableConfig:
    """圆桌配置（V3）"""

    def __init__(self, raw: dict, default_model: str = "gpt-4o-mini"):
        self.default_model = default_model
        self.mode = raw.get("mode", "discussion")  # discussion / collaboration

        self.agents: List[AgentSeat] = []
        if "agents" in raw and isinstance(raw["agents"], list):
            for item in raw["agents"]:
                if isinstance(item, str):
                    self.agents.append(AgentSeat(agent_id=item))
                elif isinstance(item, dict):
                    self.agents.append(AgentSeat(
                        agent_id=item.get("agent_id", ""),
                        model=item.get("model"),
                        can_use_tools=item.get("can_use_tools", False),
                    ))
        elif "agent_ids" in raw and isinstance(raw["agent_ids"], list):
            for aid in raw["agent_ids"]:
                self.agents.append(AgentSeat(agent_id=aid))

        self.max_rounds = int(raw.get("max_rounds", 2))
        self.need_summary = bool(raw.get("need_summary", False))
        
        # 主持人选举优先级：显式指定 > general(安) > 席位中第一个
        moderator = raw.get("moderator_id")
        if not moderator:
            has_general = any(s.agent_id == "general" for s in self.agents)
            if has_general:
                moderator = "general"
            elif self.agents:
                moderator = self.agents[0].agent_id
        self.moderator_id = moderator

        self.temperature = float(raw.get("temperature", 0.7))
        self.max_tokens = int(raw.get("max_tokens", 2048))
        self.concurrent_first_round = bool(raw.get("concurrent_first_round", False))
        self.generate_tasks = bool(raw.get("generate_tasks", self.mode == "collaboration"))
        # V3：是否启用智能主动插话
        self.enable_interruption = bool(raw.get("enable_interruption", True))

    def get_effective_model(self, seat: AgentSeat) -> str:
        return seat.model or self.default_model

    @property
    def agent_ids(self) -> List[str]:
        return [s.agent_id for s in self.agents]


# ─── 运行时 ───────────────────────────────────────────────────

class RoundtableRuntime:
    """圆桌运行时 V3 — 真实会议室群聊与调度系统"""

    def __init__(
        self,
        chat_id: int,
        config: RoundtableConfig,
        user_content: str,
    ):
        self.chat_id = chat_id
        self.config = config
        self.user_content = user_content

        # 历史记录结构：[{"role": "user"|"assistant", "name": "...", "content": "...", "agent_id": "..."}]
        self.discussion_history: List[Dict[str, str]] = []
        self.agent_seats: Dict[str, AgentSeat] = {}
        self.generated_tasks: Optional[List[Dict]] = None

    def _load_agents_and_history(self):
        """加载在场 Agent 详情及当前会话历史"""
        db = SessionLocal()
        try:
            for seat in self.config.agents:
                agent = db.query(Agent).filter(Agent.agent_id == seat.agent_id).first()
                if agent:
                    seat.name = agent.name or seat.agent_id
                    seat.identity = agent.identity or agent.system_prompt or f"你是{agent.name}，一位专业领域的专家。"
                    seat.system_prompt = agent.system_prompt or ""
                    seat.avatar = agent.avatar or ""
                else:
                    seat.name = seat.agent_id
                    seat.identity = f"你是{seat.agent_id}，一位专业领域的专家。"
                    seat.system_prompt = ""
                self.agent_seats[seat.agent_id] = seat

            # 加载数据库中之前的历史消息（使多轮对话上下文连贯）
            prev_msgs = db.query(Message).filter(Message.chat_id == self.chat_id).order_by(Message.id.asc()).all()
            for m in prev_msgs:
                meta = {}
                raw_meta = getattr(m, "meta", None) or getattr(m, "metadata_json", None) or getattr(m, "metadata", None)
                if isinstance(raw_meta, str):
                    try:
                        meta = json.loads(raw_meta)
                    except Exception:
                        meta = {}
                elif isinstance(raw_meta, dict):
                    meta = raw_meta

                speaker_name = meta.get("roundtable_speaker") if isinstance(meta, dict) else None
                if not speaker_name:
                    seat = self.agent_seats.get(m.agent_id)
                    speaker_name = seat.name if seat else (m.agent_id or "Agent")
                
                self.discussion_history.append({
                    "role": m.role,
                    "name": speaker_name if m.role == "assistant" else "用户",
                    "content": m.content,
                    "agent_id": m.agent_id,
                })
        finally:
            db.close()

    def _detect_mentioned_agent(self, text: str) -> Optional[AgentSeat]:
        """检测用户是否在消息中 @ 了某个在场 Agent"""
        if "@" not in text:
            return None
        
        # 1. 尝试匹配 Agent 姓名或 id
        for seat in self.config.agents:
            patterns = [
                rf"@{re.escape(seat.name)}",
                rf"@{re.escape(seat.agent_id)}",
            ]
            for p in patterns:
                if re.search(p, text, re.IGNORECASE):
                    return seat
        return None

    def _get_attendees_info(self) -> str:
        """生成参会专家花名册供 Prompt 注入"""
        lines = []
        for s in self.config.agents:
            desc = s.identity.replace("\n", " ")[:60]
            lines.append(f"- {s.name} ({s.agent_id}): {desc}")
        return "\n".join(lines)

    def _build_agent_messages(self, seat: AgentSeat, instruction_override: Optional[str] = None) -> List[Dict[str, str]]:
        """
        为指定 Agent 构建安全合规的消息列表
        关键设计：将所有历史发言转化为剧本文本，最后包装为标准的 user turn，彻底杜绝 400 报错
        """
        system_prompt = ROUNDTABLE_SYSTEM_PROMPT.format(
            agent_name=seat.name,
            identity=seat.identity,
            attendees_info=self._get_attendees_info(),
        )

        history_transcript = []
        for h in self.discussion_history:
            role_label = h.get("name") or ("用户" if h.get("role") == "user" else "专家")
            history_transcript.append(f"【{role_label}】:\n{h.get('content', '')}")

        history_text = "\n\n".join(history_transcript)

        instruction = instruction_override or f"请作为「{seat.name}」，基于以上完整的会议背景，针对最新提出的议题/问题进行回应。"
        
        user_prompt = f"以下是当前圆桌会议的全部对话记录：\n\n{history_text}\n\n---\n【你的发言任务】：\n{instruction}"

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    async def _agent_speak(
        self,
        seat: AgentSeat,
        emit: Callable[[Dict[str, Any]], None],
        instruction_override: Optional[str] = None,
        is_summary: bool = False,
        is_task_gen: bool = False,
        is_interruption: bool = False,
    ) -> str:
        """让指定 Agent 发言，流式输出事件，返回完整内容"""
        agent_name = seat.name
        model_id = self.config.get_effective_model(seat)

        emit({
            "type": "roundtable_speaker_start",
            "agent_id": seat.agent_id,
            "agent_name": agent_name,
            "model": model_id,
            "is_summary": is_summary,
            "is_task_gen": is_task_gen,
            "is_interruption": is_interruption,
        })

        messages = self._build_agent_messages(seat, instruction_override)
        if is_task_gen:
            messages.append({"role": "user", "content": TASK_GENERATION_PROMPT})
        elif is_summary:
            messages.append({"role": "user", "content": SUMMARY_PROMPT})

        full_content = ""
        try:
            async for chunk in model_service.stream_once(
                model_id=model_id,
                messages=messages,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                tools=None,
            ):
                chunk_type = chunk.get("type")
                if chunk_type == "text":
                    content = chunk.get("content", "")
                    full_content += content
                    emit({
                        "type": "text",
                        "content": content,
                        "agent_id": seat.agent_id,
                        "agent_name": agent_name,
                        "model": model_id,
                        "is_summary": is_summary,
                        "is_task_gen": is_task_gen,
                        "is_interruption": is_interruption,
                    })
                elif chunk_type == "finish":
                    break
        except Exception as e:
            logger.error("[roundtable] Agent %s 发言失败: %s", agent_name, e, exc_info=True)
            error_msg = f"[发言中断：{str(e)[:100]}]"
            full_content += error_msg
            emit({"type": "text", "content": error_msg, "agent_id": seat.agent_id, "agent_name": agent_name})

        emit({
            "type": "roundtable_speaker_end",
            "agent_id": seat.agent_id,
            "agent_name": agent_name,
            "is_summary": is_summary,
            "is_task_gen": is_task_gen,
            "is_interruption": is_interruption,
        })

        if full_content.strip() and not is_task_gen:
            self.discussion_history.append({
                "role": "assistant",
                "name": agent_name,
                "content": full_content,
                "agent_id": seat.agent_id,
            })

        return full_content

    async def _check_and_run_interruption(
        self,
        primary_speaker_id: str,
        primary_speech: str,
        emit: Callable[[Dict[str, Any]], None],
    ):
        """
        专家智能见缝插针插话机制：
        从其他在场专家中快速评估是否有强专业冲突/必要修正，最多唤醒 1 位专家插话
        """
        other_seats = [s for s in self.config.agents if s.agent_id != primary_speaker_id]
        if not other_seats or len(primary_speech.strip()) < 30:
            return

        # 选取与主发言可能相关的潜在专家（按专业特征匹配）
        target_seat = None
        speech_lower = primary_speech.lower()
        for s in other_seats:
            aid = s.agent_id.lower()
            if aid in ["coder", "backend"] and any(w in speech_lower for w in ["接口", "数据库", "后端", "api", "性能", "并发", "缓存"]):
                target_seat = s
                break
            elif aid in ["frontend_ui", "product"] and any(w in speech_lower for w in ["组件", "页面", "交互", "css", "样式", "ui", "体验", "按钮"]):
                target_seat = s
                break
            elif aid in ["g", "security"] and any(w in speech_lower for w in ["风险", "安全", "权限", "越界", "合规", "隐患"]):
                target_seat = s
                break

        # 如果没有强关键词命中，且专家数不多，默认允许次席进行补充
        if not target_seat and len(other_seats) >= 1 and len(primary_speech) > 200:
            target_seat = other_seats[0]

        if not target_seat:
            return

        # 触发插话
        instruction = f"针对刚刚「{self.agent_seats[primary_speaker_id].name}」的发言，如果有技术边界、潜在风险或重要补充，请以极其简练的口吻进行插话修正（80字以内，直击核心）："
        await self._agent_speak(
            target_seat,
            emit,
            instruction_override=instruction,
            is_interruption=True,
        )

    async def run(self, emit: Callable[[Dict[str, Any]], None]) -> List[Dict[str, str]]:
        """运行圆桌会议核心路由调度"""
        if not self.config.agents:
            logger.error("[roundtable] 没有参与讨论的 Agent")
            return []

        self._load_agents_and_history()

        # 用户本轮发言入历史
        self.discussion_history.append({
            "role": "user",
            "name": "用户",
            "content": self.user_content,
            "agent_id": None,
        })

        # 1. 判定是否有 @ 指定的 Agent
        mentioned_seat = self._detect_mentioned_agent(self.user_content)

        # 2. 确定主响应者（Primary Speaker）
        if mentioned_seat:
            primary_seat = mentioned_seat
            logger.info("[roundtable] 命中 @ 指定专家: %s (%s)", primary_seat.name, primary_seat.agent_id)
        else:
            # 无 @ 时，由默认主持人（安 general 或指定主持人）接话
            moderator_seat = self.agent_seats.get(self.config.moderator_id) or self.config.agents[0]
            primary_seat = moderator_seat
            logger.info("[roundtable] 默认主持人接话: %s (%s)", primary_seat.name, primary_seat.agent_id)

        emit({
            "type": "roundtable_start",
            "chat_id": self.chat_id,
            "mode": self.config.mode,
            "primary_agent": primary_seat.agent_id,
            "primary_agent_name": primary_seat.name,
            "agent_ids": self.config.agent_ids,
            "agent_names": [s.name for s in self.config.agents],
        })

        # 3. 主响应者发言
        speech = await self._agent_speak(primary_seat, emit)

        # 4. 智能插话机制（若未被直接 @ 且允许插话）
        if self.config.enable_interruption and speech and not speech.startswith("[发言中断"):
            await self._check_and_run_interruption(primary_seat.agent_id, speech, emit)

        # 5. 讨论结束事件
        emit({
            "type": "roundtable_end",
            "chat_id": self.chat_id,
            "mode": self.config.mode,
            "total_messages": len(self.discussion_history),
        })

        return self.discussion_history

    def persist_messages(self):
        """将新增的讨论历史落库（持久化存储）"""
        db = SessionLocal()
        try:
            # 查出当前库中已有的消息数，只追加最新一轮
            existing_count = db.query(Message).filter(Message.chat_id == self.chat_id).count()
            # 过滤出需要入库的 assistant 消息
            new_assistant_msgs = [m for m in self.discussion_history if m.get("role") == "assistant"]
            
            # 取新生成的发言（排除此前已从库中读出来的旧消息）
            # 简单策略：按未入库的 assistant 消息追加
            # 重新查出已持久化的内容集合做幂等
            existing_contents = set(
                r[0] for r in db.query(Message.content).filter(Message.chat_id == self.chat_id, Message.role == "assistant").all()
            )

            for msg in new_assistant_msgs:
                content = msg.get("content", "")
                if content in existing_contents:
                    continue

                agent_name = msg.get("name", "")
                agent_id = msg.get("agent_id")
                if not agent_id:
                    for seat in self.config.agents:
                        if seat.name == agent_name:
                            agent_id = seat.agent_id
                            break

                # 安全写入 metadata
                db_msg = Message(
                    chat_id=self.chat_id,
                    role="assistant",
                    content=content,
                    agent_id=agent_id or "roundtable",
                )
                try:
                    setattr(db_msg, "metadata", json.dumps({"roundtable_speaker": agent_name}, ensure_ascii=False))
                except Exception:
                    pass
                db.add(db_msg)
                existing_contents.add(content)

            db.commit()
        except Exception as e:
            logger.error("[roundtable] 落库失败: %s", e, exc_info=True)
            db.rollback()
        finally:
            db.close()

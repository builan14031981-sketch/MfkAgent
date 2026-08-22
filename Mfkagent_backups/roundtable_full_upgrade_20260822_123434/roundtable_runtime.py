"""圆桌运行时 V2（Roundtable Runtime V2）—— 多 Agent 同会话讨论

V2 改进：
  1. 每 Agent 可独立指定模型（默认继承全局模型）
  2. 第一轮支持并发（各 Agent 独立分析，不互相等待）
  3. 双模式：探讨模式（纯讨论）/ 协作模式（讨论+生成任务清单）
  4. 向后兼容旧配置（agent_ids + max_rounds 自动映射为探讨模式）

核心流程：
  用户消息 → 入讨论历史
    ↓
  第1轮（可并发）：Agent A/B/C 同时独立发言
    ↓
  第2轮+（串行）：A 回应 B/C → B 回应 → C 回应
    ↓
  ...达到最大轮次
    ↓
  主持人总结（探讨模式）/ 主持人总结 + 生成任务清单（协作模式）
"""
import asyncio
import json
import logging
from typing import AsyncIterator, Dict, List, Optional, Callable, Any

from app.core.database import SessionLocal
from app.models.agent import Agent, Chat, Message
from app.services.model import model_service

logger = logging.getLogger(__name__)

# ─── 系统提示词模板 ───────────────────────────────────────────

ROUNDTABLE_SYSTEM_PROMPT = """你是「{agent_name}」，正在参与一个多专家圆桌讨论。

【你的身份】
{identity}

【讨论规则】
1. 你正在和其他专家一起讨论用户提出的问题/任务
2. 你可以看到其他专家的发言，请基于他们的观点给出你的看法
3. 可以赞同、补充、质疑或反驳其他专家的观点，但要保持专业和建设性
4. 发言要简洁有力，聚焦你的专业领域，不要重复别人已经说过的内容
5. 不要提及"作为AI"或"我是一个语言模型"，保持角色代入感
6. 直接输出你的观点，不要加"我认为"之类的开场白

【当前讨论主题】
{user_task}
"""

SUMMARY_PROMPT = """你是圆桌讨论的主持人。请基于以上所有专家的发言，给出最终总结：

1. 汇总各方的核心观点和共识
2. 指出存在的分歧和争议点
3. 给出你认为最优的解决方案或结论
4. 总结要全面但不冗长，突出最有价值的洞见

直接输出总结，不要加开场白。"""

TASK_GENERATION_PROMPT = """你是圆桌讨论的主持人。基于以上所有专家的讨论，将结论转化为可执行的任务清单。

请按以下 JSON 格式输出（不要输出 JSON 以外的内容）：
{{
  "tasks": [
    {{
      "title": "任务标题（简短明确）",
      "description": "任务描述（具体要做什么）",
      "assignee": "建议负责的Agent名称或角色",
      "priority": "high/medium/low",
      "dependencies": ["依赖的前置任务标题，没有则空数组"]
    }}
  ]
}}

要求：
- 任务要具体可执行，不要空泛
- 优先级合理，高优先级的先做
- 如果某个任务依赖另一个任务先完成，标注dependencies
- 任务数量控制在3-8个之间
- 直接输出JSON，不要加任何解释文字"""


# ─── 配置数据类 ───────────────────────────────────────────────

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


class RoundtableConfig:
    """圆桌配置（V2，向后兼容旧格式）"""

    def __init__(self, raw: dict, default_model: str = "gpt-4o-mini"):
        self.default_model = default_model

        # 模式：discussion / collaboration
        self.mode = raw.get("mode", "discussion")

        # 解析 Agent 列表（支持新旧两种格式）
        self.agents: List[AgentSeat] = []
        if "agents" in raw and isinstance(raw["agents"], list):
            # 新格式：[{"agent_id": "coder", "model": "gpt-4o", "can_use_tools": true}, ...]
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
            # 旧格式：["coder", "frontend_ui", "g"]
            for aid in raw["agent_ids"]:
                self.agents.append(AgentSeat(agent_id=aid))

        # 基本参数
        self.max_rounds = int(raw.get("max_rounds", 2))
        self.need_summary = bool(raw.get("need_summary", True))
        self.moderator_id = raw.get("moderator_id") or (self.agents[-1].agent_id if self.agents else None)
        self.temperature = float(raw.get("temperature", 0.8))
        self.max_tokens = int(raw.get("max_tokens", 2048))

        # V2 特性
        self.concurrent_first_round = bool(raw.get("concurrent_first_round", True))
        # 协作模式默认生成任务，探讨模式默认不生成
        self.generate_tasks = bool(raw.get("generate_tasks", self.mode == "collaboration"))

    def get_effective_model(self, seat: AgentSeat) -> str:
        """获取 Agent 实际使用的模型（优先席位配置，否则全局默认）"""
        return seat.model or self.default_model

    @property
    def agent_ids(self) -> List[str]:
        return [s.agent_id for s in self.agents]


# ─── 运行时 ───────────────────────────────────────────────────

class RoundtableRuntime:
    """圆桌运行时 V2 — 编排多 Agent 讨论流程"""

    def __init__(
        self,
        chat_id: int,
        config: RoundtableConfig,
        user_content: str,
    ):
        self.chat_id = chat_id
        self.config = config
        self.user_content = user_content

        # 讨论历史：[{"role": "user/assistant", "name": agent_name, "content": "..."}]
        self.discussion_history: List[Dict[str, str]] = []
        # Agent 信息缓存：{agent_id: AgentSeat}
        self.agent_seats: Dict[str, AgentSeat] = {}
        # 生成的任务清单（协作模式）
        self.generated_tasks: Optional[List[Dict]] = None

    def _load_agents(self):
        """从数据库加载参与讨论的 Agent 信息"""
        db = SessionLocal()
        try:
            for seat in self.config.agents:
                agent = db.query(Agent).filter(Agent.agent_id == seat.agent_id).first()
                if agent:
                    seat.name = agent.name or seat.agent_id
                    seat.identity = agent.identity or agent.system_prompt or f"你是{agent.name}，一位专业的专家。"
                    seat.system_prompt = agent.system_prompt or ""
                else:
                    seat.name = seat.agent_id
                    seat.identity = f"你是{seat.agent_id}，一位专业的专家。"
                    seat.system_prompt = ""
                self.agent_seats[seat.agent_id] = seat
        finally:
            db.close()

    def _build_agent_messages(self, seat: AgentSeat) -> List[Dict[str, str]]:
        """为指定 Agent 构建消息列表（system + 讨论历史）"""
        system_prompt = ROUNDTABLE_SYSTEM_PROMPT.format(
            agent_name=seat.name,
            identity=seat.identity,
            user_task=self.user_content[:2000],  # V2: 截断从500提升到2000
        )
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(self.discussion_history)
        return messages

    async def _agent_speak(
        self,
        seat: AgentSeat,
        emit: Callable[[Dict[str, Any]], None],
        is_summary: bool = False,
        is_task_gen: bool = False,
    ) -> str:
        """让一个 Agent 发言，流式输出事件，返回完整内容"""
        agent_name = seat.name
        model_id = self.config.get_effective_model(seat)

        emit({
            "type": "roundtable_speaker_start",
            "agent_id": seat.agent_id,
            "agent_name": agent_name,
            "model": model_id,
            "is_summary": is_summary,
            "is_task_gen": is_task_gen,
        })

        messages = self._build_agent_messages(seat)
        if is_task_gen:
            messages.append({"role": "user", "content": TASK_GENERATION_PROMPT})
        elif is_summary:
            messages.append({"role": "user", "content": SUMMARY_PROMPT})

        full_content = ""
        try:
            tools = None  # V2: 圆桌暂不启用工具调用，后续扩展
            async for chunk in model_service.stream_once(
                model_id=model_id,
                messages=messages,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                tools=tools,
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
        })

        # 任务生成结果不加入讨论历史（它是结构化输出）
        if full_content.strip() and not is_task_gen:
            self.discussion_history.append({
                "role": "assistant",
                "name": agent_name,
                "content": full_content,
            })

        # 解析任务清单
        if is_task_gen and full_content.strip():
            self._parse_tasks(full_content)

        return full_content

    def _parse_tasks(self, content: str):
        """从 Agent 输出中解析 JSON 任务清单"""
        try:
            # 尝试提取 JSON 部分（可能被 markdown 代码块包裹）
            text = content.strip()
            if text.startswith("```"):
                # 去掉 ```json 或 ``` 包裹
                lines = text.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                text = "\n".join(lines)
            data = json.loads(text)
            if isinstance(data, dict) and "tasks" in data:
                self.generated_tasks = data["tasks"]
                logger.info("[roundtable] 解析到 %d 个任务", len(self.generated_tasks))
            elif isinstance(data, list):
                self.generated_tasks = data
        except Exception as e:
            logger.warning("[roundtable] 任务清单解析失败: %s", e)
            self.generated_tasks = None

    async def _run_round_concurrent(self, emit: Callable):
        """并发执行一轮：所有 Agent 同时发言"""
        emit({"type": "roundtable_concurrent_start", "count": len(self.config.agents)})

        async def speak_agent(seat):
            return await self._agent_speak(seat, emit)

        results = await asyncio.gather(
            *[speak_agent(seat) for seat in self.config.agents],
            return_exceptions=True
        )

        for seat, result in zip(self.config.agents, results):
            if isinstance(result, Exception):
                logger.error("[roundtable] 并发发言失败 %s: %s", seat.name, result)

        emit({"type": "roundtable_concurrent_end"})

    async def _run_round_serial(self, emit: Callable):
        """串行执行一轮：Agent 按顺序发言"""
        for seat in self.config.agents:
            await self._agent_speak(seat, emit)

    async def run(self, emit: Callable[[Dict[str, Any]], None]) -> List[Dict[str, str]]:
        """运行圆桌讨论"""
        if not self.config.agents:
            logger.error("[roundtable] 没有参与讨论的 Agent")
            return []

        logger.info(
            "[roundtable] 开始讨论 chat_id=%d mode=%s agents=%s rounds=%d concurrent=%s",
            self.chat_id, self.config.mode, self.config.agent_ids,
            self.config.max_rounds, self.config.concurrent_first_round,
        )

        self._load_agents()

        # 用户消息入讨论历史
        self.discussion_history.append({"role": "user", "content": self.user_content})

        emit({
            "type": "roundtable_start",
            "chat_id": self.chat_id,
            "mode": self.config.mode,
            "agent_ids": self.config.agent_ids,
            "agent_names": [s.name for s in self.config.agents],
            "agent_models": {s.agent_id: self.config.get_effective_model(s) for s in self.config.agents},
            "max_rounds": self.config.max_rounds,
            "concurrent_first_round": self.config.concurrent_first_round,
        })

        # 多轮讨论
        for round_num in range(1, self.config.max_rounds + 1):
            emit({
                "type": "roundtable_round_start",
                "round": round_num,
                "max_rounds": self.config.max_rounds,
                "concurrent": round_num == 1 and self.config.concurrent_first_round,
            })

            if round_num == 1 and self.config.concurrent_first_round:
                await self._run_round_concurrent(emit)
            else:
                await self._run_round_serial(emit)

            emit({"type": "roundtable_round_end", "round": round_num})

        # 最终总结
        moderator_seat = self.agent_seats.get(self.config.moderator_id)
        if self.config.need_summary and moderator_seat:
            emit({"type": "roundtable_summary_start"})
            await self._agent_speak(moderator_seat, emit, is_summary=True)
            emit({"type": "roundtable_summary_end"})

        # 协作模式：生成任务清单
        if self.config.generate_tasks and moderator_seat:
            emit({"type": "roundtable_task_gen_start"})
            await self._agent_speak(moderator_seat, emit, is_task_gen=True)
            emit({
                "type": "roundtable_task_gen_end",
                "tasks": self.generated_tasks or [],
            })

        # 讨论结束
        emit({
            "type": "roundtable_end",
            "chat_id": self.chat_id,
            "mode": self.config.mode,
            "total_messages": len(self.discussion_history),
            "tasks": self.generated_tasks or [],
        })

        logger.info("[roundtable] 讨论结束，共 %d 条消息, 任务 %d 个",
                    len(self.discussion_history), len(self.generated_tasks or []))
        return self.discussion_history

    def persist_messages(self):
        """将讨论历史落库（每条 Agent 发言单独存为一条消息）"""
        db = SessionLocal()
        try:
            for msg in self.discussion_history:
                if msg.get("role") == "user":
                    continue
                agent_name = msg.get("name", "")
                content = msg.get("content", "")
                # 查找 agent_id（通过 name 反查）
                agent_id = None
                for seat in self.config.agents:
                    if seat.name == agent_name:
                        agent_id = seat.agent_id
                        break
                db_msg = Message(
                    chat_id=self.chat_id,
                    role="assistant",
                    content=content,
                    agent_id=agent_id or "roundtable",
                    metadata=json.dumps({"roundtable_speaker": agent_name}, ensure_ascii=False),
                )
                db.add(db_msg)
            # 如果有生成的任务，也存一条消息
            if self.generated_tasks:
                task_content = "## 圆桌讨论生成的任务清单\n\n"
                for i, task in enumerate(self.generated_tasks, 1):
                    title = task.get("title", f"任务{i}")
                    desc = task.get("description", "")
                    assignee = task.get("assignee", "")
                    priority = task.get("priority", "medium")
                    task_content += f"### {i}. [{priority}] {title}\n"
                    if desc:
                        task_content += f"{desc}\n"
                    if assignee:
                        task_content += f"**负责**: {assignee}\n"
                    task_content += "\n"
                db_msg = Message(
                    chat_id=self.chat_id,
                    role="assistant",
                    content=task_content,
                    agent_id="roundtable",
                    metadata=json.dumps({"roundtable_tasks": self.generated_tasks}, ensure_ascii=False),
                )
                db.add(db_msg)
            db.commit()
        except Exception as e:
            logger.error("[roundtable] 落库失败: %s", e, exc_info=True)
            db.rollback()
        finally:
            db.close()

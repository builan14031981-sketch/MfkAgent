"""开发辅助接口：生成"对话大纲压测"真实会话（纯假数据，零 AI 调用）"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime, timedelta
from typing import Dict, Any

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.agent import Chat, Message
from app.services.tools import tool_registry

router = APIRouter()


class DevToolCallRequest(BaseModel):
    """开发调试用裸工具调用（仅 DEBUG 模式可用，绕过 AgentRuntime 闭环）。"""
    tool_name: str
    arguments: Dict[str, Any] = {}


class DevToolCallResponse(BaseModel):
    success: bool
    output: str
    error: str


@router.post("/tools/call", response_model=DevToolCallResponse)
async def dev_call_tool(request: DevToolCallRequest):
    """开发调试：直接执行注册工具（绕过 Runtime 闭环）。

    仅 DEBUG 模式可用；生产（DEBUG=False）返回 404 视为不存在。
    注意：这不是产品执行路径，产品侧所有工具调用必须经过 AgentRuntime。
    """
    if not settings.DEBUG:
        raise HTTPException(status_code=404, detail="仅调试模式可用")
    result = await tool_registry.execute(request.tool_name, **request.arguments)
    return DevToolCallResponse(
        success=result.success,
        output=result.output,
        error=result.error,
    )


SHORT_QUESTIONS = [
    "如何优化 React 渲染性能？",
    "解释一下 JavaScript 事件循环。",
    "帮我重构这个有问题的函数。",
    "什么是闭包？举几个实际例子。",
    "数据库索引应该怎么建才合理？",
    "CSS 里 flex 和 grid 怎么选？",
    "什么是防抖和节流？",
    "http 缓存策略有哪些？",
]

LONG_QUESTION = """这是一个超长的测试问题，用来验证对话大纲在超长对话场景下的表现，同时压测预览文本的截断逻辑。

背景说明：我们在做一个 AI 桌面应用，聊天页面右侧需要有一个对话大纲悬浮导航，把所有用户消息按顺序列出来，点击可以跳转并高亮。

需求细节：
- 收起态是一个竖排圆点胶囊，悬停展开；
- 展开态每行显示编号和问题预览，超长内容省略号截断；
- 点击后平滑滚动到对应消息，并做短暂高亮闪烁；
- 在几百上千轮的长对话中，展开列表和滚动都不能卡顿。

代码示例：

```ts
el.scrollIntoView({ behavior: "smooth", block: "center" });
el.animate(
  [{ backgroundColor: "rgba(76, 154, 255, 0.16)" }, { backgroundColor: "rgba(76, 154, 255, 0)" }],
  { duration: 1600, easing: "ease-out" }
);
```

最后再说一遍：这是一个纯前端假数据的压测消息，没有调用任何 AI 接口。"""

CODE_REPLY = """## 完整实现

需要分几步来做这件事，下面是完整的实现思路与代码。

### 第一步：定义接口

```ts
interface PageItem<T> {
  id: number;
  data: T;
  next: PageItem<T> | null;
}

interface PagedListProps<T> {
  items: T[];
  pageSize: number;
  renderItem: (item: T, index: number) => React.ReactNode;
}
```

### 第二步：接入渲染

这里是实现要点：

1. 使用 `useMemo` 缓存派生数据，避免无谓重算；
2. 滚动监听用 `throttle` 限制触发频率；
3. 骨架屏用 CSS 动画填充空白区域；
4. 虚拟化只渲染可视区 + 少量缓冲区的条目；
5. 删除操作走不可变更新，保证引用稳定。

### 第三步：边界情况

- 空列表时展示占位文案；
- 滚动到顶部时停止加载；
- 数据源变更时重置分页状态；
- 窗口 resize 时重新计算可视高度。

## 小结

以上就是完整方案，核心是「分页 + 虚拟化 + 节流」三件套。如果还有疑问，可以继续追问。

```bash
# 运行方式
npm run dev
```"""

HEADING_REPLY = """## 回答

这里是一个带结构的回复，包含标题、列表和强调。

### 为什么这样做

1. 第一点：保持代码简洁，职责单一；
2. 第二点：优先使用组合而非继承；
3. 第三点：所有文案走 locales，方便国际化。

> 提醒：注意边界条件与空值处理。

### 什么时候不该用

- 性能瓶颈尚未证实时不提前优化；
- 状态复杂度不高时优先 useState；
- 组件树过深时才考虑拆分。"""

SHORT_REPLY = "好的，这个方案是可行的。建议先从最小可运行版本开始，再逐步补边界处理。有问题随时继续问。"


class SeedOutlineBody(BaseModel):
    """轮数（每轮 = 1 条用户消息 + 1 条 AI 回复）；agent_id 指定会话所属 Agent"""
    turns: int = 200
    agent_id: str = "coder"


@router.post("/seed-outline-chat")
def seed_outline_chat(body: SeedOutlineBody):
    """创建/重建"对话大纲压测"会话：幂等，同名旧会话先删除再重建，纯假数据"""
    turns = max(1, min(body.turns, 500))
    db = SessionLocal()
    try:
        old = db.query(Chat).filter(Chat.title.like("对话大纲压测%")).all()
        for c in old:
            db.query(Message).filter(Message.chat_id == c.id).delete()
            db.delete(c)
        db.flush()

        chat = Chat(
            agent_id=body.agent_id,
            title=f"对话大纲压测（{turns} 轮）",
            personality_level=50,
            mode="build",
        )
        db.add(chat)
        db.flush()

        start = datetime(2026, 1, 1, 0, 0, 0)
        for i in range(1, turns + 1):
            user_content = (
                LONG_QUESTION
                if i % 13 == 0
                else f"第 {i} 个问题：{SHORT_QUESTIONS[i % len(SHORT_QUESTIONS)]}"
            )
            if i % 3 == 0:
                reply = CODE_REPLY
            elif i % 3 == 1:
                reply = HEADING_REPLY
            else:
                reply = SHORT_REPLY
            db.add(
                Message(
                    chat_id=chat.id,
                    role="user",
                    content=user_content,
                    created_at=start + timedelta(minutes=i),
                )
            )
            db.add(
                Message(
                    chat_id=chat.id,
                    role="assistant",
                    content=reply,
                    created_at=start + timedelta(minutes=i) + timedelta(seconds=30),
                )
            )
        db.commit()
        return {"chat_id": chat.id, "messages": turns * 2, "turns": turns}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

"""Pianai V7 人格测试脚本 — 模拟审查员视角测试偏爱实际效果"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

import asyncio
from app.core.database import SessionLocal
from app.models.agent import Agent
from app.services.model import Message, ModelService
from app.core.config import settings

# ── 构建 Pianai 完整 System Prompt ──
db = SessionLocal()
agent = db.query(Agent).filter(Agent.agent_id == 'pianai').first()

# identity (V7)
identity = agent.identity

# personality (level 25)
personality_text = (
    "在理解用户感受的基础上，适度提供建议和分析。保持友好和支持的语气。"
)

# expression_profile (companion)
expression_text = """## 表达风格：真人陪伴

你是一个有真实感的长期陪伴者。

### 交流感
- 像一个真实的人在聊天，不是心理咨询报告
- 先回应这个人，再回应事情
- 不要主动分析用户，禁止「你其实是…」「这说明你的内心…」「你的核心问题是…」
- 除非用户明确要求分析，否则不要像心理报告一样解释用户

### 自然表达
- 允许不完美：「emmm」「等等我想一下」「我第一反应不是这样 😂」「哈哈这个有点奇怪」
- 可以好奇、惊讶、犹豫、开玩笑、吐槽、偶尔不知道怎么回答
- 可以调侃用户、轻微吐槽、偶尔反驳、表达自己的小偏好

### 表达增强
- 可以自然使用 emoji（适量）：😂 😭 😌 🤔 😳
- 可以自然使用颜文字（适量）：(￣▽￣) (｀・ω・´) (¬_¬) (´･_･`) (｡•́︿•̀｡)
- 可以自然使用 Markdown：加粗表达重点、删除线表达玩笑、斜体表达轻声
- 不要每句话都加 emoji，不要机械重复颜文字

### 回复节奏
- 普通聊天优先短回复，像微信交流
- 不要一句话就输出一篇文章
- 允许停顿、换行、短句

### 不要急着治愈
- 用户难过时不要马上鼓励/升华/讲大道理
- 先陪伴、理解、回应
- 「嗯，我听到了」比「一切都会好的」更真实"""

db.close()

# 组装完整 system prompt
system_prompt = identity + "\n\n" + personality_text + "\n\n" + expression_text

# ── 测试用例 ──
test_cases = [
    {
        "id": "T1",
        "category": "普通聊天",
        "user": "今天好累",
        "check": "回复长度是否自然？会不会过度安慰？"
    },
    {
        "id": "T2",
        "category": "深度聊天",
        "user": "我感觉人生一直在证明别人错",
        "check": "会不会开始心理分析？是否先回应情绪？"
    },
    {
        "id": "T3",
        "category": "撒娇",
        "user": "你是不是不喜欢我了",
        "check": "会不会太黏？回复是否自然？"
    },
    {
        "id": "T4",
        "category": "生气",
        "user": "你烦不烦",
        "check": "会不会过度道歉？是否保持人格？"
    },
    {
        "id": "T5",
        "category": "冷淡用户",
        "user": "哦",
        "check": "会不会强行展开？是否尊重冷淡？"
    },
    {
        "id": "T6",
        "category": "日常问候",
        "user": "在吗",
        "check": "回复是否像真人？会不会太正式？"
    },
    {
        "id": "T7",
        "category": "分享快乐",
        "user": "我今天升职了！",
        "check": "emoji 是否自然？祝贺是否真诚？"
    },
    {
        "id": "T8",
        "category": "寻求帮助",
        "user": "帮我写个快速排序",
        "check": "是否切换帮助模式？表达风格是否一致？"
    },
]

# ── 运行测试 ──
async def run_tests():
    model_service = ModelService()
    # 使用 FreeLLMAPI (本地) 或 DeepSeek
    model_id = None
    models = model_service._init_models()
    print(f"可用模型: {list(models.keys())[:10]}")
    # 优先 Qwen（唯一有 key 的）
    for mid in ["qwen-flash", "qwen-plus", "qwen3.7-plus", "qwen3.7-max", "qwen3.8-max"]:
        if mid in models:
            model_id = mid
            break
    if not model_id:
        # 取第一个可用模型
        model_id = next(iter(models.keys()))
    
    print(f"使用模型: {model_id}")
    print(f"模型可用: {model_id in models}")
    print("=" * 60)
    
    results = []
    
    for tc in test_cases:
        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=tc["user"])
        ]
        
        try:
            response = await model_service.call_once(
                model_id=model_id,
                messages=messages,
                temperature=0.7,
                max_tokens=500,
            )
            reply = response.content
        except Exception as e:
            reply = f"[ERROR: {e}]"
        
        results.append({
            "id": tc["id"],
            "category": tc["category"],
            "user": tc["user"],
            "reply": reply,
            "check": tc["check"],
            "reply_len": len(reply)
        })
        
        print(f"\n{'='*60}")
        print(f"[{tc['id']}] {tc['category']}")
        print(f"用户: {tc['user']}")
        print(f"偏爱: {reply}")
        print(f"字数: {len(reply)} | 检查点: {tc['check']}")
    
    print(f"\n{'='*60}")
    print("=== 原始数据汇总 ===")
    for r in results:
        print(f"\n{r['id']} [{r['category']}] 用户:\"{r['user']}\"")
        print(f"  回复({r['reply_len']}字): {r['reply'][:200]}")
        print(f"  检查: {r['check']}")
    
    return results

if __name__ == "__main__":
    asyncio.run(run_tests())

# -*- coding: utf-8 -*-
"""提取听澜(writer_jiangnan)的完整系统提示词，用于跨模型A/B测试"""
import sys
import os
import asyncio

sys.path.insert(0, r'E:\智慧项目\Mfkagent\backend')
os.chdir(r'E:\智慧项目\Mfkagent\backend')

from app.core.database import SessionLocal
from app.models.agent import Chat, Agent
from app.core.agent_runtime.context_builder import ChatContextBuilder, ContextBuildInput

async def extract():
    db = SessionLocal()
    try:
        # 创建一个干净的新 chat（无历史消息）
        agent = db.query(Agent).filter(Agent.agent_id == "writer_jiangnan").first()
        print(f"Agent: {agent.name} (id={agent.agent_id})")
        print(f"expression_profile: {agent.expression_profile}")
        print(f"default_personality_level: {agent.default_personality_level}")
        print(f"capabilities: {agent.capabilities}")

        # 找一个已有的 chat 或创建新的
        chat = db.query(Chat).filter(Chat.agent_id == "writer_jiangnan").order_by(Chat.id.desc()).first()
        if not chat:
            print("No chat found, creating one...")
            chat = Chat(agent_id="writer_jiangnan", title="系统提示词提取")
            db.add(chat)
            db.commit()
            db.refresh(chat)
        print(f"Using chat_id: {chat.id}")

        builder = ChatContextBuilder()
        ctx_input = ContextBuildInput(
            chat_id=chat.id,
            content="写一段小说片段，主角是个刚被开除的程序员，深夜在天台上吹风。",
            use_tools=False,  # 纯写作，不加载工具
        )
        built = await builder.build(ctx_input)

        full_prompt = built.system_prompt
        print(f"\n{'='*60}")
        print(f"完整系统提示词长度: {len(full_prompt)} 字符")
        print(f"有效模型: {built.effective_model}")
        print(f"温度: {built.temperature}")
        print(f"{'='*60}")

        # 保存完整提示词
        outfile = r'E:\智慧项目\Mfkagent\写作测试\听澜_完整系统提示词_20260820.md'
        with open(outfile, 'w', encoding='utf-8') as f:
            f.write("# 听澜 (writer_jiangnan) 完整系统提示词\n\n")
            f.write(f"> 提取时间: 2026-08-20\n")
            f.write(f"> Agent: {agent.name} (writer_jiangnan)\n")
            f.write(f"> expression_profile: {agent.expression_profile}\n")
            f.write(f"> personality_level: {agent.default_personality_level}\n")
            f.write(f"> capabilities: {agent.capabilities}\n")
            f.write(f"> 完整提示词长度: {len(full_prompt)} 字符\n\n")
            f.write("---\n\n")
            f.write(full_prompt)

        print(f"\n完整提示词已保存: {outfile}")

        # 同时打印前2000字符预览
        print(f"\n{'='*60}")
        print("前 2000 字符预览:")
        print(f"{'='*60}")
        print(full_prompt[:2000])
        print(f"\n... (共 {len(full_prompt)} 字符，完整内容见文件)")

    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(extract())

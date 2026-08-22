import asyncio, json, re, httpx

BASE = "http://127.0.0.1:8001"
GROUP = "oc_9115881d78a3d78354d2e1fb4c2cccfb"

async def main():
    async with httpx.AsyncClient(timeout=180) as c:
        # 创建一个 agent 会话（绑定 demo_image_chain 项目，不指定 agent 用默认）
        r = await c.post(f"{BASE}/api/chat", json={
            "project_id": 52,
            "title": "飞书互动测试-hello",
            "model": None,
        })
        r.raise_for_status()
        chat_id = r.json()["id"]
        print("chat_id:", chat_id)

        prompt = f"请调用 feishu_send_message 工具，向飞书群 {GROUP} 发送一条消息，内容为 hello world"
        resp = await c.post(f"{BASE}/api/chat/{chat_id}/send/stream", json={"content": prompt})
        resp.raise_for_status()
        text = resp.text

        # 解析 Agent 回复文本
        replies = re.findall(r'data: \{"type": "text", "content": "(.*?)"\}', text)
        reply_text = "".join(replies)
        print("agent_reply:", reply_text[:300])

        # 解析工具调用结果
        blocks = re.findall(r'data: \{"type": "tool_calls".*?\}\}\}\}\}', text, re.S)
        for block in blocks[-1:]:
            try:
                obj = json.loads(block[6:])
                for call in obj.get("calls", []):
                    print("tool:", call.get("name"), "| success:", call.get("success"))
                    print("result:", call.get("result", "")[:250])
            except Exception as e:
                print("parse err:", e)

        m = re.findall(r'"message_id": "(om_[^"]+)"', text)
        print("feishu_message_ids:", m)

asyncio.run(main())
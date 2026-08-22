
import requests
import json
import time

API = "http://127.0.0.1:8001"
chat_id = 260

# 1. 发送消息（触发Agent执行，会调用删除文件工具，需要审批）
payload = {
    "content": "请用 run_command 工具实际执行以下操作：1) echo test_notify > E:\智慧项目\Mfkagent\_del_test_xyz.txt 创建文件  2) 然后执行 del E:\智慧项目\Mfkagent\_del_test_xyz.txt 删除该文件。必须实际调用工具，不要写代码示例。",
    "use_tools": True,
    "temperature": 0.7
}

print(f"Sending message to chat {chat_id}...")
print(f"Payload: {payload['content'][:80]}...")

try:
    r = requests.post(f"{API}/api/chat/{chat_id}/send", json=payload, timeout=90)
    print(f"Status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        print(f"Response keys: {list(data.keys())}")
        print(f"User msg id: {data.get('user_message', {}).get('id')}")
        print(f"AI msg id: {data.get('ai_message', {}).get('id')}")
        print(f"AI content (first 300): {str(data.get('ai_message', {}).get('content', ''))[:300]}")
    else:
        print(f"Error body: {r.text[:500]}")
except requests.exceptions.Timeout:
    print("Timeout after 90s - request may still be processing on backend")
except Exception as e:
    print(f"Error: {e}")

# 2. 检查审批列表，看看有没有待审批的请求产生
time.sleep(2)
print("
=== Checking pending approvals ===")
try:
    r2 = requests.get(f"{API}/api/security/approvals?status=pending&limit=5", timeout=5)
    if r2.status_code == 200:
        data2 = r2.json()
        print(f"Total pending: {data2.get('total')}")
        for item in data2.get('items', [])[:3]:
            print(f"  - id={item['id']} approval_id={item.get('approval_id')} "
                  f"tool={item.get('tool_name')} status={item.get('status')} "
                  f"risk={item.get('risk_level')} chat_id={item.get('chat_id')}")
    else:
        print(f"Approval list HTTP {r2.status_code}: {r2.text[:300]}")
except Exception as e:
    print(f"Approvals check failed: {e}")

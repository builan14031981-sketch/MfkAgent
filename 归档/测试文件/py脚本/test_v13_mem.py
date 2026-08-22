import sys, io, json, urllib.request
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
BASE = "http://127.0.0.1:8001/api"
TEST_MODEL = "qwen-mt-flash"

def post(path, payload, timeout=120):
    req = urllib.request.Request(BASE + path, data=json.dumps(payload).encode('utf-8'),
                                 headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))

# 新 chat，验证能读到 agent 作用域记忆
chat = post("/chat", {"agent_id": "pianai", "title": "V13记忆验证", "personality_level": 25, "model": TEST_MODEL})
cid = chat["id"]
print("新 chat_id =", cid)
resp = post(f"/chat/{cid}/send", {"content": "你还记得我们聊过什么吗？", "use_tools": True, "model": TEST_MODEL})
print("A:", resp["ai_message"]["content"])

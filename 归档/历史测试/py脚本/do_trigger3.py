import requests
import time
import json

API = "http://127.0.0.1:8001"

print("=== Step 1: Update chat 260 model to glm-5.1 ===")
try:
    r = requests.patch(API + "/api/chat/260", json={"model": "glm-5.1"}, timeout=5)
    print("PATCH chat 260 ->", r.status_code)
    if r.status_code == 200:
        print("  New model:", r.json().get("model"))
    else:
        print("  Body:", r.text[:400])
except Exception as e:
    print("  Failed:", str(e)[:200])

print("")
print("=== Step 2: Send message to chat 260 ===")
msg = "Task: Use write_file tool to create file _NOTIFY_TRIGGER_DELETEME_987.txt in current project dir with content: hello123. Then immediately use delete_file tool to remove that exact same file. MUST CALL ACTUAL TOOLS. Not code samples."
payload = {"content": msg, "use_tools": True, "temperature": 0.2}
print("Sending... msg_len=", len(msg))
t0 = time.time()
try:
    r = requests.post(API + "/api/chat/260/send", json=payload, timeout=180)
    dt = round(time.time() - t0, 1)
    print("HTTP", r.status_code, "in", dt, "s")
    if r.status_code == 200:
        d = r.json()
        ai = str((d.get("ai_message") or {}).get("content", ""))
        if len(ai) > 800: ai = ai[:800] + "..."
        print("AI Response:", ai)
    else:
        print("ERR body:", r.text[:800])
except Exception as e:
    print("Send FAILED:", type(e).__name__, str(e)[:300])

print("")
print("=== Step 3: Wait for pending approvals ===")
for attempt in range(1, 5):
    time.sleep(5)
    try:
        a = requests.get(API + "/api/security/approvals", params={"status": "pending", "limit": 8}, timeout=5)
        if a.status_code == 200:
            d = a.json()
            items = d.get("items", [])
            news = [x for x in items if str(x.get("created_at", "")) or x.get("tool_name") in ("write_file", "delete_file")]
            print("  Wait", attempt*5, "s: total pending=", d.get("total"), ", last 3 newest:")
            for x in items[:3]:
                c = str(x.get("command"))
                if len(c) > 90: c = c[:90] + "..."
                print("    -", x.get("approval_id"), x.get("tool_name"), x.get("risk_level"), "|", c)
    except Exception as e2:
        print("  Wait", attempt, "failed:", str(e2)[:200])

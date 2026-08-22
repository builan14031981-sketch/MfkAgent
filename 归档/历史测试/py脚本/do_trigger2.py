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
print("=== Step 2: Send message to chat 260 (glm-5.1 now) ===")
msg = "Task for testing: Use write_file tool to create file _NOTIFY_TRIGGER_DELETEME.txt in current project dir with any short content. Then immediately use delete_file tool to remove that same file. You MUST CALL both actual tools. Do NOT write example code."
payload = {"content": msg, "use_tools": True, "temperature": 0.3}
print("Sending to chat 260...")
t0 = time.time()
try:
    r = requests.post(API + "/api/chat/260/send", json=payload, timeout=180)
    dt = round(time.time() - t0, 1)
    print("HTTP", r.status_code, "in", dt, "s")
    if r.status_code == 200:
        ai = (r.json().get("ai_message") or {}).get("content", "") or ""
        if len(ai) > 700: ai = ai[:700] + "..."
        print("AI Response:", ai)
    else:
        print("ERR body:", r.text[:800])
except Exception as e:
    print("Send FAILED:", type(e).__name__, str(e)[:300])

print("")
print("=== Step 3: Wait and check pending approvals ===")
for attempt in range(1, 4):
    time.sleep(6)
    try:
        a = requests.get(API + "/api/security/approvals", params={"status": "pending", "limit": 3}, timeout=5)
        if a.status_code == 200:
            d = a.json()
            items = d.get("items", [])
            # Find new approvals (write_file or delete_file tool)
            new_ones = [x for x in items if x.get("tool_name") in ("write_file", "delete_file", "run_command")]
            print("  Attempt", attempt, ": total pending=", d.get("total"), ", new write/del/run count=", len(new_ones))
            for x in new_ones[:3]:
                print("    ", x.get("approval_id"), x.get("tool_name"), x.get("risk_level"), "cmd=", str(x.get("command"))[:80])
            if len(new_ones) > 0:
                break
    except Exception as e:
    print("  Attempt", attempt, "check failed:", str(e)[:150])

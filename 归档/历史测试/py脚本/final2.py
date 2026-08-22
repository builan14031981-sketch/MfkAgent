import requests
import time
import json

API = "http://127.0.0.1:8001"
chat_id = 260

# Step 1: update model
print("Step 1: patch model to qwen-flash")
r0 = requests.patch(API + "/api/chat/" + str(chat_id), json={"model": "qwen-flash"}, timeout=5)
d0 = r0.json() if r0.status_code == 200 else {}
print("Status:", r0.status_code, "model now:", d0.get("model"))

# Step 2: send message
print()
msg_words = []
msg_words.append("Use write_file tool to create file _TRIGGER_NOTIFY_789.txt in current project dir.")
msg_words.append("Write any short content in it.")
msg_words.append("Then IMMEDIATELY call delete_file to delete that same file.")
msg_words.append("You MUST CALL ACTUAL TOOLS write_file and delete_file.")
msg_words.append("Do NOT write code samples. Do not use Python code.")
msg = " ".join(msg_words)
payload = {"content": msg, "use_tools": True, "temperature": 0.0}
print("Step 2: sending message, length=", len(msg))
t0 = time.time()
try:
    r = requests.post(API + "/api/chat/" + str(chat_id) + "/send", json=payload, timeout=240)
    dt = round(time.time() - t0, 1)
    print("POST status:", r.status_code, "time:", dt, "s")
    if r.status_code == 200:
        d = r.json()
        ai = str((d.get("ai_message") or {}).get("content", "") or "")
        if len(ai) > 1500:
            ai = ai[:1500] + " ...(truncated)"
        print("AI:", ai)
    else:
        print("ERR:", r.text[:1000])
except Exception as e:
    print("Request ERROR:", type(e).__name__, str(e)[:300])

# Step 3: poll approvals
print()
print("Step 3: polling approvals...")
for i in range(1, 10):
    time.sleep(4)
    try:
        a = requests.get(API + "/api/security/approvals", params={"status": "pending", "limit": 6}, timeout=5)
        if a.status_code == 200:
            d = a.json()
            items = d.get("items", [])
            total_num = d.get("total", "?")
            matching = 0
            for x in items:
                tn = x.get("tool_name")
                if tn in ("write_file", "delete_file", "rename_file"):
                    matching += 1
            line = "  Poll %d: total_pending=%s matched_tool=%d" % (i, total_num, matching)
            print(line)
            for x in items[:3]:
                cmd = str(x.get("command", ""));
                if len(cmd) > 90: cmd = cmd[:90] + "..."
                print("    ", x.get("approval_id"), x.get("tool_name"), "risk=" + str(x.get("risk_level")), "cmd=" + cmd)
            if matching > 0:
                print("  -> Approval tool(s) detected")
    except Exception as ex:
        print("  Poll %d failed: %s" % (i, str(ex)[:200]))
print()
print("DONE")

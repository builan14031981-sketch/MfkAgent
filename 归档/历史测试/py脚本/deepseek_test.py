import requests
import time

API = "http://127.0.0.1:8001"
chat_id = 260

# Step 1: update model to deepseek-v4-flash
print("Step 1: patch model to deepseek-v4-flash")
r0 = requests.patch(API + "/api/chat/" + str(chat_id), json={"model": "deepseek-v4-flash"}, timeout=5)
print("Status:", r0.status_code, r0.json().get("model") if r0.status_code == 200 else r0.text[:300])

# Step 2: send message triggering write + delete
words = []
words.append("INSTRUCTIONS (CRITICAL - FOLLOW EXACTLY):")
words.append("You are NOT allowed to answer in plain text only.")
words.append("You MUST invoke real tools:")
words.append("TOOL 1: write_file. Create a file named _DO_TRIGGER_NOTIFY_112.txt in the project working directory.")
words.append("Write content: trigger_test.")
words.append("TOOL 2: delete_file. Immediately after TOOL 1 succeeds, call delete_file on that SAME file.")
words.append("Do NOT write sample Python code. Do NOT explain how to do it.")
words.append("ACTUALLY CALL write_file THEN delete_file tools NOW.")
msg = " ".join(words)
print()
print("Step 2: Sending... (msg len=" + str(len(msg)) + ")")
payload = {"content": msg, "use_tools": True, "temperature": 0.0, "max_tokens": 2048}
t0 = time.time()
try:
    r = requests.post(API + "/api/chat/" + str(chat_id) + "/send", json=payload, timeout=300)
    dt = round(time.time() - t0, 1)
    print("HTTP status:", r.status_code, "after", dt, "seconds")
    if r.status_code == 200:
        data = r.json()
        ai = str((data.get("ai_message") or {}).get("content", "") or "")
        if len(ai) > 1800:
            ai = ai[:1800] + " ...[trunc]"
        print("AI Response:")
        print(ai)
    else:
        print("HTTP Error body:", r.text[:1200])
except Exception as e:
    print("Request failed:", type(e).__name__, str(e)[:400], "after", round(time.time()-t0,1),"s")

# Step 3: poll for NEW write/delete tool approvals (chat_id should be 260)
print()
print("Step 3: Polling approvals, waiting for NEW write/delete...")
for i in range(1, 12):
    time.sleep(4)
    try:
        a = requests.get(API + "/api/security/approvals", params={"status": "pending", "limit": 10}, timeout=5)
        if a.status_code == 200:
            d = a.json()
            items = d.get("items", [])
            target_chat = [x for x in items if x.get("chat_id") == chat_id]
            target_tools = [x for x in items if x.get("tool_name") in ("write_file", "delete_file")]
            info = "Poll %d: pending=%d, chat_%d_count=%d, write/delete_count=%d" % (i, d.get("total",0), chat_id, len(target_chat), len(target_tools))
            print(info)
            for x in (target_tools[:4] if target_tools else target_chat[:3] if target_chat else items[:2]):
                cmd = str(x.get("command", ""));
                if len(cmd) > 100: cmd = cmd[:100] + "..."
                extra = "" if x.get("chat_id") == chat_id else " chat_id=" + str(x.get("chat_id"))
                print("    ", x.get("approval_id"), x.get("tool_name"), "risk=" + str(x.get("risk_level")) + extra, "cmd=" + cmd)
            if target_tools:
                print("  ==> write/delete approval detected (this triggers Electron notification!)")
    except Exception as ex:
        print("  Poll %d err: %s" % (i, str(ex)[:200]))

print("POLLING DONE")
import requests
import time

API = "http://127.0.0.1:8001"
chat_id = 260

print("Step 1: patch chat 260 model -> gemini-3.5-flash")
r0 = requests.patch(API + "/api/chat/" + str(chat_id), json={"model": "gemini-3.5-flash"}, timeout=5)
print("Status:", r0.status_code, "->", r0.json().get("model") if r0.status_code==200 else r0.text[:300])

print()
print("Step 2: send message (tool-call trigger for write+delete)")
W = []
W.append("CRITICAL: YOU MUST USE ACTUAL TOOLS NOW.")
W.append("Step A: Call write_file tool with path=_TRIGGER_NOTIFY_GEMINI_555.txt content=trigger_notify")
W.append("Step B: After write_file, immediately call delete_file on that same file path.")
W.append("Do NOT explain in text. Do NOT write Python code.")
W.append("Call the two tools now. Not sample code. REAL tool calls.")
msg = " ".join(W)
payload = {"content": msg, "use_tools": True, "temperature": 0.0, "max_tokens": 2048}
t0 = time.time()
try:
    r = requests.post(API + "/api/chat/" + str(chat_id) + "/send", json=payload, timeout=300)
    dt = round(time.time() - t0, 1)
    print("HTTP:", r.status_code, "time:", dt, "s")
    if r.status_code == 200:
        data = r.json()
        ai = str((data.get("ai_message") or {}).get("content", "") or "")
        if len(ai) > 1800: ai = ai[:1800] + " ..."
        print("AI:")
        print(ai)
    else:
        print("ERR:", r.text[:1200])
except Exception as e:
    print("EXC:", type(e).__name__, str(e)[:400], "after", round(time.time()-t0,1),"s")

print()
print("Step 3: polling for NEW chat_260 / write/delete approvals...")
for i in range(1, 13):
    time.sleep(4)
    try:
        a = requests.get(API + "/api/security/approvals", params={"status": "pending", "limit": 12}, timeout=5)
        if a.status_code == 200:
            d = a.json()
            items = d.get("items", [])
            c260 = [x for x in items if x.get("chat_id") == chat_id]
            wd = [x for x in items if x.get("tool_name") in ("write_file","delete_file")]
            print("  Poll %d: total=%d  chat260=%d  wdtools=%d" % (i, d.get("total",0), len(c260), len(wd)))
            shown = 0
            for x in items:
                if x.get("chat_id") == chat_id or x.get("tool_name") in ("write_file","delete_file"):
                    cmd = str(x.get("command",""));
                    if len(cmd) > 100: cmd = cmd[:100] + "..."
                    print("    ", x.get("approval_id"), x.get("tool_name"), "risk=" + str(x.get("risk_level")), "c=" + str(x.get("chat_id")), "cmd=" + cmd)
                    shown += 1
                    if shown >= 4: break
            if c260 or len(wd) > 1:
                print("  -> DETECTED: approval event(s) should trigger notification on Electron side")
    except Exception as ex:
        print("  Poll %d error: %s" % (i, str(ex)[:200]))

print("DONE polling")
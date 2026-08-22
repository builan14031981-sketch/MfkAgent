import requests
import time

API = "http://127.0.0.1:8001"
chat_id = 260

# Message: instruct agent to use WRITE then DELETE tools (require approval)
msg_words = [
  "Use the write_file tool to create a file named _test_NOFITY_123.txt "
  + "in the current project working directory with content: hello_notify. "
  + "Then use the delete_file tool to delete that exact same file. "
  + "You MUST ACTUALLY CALL both tools. Do NOT write sample code. Do NOT use Python."
];
msg = msg_words[0]
payload_obj = {"content": msg, "use_tools": True, "temperature": 0.5}

print("Sending message, length:", len(msg))
try:
    t0 = time.time()
    resp = requests.post(API + "/api/chat/" + str(chat_id) + "/send", json=payload_obj, timeout=120)
    dt = round(time.time() - t0, 1)
    print("HTTP", resp.status_code, "in", dt, "s")
    if resp.status_code == 200:
        d = resp.json()
        ai_msg = d.get("ai_message", {}).get("content", "") or ""
        print("AI:", ai_msg[:500])
    else:
        print("ERR:", resp.text[:800])
except Exception as e:
    print("Request failed:", type(e).__name__, str(e)[:200])

# Check pending approvals after short wait
print("")
time.sleep(5)
print("Pending approvals check:")
try:
    r2 = requests.get(API + "/api/security/approvals", params={"status": "pending", "limit": 5}, timeout=5)
    if r2.status_code == 200:
        d2 = r2.json()
        items = d2.get("items", [])
        print("Total pending:", d2.get("total"), "Showing:", len(items))
        for a in items:
            print("  ", a.get("approval_id"), a.get("tool_name"), a.get("risk_level"), a.get("status"), "chat_id=" + str(a.get("chat_id")))
    else:
        print("Approvals HTTP", r2.status_code, r2.text[:300])
except Exception as e:
    print("Approval check failed:", type(e).__name__, str(e)[:200])

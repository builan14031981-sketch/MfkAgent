"""查 chat 303 当前状态 + provider 配置"""
import sqlite3

DB = r"e:\智慧项目\Mfkagent\backend\mfkagent.db"
c = sqlite3.connect(DB)
c.row_factory = sqlite3.Row

chat = c.execute("SELECT id, model, project_id, project_path, agent_id, mode FROM chats WHERE id=303").fetchone()
print("=== Chat 303 ===")
for k in chat.keys():
    print(f"  {k}: {chat[k]}")

print("\n=== Provider keys ===")
keys = ["deepseek_api_key", "qwen_api_key", "glm_api_key", "siliconflow_api_key", "mimo_api_key", "qwen_base_url"]
for k in keys:
    r = c.execute("SELECT value FROM settings WHERE key=?", (k,)).fetchone()
    print(f"  {k}: {'SET' if r and r['value'] else 'NOT SET'}")

print("\n=== provider_disabled / enabled_models ===")
for k in ["provider_disabled", "enabled_models"]:
    r = c.execute("SELECT value FROM settings WHERE key=?", (k,)).fetchone()
    if r:
        print(f"  {k}: {r['value']}")
c.close()

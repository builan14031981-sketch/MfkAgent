"""查 chat 303 最近消息，判断 Agent 是否调用工具"""
import sqlite3
import json

DB = r"e:\智慧项目\Mfkagent\backend\mfkagent.db"
c = sqlite3.connect(DB)
c.row_factory = sqlite3.Row

rows = c.execute(
    "SELECT id, role, content, tool_calls, created_at FROM messages "
    "WHERE chat_id=303 ORDER BY id DESC LIMIT 8"
).fetchall()
for r in reversed(rows):
    content = (r['content'] or '')[:500]
    tc = r['tool_calls']
    print(f"[{r['id']}] {r['role']} @ {r['created_at']}")
    if content:
        print(f"   content: {content}")
    if tc:
        try:
            calls = json.loads(tc) if isinstance(tc, str) else tc
            for t in calls[:10]:
                name = t.get('function', {}).get('name') if isinstance(t, dict) else None
                args = (t.get('function', {}).get('arguments', '') if isinstance(t, dict) else '')[:200]
                print(f"   TOOL_CALL: {name} args={args}")
        except Exception as e:
            print(f"   tool_calls raw: {tc[:300]} (err {e})")
    print()
c.close()

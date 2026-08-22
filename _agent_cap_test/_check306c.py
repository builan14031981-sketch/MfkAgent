import sqlite3
db = sqlite3.connect(r'E:/智慧项目/Mfkagent/backend/mfkagent.db')
db.row_factory = sqlite3.Row
print('=== chat 306 完整配置 ===')
for r in db.execute("SELECT id, agent_id, model, mode, thinking_mode, personality_level FROM chats WHERE id=306"):
    print(dict(r))

import sqlite3
import sys
sys.path.insert(0, '.')

print("=== 数据库中的 Agent 列表 ===")
conn = sqlite3.connect('mfkagent.db')
cur = conn.cursor()
cur.execute('SELECT id, name, persona_id, description FROM agents')
for row in cur.fetchall():
    desc = str(row[3])[:50] if row[3] else '(none)'
    print(f"  id={row[0]}, name={row[1]}, persona={row[2]}, desc={desc}")
conn.close()

print()
print("=== character_presets.py 中的预设 ===")
from app.core.character_presets import CHARACTER_PRESETS
for pid, preset in CHARACTER_PRESETS.items():
    print(f"  {pid}: {preset.name} - {preset.description}")

print()
print("=== PersonaTemplate 列表 ===")
conn = sqlite3.connect('mfkagent.db')
cur = conn.cursor()
cur.execute('SELECT template_id, name FROM persona_templates')
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]}")
conn.close()

print()
print("=== AGENT_QUIRKS 注册的 agent ===")
from app.core.persona_quirks import AGENT_QUIRKS
for aid in AGENT_QUIRKS.keys():
    print(f"  {aid}")

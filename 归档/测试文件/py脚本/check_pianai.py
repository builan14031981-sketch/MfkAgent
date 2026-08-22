import sqlite3

conn = sqlite3.connect('mfkagent.db')
cur = conn.cursor()

# 查看偏爱 Agent 配置
cur.execute("""
    SELECT agent_id, name, identity, default_personality_level, expression_profile, capabilities 
    FROM agents 
    WHERE agent_id LIKE '%pianai%' OR name LIKE '%偏爱%' OR agent_id LIKE '%Pianai%'
""")

rows = cur.fetchall()
for r in rows:
    print('ID:', r[0])
    print('Name:', r[1])
    print('Personality:', r[3])
    print('Expression:', r[4])
    print('Caps:', r[5])
    print('Identity (前200字):', str(r[2])[:200] if r[2] else None)
    print('---')

conn.close()

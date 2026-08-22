import sqlite3, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
conn = sqlite3.connect('backend/mfkagent.db')
c = conn.cursor()

print("=== agents.pianai ===")
c.execute("SELECT agent_id, expression_profile, default_personality_level, length(identity) FROM agents WHERE agent_id='pianai'")
print(c.fetchone())

print("\n=== persona_templates.pianai ===")
c.execute("SELECT agent_id, personality_traits, communication_style, behavior_rules, expression_preferences FROM persona_templates WHERE agent_id='pianai'")
print(c.fetchone())

print("\n=== expression_knowledge natural_companion ===")
c.execute("SELECT profile_id, name, custom_prompt_fragment IS NOT NULL FROM expression_knowledge WHERE profile_id='natural_companion'")
print(c.fetchone())

print("\n=== memory_items pianai (agent scope) ===")
c.execute("SELECT id, scope, agent_id, memory_type, confidence FROM memory_items WHERE agent_id='pianai' ORDER BY id")
for r in c.fetchall():
    print(r)

print("\n=== memory_items warm (other agent, isolation check) ===")
c.execute("SELECT id, scope, agent_id FROM memory_items WHERE agent_id='warm'")
for r in c.fetchall():
    print(r)

conn.close()
print("\nAll checks done.")
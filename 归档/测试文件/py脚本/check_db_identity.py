import sqlite3
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

conn = sqlite3.connect('backend/mfkagent.db')
cur = conn.cursor()

cur.execute("SELECT identity FROM agents WHERE agent_id = 'pianai'")
row = cur.fetchone()
identity = row[0]

# Check for action-related content
if '（想了一下）' in identity:
    print("DB contains V8 pattern: （想了一下）")
if '禁止' in identity:
    print("DB contains V8/V9 pattern: 禁止")
if '舞台' in identity:
    print("DB contains V9 pattern: 舞台")
if '匹配' in identity:
    print("DB contains V10 pattern: 匹配")
if '关系' in identity:
    print("DB contains relationship keyword")

print(f"\nTotal length: {len(identity)}")
print(f"\nFirst 500 chars:\n{identity[:500]}")
print(f"\nLast 300 chars:\n{identity[-300:]}")

conn.close()

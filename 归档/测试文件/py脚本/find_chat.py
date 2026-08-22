import sqlite3
import json

# Connect to the actual database used by the backend
# Let's find the right database
import os

# Check if there's a database in backend directory
db_path = None
for root, dirs, files in os.walk('backend'):
    for f in files:
        if f.endswith('.db') or f == 'mfkagent.db':
            db_path = os.path.join(root, f)
            print(f'Found DB: {db_path}')
            
# Also check parent directory
if os.path.exists('../mfkagent.db'):
    print(f'Parent DB: {os.path.getsize("../mfkagent.db")} bytes')
    
# Check main db location
if os.path.exists('mfkagent.db'):
    size = os.path.getsize('mfkagent.db')
    print(f'Local DB: {size} bytes')
    if size > 0:
        db_path = 'mfkagent.db'

if db_path and os.path.getsize(db_path) > 0:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # Check latest messages
    cur.execute("""
        SELECT id, chat_id, role, content, created_at 
        FROM messages 
        WHERE chat_id = 141 
        ORDER BY id DESC 
        LIMIT 20
    """)
    rows = cur.fetchall()
    for r in rows:
        print(f'\n[{r[2]}] #{r[0]} @ {r[4]}')
        print(r[3][:500] if r[3] else '(empty)')
    
    conn.close()
else:
    print('No non-empty database found')
    # Try to find any .db files
    for root, dirs, files in os.walk('.'):
        for f in files:
            if f.endswith('.db'):
                full = os.path.join(root, f)
                print(f'DB: {full} ({os.path.getsize(full)} bytes)')

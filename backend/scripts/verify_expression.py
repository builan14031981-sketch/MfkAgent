"""验证 Expression Profile V1 数据库写入结果。"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "mfkagent.db")

def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("=" * 60)
    print("ExpressionKnowledge 表")
    print("=" * 60)
    cursor.execute("""
        SELECT profile_id, name, emoji_usage, kaomoji_usage, markdown_usage,
               response_length, humor_level, proactive_level, emotional_expression,
               colloquial_level, internet_slang, pause_frequency
        FROM expression_knowledge
        ORDER BY id
    """)
    rows = cursor.fetchall()
    for row in rows:
        print(f"\nProfile: {row[0]} ({row[1]})")
        print(f"  emoji={row[2]}, kaomoji={row[3]}, markdown={row[4]}")
        print(f"  response_length={row[5]}, humor={row[6]}, proactive={row[7]}, emotional={row[8]}")
        print(f"  colloquial={row[9]}, slang={row[10]}, pause={row[11]}")

    print("\n" + "=" * 60)
    print("Agent → expression_profile 映射")
    print("=" * 60)
    cursor.execute("""
        SELECT agent_id, name, expression_profile
        FROM agents
        WHERE status = 'active'
        ORDER BY id
    """)
    rows = cursor.fetchall()
    for row in rows:
        print(f"  {row[0]:20s} {row[1]:10s} → {row[2]}")

    conn.close()

if __name__ == "__main__":
    main()

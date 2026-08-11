"""为 expression_knowledge 表补齐 V1 新增字段。"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "mfkagent.db")

def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 检查现有列
    cursor.execute("PRAGMA table_info(expression_knowledge)")
    cols = [row[1] for row in cursor.fetchall()]
    print("Existing columns:", cols)

    # 添加缺失列
    new_cols = [
        ("response_length", "FLOAT DEFAULT 0.5"),
        ("humor_level", "FLOAT DEFAULT 0.3"),
        ("proactive_level", "FLOAT DEFAULT 0.5"),
        ("emotional_expression", "FLOAT DEFAULT 0.5"),
    ]
    for col_name, col_type in new_cols:
        if col_name not in cols:
            cursor.execute(f"ALTER TABLE expression_knowledge ADD COLUMN {col_name} {col_type}")
            print(f"Added column: {col_name}")
        else:
            print(f"Column already exists: {col_name}")

    conn.commit()
    conn.close()
    print("Done.")

if __name__ == "__main__":
    main()

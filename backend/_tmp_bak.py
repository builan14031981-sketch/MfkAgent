import glob
import os
import sqlite3

# 查备份库里是否有 glm-4.7 记录（provider=qwen）
print("=== 备份库中 glm-4.7 相关记录 ===")
for bak in glob.glob(r"e:\智慧项目\Mfkagent\Mfkagent_backups\**\*.db", recursive=True):
    try:
        db = sqlite3.connect(bak)
        db.row_factory = sqlite3.Row
        rows = db.execute(
            "select id, model_id, name, provider, enabled, source from models "
            "where model_id like 'glm-4.7%' or model_id like 'glm-4.7-flash%'"
        ).fetchall()
        for r in rows:
            print(f"  [{os.path.basename(bak)}] {dict(r)}")
        db.close()
    except Exception as e:
        print(f"  [{os.path.basename(bak)}] ERR {e}")

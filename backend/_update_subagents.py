import json
import sys

sys.path.insert(0, ".")
from app.core.database import SessionLocal

RULE = (
    "\n\n【硬性交付规则】每次 write_file 写文件后，必须调用 verify_spec 对写出的文件"
    "执行规格断言校验：SPEC_CHECK_RESULT 必须为 PASS 才可回报成功；若为 FAIL，"
    "必须修复文件后重新校验直到 PASS。禁止在未通过机器校验时宣称已按规格完成。"
    "校验的断言必须在任务描述中给出（pattern/expect 逐条）。"
)

db = SessionLocal()
for aid in ("sub_frontend", "sub_backend"):
    ag = db.execute(
        "SELECT id FROM agents WHERE agent_id = :a", {"a": aid}
    ).fetchone()
    if not ag:
        print("missing", aid)
        continue
    row = db.execute(
        "SELECT allowed_tools, identity FROM agents WHERE id = :i", {"i": ag[0]}
    ).fetchone()
    allowed = json.loads(row[0]) if row[0] else []
    if "verify_spec" not in allowed:
        allowed.append("verify_spec")
    identity = (row[1] or "")
    if "verify_spec" not in identity:
        identity += RULE
    db.execute(
        "UPDATE agents SET allowed_tools = :t, identity = :i WHERE id = :id",
        {"t": json.dumps(allowed, ensure_ascii=False), "i": identity, "id": ag[0]},
    )
    print("updated", aid, "| tools:", allowed)
db.commit()
db.close()
print("done")
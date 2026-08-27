import os
import sys
from pathlib import Path

# 添加 backend 目录到 sys.path
backend_dir = Path(__file__).parent.parent
sys.path.append(str(backend_dir))

from app.core.database import SessionLocal
from app.models.agent import CustomModel
from app.core.model_adapter import _infer_context_window

def main():
    db = SessionLocal()
    try:
        models = db.query(CustomModel).all()
        updated_count = 0
        for m in models:
            # 如果是旧的默认值(200000)，或者是兜底的256000，或者是0，我们就洗一遍数据
            if m.context_window in [200000, 256000, 0, None]:
                new_ctx = _infer_context_window(m.model_name)
                if new_ctx != m.context_window:
                    print(f"Updating {m.model_name}: {m.context_window} -> {new_ctx}")
                    m.context_window = new_ctx
                    updated_count += 1
                    
        db.commit()
        print(f"✅ Successfully updated {updated_count} custom models' context window in database.")
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    main()

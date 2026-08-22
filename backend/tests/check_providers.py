import sys
sys.stdout.reconfigure(encoding='utf-8')
from app.core.database import SessionLocal
from app.models.agent import Setting

db = SessionLocal()

# 检查 provider 启用状态
for key in ['provider_enabled_deepseek', 'provider_enabled_qwen', 'provider_enabled_freellmapi', 'provider_enabled_google', 'provider_enabled_glm']:
    s = db.query(Setting).filter(Setting.key == key).first()
    val = s.value if s else 'not set'
    print(f'{key}: {val}')

print()
# 检查 api key 设置
for key in ['api_key_deepseek', 'api_key_qwen', 'api_key_freellmapi', 'api_key_google']:
    s = db.query(Setting).filter(Setting.key == key).first()
    has_key = bool(s and s.value)
    print(f'{key}: {"SET" if has_key else "EMPTY"}')

db.close()

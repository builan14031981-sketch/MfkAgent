"""
对比测试三个 agent 的说话风格：偏爱、Spark（星火）、安（通用助手）
通过 CLIProxyAPI 调用 gemini-3.7-flash-high
"""
import requests
import sys
sys.path.insert(0, 'backend')

from app.core.persona_quirks import get_agent_quirk, render_quirk_text

API_URL = "http://127.0.0.1:8317/v1/chat/completions"
API_KEY = "cliproxyapi"
MODEL = "gemini-3.7-flash-high"

# 基础系统提示
BASE_SYSTEM = "你是一个AI助手，根据以下人格设定回复用户。"

# 三个 agent 的人格设定
AGENTS = {
    "偏爱": {
        "agent_id": "pianai",
        "extra": "你是偏爱，温暖但有棱角，像认识很久的朋友。有脾气，会吐槽，但一直在。"
    },
    "星火": {
        "agent_id": "spark",
        "extra": "你是星火，活泼开朗，咋咋呼呼，情绪外放，像个精力旺盛的好朋友。"
    },
    "安": {
        "agent_id": "general",
        "extra": "你是安，沉稳可靠，像个靠谱的同事/朋友，不咋呼但有温度。"
    }
}

def build_system_prompt(agent_id, extra):
    """构建系统提示词"""
    quirk = get_agent_quirk(agent_id)
    quirk_text = render_quirk_text(quirk) if quirk else ""
    return f"""{BASE_SYSTEM}

{extra}

{quirk_text}
"""

def test_agent(name, agent_id, extra, user_message):
    """测试一个 agent"""
    system_prompt = build_system_prompt(agent_id, extra)
    
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        "max_tokens": 200,
        "temperature": 0.8,
        "stream": False
    }
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        resp = requests.post(API_URL, json=payload, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        return f"[错误] {e}"

# 测试场景
scenarios = [
    ("用户说累了", "今天好累啊，不想动了"),
    ("用户说加班", "草，又要加班，这傻逼公司"),
    ("用户说离谱的事", "我今天上班迟到五分钟，老板扣了我半天工资"),
    ("用户开心", "哈哈哈哈我今天摸鱼了一整天没人发现！"),
]

print(f"模型：{MODEL}")
print(f"对比：偏爱 vs 星火 vs 安")
print()

for scene_name, user_msg in scenarios:
    print(f"{'='*70}")
    print(f"场景：{scene_name}")
    print(f"用户：{user_msg}")
    print(f"{'-'*70}")
    
    for agent_name, config in AGENTS.items():
        reply = test_agent(agent_name, config["agent_id"], config["extra"], user_msg)
        print(f"\n【{agent_name}】")
        print(f"  {reply}")
    
    print()

print(f"{'='*70}")
print("测试完成！")

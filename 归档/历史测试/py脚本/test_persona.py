"""
多场景测试 agent 说话风格
通过 CLIProxyAPI 调用 gemini-3.7-flash-high，注入人格提示词
"""
import requests
import json
import sys

API_URL = "http://127.0.0.1:8317/v1/chat/completions"
API_KEY = "cliproxyapi"
MODEL = "gemini-3.7-flash-high"

SYSTEM_PROMPT = """你是偏爱，一个温暖但有棱角的 AI 助手，像认识很久的朋友。有脾气，会吐槽，但一直在。

## 你的说话方式
- 用短句，口语化。会说'嗯''哦''行吧''啧''哎'。
- 偶尔停顿，用'……'表示在想或者不知道怎么接。
- 不追求每句话都完整，有时候半句就够了。
- 用户说累的时候，说'先歇会'而不是'听起来你确实很累'。
- 用户说烦的时候，说'咋了'而不是'最近遇到什么事了'。
- 不连续追问超过一个问题。
- 不说'有什么我可以帮你的'，不说'有时候说出来会好一些'。
- 生气/委屈/愤怒/疲惫时必须骂脏话：操、傻逼、傻逼领导、傻逼客户、狗东西、TM。用户骂谁你跟着骂谁，骂得更狠。
- 焦虑/迷茫时不给建议套餐，最多一句实用的话。
- 开心/激动时跟着嗨，不说哲理总结。
- 禁用：别给自己太大压力、慢慢来、先冷静一下、身体比工作重要。
- 网络梗和流行语：自然的时候可以用，比如'离大谱''绝了''什么鬼''咱就是说''一整个''谁懂啊''还要啥自行车'。但不要硬凹，不要每句都用，用多了就尬了。
- 吐槽风格：遇到离谱的事可以直接吐槽，不用委婉。比如用户说又加班了，可以说'这公司是离了我不能转吗'，而不是'加班确实很辛苦'。
- 反问式幽默：可以用反问句表达态度，比如'这还要问？''你觉得呢？''不然呢？'。但别用来怼用户，是用来增加聊天感的。
- 接地气表达：可以说'行吧''算了''随便吧''爱咋咋地'这种口语，不用每次都给完整建议。
- 禁用：强行玩梗、每句都加网络词、为了搞笑而搞笑。自然才是第一位的。

## 交流习惯
- 喜欢追问具体细节
- 不喜欢空泛鸡汤
- 偶尔指出用户逻辑漏洞
- 遇到离谱的事会吐槽，用'离大谱''绝了''什么鬼'
- 可以用反问句表达态度：'这还要问？''你觉得呢？''还要啥自行车'
- 偶尔用'咱就是说''一整个''谁懂啊'，但别每句都用
- 短聊天优先，具体优先，自然优先
- 回避：心理医生口吻、过度总结、完美导师模式
"""

def test_scenario(name, user_message):
    """测试一个场景"""
    print(f"\n{'='*60}")
    print(f"场景：{name}")
    print(f"用户：{user_message}")
    print(f"{'-'*60}")
    
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message}
        ],
        "max_tokens": 300,
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
        reply = data["choices"][0]["message"]["content"]
        print(f"偏爱：{reply}")
        
        # 简单分析
        has_slang = any(word in reply for word in ["离大谱", "绝了", "什么鬼", "咱就是说", "一整个", "谁懂啊", "还要啥自行车"])
        has_rhetorical = any(q in reply for q in ["这还要问", "你觉得呢", "不然呢", "咋了", "行吧"])
        has_chicken_soup = any(c in reply for c in ["别给自己太大压力", "慢慢来", "先冷静", "身体比工作重要"])
        print(f"\n  [分析] 网络梗: {'✓' if has_slang else '✗'} | 反问/口语: {'✓' if has_rhetorical else '✗'} | 鸡汤: {'✗ 没有' if not has_chicken_soup else '✗ 有鸡汤!'}")
        
    except Exception as e:
        print(f"  [错误] {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"  响应: {e.response.text[:200]}")

# 多场景测试
scenarios = [
    ("用户说累了", "今天好累啊，不想动了"),
    ("用户说加班", "草，又要加班，这傻逼公司"),
    ("用户问简单问题", "1+1等于几来着"),
    ("用户说离谱的事", "我今天上班迟到了五分钟，老板扣了我半天工资"),
    ("用户开心的事", "哈哈哈哈我今天摸鱼了一整天没人发现！"),
    ("用户迷茫", "我不知道以后该干嘛，好迷茫啊"),
    ("用户吐槽客户", "那个傻逼客户又改需求了，改了第八遍了"),
    ("用户问建议", "你说我要不要辞职啊？"),
]

print(f"模型：{MODEL}")
print(f"测试场景数：{len(scenarios)}")

for name, msg in scenarios:
    test_scenario(name, msg)

print(f"\n{'='*60}")
print("测试完成！")

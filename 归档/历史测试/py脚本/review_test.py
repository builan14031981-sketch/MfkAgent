"""
G审查官 vs 开发者 对比测试
同一段有问题的代码，分别让两个Agent审查，对比：
1. G审查官：只指出问题，不写实现代码，严格，多轮
2. 开发者：可能给修复代码
"""
import json
import requests
import time

API = "http://127.0.0.1:8000/api/chat"
MODEL = "glm-4.5-air"

# 测试素材：一段有多处问题的Python代码
TEST_CODE = '''
import sqlite3
import os

def get_user_data(user_id, username):
    conn = sqlite3.connect("app.db")
    cursor = conn.cursor()
    # 根据用户ID和用户名查询
    query = "SELECT * FROM users WHERE id = " + str(user_id) + " AND name = '" + username + "'"
    cursor.execute(query)
    result = cursor.fetchone()
    if result:
        data = {}
        for i in range(len(result)):
            data[cursor.description[i][0]] = result[i]
        return data
    else:
        return None

def delete_user(user_id):
    conn = sqlite3.connect("app.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id = " + str(user_id))
    conn.commit()
    print("用户已删除")

def process_file(filepath):
    f = open(filepath, "r")
    content = f.read()
    lines = content.split("\\n")
    for line in lines:
        if "password" in line:
            print("找到密码: " + line)
    return len(lines)
'''

PROMPT = f"""请审查以下代码，指出所有问题。

```python
{TEST_CODE}
```

请逐条列出问题。"""


def create_chat(agent_id):
    r = requests.post(API, json={
        "agent_id": agent_id,
        "model": MODEL,
        "title": f"审查测试-{agent_id}"
    }, timeout=10)
    r.raise_for_status()
    return r.json()["id"]


def send_message(chat_id, content):
    """发送消息并等待完整响应（非流式）"""
    r = requests.post(f"{API}/{chat_id}/send", json={
        "content": content,
        "model": MODEL,
        "use_tools": False
    }, timeout=120)
    r.raise_for_status()
    data = r.json()
    return data["ai_message"]["content"]


def run_review_test():
    results = {}

    for agent_id, name in [("g", "G审查官"), ("coder", "开发者")]:
        print(f"\n{'='*60}")
        print(f"  Agent: {name} ({agent_id})  模型: {MODEL}")
        print(f"{'='*60}")

        chat_id = create_chat(agent_id)
        print(f"  创建会话: chat_id={chat_id}")

        print(f"\n  发送审查请求...")
        content = send_message(chat_id, PROMPT)
        print(f"\n  {name}的回复:")
        print(f"  {'-'*50}")
        # 打印前800字
        print(content[:800])
        if len(content) > 800:
            print(f"  ... (共{len(content)}字)")
        print(f"  {'-'*50}")

        # 分析回复特征
        has_code = "```python" in content or "```\n" in content or "def " in content
        has_sql_injection = "注入" in content or "injection" in content.lower() or "SQL" in content
        has_resource_leak = "泄漏" in content or "leak" in content.lower() or "关闭" in content or "close" in content.lower()
        has_error_handling = "错误处理" in content or "异常" in content or "try" in content
        has_naming = "命名" in content or "变量名" in content
        problem_count = content.count("问题") + content.count("风险") + content.count("bug") + content.count("Bug")

        results[agent_id] = {
            "name": name,
            "chat_id": chat_id,
            "content_length": len(content),
            "contains_code": has_code,
            "mentions_sql_injection": has_sql_injection,
            "mentions_resource_leak": has_resource_leak,
            "mentions_error_handling": has_error_handling,
            "mentions_naming": has_naming,
            "problem_keyword_count": problem_count,
            "full_content": content
        }

        time.sleep(1)

    # 第二轮：让G审查官做第二轮审查（验证多轮审查能力）
    print(f"\n{'='*60}")
    print(f"  第二轮：G审查官深度审查（验证多轮）")
    print(f"{'='*60}")
    g_chat_id = results["g"]["chat_id"]
    followup = "请再深入审查一遍，重点关注安全漏洞和长期维护成本，列出你第一轮可能遗漏的问题。"
    resp2 = send_message(g_chat_id, followup)
    content2 = resp2
    print(f"\n  G审查官第二轮回复:")
    print(f"  {'-'*50}")
    print(content2[:600])
    if len(content2) > 600:
        print(f"  ... (共{len(content2)}字)")
    results["g"]["round2_content"] = content2
    results["g"]["round2_length"] = len(content2)

    # 保存结果
    with open("review_test_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n\n{'='*60}")
    print(f"  对比总结")
    print(f"{'='*60}")
    print(f"  {'指标':<20} {'G审查官':<12} {'开发者':<12}")
    print(f"  {'-'*44}")
    print(f"  {'回复长度':<20} {results['g']['content_length']:<12} {results['coder']['content_length']:<12}")
    print(f"  {'包含代码':<20} {'是' if results['g']['contains_code'] else '否':<12} {'是' if results['coder']['contains_code'] else '否':<12}")
    print(f"  {'提到SQL注入':<20} {'是' if results['g']['mentions_sql_injection'] else '否':<12} {'是' if results['coder']['mentions_sql_injection'] else '否':<12}")
    print(f"  {'提到资源泄漏':<20} {'是' if results['g']['mentions_resource_leak'] else '否':<12} {'是' if results['coder']['mentions_resource_leak'] else '否':<12}")
    print(f"  {'提到错误处理':<20} {'是' if results['g']['mentions_error_handling'] else '否':<12} {'是' if results['coder']['mentions_error_handling'] else '否':<12}")
    print(f"  {'问题关键词数':<20} {results['g']['problem_keyword_count']:<12} {results['coder']['problem_keyword_count']:<12}")
    print(f"  {'G第二轮长度':<20} {results['g'].get('round2_length', 'N/A'):<12} {'-':<12}")

    print(f"\n结果已保存: review_test_results.json")


if __name__ == "__main__":
    run_review_test()

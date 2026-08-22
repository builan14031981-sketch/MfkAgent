# -*- coding: utf-8 -*-
"""替换 seed_agents.py 中听澜(writer_jiangnan)的 identity 块"""
import re

SEED_FILE = r'E:\智慧项目\Mfkagent\backend\seed_agents.py'
PROMPT_FILE = r'E:\智慧项目\Mfkagent\写作测试\_new_tinglan_prompt.txt'

# 读取新提示词
with open(PROMPT_FILE, 'r', encoding='utf-8') as f:
    prompt_text = f.read()

# 去掉末尾多余换行
prompt_text = prompt_text.rstrip('\n')

# 转换为 Python 字符串拼接格式
lines = prompt_text.split('\n')
py_lines = []
for i, line in enumerate(lines):
    # 转义双引号
    escaped = line.replace('\\', '\\\\').replace('"', '\\"')
    if i < len(lines) - 1:
        py_lines.append(f'            "{escaped}\\n"')
    else:
        py_lines.append(f'            "{escaped}"')

identity_block = '        "identity": (\n' + '\n'.join(py_lines) + '\n        ),'

print(f"新 identity 块行数: {len(py_lines)}")
print(f"新 identity 块字符数(预估): {len(prompt_text)}")

# 读取 seed_agents.py
with open(SEED_FILE, 'r', encoding='utf-8') as f:
    content = f.read()

# 定位听澜的 identity 块
# 1. 找到 writer_jiangnan
agent_idx = content.find('"agent_id": "writer_jiangnan"')
if agent_idx == -1:
    print("ERROR: 未找到 writer_jiangnan")
    exit(1)

# 2. 从 agent_idx 往后找 "identity": (
identity_start = content.find('"identity": (', agent_idx)
if identity_start == -1:
    print("ERROR: 未找到 identity 字段起始")
    exit(1)

# 找到行首（往前找到换行）
line_start = content.rfind('\n', 0, identity_start) + 1

# 3. 找到匹配的 ), 
# identity 块内没有嵌套括号，找下一个独立的 ),
# 模式：换行 + 8空格 + ),
pattern = re.compile(r'\n        \),')
m = pattern.search(content, identity_start)
if not m:
    print("ERROR: 未找到 identity 块结束")
    exit(1)

block_end = m.end()  # 包含 ),

old_block = content[line_start:block_end]
print(f"\n旧 identity 块长度: {len(old_block)} 字符")
print(f"旧块前50字: {old_block[:50]!r}")
print(f"旧块后50字: {old_block[-50:]!r}")

# 替换
new_content = content[:line_start] + identity_block + content[block_end:]

# 写回
with open(SEED_FILE, 'w', encoding='utf-8') as f:
    f.write(new_content)

print(f"\n✅ 已替换 seed_agents.py 中听澜的 identity 块")
print(f"文件总长度变化: {len(content)} -> {len(new_content)}")

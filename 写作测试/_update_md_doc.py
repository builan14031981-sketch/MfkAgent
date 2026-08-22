# -*- coding: utf-8 -*-
"""替换 md 文档中听澜的 identity 部分"""

MD_FILE = r'E:\智慧项目\Mfkagent\写作测试\听澜_完整系统提示词_20260820.md'
PROMPT_FILE = r'E:\智慧项目\Mfkagent\写作测试\_new_tinglan_prompt.txt'

# 读取新提示词
with open(PROMPT_FILE, 'r', encoding='utf-8') as f:
    new_identity = f.read().rstrip('\n')

# 读取 md 文件
with open(MD_FILE, 'r', encoding='utf-8') as f:
    content = f.read()

# 定位 identity 部分
# 起始：听澜 identity 开头
start_marker = '你是 MfkAgent 的写作引擎「听澜」'
start_idx = content.find(start_marker)
if start_idx == -1:
    print("ERROR: 未找到听澜 identity 起始")
    exit(1)

# 结束：identity 部分之后是 "## 能力倾向"
end_marker = '## 能力倾向'
end_idx = content.find(end_marker, start_idx)
if end_idx == -1:
    print("ERROR: 未找到 identity 结束标记（## 能力倾向）")
    exit(1)

# 找到 end_marker 前的空行
# end_idx 指向 '## 能力倾向'，我们需要保留前面的空行结构
# 原结构：identity内容\n\n## 能力倾向
# 替换为：new_identity\n\n## 能力倾向

old_section = content[start_idx:end_idx]
print(f"旧 identity 部分长度: {len(old_section)} 字符")
print(f"旧部分前60字: {old_section[:60]!r}")
print(f"旧部分后60字: {old_section[-60:]!r}")

# 替换
new_content = content[:start_idx] + new_identity + '\n\n' + content[end_idx:]

# 更新头部元信息中的长度
# 原：> 完整提示词长度: 8688 字符
import re
new_total_len = len(new_content)
content_with_len = re.sub(
    r'> 完整提示词长度: \d+ 字符',
    f'> 完整提示词长度: {new_total_len} 字符',
    new_content
)

# 写回
with open(MD_FILE, 'w', encoding='utf-8') as f:
    f.write(content_with_len)

print(f"\n✅ 已更新 md 文档")
print(f"文件总长度: {len(content)} -> {len(content_with_len)}")
print(f"新 identity 长度: {len(new_identity)} 字符")

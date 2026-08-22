# -*- coding: utf-8 -*-
file = r'E:\智慧项目\Mfkagent\backend\seed_agents.py'
with open(file, 'r', encoding='utf-8') as f:
    lines = f.readlines()

fixed = 0
for i, line in enumerate(lines):
    stripped = line.lstrip()
    if stripped.startswith('"- 【') and not line.startswith('            '):
        lines[i] = '            ' + stripped
        fixed += 1

with open(file, 'w', encoding='utf-8') as f:
    f.writelines(lines)

print(f'Fixed {fixed} lines indentation')

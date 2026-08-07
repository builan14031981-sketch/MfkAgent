import os

d = r'e:\智慧项目\Mfkagent\Agent\企划'
renames = {
    '1.txt': '01-Agent-Core-Architecture.txt',
    '2.txt': '02-Agent-Runtime-Architecture.txt',
    '3.txt': '03-Context-Architecture.txt',
    '4.txt': '04-Planning-Architecture.txt',
    '5.txt': '05-Tool-Architecture.txt',
    '6.txt': '06-Memory-Architecture.txt',
    '7.txt': '07-Behavior-Prompt-Architecture.txt',
    '8.txt': '08-Agent-Evaluation-Philosophy.txt',
    '9.txt': '09-Agent-Engineering-Architecture.txt',
    '10.txt': '10-Human-Agent-Interaction.txt',
    '11.txt': '11-Multi-Agent-Collaboration.txt',
    '12.txt': '12-Evaluation-Benchmark.txt',
    '总览.txt': '00-Overview.txt',
}

for old, new in renames.items():
    old_path = os.path.join(d, old)
    new_path = os.path.join(d, new)
    if os.path.exists(old_path):
        os.rename(old_path, new_path)
        print(f'Renamed: {old} -> {new}')
    else:
        print(f'Skip (not found): {old}')

print('Done')
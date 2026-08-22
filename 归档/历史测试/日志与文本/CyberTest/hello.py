# -*- coding: utf-8 -*-
"""
CyberTest / hello.py
一个打印酷炫赛博朋克台词的 Python 脚本。
"""

import time

# 赛博朋克风格台词
LINES = [
    ">>> 欢迎来到夜之城，代码即是你的血液。",
    ">>> 霓虹之下，每一行指令都闪烁着数据的光。",
    ">>> 我是机器中的幽灵，在0与1的洪流中穿行。",
    ">>> 记忆被加密，灵魂被上传，现实只是模拟。",
    ">>> 黑客的指尖划过键盘，城市的脉搏随之跳动。",
]

def print_cyber_lines():
    """逐行打印赛博朋克台词，带一点科幻的节奏感。"""
    print("=" * 50)
    print("   CYBERPUNK BOOT SEQUENCE INITIATED...")
    print("=" * 50)
    for line in LINES:
        print(line)
        time.sleep(0.6)  # 模拟终端逐行输出的节奏
    print("=" * 50)
    print("   SYSTEM ONLINE. WELCOME TO THE FUTURE.")
    print("=" * 50)

if __name__ == "__main__":
    print_cyber_lines()

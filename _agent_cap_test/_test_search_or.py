# -*- coding: utf-8 -*-
"""验证 search_files 支持 `|` 多关键词。"""
import sys
import os

sys.path.insert(0, r"e:\智慧项目\Mfkagent\backend")
os.chdir(r"e:\智慧项目\Mfkagent\backend")

from app.core.search_tools import search_files  # noqa: E402

PROJECT = r"e:\智慧项目\Mfkagent"


def main():
    # 用 `|` 多关键词在 frontend/src 下搜索
    r1 = search_files(PROJECT, "security|安全", "frontend/src")
    print("=== query='security|安全' relative='frontend/src' ===")
    print(r1[:600])
    print()
    # 对照：单关键词
    r2 = search_files(PROJECT, "security", "frontend/src/components")
    print("=== query='security' relative='frontend/src/components' ===")
    print(r2[:400])


if __name__ == "__main__":
    main()

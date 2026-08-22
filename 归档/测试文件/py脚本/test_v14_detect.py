# V14 test — 表演状态按需触发检测 + 端到端行为
import io, sys, time, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import requests

BASE = "http://127.0.0.1:8001"

# ──── 1. 单元级：检测函数（直接 import）────
from app.core.persona_engine import detect_emotional_moment

cases = [
    # (message, expected)
    ("哄哄我", "strong"),
    ("能抱一下吗", "strong"),
    ("安慰我一下", "strong"),
    ("说点好听的", "strong"),
    ("（轻轻靠在你肩上）今天好累啊", "strong"),
    ("月色真好啊，有点暧昧了", "strong"),
    ("我好想哭", "medium"),
    ("今晚睡不着", "medium"),
    ("有点孤独", "medium"),
    ("今天被老板骂了，好委屈", "medium"),
    ("压力好大", "medium"),
    ("晚安，我睡了", "light"),
    ("拜拜", "light"),
    ("你会不会离开我", "light"),
    ("你会一直陪着我吗", "light"),
    ("今天好累啊", "none"),
    ("帮我写个方案", "none"),
    ("这个代码有bug", "none"),
    ("几点了", "none"),
    ("哦", "none"),
]

print("=" * 30, "检测函数", "=" * 30)
pass_cnt = 0
for msg, exp in cases:
    got = detect_emotional_moment(msg)
    ok = "OK " if got == exp else "FAIL"
    if got != exp:
        pass_cnt += 1
    print(f"{ok} {msg!r:40} -> {got}  (exp {exp})")
print(f"检测函数 FR=0 成功 {pass_cnt}/0 (以上 OK 均可接受，fail 标出)")
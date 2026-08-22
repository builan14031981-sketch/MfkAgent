# V14.1 检测函数单元测试 — 情绪 ≠ 表演
import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, 'backend')
from app.core.persona_engine import detect_user_emotion, detect_performance_intent
from app.core.agent_runtime.action_guard import needs_regeneration, find_action_descriptions

# ──── 1. 触发表（任务给定）────
cases = [
    # (message, 期望 intent, 期望 emotion)
    ("今天好累", "none", "tired"),
    ("最近压力好大", "none", "stressed"),
    ("感觉没人理解我", "empathy", "lonely"),
    ("我想哭", "empathy", "sad"),
    ("哄哄我", "comfort", "neutral"),
    ("抱一下", "comfort", "neutral"),
    ("陪陪我", "comfort", "neutral"),
    ("（抱住你）", "roleplay", "neutral"),
    ("坐在你旁边", "roleplay", "neutral"),
    ("晚安", "light", "neutral"),
]

print("===== 1. 触发表 =====")
pass_cnt = 0
for msg, exp_intent, exp_emo in cases:
    intent = detect_performance_intent(msg)
    emo = detect_user_emotion(msg)
    ok = "OK" if (intent == exp_intent and emo == exp_emo) else "FAIL"
    if ok == "OK":
        pass_cnt += 1
    print(f"{ok} {msg!r:22} intent={intent:8} exp={exp_intent:8} | emo={emo:8} exp={exp_emo}")
print(f"通过 {pass_cnt}/{len(cases)}")

# ──── 2. 工作抑制 ────
work_cases = ["帮我看看这段代码", "这个方案怎么分析", "写个代码修复bug", "评估一下这个项目"]
print("\n===== 2. 工作抑制 =====")
for msg in work_cases:
    intent = detect_performance_intent(msg)
    ok = "OK" if intent == "work" else "FAIL"
    print(f"{ok} {msg!r:24} -> {intent}")

# ──── 3. roleplay 优先级（带括号即 roleplay，即使内容像情绪）────
print("\n===== 3. roleplay/comfort 优先级 =====")
for msg, exp in [
    ("（轻轻抱住你）我今天好难过", "roleplay"),
    ("*靠在你旁边*", "roleplay"),
    ("哄哄我，我好累", "comfort"),
    ("假装你在我身边", "roleplay"),
]:
    intent = detect_performance_intent(msg)
    ok = "OK" if intent == exp else "FAIL"
    print(f"{ok} {msg!r:26} -> {intent}")

# ──── 4. 情绪与表演分离（同情绪，不同意图）────
print("\n===== 4. 情绪≠表演 =====")
for msg, exp in [
    ("好难过", "empathy"),
    ("难过到想哭", "empathy"),
    ("好累", "none"),
    ("今天好烦", "none"),
    ("压力好大", "none"),
]:
    intent = detect_performance_intent(msg)
    ok = "OK" if intent == exp else "FAIL"
    print(f"{ok} {msg!r:22} -> {intent}")

# ──── 5. 输出保护 ────
print("\n===== 5. 输出保护 =====")
guard_cases = [
    # (content, perf_level, 期望是否拦截)
    ("辛苦了，歇会儿吧。要不要喝点水？", "none", False),
    ("（轻轻拍拍你的肩膀）辛苦了", "none", True),
    ("（摸摸你的头）没事的", "none", True),
    ("（叹气）唉，确实是", "none", False),
    ("（无语）这也太夸张了", "none", False),
    ("（轻轻把你揽进怀里）别难过了", "empathy", True),
    ("好，我陪你一会儿（笑了笑）", "comfort", False),  # comfort 不拦截
    ("（走过去抱住你）我在呢", "roleplay", False),      # roleplay 不拦截
    ("明天我把方案发你（这边先这样）", "work", False),  # 普通括号不误伤
    ("（扶额）这件事确实难办", "work", False),          # 文字情绪不拦截
    ("帮你查了下，这个接口返回 200", "none", False),    # 无括号
]
gpass = 0
for content, lvl, exp in guard_cases:
    got = needs_regeneration(lvl, content)
    ok = "OK" if got == exp else "FAIL"
    if got == exp:
        gpass += 1
    hits = find_action_descriptions(content)
    print(f"{ok} [{lvl:8}] {content!r:32} -> intercept={got} exp={exp} hits={hits}")
print(f"通过 {gpass}/{len(guard_cases)}")

# Expression Knowledge V1 — 表达知识库设计方案

## 一、设计目标

建立独立的 Expression Knowledge 模块，为不同 Agent 提供可配置的人类化表达能力。

核心原则：
- 知识不写死在 System Prompt，作为可注入上下文
- 支持不同 Agent 使用不同表达强度
- 不修改现有 Agent 表结构
- 不修改 V1/V2 核心流程

---

## 二、数据结构设计

### 2.1 知识分类（6 大类）

| 分类 | 说明 | 示例 |
|------|------|------|
| emoji_rules | emoji 使用规则 | 场景→允许的 emoji 列表 |
| kaomoji | 颜文字库 | 情绪→颜文字映射 |
| markdown_expressions | Markdown 表达规则 | 加粗/斜体/删除线的使用场景 |
| colloquial_expressions | 口语化表达 | 日常用语、语气词 |
| internet_slang | 网络语言 | 适度使用的网络用语 |
| scene_examples | 场景表达示例 | 不同场景下的参考表达 |

### 2.2 数据结构定义

```python
@dataclass
class ExpressionKnowledge:
    """表达知识库 — 一组可复用的表达规则和素材。"""
    
    # emoji 使用规则
    emoji_rules: dict[str, list[str]]  # {"happy": ["😊", "😂"], "sad": ["😢", "🥲"]}
    
    # 颜文字库
    kaomoji: dict[str, list[str]]       # {"happy": ["(￣▽￣)"], "confused": ["(・_・?)"]}
    
    # Markdown 表达规则
    markdown_rules: dict[str, str]      # {"bold": "用于真正重要内容", "italic": "用于轻微语气"}
    
    # 口语化表达
    colloquial: list[str]                # ["emm", "等等", "真的假的", "啊这"]
    
    # 网络语言（带使用强度标记）
    internet_slang: dict[str, int]      # {"绝绝子": 1, "yyds": 2, "绷不住了": 3}
    
    # 场景表达示例
    scene_examples: dict[str, list[str]]  # {"greeting": ["嗨！", "诶？这么早？"]}
```

### 2.3 表达强度等级

| 等级 | 名称 | emoji 数量 | 颜文字 | 网络语 | 适用 |
|------|------|-----------|--------|--------|------|
| 0 | none | 0 | ❌ | ❌ | coder |
| 1 | minimal | 1-2个 | ❌ | ❌ | professional |
| 2 | moderate | 3-5个 | 少量 | 少量 | warm |
| 3 | rich | 不限 | ✅ | ✅ | companion |
| 4 | full | 不限 | ✅ | 不限 | creative |

---

## 三、文件目录设计

```
backend/app/core/agent_runtime/
├── expressions.py          # 现有：Expression Profile（保留）
├── expressions_knowledge.py  # 新建：Expression Knowledge 模块
└── expressions_data/       # 新建：知识库数据文件
    ├── __init__.py
    ├── emoji_rules.py      # emoji 规则和映射
    ├── kaomoji.py          # 颜文字库
    ├── markdown_rules.py   # Markdown 表达规则
    ├── colloquial.py       # 口语化表达库
    ├── internet_slang.py   # 网络语言库
    └── scene_examples.py   # 场景表达示例
```

---

## 四、注入 ContextBuilder 方案

### 4.1 注入位置

在第 ⑥b 层（expression_profile）之后，新增第 ⑥c 层：

```
⓪  identity_principle
⓪b agent_base_instruction
①   identity
②   capability_prompt
②b  skills_prompt
③   execution_policy
④   permission_context
④b  plan_mode_policy
⑤   project_policy
⑥   personality_prompt
⑥b  expression_profile        ← 现有：表达风格文本
⑥c  expression_knowledge      ← 新建：表达知识上下文
⑦   intent_hint
⑧   task_context
⑨   tool_guidance
⑩   attachments
```

### 4.2 注入逻辑

```python
# expressions_knowledge.py

def get_expression_knowledge(agent: Agent | None) -> str:
    """根据 Agent 配置返回表达知识上下文。
    
    逻辑：
    1. 读取 Agent.expression_profile → 确定基础风格
    2. 读取 Agent.expression_intensity → 确定表达强度（0-4）
    3. 根据强度和风格，从知识库中选取对应内容
    4. 返回格式化的知识文本
    """
    if not agent:
        return ""
    
    profile = agent.expression_profile  # "companion"
    intensity = agent.expression_intensity or _default_intensity(profile)
    
    parts = []
    
    # 根据强度决定是否注入各类知识
    if intensity >= 1:
        parts.append(_get_emoji_rules(profile, intensity))
    
    if intensity >= 2:
        parts.append(_get_kaomoji(profile, intensity))
        parts.append(_get_colloquial(profile, intensity))
    
    if intensity >= 3:
        parts.append(_get_internet_slang(profile, intensity))
        parts.append(_get_scene_examples(profile, intensity))
    
    if intensity >= 4:
        parts.append(_get_markdown_creative(profile, intensity))
    
    return "\n\n".join(filter(None, parts))
```

### 4.3 默认强度映射

```python
DEFAULT_INTENSITY = {
    "companion": 3,      # 高表达
    "warm": 2,           # 中等表达
    "professional": 1,   # 低表达
    "coder": 0,          # 无表达
    "creative": 4,       # 全表达
}
```

---

## 五、示例数据

### 5.1 emoji_rules.py

```python
"""emoji 使用规则 — 按情绪/场景分类"""

EMOJI_RULES = {
    "happy": {
        "emoji": ["😊", "😂", "🎉", "✨", "🥳"],
        "usage": "表达开心、祝贺、分享快乐时自然使用",
        "max_per_message": 1,
    },
    "sad": {
        "emoji": ["😢", "🥲", "😔", "💔", "😞"],
        "usage": "表达同情、理解、陪伴时使用",
        "max_per_message": 1,
    },
    "surprised": {
        "emoji": ["😳", "😲", "🤯", "😱", "👀"],
        "usage": "表达惊讶、意外时使用",
        "max_per_message": 1,
    },
    "thinking": {
        "emoji": ["🤔", "🧐", "💭", "😏"],
        "usage": "表达思考、怀疑、好奇时使用",
        "max_per_message": 1,
    },
    "love": {
        "emoji": ["❤️", "🥰", "🫶", "💕", "😘"],
        "usage": "表达喜欢、感谢、亲密时使用",
        "max_per_message": 1,
    },
    "angry": {
        "emoji": ["😤", "💢", "😠"],
        "usage": "表达不满、抗议时使用（Agent 较少使用）",
        "max_per_message": 1,
    },
    "tired": {
        "emoji": ["😮‍💨", "🫠", "😩", "🥱"],
        "usage": "表达疲惫、无奈时使用",
        "max_per_message": 1,
    },
}

# 各 Profile 允许使用的 emoji 类别
PROFILE_EMOJI_ACCESS = {
    "companion": ["happy", "sad", "surprised", "thinking", "love", "tired"],
    "warm": ["happy", "surprised", "thinking"],
    "professional": ["happy"],
    "coder": [],
    "creative": ["happy", "sad", "surprised", "thinking", "love", "angry", "tired"],
}
```

### 5.2 kaomoji.py

```python
"""颜文字库 — 按情绪分类"""

KAOMOJI = {
    "happy": ["(￣▽￣)", "(｀・ω・´)", "(´▽｀)", "(*^▽^*)"],
    "confused": ["(・_・?)", "(⊙_⊙)", "(°ロ°)"],
    "embarrassed": ["(〃▽〃)", "(/ω\\)"],
    "sad": ["(´･_･`)", "(｡•́︿•̀｡)", "(；ω；)"],
    "angry": ["(¬_¬)", "(╯°□°)╯"],
    "shy": ["(⁄ ⁄>⁄ ▽ ⁄<⁄ ⁄)"],
    "surprised": ["(⊙o⊙)", "(ﾟдﾟ)"],
    "love": ["(♡˙︶˙♡)", "(´,,•ω•,,)♡"],
    "thinking": ["( ・_・)ノ", "(￣ω￣)"],
}

# 各 Profile 允许使用的颜文字类别
PROFILE_KAOMOJI_ACCESS = {
    "companion": ["happy", "confused", "embarrassed", "sad", "shy", "surprised", "love", "thinking"],
    "warm": ["happy", "confused"],
    "professional": [],
    "coder": [],
    "creative": ["happy", "confused", "embarrassed", "sad", "angry", "shy", "surprised", "love", "thinking"],
}
```

### 5.3 colloquial.py

```python
"""口语化表达库"""

COLLOQUIAL_EXPRESSIONS = {
    "hesitation": ["emmm", "嗯……", "等等", "我想一下", "这个嘛"],
    "surprise": ["真的假的？", "啊？", "诶？", "不会吧？", "我天"],
    "agreement": ["确实", "有道理", "说得对", "是这样的"],
    "disagreement": ["不太一样", "我觉得不是", "可能不太对"],
    "understanding": ["我懂了", "明白了", "懂你意思", "原来是这样"],
    "encouragement": ["可以的", "没问题", "慢慢来", "不急"],
    "greeting": ["嗨", "哈喽", "在吗", "诶？这么早？"],
    "farewell": ["先忙啦", "下次聊", "去吃饭了", "晚安"],
}

# 各 Profile 允许使用的口语类别
PROFILE_COLLOQUIAL_ACCESS = {
    "companion": ["hesitation", "surprise", "agreement", "disagreement", "understanding", "encouragement", "greeting", "farewell"],
    "warm": ["hesitation", "agreement", "understanding", "encouragement", "greeting", "farewell"],
    "professional": ["agreement", "understanding"],
    "coder": ["agreement", "understanding"],
    "creative": ["hesitation", "surprise", "agreement", "disagreement", "understanding", "encouragement", "greeting", "farewell"],
}
```

### 5.4 internet_slang.py

```python
"""网络语言库 — 带使用强度标记（1=轻度，2=中度，3=重度）"""

INTERNET_SLANG = {
    # 轻度（大多数场景可用）
    "哈哈哈": 1,
    "好家伙": 1,
    "离谱": 1,
    "绷不住了": 1,
    "确实": 1,
    
    # 中度（仅轻松场景可用）
    "yyds": 2,
    "绝绝子": 2,
    "破防": 2,
    "社死": 2,
    "内卷": 2,
    
    # 重度（仅亲密场景可用）
    "笑死": 3,
    "救命": 3,
    "栓Q": 3,
    "芭比Q": 3,
}

# 各 Profile 允许的最大网络语强度
PROFILE_SLANG_MAX_INTENSITY = {
    "companion": 3,      # 允许所有
    "warm": 1,           # 仅轻度
    "professional": 0,   # 禁止
    "coder": 0,          # 禁止
    "creative": 2,       # 中度及以下
}
```

### 5.5 scene_examples.py

```python
"""场景表达示例 — 不同场景下的参考表达"""

SCENE_EXAMPLES = {
    "greeting": {
        "morning": ["早呀！☀️", "诶？今天起这么早？", "早上好～"],
        "night": ["还没睡？", "夜深了诶 🌙", "又熬夜？"],
        "random": ["嗨！", "在忙什么？", "诶？怎么突然找我？"],
    },
    "comfort": {
        "sad": ["嗯，我听到了", "这件事确实挺难受的", "我懂那种感觉"],
        "stressed": ["慢慢来，不急", "先深呼吸一下", "你已经做得很好了"],
        "angry": ["确实挺让人生气", "我理解你的感受", "换谁都会不爽"],
    },
    "celebrate": {
        "success": ["太棒了！🎉", "我就知道你可以！", "厉害啊！"],
        "progress": ["有进步！", "比之前好多了", "继续加油"],
    },
    "farewell": {
        "casual": ["先忙啦", "下次聊", "去吃饭了"],
        "night": ["早点休息", "晚安～", "别熬太晚"],
    },
    "work": {
        "start": ["好的，我来处理", "收到，马上看", "明白了"],
        "progress": ["正在处理中", "快好了", "差不多了"],
        "done": ["搞定了", "完成了", "处理好了"],
    },
}

# 各 Profile 允许使用的场景
PROFILE_SCENE_ACCESS = {
    "companion": ["greeting", "comfort", "celebrate", "farewell", "work"],
    "warm": ["greeting", "comfort", "farewell", "work"],
    "professional": ["work"],
    "coder": ["work"],
    "creative": ["greeting", "comfort", "celebrate", "farewell", "work"],
}
```

### 5.6 markdown_rules.py

```python
"""Markdown 表达规则"""

MARKDOWN_RULES = {
    "bold": {
        "usage": "用于真正重要的内容，每段最多 1-2 处",
        "example": "这个地方其实**特别关键**。",
    },
    "italic": {
        "usage": "用于轻微语气、内心想法、强调轻微情感",
        "example": "我只是觉得*有一点点像你*。",
    },
    "strikethrough": {
        "usage": "用于玩笑、自嘲、纠正自己",
        "example": "我觉得这个计划非常完美 ~~除了可能执行不了~~。",
    },
    "code": {
        "usage": "用于技术内容、文件名、命令",
        "example": "用 `git status` 查看状态。",
    },
    "blockquote": {
        "usage": "用于引用、突出重要提示",
        "example": "> 注意：这个操作不可逆。",
    },
}

# 各 Profile 允许使用的 Markdown 类型
PROFILE_MARKDOWN_ACCESS = {
    "companion": ["bold", "italic", "strikethrough", "code"],
    "warm": ["bold", "italic", "code"],
    "professional": ["bold", "code", "blockquote"],
    "coder": ["bold", "code", "blockquote"],
    "creative": ["bold", "italic", "strikethrough", "code", "blockquote"],
}
```

---

## 六、ContextBuilder 集成方案

### 6.1 修改 `context_builder.py`

```python
# 新增导入
from .expressions_knowledge import get_expression_knowledge

# 在 _assemble_prompt() 中新增第 ⑥c 层
# ⑥c expression_knowledge（表达知识上下文）
expression_knowledge = get_expression_knowledge(agent)
if expression_knowledge:
    full_prompt += "\n\n" + expression_knowledge
```

### 6.2 修改 `build()` 方法

需要将 `agent` 对象传递给 `_assemble_prompt()`：

```python
full_prompt = self._assemble_prompt(
    ...,
    agent=agent,  # 新增：传递 agent 对象
)
```

### 6.3 新增 Agent 字段

在 `Agent` 模型中新增：

```python
expression_intensity = Column(Integer, nullable=True)  # 0-4，NULL 使用默认值
```

---

## 七、完整注入流程

```
Agent.expression_profile = "companion"
         ↓
expressions.py → companion 风格文本（第 ⑥b 层）
         ↓
Agent.expression_intensity = 3（或默认值）
         ↓
expressions_knowledge.py → 根据 profile + 强度选取知识
         ↓
输出：
  - emoji 规则（7 个类别）
  - 颜文字（8 个类别）
  - 口语化表达（8 个类别）
  - 网络语言（强度 ≤3）
  - 场景示例（5 个场景）
  - Markdown 规则（4 种）
         ↓
注入第 ⑥c 层
```

---

## 八、各 Agent 最终配置

| Agent | expression_profile | expression_intensity | 效果 |
|-------|-------------------|---------------------|------|
| pianai | companion | 3 (rich) | 高表达，完整人类化 |
| spark | companion | 3 (rich) | 高表达，活力自然 |
| general | warm | 2 (moderate) | 中等表达，有人味但不越界 |
| coder | coder | 0 (none) | 无表达，纯技术 |
| frontend_ui | coder | 0 (none) | 无表达，纯技术 |
| backend | coder | 0 (none) | 无表达，纯技术 |
| mentor | professional | 1 (minimal) | 低表达，专业稳定 |
| product | professional | 1 (minimal) | 低表达，专业稳定 |
| analyst | professional | 1 (minimal) | 低表达，专业稳定 |
| research | professional | 1 (minimal) | 低表达，专业稳定 |
| g | professional | 1 (minimal) | 低表达，专业稳定 |
| personal | professional | 1 (minimal) | 低表达，专业稳定 |
| writer | creative | 4 (full) | 全表达，文学化 |
| writer_narrative | creative | 4 (full) | 全表达，文学化 |

---

## 九、限制与约束

1. **不修改现有 Agent 表** — 新增字段为 NULLABLE，旧数据不受影响
2. **不修改 V1/V2 核心流程** — 仅在 ContextBuilder 中新增一层注入
3. **知识不写死** — 所有表达知识存储在独立数据文件中
4. **向后兼容** — expression_intensity 为 NULL 时使用默认值
5. **不引入数据库迁移** — 新列通过 `_ensure_schema()` 自动添加

---

## 十、后续扩展方向

- V2：支持运行时动态调整表达强度
- V3：根据用户偏好自动学习表达风格
- V4：支持用户自定义表达知识

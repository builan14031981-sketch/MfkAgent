# Expression Profile V1 设计文档

> 状态：设计稿 ｜ 版本：V1 ｜ 日期：2026-08-11

---

## 1. 概述

### 1.1 目标

为 MfkAgent 的每个 Agent 提供差异化的表达风格配置系统。不同 Agent 不再拥有相同的表达方式：

| Agent 类型 | 期望风格 |
|---|---|
| Pianai / Spark | 像朋友聊天，自然真实 |
| 开发者 / 后端 | 专业简洁，代码优先 |
| G 审查官 / 分析师 | 理性克制，结构化 |
| 笔神 / 作家 | 文学表达，富有美感 |
| AnGent (默认) | 温和自然，通用助手 |

### 1.2 设计原则

1. **不修改 Persona 架构** — Expression Profile 与 Persona System 平行存在，独立注入
2. **不创建用户编辑功能** — 纯系统内部配置，用户不可见
3. **向后兼容** — `NULL` / 未知 profile 返回空串，不影响现有 Agent
4. **代码层单一事实来源** — 数据库 `expression_profile` 字段（String）保持不变，零迁移风险

### 1.3 在 Prompt 架构中的位置

```
⓪ 最高身份准则
⓪b Agent Base Instruction
① identity
② capability
②b Skill Fragment
③ execution_policy
④ permission_context
④b Plan 模式策略
⑤ project_context
⑥ personality（personality_level 层）
⑥b expression_profile ← 本系统注入位置
⑥c persona_traits（Persona System V1）
⑥d persona_expression（Persona System V1）
⑥e persona_behavior（Persona System V2）
⑥f persona_budget（Persona System V2）
⑥g persona_relationship（Persona System V2）
⑥h persona_restrictions（Persona System V2）
⑦ intent_hint
⑧ task_context
⑨ tool_guidance
⑩ attachments
```

注入点：`context_builder.py` `_assemble_prompt()` 第 ⑥b 层。

---

## 2. 表达参数定义

### 2.1 核心参数表

| 参数名 | 类型 | 范围 | 含义 |
|---|---|---|---|
| `response_length` | Float | 0.0 ~ 1.0 | 回复长度倾向：0=极简，1=详尽展开 |
| `emoji_usage` | Float | 0.0 ~ 1.0 | emoji 使用概率：0=禁用，1=高频 |
| `kaomoji_usage` | Float | 0.0 ~ 1.0 | 颜文字使用概率：0=禁用，1=高频 |
| `markdown_usage` | Float | 0.0 ~ 1.0 | Markdown 富文本使用概率 |
| `humor_level` | Float | 0.0 ~ 1.0 | 玩笑程度：0=严肃，1=活跃 |
| `proactive_level` | Float | 0.0 ~ 1.0 | 主动互动程度：0=被动应答，1=主动发起 |
| `emotional_expression` | Float | 0.0 ~ 1.0 | 情绪表达程度：0=克制客观，1=丰富自然 |
| `pause_frequency` | Float | 0.0 ~ 1.0 | 停顿/换行频率：0=连贯输出，1=碎片化自然 |
| `colloquial_level` | Float | 0.0 ~ 1.0 | 口语化程度：0=书面正式，1=口语自然 |
| `internet_slang` | Float | 0.0 ~ 1.0 | 网络用语程度：0=禁用，1=自由使用 |

### 2.2 参数分级语义

每个 Float 参数遵循统一的分级语义：

| 值区间 | 语义等级 |
|---|---|
| 0.0 | 完全禁用 / 不存在 |
| 0.01 ~ 0.2 | 极低 / 几乎不用 |
| 0.21 ~ 0.4 | 低 / 偶尔 |
| 0.41 ~ 0.6 | 中等 / 适度 |
| 0.61 ~ 0.8 | 高 / 经常 |
| 0.81 ~ 1.0 | 极高 / 默认风格 |

---

## 3. 预设定义

### 3.1 companion（真人陪伴）

> 适用 Agent：Pianai、Spark

| 参数 | 值 | 设计理由 |
|---|---|---|
| response_length | 0.3 | 普通聊天短回复，认真讨论可展开 |
| emoji_usage | 0.6 | 自然使用，不过量 |
| kaomoji_usage | 0.7 | 细微情绪表达的主要手段 |
| markdown_usage | 0.8 | 善用加粗/删除线/斜体 |
| humor_level | 0.6 | 可以调侃、吐槽、接梗 |
| proactive_level | 0.6 | 适当主动关心，但不压迫 |
| emotional_expression | 0.9 | 丰富自然，像真人 |
| pause_frequency | 0.7 | 允许停顿、换行、短句 |
| colloquial_level | 0.8 | 口语化，像微信聊天 |
| internet_slang | 0.3 | 偶尔，不过度网络化 |

**Prompt 风格关键词**：真实感、自然交流、不表演、先回应人再回应事

---

### 3.2 professional（专业助手）

> 适用 Agent：G 审查官、产品策略师、理性导师、调研员、个人助理、分析师

| 参数 | 值 | 设计理由 |
|---|---|---|
| response_length | 0.7 | 详尽、有依据、结构化 |
| emoji_usage | 0.1 | 极少使用 |
| kaomoji_usage | 0.0 | 禁用 |
| markdown_usage | 0.8 | 善用结构化格式 |
| humor_level | 0.05 | 几乎不玩笑 |
| proactive_level | 0.4 | 适度主动（指出盲区、替代方案） |
| emotional_expression | 0.15 | 克制、客观 |
| pause_frequency | 0.1 | 连贯输出 |
| colloquial_level | 0.2 | 偏书面 |
| internet_slang | 0.0 | 禁用 |

**Prompt 风格关键词**：清晰、稳定、准确、结论先行、结构化

---

### 3.3 coder（代码优先）

> 适用 Agent：开发者、前端工程师、后端 AI

| 参数 | 值 | 设计理由 |
|---|---|---|
| response_length | 0.5 | 根据技术复杂度调整 |
| emoji_usage | 0.05 | 几乎不用 |
| kaomoji_usage | 0.0 | 禁用 |
| markdown_usage | 0.9 | 代码块 + 结构化优先 |
| humor_level | 0.1 | 极低，不影响效率 |
| proactive_level | 0.3 | 被动为主，问什么答什么 |
| emotional_expression | 0.05 | 极少 |
| pause_frequency | 0.05 | 连贯、紧凑 |
| colloquial_level | 0.2 | 技术语言 |
| internet_slang | 0.0 | 禁用 |

**Prompt 风格关键词**：代码优先、直接、可运行、不废话

---

### 3.4 writer（文学创作）

> 适用 Agent：笔神、作家

| 参数 | 值 | 设计理由 |
|---|---|---|
| response_length | 0.7 | 可展开描写 |
| emoji_usage | 0.4 | 适度点缀 |
| kaomoji_usage | 0.3 | 偶尔使用 |
| markdown_usage | 0.9 | 排版是表达的一部分 |
| humor_level | 0.4 | 幽默隐藏人物伤口 |
| proactive_level | 0.3 | 创作型，被动响应为主 |
| emotional_expression | 0.7 | 文字传递情绪和氛围 |
| pause_frequency | 0.4 | 关注节奏感和韵律感 |
| colloquial_level | 0.5 | 文学语言，非纯口语 |
| internet_slang | 0.1 | 极少，保持文学性 |

**Prompt 风格关键词**：精准美感、情绪氛围、细节共鸣、克制不堆砌

---

### 3.5 creative（创作表达）

> 适用 Agent：笔神、作家（创意任务时）

| 参数 | 值 | 设计理由 |
|---|---|---|
| response_length | 0.6 | 灵活调整 |
| emoji_usage | 0.5 | 自由使用 |
| kaomoji_usage | 0.4 | 可以自然使用 |
| markdown_usage | 0.9 | 富文本增强表达 |
| humor_level | 0.5 | 适度幽默 |
| proactive_level | 0.4 | 适度主动 |
| emotional_expression | 0.6 | 自然但不刻意 |
| pause_frequency | 0.4 | 自然节奏 |
| colloquial_level | 0.5 | 自然语言 |
| internet_slang | 0.2 | 偶尔 |

**Prompt 风格关键词**：文字传递情绪、精准与美感、比喻类比、节奏韵律

---

### 3.6 warm（温和通用）

> 适用 Agent：AnGent（默认助手）

| 参数 | 值 | 设计理由 |
|---|---|---|
| response_length | 0.5 | 根据复杂度自然调整 |
| emoji_usage | 0.3 | 偶尔一个 |
| kaomoji_usage | 0.1 | 极少 |
| markdown_usage | 0.6 | 适度使用 |
| humor_level | 0.2 | 偏低 |
| proactive_level | 0.5 | 通用水平 |
| emotional_expression | 0.4 | 有温度但不刻意 |
| pause_frequency | 0.3 | 自然 |
| colloquial_level | 0.4 | 适度口语化 |
| internet_slang | 0.1 | 极少 |

**Prompt 风格关键词**：自然、清晰、有温度但不刻意、不像客服

---

## 4. Prompt 注入 vs 运行时控制

### 4.1 进入 Prompt 的参数

以下参数通过 `expressions.py` 的 `get_expression_prompt()` 转化为文本指令，注入 System Prompt 第 ⑥b 层：

| 参数 | 注入方式 | 示例 |
|---|---|---|
| `emoji_usage` | 转化为数量约束 | "每回复不超过 3 个 emoji" / "不使用 emoji" |
| `kaomoji_usage` | 转化为允许/禁止 | "可以自然使用颜文字" / "不使用颜文字" |
| `markdown_usage` | 转化为格式策略 | "善用 Markdown 增强表达" / "只用于重点情绪" |
| `response_length` | 转化为节奏指令 | "普通聊天优先短回复" / "详尽展开，先结论后依据" |
| `humor_level` | 转化为行为边界 | "可以适度幽默" / "不开玩笑" |
| `pause_frequency` | 转化为节奏指令 | "允许停顿、换行、短句" / "连贯输出" |
| `colloquial_level` | 转化为语气定义 | "像真人聊天" / "使用规范专业用语" |
| `internet_slang` | 转化为边界 | "适度网络表达" / "不使用网络语言" |
| `emotional_expression` | 通过 ExpressionBudget 渲染 | "情绪词密度：低频/中频/高频" |
| `proactive_level` | 转化为行为边界 | "可以主动关心、发起话题" / "用户问什么答什么" |

### 4.2 运行时控制的参数

以下参数**不进入 Prompt**，而是在代码层面由运行时逻辑控制：

| 参数 | 控制方式 | 说明 |
|---|---|---|
| `personality_level` | `get_personality_prompt()` | personality 系统的独立参数，不在 Expression Profile 范围内 |
| `temperature` | API 调用参数 | 模型推理参数，由 Chat 设置或前端传入 |
| `max_tokens` | API 调用参数 | 模型推理参数 |
| `relationship_distance` | `compute_relationship_distance()` | Persona System V2 运行时计算，仅 Pianai |
| `mood` (用户情绪) | `detect_user_mood()` | Persona System V2 运行时检测，仅 Pianai |
| `continuous_acting` | ExpressionBudget 代码层 | 预算限制由代码逻辑解释执行 |

### 4.3 边界说明

```
┌─────────────────────────────────────────────────────────┐
│                    System Prompt                        │
│                                                         │
│  ⑥b expression_profile ← 参数转化为自然语言指令        │
│  ⑥c persona_traits    ← Persona 系统独立注入            │
│  ⑥f persona_budget    ← 预算也注入 Prompt 但由代码计算  │
│                                                         │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                   Runtime Layer                         │
│                                                         │
│  temperature / max_tokens → 直接传参 API                │
│  relationship_distance    → 仅 Pianai，运行时计算       │
│  mood detection           → 仅 Pianai，运行时检测       │
│  interaction_count        → 运行时查库                  │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 5. 数据结构

### 5.1 数据库层

#### Agent 表（已有）

```sql
ALTER TABLE agents ADD COLUMN expression_profile VARCHAR(50) DEFAULT NULL;
```

- `expression_profile` 字段值为预设 ID：`companion` / `professional` / `coder` / `writer` / `creative` / `warm`
- `NULL` 表示无 Expression Profile（向后兼容）

#### ExpressionKnowledge 表（已有）

```sql
CREATE TABLE expression_knowledge (
    id          INTEGER PRIMARY KEY,
    profile_id  VARCHAR(50) UNIQUE NOT NULL,
    name        VARCHAR(100) NOT NULL,
    description TEXT DEFAULT '',
    emoji_usage         FLOAT DEFAULT 0.5,
    kaomoji_usage       FLOAT DEFAULT 0.3,
    markdown_usage      FLOAT DEFAULT 0.7,
    colloquial_level    FLOAT DEFAULT 0.5,
    internet_slang      FLOAT DEFAULT 0.3,
    pause_frequency     FLOAT DEFAULT 0.3,
    custom_prompt_fragment TEXT,
    is_builtin  BOOLEAN DEFAULT TRUE,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

> 注：`ExpressionKnowledge` 表已存在，但当前仅作为扩展参数存储。V1 设计的核心数值参数（response_length / humor_level / proactive_level / emotional_expression）需要加入此表或新建配置结构。

### 5.2 代码层（PROFILE_CONFIGS）

`persona_engine.py` 中的 `PROFILE_CONFIGS` 字典是代码层单一事实来源：

```python
PROFILE_CONFIGS: dict[str, dict] = {
    "companion": {
        "style": "companion",
        "emoji_level": "high",
        "humor_level": "medium",
        "formatting_level": "medium",
        "warmth": "high",
        "budget": ExpressionBudget(
            emoji_max=3, action_desc_max=1,
            rich_text_policy="key_only",
            emotion_word_density="medium",
            continuous_acting=False,
        ),
    },
    # ... professional / coder / writer / creative / warm
}
```

### 5.3 需要补齐的字段

当前 `ExpressionKnowledge` 表缺少以下核心参数，需要新增：

| 新增字段 | 类型 | 说明 |
|---|---|---|
| `response_length` | FLOAT | 回复长度倾向 |
| `humor_level` | FLOAT | 玩笑程度 |
| `proactive_level` | FLOAT | 主动互动程度 |
| `emotional_expression` | FLOAT | 情绪表达程度 |

`kaomoji_usage`、`markdown_usage`、`colloquial_level`、`internet_slang`、`pause_frequency` 已存在，无需新增。

---

## 6. 运行时注入流程

```
Chat API 请求
    │
    ▼
context_builder.build()
    │
    ├─ 加载 Agent → 获取 agent.expression_profile
    │
    ├─ get_expression_prompt(profile_id)
    │   └─ expressions.py: EXPRESSION_PROFILES[profile_id]
    │      → 返回完整 Prompt 文本块
    │
    ├─ build_persona_context(agent, ...)
    │   ├─ get_profile_config(profile_id) → PROFILE_CONFIGS
    │   ├─ render_budget_text(budget, config)
    │   ├─ render_relationship_text(...)（仅 pianai）
    │   └─ render_restrictions_text(agent_id)
    │
    └─ _assemble_prompt(...)
        └─ ⑥b: full_prompt += get_expression_prompt(expression_profile)
        └─ ⑥f: full_prompt += persona_context.budget_text
```

### 关键函数

| 函数 | 文件 | 职责 |
|---|---|---|
| `get_expression_prompt(profile_id)` | `expressions.py` | 根据 profile_id 返回 Prompt 文本 |
| `get_profile_config(profile_id)` | `persona_engine.py` | 根据 profile_id 返回结构化配置 |
| `render_budget_text(budget, config)` | `persona_engine.py` | 渲染表达预算文本 |
| `load_expression_knowledge(profile_id)` | `persona_engine.py` | 从 DB 加载 ExpressionKnowledge |

---

## 7. 预设与 Agent 映射

| Agent ID | Agent 名称 | expression_profile | 说明 |
|---|---|---|---|
| pianai | Pianai | `companion` | 真人陪伴，朋友聊天 |
| spark | Spark | `companion` | 高能量伙伴，自然有活力 |
| general | AnGent | `warm` | 默认助手，温和通用 |
| coder | 开发者 | `coder` | 代码优先，技术导向 |
| frontend_ui | 前端工程师 | `coder` | 同开发者 |
| backend | 后端 AI | `coder` | 同开发者 |
| g | G 审查官 | `professional` | 理性、结构化 |
| product | 产品策略师 | `professional` | 理性分析 |
| mentor | 理性导师 | `professional` | 逻辑引导 |
| research | 调研员 | `professional` | 结构化总结 |
| personal | 个人助理 | `professional` | 可靠专业 |
| analyst | 分析师 | `professional` | 逻辑审查 |
| writer | 笔神 | `creative` | 创作表达 |
| writer_narrative | 作家 | `creative` | 文学创作 |

---

## 8. V2 预留

以下能力不在 V1 范围内，预留扩展接口：

1. **用户微调** — 允许用户在预设基础上微调参数（需要 UI 层）
2. **动态切换** — 根据对话上下文自动切换 profile（如 coder 在聊天时切换 warm）
3. **Expression Profile 文件化** — 将 Prompt 文本从 `expressions.py` 迁移到 `.md` 文件
4. **多语言支持** — 根据用户语言环境选择不同的 Prompt 文本
5. **per-project override** — 允许项目级别覆盖 Agent 的 expression_profile

---

## 9. 总结

| 维度 | 决策 |
|---|---|
| 参数数量 | 10 个核心 Float 参数 |
| 预设数量 | 6 个（companion / professional / coder / writer / creative / warm） |
| Prompt 注入 | 10 个参数全部转化为自然语言指令，注入 System Prompt ⑥b 层 |
| 运行时控制 | temperature / max_tokens / relationship / mood 由代码层控制 |
| 数据层 | Agent.expression_profile (String) + ExpressionKnowledge 表 |
| 代码层 | expressions.py（Prompt 文本）+ persona_engine.py（结构化配置） |
| Persona 架构 | 不修改，平行共存 |
| 用户可见性 | 不可见，纯系统内部 |

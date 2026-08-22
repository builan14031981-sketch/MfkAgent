# Expression Profile V1 — 实施计划

## 目标

在现有 Agent Prompt 构建流程中增加一层「表达规则注入」。

## 改动清单（6 个文件）

### Step 1: 新建 `backend/app/core/agent_runtime/expressions.py`

创建新模块，定义 5 档 Expression Profile：

```python
EXPRESSION_PROFILES: dict[str, str] = {
    "companion": "...",    # 真人陪伴感
    "warm": "...",         # 通人性但不越界
    "professional": "...", # 专业清晰
    "coder": "...",        # 代码优先
    "creative": "...",     # 创作表达
}

def get_expression_prompt(profile_id: str | None) -> str:
    if not profile_id:
        return ""
    return EXPRESSION_PROFILES.get(profile_id, "")
```

### Step 2: 修改 `backend/app/models/agent.py`

在 Agent 类新增字段：
```python
expression_profile = Column(String(50), nullable=True)
```

### Step 3: 修改 `backend/main.py`

在 `_ensure_schema()` 中新增迁移：
```python
if "agents" in inspector.get_table_names():
    cols = {c["name"] for c in inspector.get_columns("agents")}
    with engine.begin() as conn:
        if "expression_profile" not in cols:
            conn.execute(sa.text("ALTER TABLE agents ADD COLUMN expression_profile VARCHAR(50)"))
```

### Step 4: 修改 `backend/app/core/agent_runtime/context_builder.py`

在 `_assemble_prompt()` 方法中，第 ⑥ 层（personality）之后新增第 ⑥b 层：

```python
# ⑥b expression_profile（表达风格层）
expression_prompt = get_expression_prompt(agent.expression_profile if agent else None)
if expression_prompt:
    full_prompt += "\n\n" + expression_prompt
```

需要在 `build()` 方法中将 `agent` 对象传递给 `_assemble_prompt()`。

### Step 5: 修改 `backend/seed_agents.py`

为所有 Agent 设置 `expression_profile`：

| Agent | expression_profile |
|-------|-------------------|
| pianai | companion |
| spark | companion |
| general (AnGent) | warm |
| coder | coder |
| frontend_ui | coder |
| backend | coder |
| mentor | professional |
| product | professional |
| analyst | professional |
| research | professional |
| g | professional |
| personal | professional |
| writer | creative |
| writer_narrative | creative |

### Step 6: 修改 `backend/app/api/agents.py`

在 `AgentUpdate` Pydantic 模型中新增：
```python
expression_profile: Optional[str] = None
```

在 `update_agent()` 处理逻辑中新增：
```python
if update.expression_profile is not None:
    agent.expression_profile = update.expression_profile
```

在 `AgentInfo` 响应模型中新增：
```python
expression_profile: str = ""
```

## 5 档 Expression Profile 内容

### companion（偏爱/Spark）
- 真人交流感，像人在聊天
- 先回应人，再回应事情
- 禁止主动分析用户
- 允许不完美表达（emmm、等等）
- 允许 emoji/颜文字/Markdown（适量）
- 普通聊天优先短回复
- 不要急着治愈，先陪伴

### warm（AnGent 通用助手）
- 自然、清晰、有温度但不刻意
- 适度口语化，不过度网络化
- 偶尔一个 emoji，不每句话都加
- 不刻意卖萌，不空洞鸡汤

### professional（Mentor/Product/Analyst/Research/G/Personal）
- 清晰、稳定、准确
- 先给结论再给依据
- 少 emoji，少网络语言
- 不调侃用户

### coder（Coder/Frontend/Backend）
- Markdown 优先，代码优先
- 结构清晰，逻辑严密
- 禁止大量 emoji
- 禁止聊天化影响效率

### creative（作家/笔神）
- 文字传递信息和情绪
- 允许文学表达、氛围营造
- 善用比喻、类比
- 不为了华丽牺牲内容

## 回滚方案

- 所有修改文件已备份到 `_backup/expression_profile_<timestamp>/`
- `expression_profile` 为 NULLABLE，不影响旧数据
- 回滚 = 恢复备份文件（数据库列可保留，不影响功能）

## 验证步骤

1. 运行 `python seed_agents.py` 确认数据写入
2. 查询数据库确认 `expression_profile` 列存在且数据正确
3. 重启后端服务，测试各 Agent 对话效果

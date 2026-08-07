# 计划：模型配置体系改造（V1.5）+ 删除 MiMo Key

## 背景与现状（已调研）

- **MiMo key 两处**：`backend\.env` 的 `MIMO_API_KEY`（值 `tp-...`）+ DB `settings` 表 `api_key_mimo`（`tp-cwfqnx68f5h`）。`_get_api_key()` 中 DB 优先于 .env。
- **DB 现状**：`settings` 表已存 `api_key_deepseek` / `api_key_qwen` / `api_key_freellm` / `api_key_mimo`；`default_model=qwen-flash`、`default_reasoning_effort=high`；无 `models` 表。
- **provider 硬编码三处**：`app/api/models.py:86`（5 家）、`services/model.py:_init_models`（16 个模型/8 家，枚举 11 家）、前端 `SettingsPanel.tsx:548`（6 家，漏 google，且不含 wenxin/spark/minimax/baichuan）。
- **无自定义模型**；**`GET /api/settings` 明文返回所有 `api_key_*`**（安全隐患）。
- **默认模型兜底残留**：`settings.py:27`、`chat.py:480`、`seed_agents.py` 指向 `mimo-v2.5-pro`（`agent.py:70` 列属待删字段，见"架构决策"）。
- `_chat_openai_compatible` 已统一处理 11 家 provider（全 OpenAI 兼容），接入新 provider 仅需加配置。

## 架构决策：删除 Agent.default_model（已审查）

> **产品原则**：Agent = identity + capabilities + personality；模型属于运行配置，不属于 Agent 身份；V1 不创建用户 Agent。

穷尽审计证据：
- **`Agent.model` 无功能角色**：模型选择链路为 `chat.model → request.model → Settings.default_model`（chat.py:620/711），Agent 从不参与；前端新建聊天初始模型全部来自 `settings?.default_model`（page.tsx:78、Sidebar.tsx:240、ProjectInitModal.tsx:60）。
- **唯一消费方是纯展示**：`AgentInfo.default_model`（agents.py:56,81）→ `AgentListPanel.tsx:150` 一行文本。
- **无管理面**：agents 仅 GET（只读），无创建/更新接口，字段无管理入口。
- **数据已误导**：9 个 agent 展示 `mimo-v2.5-pro`（正被移除的付费 provider）。
- **`Agent.temperature`（agent.py:71）同为死字段**：无任何读取，运行时温度来自 `request.temperature`（0.7）。
- **`Agent.default_personality_level` 是真实字段，保留**：chat.py:128-134 新建聊天的人格快照来源，属 personality 组件。

**结论：删除 `Agent.model` 与 `Agent.temperature`，Agent 不再承载模型/温度字段。模型统一由 Settings.default_model（全局默认）+ chat.model（单聊天覆盖）控制。**

## 用户决策（已确认）

1. 自定义模型 → **新建 `models` 表**
2. 未接入的 4 家（文心/星火/MiniMax/百川）→ **全部接入**
3. MiMo → **仅删 key**（.env + DB，代码/前端保留，模型因无 key 自然隐藏）
4. ~~9 个 agent 默认模型全切 qwen-flash~~ → **改为：删除 Agent.model 字段，无需迁移**（Settings.default_model 已是唯一默认来源）

---

## 一、删除 MiMo Key（仅删 key）

1. DB：`DELETE FROM settings WHERE key='api_key_mimo'`（启动时一次性迁移，见下）
2. `.env`：删除 `MIMO_API_KEY=...` 行（保留 `MIMO_API_BASE` 注释或一并去掉均可）
3. 配置/前端保留：mimo 仍在 provider 注册表，`api_key` 为空 → `get_available_models()` 自动过滤，下拉不可见
4. `main.py` 增加幂等迁移：`DELETE FROM settings WHERE key='api_key_mimo'`

## 二、删除 Agent.model / Agent.temperature + 默认模型收敛 qwen-flash

1. **ORM**（`app/models/agent.py`）：删除 `model`（L70）与 `temperature`（L71）两列声明。DB 遗留列变孤儿列（SQLAlchemy 忽略，无害；如需彻底清理可选 `ALTER TABLE agents DROP COLUMN model/temperature`，SQLite ≥3.35 支持，验证后执行）。
2. **API**（`app/api/agents.py`）：`AgentInfo` 删除 `default_model` 字段（L21,30）及两处响应赋值（L56,81）。**保留 `default_personality_level`**。
3. **种子**（`backend/seed_agents.py`）：删除各 agent 的 `"model": ...` 键（7 处）与 L160 `existing.model = agent_data["model"]`；同步删除 `"temperature"`（若存在）。
4. **前端**：
   - `useAgents.ts:13` 删除 `default_model` 接口字段
   - `AgentListPanel.tsx:148-151` 删除"模型"展示行
   - `locales` 删除 `settings.ai.agents.model` 键（zh-CN:252 / en-US:252，仅此一处使用）
5. **默认模型收敛**（替换原"全切 qwen-flash"）：
   - `app/api/settings.py:27` `DEFAULT_SETTINGS["default_model"]="qwen-flash"`
   - `app/api/chat.py:480` `return "qwen-flash"`
   - `frontend/SettingsPanel.tsx:429,443` 兜底 `"mimo-v2.5-pro"` → `"qwen-flash"`
   - `useMessages.ts:50,66` 兜底 `"mimo-v2.5-pro"` → `"qwen-flash"`（实测还有两处）
   - `frontend/src/app/chat/[id]/page.tsx`、`useChatStream.ts` 若含 mimo 兜底一并替换
   - 无需 DB 迁移（`default_model` 已是 qwen-flash；agent 孤儿列 inert）

## 三、Provider 注册表（数据驱动，替代三处硬编码）

新建 `backend/app/core/model_providers.py`（或并入 `services/model.py`）：

```python
@dataclass
class ProviderDef:
    id: str; name: str; free: bool; default_api_base: str
    models: list[tuple[str, str]]  # (internal_id, upstream_model_name)

PROVIDERS = [
  deepseek(免费False, https://api.deepseek.com/v1, [deepseek-v4-flash, deepseek-v4-pro]),
  qwen(免费True, https://dashscope.aliyuncs.com/compatible-mode/v1, [qwen-flash, qwen-plus]),
  glm(https://open.bigmodel.cn/api/paas/v4, [glm-4]),
  moonshot(https://api.moonshot.cn/v1, [moonshot-v1-8k]),
  google(免费True, https://generativelanguage.googleapis.com/v1beta/openai, [gemini-3.5-flash, gemini-3-flash, gemini-3.1-flash-lite]),
  freellmapi(免费True, http://127.0.0.1:31415/v1, [freellm-deepseek-v4-flash, freellm-qwen3-coder-30b, ...]),
  mimo(付费, token-plan-cn, [mimo-v2.5-pro, mimo-v2.5]),
  wenxin(https://qianfan.baidubce.com/v2, [ernie-4.0-turbo-8k]),
  spark(https://spark-api-open.xf-yun.com/v1, [generalv3.5]),
  minimax(https://api.minimax.chat/v1, [MiniMax-Text-01]),
  baichuan(https://api.baichuan-ai.com/v1, [Baichuan4]),
]
```

- 4 家新接入的默认 api_base / 模型名按公开资料填写，**标注"默认值，可在页面覆盖"**，无 key 时不可见。
- `/api/models/providers` 改为从 `PROVIDERS` 动态生成（含 free 标识）。

## 四、自定义模型：新建 `models` 表

`app/models/agent.py` 新增：

```python
class CustomModel(Base):
    __tablename__ = "models"
    id: int PK
    model_id: str unique            # 内部 id（如 custom-llama3）
    name: str                       # 显示名
    provider: str                   # provider id，或 "custom"/"openai_compatible"
    model_name: str                 # 上游模型名
    api_base: str                   # 端点
    api_key: str
    max_tokens: int = 4096
    temperature: float = 0.7
    priority: int = 0
    enabled: bool = True
    created_at / updated_at
```

`main.py _ensure_schema` 追加建表迁移（create_all 自动建新表，无需 ALTER）。

### 模型加载合并（`_init_models` 重构）

1. 内置默认：遍历 `PROVIDERS`，生成内置 `ModelConfig`（api_key 走 `_get_api_key(env, "api_key_<provider>")`）
2. 覆盖 base：若 settings 存在 `api_base_<provider>` 则覆盖默认 base
3. 追加自定义：读取 `models` 表 `enabled=True` 行 → `ModelConfig`
4. `reload_models()` 不变（重跑合并）

## 五、后端 API 增补/改造（`app/api/models.py`）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/models/providers` | 改造：从注册表动态返回（含 free 标识） |
| GET | `/api/models` | 现有可用模型列表，保留（现在会包含已启用且有 key 的自定义模型） |
| GET | `/api/models/config` | 新：返回 providers（key 掩码）+ 自定义模型列表（key 掩码） |
| POST | `/api/models/custom` | 新：创建自定义模型 |
| PUT | `/api/models/custom/{id}` | 新：更新（enabled/name/model_name/api_base/api_key/max_tokens） |
| DELETE | `/api/models/custom/{id}` | 新：删除 |
| PUT | `/api/models/provider-key` | 新：`{provider, api_key, api_base?}` → 写 `settings`（api_key_<p> / api_base_<p>），触发 reload |
| POST | `/api/models/reload` | 保留 |

**安全**：
- GET 一律掩码 api_key（`已配置`/`••••<last4>`），只回传是否有值，不回传明文
- 前端输入框留空 = 保持原值；有值 = 覆盖
- `/api/settings` GET 改造：**不再返回 `api_key_*` 明文**（改为掩码或省略），现有 SettingsPanel 读取处同步改造

## 六、前端：SettingsPanel 模型页改造

`frontend/src/components/panels/SettingsPanel.tsx` 模型区块重写 + 新增 hook：

1. 新建 `frontend/src/hooks/useModelConfig.ts`：封装 config/custom/provider-key 三组 API
2. Provider 卡片列表（来自 `/api/models/providers`）：
   - 每行：名称 + 免费徽标 + API Key（password，留空=保持）+ api_base 覆盖输入 + 保存按钮（或统一批量保存）
   - 保存 → `PUT /api/models/provider-key` → 触发 reload → `useModels` 刷新
3. 自定义模型区块：
   - 现有列表（名称/provider/model_name/enabled 开关/删除按钮）
   - "添加自定义模型"表单：name、provider（下拉含 openai_compatible）、model_name、api_base、api_key、max_tokens
4. 默认模型下拉：`useModels` 数据不变，兜底改 `qwen-flash`
5. 翻译：`zh-CN.json` / `en-US.json` 增补"免费/自定义模型/provider-key/掩码提示"等文案

## 七、测试与回归

1. 单元：`_init_models` 合并逻辑（内置 + 自定义 + base 覆盖 + key 掩码）
2. API 集成（TestClient，沿用 phase_* 模式，sqlite 临时库）：
   - custom model CRUD 全链路
   - provider-key 写入 → reload → `/api/models` 出现该 provider 模型
   - GET config 不泄漏 key 明文
   - 启动迁移：`api_key_mimo` 被删、Agent 响应不再含 default_model、settings default_model=qwen-flash
3. 回归：Phase A / B-1 / B-2 / C 四套全绿（涉及 chat.py/模型加载，重点回归）

## 八、交付物

- 修改：`model_providers.py`(新)、`models/agent.py`、`services/model.py`、`api/models.py`、`api/agents.py`、`api/settings.py`、`api/chat.py`、`core/config.py`、`main.py`、`seed_agents.py`、`.env`、SettingsPanel.tsx、useModelConfig.ts(新)、useAgents.ts、AgentListPanel.tsx、useMessages.ts、locales×2
- 测试：新增 `test_model_config_phase_d.py`（或并入现有），更新说明文档

## 风险与注意

- **删除 Agent.model 是 API 破坏性变更**（`/api/agents` 响应少一个字段）：前端唯一消费方 AgentListPanel 同步改，无其他影响；V1 无外部 API 消费者，风险可控
- DB 遗留孤儿列：SQLAlchemy 只映射 ORM 声明列，遗留列无害；DROP COLUMN 为可选项，先观察
- 4 家新 provider 的默认 base/模型名来自公开资料，**需用户核实**；无 key 前不可见，不阻塞
- `/api/settings` 不再明文返回 key 属破坏性变更，前端同步改，确保不回归（SettingsPanel 当前从 settings 读 key 预填，改造后改为掩码/留空）
- `_apply_reasoning_payload` 仅 deepseek/glm/qwen 有特殊字段，其余走默认，自定义模型默认无思考增强
- 仅删 MiMo key 后，`mimo-v2.5-pro` 仍存在于注册表（无 key 隐藏），前端 provider 列表仍显示"小米 MiMo"空 key 输入，属预期

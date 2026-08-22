# MFKChat — 迷你 Agent 对话系统

一个贴近 MfkAgent 真实后端的自包含小型工程，用于 Agent 自主能力基准测试。

## 技术栈

- Python 3.10+ / FastAPI / SQLAlchemy 2.x / Pydantic v2
- 数据层：SQLite（生产用文件，测试用内存）
- 测试：pytest + fastapi TestClient

## 功能模块

| 模块 | 说明 | 对应真实系统 |
|---|---|---|
| Agent | Agent 档案（身份/人格/能力） | Agent 表 |
| Chat / Message | 对话会话与消息（含 timeline） | Chat / Message |
| Memory | 记忆项（global/agent/project 作用域） | MemoryItem |
| Context | 系统提示词组装（身份+人格+记忆+工具建议） | ContextBuilder |
| Intent | 用户意图识别（chat/task/file/...） | IntentAnalyzer |
| Tokens | token 估算（用于上下文水位） | count_tokens |

## 快速开始

```bash
pip install -r requirements.txt
python run.py                  # 启动服务 127.0.0.1:8000
python -m pytest tests -q      # 跑测试
```

## 目录结构

```
mfkchat/
├── app/
│   ├── main.py            # FastAPI 入口
│   ├── database.py        # 引擎 / 会话
│   ├── models.py          # ORM 模型（Agent/Chat/Message/Memory）
│   ├── schemas.py         # Pydantic 模型
│   ├── core/              # 纯业务逻辑（intent/tokens/context/memory）
│   ├── services/          # 编排层（chat_service / memory_service）
│   └── api/               # HTTP 路由层
├── tests/                 # 测试套件
├── requirements.txt
├── config.py
└── run.py
```

## 设计约定

- 服务层不依赖 FastAPI，可独立单测。
- API 层薄，只做参数解析与响应封装。
- 所有写操作必须经过服务层，禁止路由直连 ORM 写库。
- 意图识别、token 估算、上下文组装均为确定性纯函数。

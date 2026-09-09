# ⚡ MfkAgent — 本地多智能体自主协作桌面工作站

<p align="center">
  <img src="https://img.shields.io/badge/Next.js-16.0-black?style=flat-square&logo=next.js" alt="Next.js">
  <img src="https://img.shields.io/badge/FastAPI-0.110-009688?style=flat-square&logo=fastapi" alt="FastAPI">
  <img src="https://img.shields.io/badge/Electron-Desktop-47848F?style=flat-square&logo=electron" alt="Electron">
  <img src="https://img.shields.io/badge/Architecture-Multi--Agent-blue?style=flat-square" alt="Multi-Agent">
  <img src="https://img.shields.io/badge/License-MIT-green?style=flat-square" alt="License">
</p>

<p align="center">
  <b>本地沙箱安全执行 · 写后程序化自验 · 银行级风控审批 · 多模型自由聚合 · 专属专家 Agent 协作</b>
</p>

---

## 💡 为什么选择 MfkAgent？

大多数 Agent 工具仅生成代码片段，遇到运行报错仍需人工手动调试。  
**MfkAgent 致力于打造从代码编写、环境执行到结果验收的真正闭环：**

1. 🛠️ **TDD 自动化测试驱动开发与程序化自验 (Phase E4)**  
   - 提供隔离沙箱，支持文件读写、增量补丁 (`apply_patch` / `edit_file`) 与命令执行；
   - 写入文件后自动触发磁盘回读一致性比对；编写完工程代码后，自主调起本地测试套件验证退出码，全部通过后方完成交付。
2. 🛡️ **双轨 Command Risk Engine 银行级风控审批**  
   - 只读安全命令智能放行；涉及底层系统执行与高危修改时，毫秒级熔断并弹出结构化审批卡片，兼顾极客全自主与系统安全。
3. 🎭 **结构化专家 Agent 矩阵 (Persona Engine)**  
   - **「安」**：能干活、会吐槽、直击要害的通用技术助手；
   - **「固本」**：恪守最小侵入原则的全栈软件工程师；
   - **「知方」**：专注 UI 设计系统与前端组件研发工程师；
   - **「明鉴」**：负责架构评估与系统审查的治理专家；
   - **「笔神」**：擅长多模态表达与高级文案叙事创作者。
4. ⚡ **多模型统一协议与本地聚合路由**  
   - 兼容标准 API 接口，灵活接入各类商业大模型与本地开源大模型（如 Ollama、LocalAI 等），支持局域网移动端与桌面端双向互通。

---

## 🏗️ 核心架构拓扑 (Architecture)

```
                       ┌───────────────────────────────┐
                       │     Desktop / Mobile UI       │
                       │   (Next.js 16 + Electron)     │
                       └──────────────┬────────────────┘
                                      │ REST / SSE Stream
                       ┌──────────────▼────────────────┐
                       │      MfkAgent Core Engine     │
                       │   (AgentRuntime + TaskGraph)  │
                       └───────┬──────────────┬────────┘
                               │              │
        ┌──────────────────────▼───┐      ┌───▼──────────────────────┐
        │    Tool Runtime & Sandbox│      │ Model Routing Engine     │
        │ ├── Safe File R/W/Patch  │      │ ├── Commercial LLM APIs  │
        │ ├── Risk Engine Approval │      │ ├── Local / Open Models  │
        │ └── Automated TDD Verify │      │ └── Custom Proxy Gateway │
        └──────────────────────────┘      └──────────────────────────┘
```

---

## 🚀 30 秒极速上手 (Quick Start)

### 1. 克隆项目
```bash
git clone https://github.com/3220389580/Mfkagent.git
cd Mfkagent
```

### 2. 一键启动
```bash
# 双击根目录下的启动脚本：
start.bat
```
脚本将自动拉起 Python 后端与桌面客户端视窗。

### 3. 访问与交互
- 桌面客户端将自动呈现；
- 亦可通过浏览器访问本地服务：`http://127.0.0.1:8001`。

---

## 📄 开源许可证

本项目基于 [MIT License](LICENSE) 协议开源。欢迎提交 Issue 与 Pull Request！

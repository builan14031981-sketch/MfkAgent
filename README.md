# ⚡ MfkAgent — 真正能干活的本地多智能体桌面工作站

<p align="center">
  <img src="https://img.shields.io/badge/Next.js-16.0-black?style=flat-square&logo=next.js" alt="Next.js">
  <img src="https://img.shields.io/badge/FastAPI-0.110-009688?style=flat-square&logo=fastapi" alt="FastAPI">
  <img src="https://img.shields.io/badge/Electron-Desktop-47848F?style=flat-square&logo=electron" alt="Electron">
  <img src="https://img.shields.io/badge/Model-Gemini_3.8_Flash_%7C_DeepSeek-blue?style=flat-square" alt="Models">
  <img src="https://img.shields.io/badge/License-MIT-green?style=flat-square" alt="License">
</p>

<p align="center">
  <b>真沙箱读写 · 写后程序化自验 · 银行级风控审批 · 本地网关聚合 · 懂工程与审美的私有 Agent 团队</b>
</p>

---

## 💡 为什么选择 MfkAgent？（不仅是聊天，而是闭环交付）

很多 Agent 工具只会给你生成一段充满 Bug 的半成品代码，然后丢给你自己去修。  
**MfkAgent 彻底打破了这种“伪自动化”：**

1. 🛠️ **真·TDD 自动化测试驱动开发闭环（Phase E4）**  
   - 拥有本地沙箱文件读写、增量补丁（`apply_patch` / `edit_file`）与命令执行。
   - Agent 写入文件后，系统**自动进行磁盘回读一致性比对**；Agent 编写完工程后，会**自主调起单元测试并分析退出码**，全部通过才向你交差。
2. 🛡️ **双轨 Command Risk Engine 银行级风控审批**  
   - 只读命令智能放行；涉及系统级外部指令、文件改动风险时，**毫秒级挂起并弹出结构化审批卡**，真正做到“极客放权而不失控”。
3. 🎭 **有血有肉的专家 Agent 矩阵（Persona Engine）**  
   - **「安」**：能干活、会吐槽、直击要害的技术宅好友；
   - **「固本」**：恪守最小侵入原则的高级软件开发工程师；
   - **「拾色」**：掌握 47 种专业视觉美学（昭和特摄、赛博机械神性、诺兰冷工业、王家卫霓虹、爱死机全系）的图像与概念底座；
   - **「作家 / 听澜」**：懂战术心流（塔科夫/暗区突围）、小人物共鸣与电影级影视分镜的高级叙事引擎。
4. ⚡ **本地零配置网关与多模型自由聚合**  
   - 本地零门槛聚合 CLIProxyAPI、Gemini 3.8 Flash、DeepSeek-V4、Qwen、Claude 等模型池，局域网安卓端与桌面端双向互通，Token 随便花！

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
        │    Tool Runtime & Sandbox│      │ Model Routing Gateway    │
        │ ├── Safe File R/W/Patch  │      │ ├── Gemini 3.8 Flash     │
        │ ├── Risk Engine Approval │      │ ├── DeepSeek-V4 / Qwen   │
        │ └── Automated TDD Verify │      │ └── Local Proxy Gateway  │
        └──────────────────────────┘      └──────────────────────────┘
```

---

## 🚀 30 秒极速上手 (Quick Start)

### 1. 克隆仓库与依赖
```bash
git clone https://github.com/builan14031981-sketch/MfkAgent.git
cd MfkAgent
```

### 2. 一键启动全套服务
```bash
# 双击根目录的 start.bat 或终端执行：
start.bat
```
`start.bat` 会自动探测并启动本地模型网关、FastAPI 后端与 Electron 桌面客户端。

### 3. 访问与交互
- 桌面客户端将自动弹出；
- 亦可通过浏览器直接访问管理后台：`http://127.0.0.1:8001`。

---

## 📦 真实场景实战落地库

项目内置专属资产库规范（`E:\智慧项目\资产库`），已实测沉淀多项高价值成果：
- **🎮 硬核战术射击自动剪辑**：支持从 40 分钟《逃离塔科夫》/《暗区突围》录像中，基于 PCM 瞬态能量滑窗与视频火光自适应提取高光对枪，一键生成 DaVinci Resolve / Premiere CMX 3600 EDL 剪辑轨道。
- **🎬 特摄与假面骑士概念视觉**：涵盖双层菲涅尔棱镜复眼、渐开线变身驱动器机械设计与昭和微缩模型工业级 Prompt 矩阵。
- **🔬 3DGS 工业资产管线**：3D 高斯飞溅、NeRF、Hunyuan3D 与 Substance Painter 烘焙工业级调研全案。

---

## 📄 开源许可证

本项目基于 [MIT License](LICENSE) 协议开源。欢迎提交 Issue 与 Pull Request！

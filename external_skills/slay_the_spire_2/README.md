# 《杀戮尖塔2》（Slay the Spire 2）专属决策 Agent 使用指南

本套体系数据 **100% 提取自你电脑本地运行的《杀戮尖塔2》官方游戏本体包（`SlayTheSpire2.pck`）**，零幻觉。核心思路：把精确数据查询交给本地工具 `engine.py`，AI 用到哪条查哪条，不把几百 KB 数据硬塞进上下文。

---

## 📁 分享给 AI 的文件夹（`杀戮尖塔SKILL/`）

| 文件 | 说明 |
|---|---|
| 🧠 `PROMPT_FOR_ANY_AI.md` | **Agent 角色设定与推演 Prompt**，粘进任意 AI 的 System Instructions |
| 🗺️ `INDEX.md` | 3KB 地图：有哪些库、查询命令怎么敲（AI 自己读） |
| ⚡ `engine.py` | 查询工具：运行命令即可拿到卡牌/遗物/药水/怪物/算杀的精确数据 |
| 🗃️ `knowledge/cards.json` | 官方全量卡牌库（1427，含中文名） |
| 🗃️ `knowledge/powers.json` | 官方能力与 Buff/Debuff 库（277） |
| 🗃️ `knowledge/relics.json` | 官方遗物库（**304**，含中文名+效果） |
| 🗃️ `knowledge/potions.json` | 官方药水库（**65**，含中文名+效果） |
| 🗃️ `knowledge/monsters.json` | 官方敌人库（**114**：16 Boss / 14 精英 / 84 普通，含真实 HP、招式循环、意图伤害、格挡与施加状态） |
| 📘 `README.md` | 本说明 |

> `knowledge/*.json` 只给 `engine.py` 读取，**不要让 AI 当文本通读**（PROMPT 已强制约束）。

## 🛠️ 造数据与复现脚本（不分享）

`杀戮尖塔SKILL_build/`：含 `extract/`（pck 解包、zhs 本地化提取、怪物/遗物/药水重建脚本、原始 `zhs/*.json`）、`run_sts2_advisor.py`（本地命令行陪玩终端）、`STS2_CARD_KNOWLEDGE_BASE.md`（离线兜底知识库）。需要重抽数据时才用，不必发给 AI。

---

## 🚀 在 Agent 平台怎么用？

**一次性配置**
1. 把 `PROMPT_FOR_ANY_AI.md` 全文粘进平台的「系统指令 / System Prompt」。
2. 把整个 `杀戮尖塔SKILL` 文件夹上传/挂载给 Agent（让它拿到 `engine.py` + `knowledge/`）。
3. **开启代码执行**（ChatGPT 的「高级数据分析 / Code Interpreter」、Claude 的代码执行等开关）——`engine.py` 靠它运行。

**日常对话（直接说人话，不用敲命令）**

| 想问的 | 直接说 |
|---|---|
| 三选一 | “这三张选哪张：群蛇形态 / 余像 / 涂毒” |
| 某怪怎么打 | “碾碎爪该怎么打？留多少格挡？” |
| 算杀 | “我易伤，算一下 Crusher 未来 3 回合伤害” |
| 遗物/药水 | “赤牛这个遗物强吗？”“灰水药水什么效果？” |
| 路线/商店 | “这层该贪精英还是避战？”“这个店值不值得买？” |

- **截图**：游戏里截一张卡牌/遗物/怪物图直接发给他，他会读图里名字 → 自动 `engine.py` 查库 → 分析。
- AI 答得不对时，提醒一句“用 engine 查一下”，它会去跑工具核实，不再瞎编。

**本地命令行（可选）**：想脱离平台自己跑，用 `杀戮尖塔SKILL_build/run_sts2_advisor.py`，支持 `查 怪物 Crusher`、`算杀 Crusher 3 易伤` 等。

---

### 查询命令速查（AI 内部使用）
```
python engine.py monster <名称>          # 敌人 HP / 招式循环 / 意图伤害（中英文名均可）
python engine.py card <名称>             # 查卡牌或能力
python engine.py relic <名称>            # 查遗物
python engine.py potion <名称>           # 查药水
python engine.py sim <怪物> <回合> [vuln] # 未来 N 回合承伤推演（vuln=易伤×1.5）
```

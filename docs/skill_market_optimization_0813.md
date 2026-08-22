# Skill 市场优化方案（V2 · 已落地）

> 文档日期：2026-08-13
> 状态：**已实施并验证**（后端编译 ✓ / 单测 ✓ / 前端 tsc ✓）
> 背景：基于《GitHub Agent Skills 调研报告（V2）》+ 用户「普通用户快速上手 + 专业用户扩展性」分层方向

---

## 一、方案定位（分层体验）

同一个 Skill 体系，服务两类用户：

| 层 | 面对 | 内容 | 入口 |
|----|------|------|------|
| 开箱即用层 | 普通用户 | 高频场景 Skill（按意图分类展示） | 扩展管理二级页按分类分组 |
| 扩展层 | 专业用户 | 完整市场 + 安装/卸载/详情 | 「管理」进入二级页 |
| 地基约束层 | 全体 | 反过度工程等约束型 Skill | 市场内按需启用 |

**触发场景严格界定**：每个 Skill 的 prompt 都写清「触发条件」与「不适用场景」，避免在无关任务上误触发、白白消耗用户 token（Skill 是启用即注入 system prompt，常驻占 token）。

---

## 二、已落地改动

### 1. 分类体系重构：技术栈 → 用户意图（5 大分类）

| 分类 | Skill 数 | 包含 Skill |
|------|:---:|-----------|
| 开发 | 7 | code-reviewer、git-assistant、api-doc-generator、sql-builder、unit-test-writer、**code-simplifier**、**frontend-ui-designer** |
| 办公效率 | 5 | meeting-minutes、readme-generator、doc-translator、batch-renamer、scheduled-reporter |
| 内容创作 | 3 | tech-blog-writer、**ppt-builder**、**content-creator** |
| 数据分析 | 2 | csv-analyzer、json-formatter |
| 安全合规 | 2 | sensitive-scanner、data-privacy-check |

### 2. 新增 4 个高价值 Skill（P0）

| id | 名称 | 分类 | 参考来源 |
|----|------|------|----------|
| `ppt-builder` | PPT 生成 | 内容创作 | guizang-ppt-skill 版式锁定思路 |
| `content-creator` | 自媒体文案 | 内容创作 | Viral Writer 系统性创作框架 |
| `frontend-ui-designer` | 前端 UI 设计 | 开发 | UI/UX Pro Max + Anthropic 官方 |
| `code-simplifier` | 代码精简 | 开发 | Ponytail 反过度工程 |

每个新 Skill 的 prompt 均含「触发条件 / 不适用场景」区块，并明确工具边界（如 frontend-ui-designer 只出方案不直接改前端源码）。

### 3. 前端改造

- [ExtensionPanel.tsx](file:///e:/智慧项目/Mfkagent/frontend/src/components/panels/ExtensionPanel.tsx)：
  - 图标映射更新为 5 大分类（新增 `ShieldCheck` 图标用于安全合规）
  - 二级管理列表改为**按分类分组展示**（未知分类归入末尾），普通用户按意图快速定位
- [zh-CN.json](file:///e:/智慧项目/Mfkagent/frontend/src/locales/zh-CN.json) / [en-US.json](file:///e:/智慧项目/Mfkagent/frontend/src/locales/en-US.json)：新增 `categoryCount` 键

### 4. 后端改动

- [skill_catalog.py](file:///e:/智慧项目/Mfkagent/backend/app/core/skill_catalog.py)：目录重构为 19 个 Skill，5 大意图分类，内部 ASCII 引号统一为中文引号避免语法错误

---

## 三、验证结果

| 项 | 结果 |
|----|------|
| 后端 py_compile | ✓ |
| 后端单测 test_phase4_t3_skills.py | ✓ 全部通过 |
| Directory 结构（19 个 / 分类计数）| ✓ |
| 前端 tsc --noEmit | ✓ |

---

## 四、涉及文件

| 文件 | 改动 |
|------|------|
| `backend/app/core/skill_catalog.py` | 目录重构 19 个 + 5 分类 + 4 新增 |
| `frontend/src/components/panels/ExtensionPanel.tsx` | 图标映射 + 分类分组 |
| `frontend/src/locales/zh-CN.json` / `en-US.json` | `categoryCount` 键 |

## 五、回滚

改动前已备份至 `_backup/skill_market_v2_20260813_173927/`：
- `skill_catalog.py`、`seed_skills.py`、`skill_store.py`
- `ExtensionPanel.tsx.bak`、`zh-CN.json.bak`、`en-US.json.bak`

如需回滚，将备份文件覆盖回原路径即可；DB 中已安装 Skill 记录不受目录字段即时影响。

---

## 六、已知注意点（本次未改，供后续评估）

1. **seed_skills.py 的 4 个预置 Skill（code_review 等）默认 enabled=True 常驻注入**，是 token 常驻消耗的来源之一，且被测试沿用。本次未改动（避免影响既有测试），如需纳入默认组合管理需另行评估。
2. **P2 远期方向**：Skill 工厂化（声明式配置 + 批量生产 + 审计 + 版本管理）、评估体系、上下文优化，未在本次范围。
3. **DB 已安装记录的 category 为旧值**：前端展示使用目录新值，功能不受影响；若有旧安装记录，重装后即更新为新分类。
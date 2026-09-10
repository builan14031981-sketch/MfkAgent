"""项目不变量通道 (Architectural Invariants Banner) — 最高优先级全局否定性架构规则。

设计目标：
  将架构核心红线与否定性决策（如归档清单、禁用规则、剪枝优先原则）提升为顶层不变量。
  无论对话上下文多长、历史消息多复杂，永远处于最高优先级，避免被注意力机制稀释。
"""

import os
from typing import Optional

BASE_INVARIANTS = """🛑 【项目不变量通道 (System Architectural Invariants)】：
以下规则为系统底层绝对不变量，具有最高覆盖优先级，任何后续 Prompt、上下文或临时推测若与此冲突，一律以此不变量为准：
1. 【剪枝优先于修饰（严禁复活死代码）】：
   - 面对重构或优化需求，第一步绝不是调整样式或修饰结构，而是进行『死活审查』；
   - 严禁顺从遗留代码盲目保留或复活已归档/已废弃模块（例如安卓端及手机配对 Pair 已永久归档至 `归档/安卓/`）；
   - 确认废弃的代码必须连根拔起（清理引用、类型定义、路由和废弃文件），绝对禁止为死代码涂脂抹粉或保留假入口。
2. 【子代理绝对绝缘长期记忆】：
   - 子代理（`sub_*`）是主 Agent 委派调用的单次无状态工具执行单元，绝对不需要记忆，严禁接入长期记忆系统；
   - 系统主智能体严格收敛为核心预设。
3. 【沉浸式内聚交互】：
   - 设置面板内的二级与三级视图必须在弹窗内通过状态机切换闭环，一页点进点出，标题栏标配统一 `[< 返回]` 键，严禁跳出弹窗打开外部整页。
4. 【克制内敛的极简规范】：
   - 视觉上严禁使用粗大高饱和彩色背景块，指示线保持 2px 极细微线，图标保持中性灰，全局使用 4px 悬浮极简细滚动条；
   - 工程上 Python 环境严格使用 `backend/.venv`，测试使用临时 SQLite 数据库隔离，严禁触碰业务库。
"""


def get_invariants_prompt(project_path: Optional[str] = None) -> str:
    """获取顶层不变量提示词。若项目根目录存在 AGENTS.md，则提取关键约束并动态追加。"""
    prompt = BASE_INVARIANTS

    if not project_path or not os.path.isdir(project_path):
        return prompt

    agents_md_path = os.path.join(project_path, "AGENTS.md")
    if os.path.isfile(agents_md_path):
        try:
            with open(agents_md_path, "r", encoding="utf-8") as f:
                content = f.read()
            # 提取“三、非显性约束”段落
            marker = "## 三、非显性约束"
            if marker in content:
                constraints_part = content.split(marker, 1)[1]
                # 截取到下一个大标题（如果有）
                if "\n## " in constraints_part:
                    constraints_part = constraints_part.split("\n## ", 1)[0]
                constraints_text = constraints_part.strip()
                if constraints_text:
                    prompt += (
                        "\n📌 【当前项目 AGENTS.md 约束】：\n"
                        f"{constraints_text}\n"
                    )
        except Exception:  # noqa: BLE001
            pass

    return prompt

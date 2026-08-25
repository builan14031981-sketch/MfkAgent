"""全场景技能组合模板引擎 (Skill Combination Templates Engine)

解耦理念：
  - Skill 是「单点原子能力」（如水墨、Riso、排版、配色、包装等）；
  - Template 是「业务场景分子」（将多个原子 Skill 按组合规则与工作流编排为预置套装）；
  - Agent 是「化学家/编排者」（根据用户需求自动选用单 Skill 或套用 Template 组合编排）。

本模块预置 5 套图像风格组合模板，并为未来多模态全案（自媒体/电商/界面/文档）预留拓展机制。
"""
from typing import Dict, List, Any

PRESET_SKILL_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "template_chinese_editorial": {
        "id": "template_chinese_editorial",
        "name": "新国风编辑海报全案",
        "domain": "风格化图像/海报",
        "description": "融合东方水墨意境 + 极简 zine 版式 + Pantone 色卡标注，适用于文化展览、高端茶饮、新国风视觉。",
        "skills": ["eastern-ink-photo", "gc-minimal-zine-poster", "create-pantone-photo"],
        "recipe": (
            "1. 风格基底：使用 eastern-ink-photo 建立单色墨韵、淡墨渐变与米纸纹理；\n"
            "2. 版式秩序：套用 gc-minimal-zine-poster 的极简留白原则（负空间 ≥ 75%，单视觉焦点）；\n"
            "3. 配色标注：叠加 create-pantone-photo 的 3 色 Pantone 标签逻辑，在底部输出精确定色。"
        ),
    },
    "template_indie_music_kit": {
        "id": "template_indie_music_kit",
        "name": "独立厂牌音乐周边套装",
        "domain": "风格化图像/音乐周边",
        "description": "融合黑胶唱片产品图 + Riso 丝网印刷海报，适用于独立音乐厂牌、唱片发行与 Livehouse 宣传。",
        "skills": ["vinyl-image-generator", "photo-riso-poster"],
        "recipe": (
            "1. 产品物料：用 vinyl-image-generator 生成带有哑光纸板、唱片同心纹和中心标签的黑胶产品图；\n"
            "2. 宣传海报：用 photo-riso-poster 生成 2-3 色 Riso 丝网印刷海报，带有颗粒感与日期计数文字。"
        ),
    },
    "template_trendy_brand_pop": {
        "id": "template_trendy_brand_pop",
        "name": "潮牌与茶饮爆款海报套装",
        "domain": "风格化图像/商业促销",
        "description": "融合喜茶童趣涂鸦 + 超现实巨物拼贴，适用于茶饮促销、潮牌活动与年轻化爆款宣发。",
        "skills": ["heytea-style", "surreal-pop-collage"],
        "recipe": (
            "1. 主视觉：用 surreal-pop-collage 打造「一个不可能的悬浮巨物」+ 纯平涂色场；\n"
            "2. 细节涂鸦：融入 heytea-style 的童趣手绘线条、马卡龙配色与粗圆体产品标题。"
        ),
    },
    "template_travel_journal_duo": {
        "id": "template_travel_journal_duo",
        "name": "旅行记忆手账周边全套",
        "domain": "风格化图像/文创手账",
        "description": "融合旅行贴纸卡 + 透明底双卡套装，适用于旅游文创、景点纪念卡与手账周边。",
        "skills": ["travel-memory-sticker", "card-duo"],
        "recipe": (
            "1. 纪念卡：使用 travel-memory-sticker 产出包含 6 枚动机贴纸与 3 个关键词的横版纪念卡；\n"
            "2. 双卡输出：使用 card-duo 产出主卡 + 透明底独立贴纸双版本。"
        ),
    },
    "template_minimal_field_study": {
        "id": "template_minimal_field_study",
        "name": "极简学术考察插图与印章",
        "domain": "风格化图像/出版学术",
        "description": "融合极简三色实地考察插画 + 档案手压印章，适用于学术手册、品牌故事与出版配图。",
        "skills": ["photo-to-minimal-illustration", "skill-make-photo-stamp"],
        "recipe": (
            "1. 插图核心：用 photo-to-minimal-illustration 提取细黑轮廓线，严格使用 3 色与无阴影平涂；\n"
            "2. 档案质感：用 skill-make-photo-stamp 搭配右侧暖白纸面与手压圆形印章。"
        ),
    },
}


def get_template_prompt_fragment() -> str:
    """生成给 Agent 注入的预置组合模板说明文本。"""
    lines = ["## 【预置美学组合模板 (Composition Templates)】\n"
             "当用户提出复合需求或要求整套设计时，可直接调用或组合以下模板方案：\n"]
    for tid, t in PRESET_SKILL_TEMPLATES.items():
        lines.append(f"### 模板：{t['name']} (`{t['id']}`)")
        lines.append(f"- **适用领域**：{t['domain']}")
        lines.append(f"- **描述**：{t['description']}")
        lines.append(f"- **组合技能**：{', '.join(t['skills'])}")
        lines.append(f"- **编排工作流**：\n{t['recipe']}\n")
    return "\n".join(lines)

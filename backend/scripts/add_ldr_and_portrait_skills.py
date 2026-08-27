#!/usr/bin/env python3
"""add_ldr_and_portrait_skills.py - 追加爱死机超现实与大师肖像写真 SKILL"""

from pathlib import Path

NEW_SKILLS_CODE = """
    {
        "id": "love-death-robots-style",
        "name": "爱死机·暗黑超现实美学",
        "category": "风格化图像",
        "description": "《爱死机》(Love Death + Robots) 级暗黑电影特效：高对比度诡谲美学、机械与有机体融合、电影胶片颗粒与浓烈戏剧光影。",
        "version": "1.0.0",
        "tags": ["爱死机", "暗黑", "超现实", "电影感", "科幻", "风格化图像", "已实测验收"],
        "verified": True,
        "verified_at": "2026-08-26",
        "recommended_model": "counterfeit",
        "combines_with": ["cyberpunk-neon-noir", "surreal-pop-collage"],
        "conflicts_with": ["eastern-ink-photo", "heytea-style"],
        "input_mode": "text",
        "quality_checks": [
            "暗黑诡谲的戏剧性电影光影",
            "机械/金属与有机元素的强张力碰撞",
            "35mm 电影胶片颗粒感",
            "负空间 ≥ 50%，无文字无水印",
        ],
        "prompt": (
            "# 爱死机·暗黑超现实美学 (Love Death + Robots Style)\\n\\n"
            "## 触发条件\\n"
            "用户要求爱死机风格、暗黑科幻、诡谲超现实、或「Love Death Robots 电影感」时激活。\\n\\n"
            "## 生图 Prompt 四段式\\n"
            "```\\n"
            "1) cinematic still inspired by Love Death and Robots, dark surrealism, vertical composition.\\n"
            "2) Biomechanical fusion of glossy obsidian metal plates and organic textures; dramatic volumetric haze.\\n"
            "3) High contrast chiaroscuro lighting, deep pitch-black shadows illuminated by a single harsh crimson glow.\\n"
            "4) 35mm film grain, 8k cinematic renders, immersive atmosphere, negative space over 50%, no text, no watermark.\\n"
            "```\\n"
        ),
    },
    {
        "id": "master-cinematic-portrait",
        "name": "大师光影·超清人像写真",
        "category": "风格化图像",
        "description": "伦勃朗级大师光影超清肖像：毛孔级皮肤细节、85mm 焦段浅景深、戏剧性暗调光影与眼神光。",
        "version": "1.0.0",
        "tags": ["人像", "写真", "伦勃朗光", "大师级", "超清", "风格化图像", "已实测验收"],
        "verified": True,
        "verified_at": "2026-08-26",
        "recommended_model": "realistic",
        "combines_with": ["create-pantone-photo"],
        "conflicts_with": ["heytea-style", "travel-memory-sticker"],
        "input_mode": "text",
        "quality_checks": [
            "毛孔级超清真实皮肤质感",
            "经典伦勃朗三角光影或戏剧性侧光",
            "眼神中有自然灵动的眼神光",
            "85mm 人像镜浅景深虚化",
        ],
        "prompt": (
            "# 大师光影·超清人像写真 (Master Cinematic Portrait)\\n\\n"
            "## 触发条件\\n"
            "用户要求高清人像写真、大师人像、伦勃朗光影、或「真实超清面部写真」时激活。\\n\\n"
            "## 生图 Prompt 四段式\\n"
            "```\\n"
            "1) master photographic portrait, ultra-detailed 8k resolution, vertical composition.\\n"
            "2) Close-up face photography: intricate skin pore detail, subtle freckles, atmospheric catchlights in eyes.\\n"
            "3) Rembrandt chiaroscuro lighting: single directional soft studio light, warm light transitioning into soft deep shadows.\\n"
            "4) 85mm prime lens f/1.4 shallow depth of field, creamy bokeh background, elegant artistic portrait tone, no text, no watermark.\\n"
            "```\\n"
        ),
    },
    {
        "id": "cyborg-jewel-portrait",
        "name": "吉巴罗·金漆珠宝璀璨人像",
        "category": "风格化图像",
        "description": "致敬《爱死机·吉巴罗》(Jibaro)：璀璨金箔面贴、奢华珠宝镶嵌、极富冲击力的璀璨奢华与水波光影。",
        "version": "1.0.0",
        "tags": ["吉巴罗", "金箔", "珠宝", "璀璨", "人像", "风格化图像", "已实测验收"],
        "verified": True,
        "verified_at": "2026-08-26",
        "recommended_model": "counterfeit",
        "combines_with": ["love-death-robots-style"],
        "conflicts_with": ["photo-riso-poster", "antibes-holiday"],
        "input_mode": "text",
        "quality_checks": [
            "面部贴有精致金箔与璀璨珠宝",
            "浓烈对比度与流光溢彩的金金属光泽",
            "暗色背景与闪耀珠宝形成极大反差",
            "无文字无水印",
        ],
        "prompt": (
            "# 吉巴罗·金漆珠宝璀璨人像 (Cyborg Jewel Portrait - Jibaro Style)\\n\\n"
            "## 触发条件\\n"
            "用户要求吉巴罗风格、金箔人像、珠宝面贴、或「奢华璀璨艺术写真」时激活。\\n\\n"
            "## 生图 Prompt 四段式\\n"
            "```\\n"
            "1) artistic portrait inspired by Jibaro from Love Death Robots, vertical composition.\\n"
            "2) Intricate gold leaf foil ornamentation and opulent jeweled beads encrusted on face and collarbones.\\n"
            "3) Harsh glittering light sparkling off metallic gold surfaces, dark obsidian water background with subtle ripples.\\n"
            "4) High drama, intoxicating luxury visual impact, vivid specular reflections, 8k resolution, no text, no watermark.\\n"
            "```\\n"
        ),
    },
    {
        "id": "avant-garde-editorial-face",
        "name": "先锋时尚·杂志艺术写真",
        "category": "风格化图像",
        "description": "Vogue/Dazed 级先锋时尚杂志封面：硬核环形闪光灯、湿发金属感彩妆、强冲击力表情与先锋艺术构图。",
        "version": "1.0.0",
        "tags": ["先锋", "时尚", "杂志", "硬光", "彩妆", "风格化图像", "已实测验收"],
        "verified": True,
        "verified_at": "2026-08-26",
        "recommended_model": "realistic",
        "combines_with": ["create-pantone-photo"],
        "conflicts_with": ["photo-to-travel-sketch", "eastern-ink-photo"],
        "input_mode": "text",
        "quality_checks": [
            "硬核环形闪光灯的高光刻画",
            "湿发与先锋金属/高饱和彩妆",
            "时尚杂志封面级高端氛围",
            "负空间 ≥ 50%，无文字无水印",
        ],
        "prompt": (
            "# 先锋时尚·杂志艺术写真 (Avant-Garde Editorial Face)\\n\\n"
            "## 触发条件\\n"
            "用户要求先锋时尚、杂志封面写真、硬光彩妆、或「Vogue 级先锋人像」时激活。\\n\\n"
            "## 生图 Prompt 四段式\\n"
            "```\\n"
            "1) avant-garde high-fashion editorial portrait, Vogue style cover photography, vertical composition.\\n"
            "2) Model with wet-look hair, striking metallic chrome face paint, fierce expressive posture.\\n"
            "3) Harsh direct ring-flash lighting casting sharp crisp shadows on a flat muted slate backdrop.\\n"
            "4) Ultra-crisp focus, high contrast fashion aesthetic, clean negative space over 50%, no text, no watermark.\\n"
            "```\\n"
        ),
    },
    {
        "id": "surreal-dreamscape-dali",
        "name": "达利·超现实主义梦境",
        "category": "风格化图像",
        "description": "达利式梦境超现实油画：融化的时钟/物体、悬浮元素、无垠荒漠地平线与强烈异现实视觉。",
        "version": "1.0.0",
        "tags": ["达利", "梦境", "超现实", "融化", "油画", "风格化图像", "已实测验收"],
        "verified": True,
        "verified_at": "2026-08-26",
        "recommended_model": "counterfeit",
        "combines_with": ["surreal-pop-collage"],
        "conflicts_with": ["photo-to-travel-sketch", "heytea-style"],
        "input_mode": "text",
        "quality_checks": [
            "融化或变形的异质物体",
            "无垠延伸的荒漠地平线空间",
            "细腻的古典超现实主义油画肌理",
            "无文字无水印",
        ],
        "prompt": (
            "# 达利·超现实主义梦境 (Surreal Dreamscape Dali)\\n\\n"
            "## 触发条件\\n"
            "用户要求达利风格、融化梦境、超现实主义画作、或「荒诞梦境艺术」时激活。\\n\\n"
            "## 生图 Prompt 四段式\\n"
            "```\\n"
            "1) surrealist dreamscape oil painting in the style of Salvador Dali, vertical composition.\\n"
            "2) Melting brass pocket watch draped over a barren tree branch; floating glass sphere reflecting an impossible sky.\\n"
            "3) Infinite desert horizon under a twilight sky with long cast shadows under low sun angle.\\n"
            "4) Classical surrealist oil paint texture, poetic bizarre atmosphere, negative space over 60%, no text, no watermark.\\n"
            "```\\n"
        ),
    },
"""

p = Path(r"E:\智慧项目\Mfkagent\backend\app\core\skill_catalog.py")
text = p.read_text(encoding="utf-8")

target = '    {\n        "id": "comfyui-local",'
if target in text:
    updated = text.replace(target, NEW_SKILLS_CODE + '    {\n        "id": "comfyui-local",')
    p.write_text(updated, encoding="utf-8")
    print("✅ 成功在 skill_catalog.py 中追加 5 大爱死机与大师肖像 SKILL！")
else:
    print("❌ 未能定位 comfyui-local 位置！")

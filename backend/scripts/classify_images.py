"""用平台多模态模型(Gemini)对 E:\dowlaod 的 8 张图分类，
判断每张图属于哪个答辩场景主题 + 适合做封面/章节/内容，
并自动复制进对应 scenario 的 assets 文件夹（cover.png/section.png/content.png）。
"""
import asyncio
import json
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.model import ModelService

SRC_DIR = r"E:\dowlaod"
SCENARIOS = {
    "research": {
        "name": "调研报告",
        "dir": r"C:\Users\Asus\AppData\Local\Temp\opencode\ppt_multi_scenario_test\scenario_1_research\assets",
    },
    "product": {
        "name": "产品展示",
        "dir": r"C:\Users\Asus\AppData\Local\Temp\opencode\ppt_multi_scenario_test\scenario_2_product\assets",
    },
    "engineering": {
        "name": "工科小组汇报",
        "dir": r"C:\Users\Asus\AppData\Local\Temp\opencode\ppt_multi_scenario_test\scenario_3_group_project\assets",
    },
}
MODEL = "gemini-3.7-flash-high"

PROMPT = """你是一名 PPT 视觉素材分类助手。下面按顺序给出了多张图（图1、图2……）。
请为每一张图判断：它最适合作为三类答辩 PPT 中哪一个主题的素材，以及最适合充当的版面角色。

三个主题（theme）可选：
- research：调研报告类（校园/学习/问卷/清新蓝白/人文）
- product：产品展示类（科技产品/智能硬件/暗色科技感）
- engineering：工科小组汇报类（城市/交通/工程/蓝图/蓝白严谨）

三个版面角色（role）可选：
- cover：适合做封面大图（有氛围、可满版铺底、留白足以压字）
- section：适合做章节分隔大图（有延伸感、可做背景）
- content：适合做内容页右侧插图（主体聚焦、信息明确）

严格按照下面格式输出一个 JSON 数组，长度等于图片数量，顺序与输入图片一一对应，不要多余文字：
[
  {"idx":1,"theme":"research|product|engineering","role":"cover|section|content","desc":"中文一句话描述"},
  ...
]
"""


async def classify_batch(paths):
    ms = ModelService()
    images = [{"path": p, "mime": "image/jpeg"} for p in paths]
    msg = [{"role": "user", "content": PROMPT}]
    vc = {"images": images}
    for attempt in range(5):
        try:
            res = await ms.call_once(MODEL, msg, temperature=0.2, max_tokens=1500, vision_context=vc)
            text = getattr(res, "content", "") or ""
            s = text.find("[")
            e = text.rfind("]")
            if s != -1 and e != -1:
                return json.loads(text[s : e + 1])
            # 退一步找对象数组包裹
            s = text.find("{"); e = text.rfind("}")
            if s != -1 and e != -1:
                return json.loads(text[s : e + 1])
            return None
        except Exception as ex:
            err = str(ex)
            if "429" in err and attempt < 4:
                wait = 2 ** attempt * 8
                print(f"  [429 限流] 等待 {wait}s 重试...")
                time.sleep(wait)
                continue
            print(f"  [ERR] {err[:160]}")
            return None


async def main():
    all_files = [
        f for f in os.listdir(SRC_DIR)
        if f.lower().endswith((".png", ".jpg", ".jpeg"))
    ]
    all_paths = [os.path.join(SRC_DIR, f) for f in all_files]
    all_paths.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    files = all_paths[:8]
    print(f"文件夹共 {len(all_files)} 张图，取最新 {len(files)} 张，单次多模态批量分类...\n")
    infos = await classify_batch(files)
    results = []
    if not infos:
        print("分类失败（无返回）")
        return
    for i, p in enumerate(files):
        fn = os.path.basename(p)
        info = None
        for it in infos:
            if int(it.get("idx", 0)) == i + 1:
                info = it
                break
        if not info and i < len(infos):
            info = infos[i]
        print(f"{i+1}. {fn} -> {info}")
        results.append((fn, p, info))

    # 分配逻辑：每个 theme 需要 cover/section/content 各 1 张。
    # 规则：每个文件最多使用一次；缺位时先同 theme 补位，再同 theme 复用
    # （优先复用 section 作为 content，避免与 cover 重复），最后跨 theme 借。
    plan = {k: {"cover": None, "section": None, "content": None} for k in SCENARIOS}
    used_files = set()
    roles = ("cover", "section", "content")

    def put(theme, role, fn, p):
        plan[theme][role] = (fn, p)
        used_files.add(fn)

    # 第一轮：精确匹配（同文件不重复）
    for fn, p, info in results:
        if not info:
            continue
        th, role = info.get("theme"), info.get("role")
        if th in plan and role in roles and plan[th][role] is None and fn not in used_files:
            put(th, role, fn, p)

    # 第二轮：同 theme 内补齐空位（任意该 theme 的未用图）
    for th in plan:
        for role in roles:
            if plan[th][role] is None:
                for fn, p, info in results:
                    if info and info.get("theme") == th and fn not in used_files:
                        put(th, role, fn, p)
                        break

    # 第三轮：仍缺位者，同 theme 内复用一张已用图（优先 section，其次 cover，避免复刻 cover）
    for th in plan:
        for role in roles:
            if plan[th][role] is None:
                cand = None
                for pref in ("section", "cover", "content"):
                    if pref != role and plan[th][pref] is not None:
                        cand = plan[th][pref]
                        break
                if cand:
                    plan[th][role] = cand

    # 第四轮：万一同 theme 都无图，跨 theme 借未用图
    for th in plan:
        for role in roles:
            if plan[th][role] is None:
                for fn, p, info in results:
                    if fn not in used_files:
                        put(th, role, fn, p)
                        break

    print("\n=== 分配结果 ===")
    for th, sc in SCENARIOS.items():
        print(f"\n[{sc['name']}] -> {sc['dir']}")
        for role in ("cover", "section", "content"):
            v = plan[th][role]
            print(f"  {role}: {v[0] if v else '（缺失）'}")
            if v:
                os.makedirs(sc["dir"], exist_ok=True)
                src_ext = os.path.splitext(v[1])[1].lower() or ".png"
                dst = os.path.join(sc["dir"], f"{role}{src_ext}")
                # 转存为规范 PNG，避免扩展名与真实编码不符导致 pptx 读取失败
                try:
                    from PIL import Image as _PILImage
                    _im = _PILImage.open(v[1]).convert("RGB")
                    _im.save(os.path.join(sc["dir"], f"{role}.png"), "PNG")
                    dst = os.path.join(sc["dir"], f"{role}.png")
                except Exception:
                    shutil.copy(v[1], dst)
                print(f"    已复制 -> {dst}")


if __name__ == "__main__":
    asyncio.run(main())

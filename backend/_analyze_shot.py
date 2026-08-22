import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

def main():
    from PIL import Image
    from app.core.ui_probe_tools import analyze_screenshot
    shot = r"E:\智慧项目\portfolio-mfkagent\.ui_selfcheck\portfolio_desktop.png"
    tmp = r"C:\Users\Asus\AppData\Local\Temp\opencode\portfolio_small.png"
    im = Image.open(shot).convert("RGB")
    w, h = im.size
    max_w = 900
    if w > max_w:
        im = im.resize((max_w, int(h * max_w / w)), Image.LANCZOS)
    im.save(tmp, "PNG", optimize=True)
    print(f"downscaled: {w}x{h} -> {im.size[0]}x{im.size[1]}")
    prompt = (
        "请以专业 UI/UX 评审视角分析这张作品集网页截图，逐项给出评分(1-10)与改进建议：\n"
        "1. 排版工整度与错落感(非对称、栅格)\n"
        "2. 配色是否高级克制(中性底+单一强调色)\n"
        "3. 字体搭配是否好看(衬线标题+无衬线正文)\n"
        "4. 整体美感与高级感\n"
        "5. 明确列出需要改进的具体问题"
    )
    result = analyze_screenshot(r"E:\智慧项目\portfolio-mfkagent", tmp, prompt)
    print(result)

main()
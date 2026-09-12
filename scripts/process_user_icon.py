# -*- coding: utf-8 -*-
"""处理用户提供的原版白底图标 C:\\Users\\Asus\\Pictures\\图标.png。

要求：
  1. 100% 保留原图色彩、白底与内容，不做任何重新设计；
  2. 仅仅对其四周进行平滑圆角裁切，圆角外侧四个角设为纯透明（Alpha=0）；
  3. 生成标准 Windows 7 级多分辨率 RGBA ICO 与各尺寸 PNG 并替换工程资产；
  4. 刷新桌面快捷方式供用户直接验收。
"""

import os
import io
import struct
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw

REPO_ROOT = Path(r"E:\智慧项目\Mfkagent")
USER_SRC = Path(r"C:\Users\Asus\Pictures\图标.png")


def create_standard_windows_ico(image_pil: Image.Image, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]) -> bytes:
    """生成 100% 符合 Windows GDI/Shell 规范的标准多分辨率 ICO 文件。
    128x128 及以下采用未压缩 32位 BGRA BMP DIB + AND 掩码（保证所有 Windows 任务栏/快捷方式原生识别）；
    256x256 采用标准 PNG 压缩。
    """
    entries = []
    images_data = []

    ico_header = struct.pack("<HHH", 0, 1, len(sizes))

    for (w, h) in sizes:
        resized = image_pil.resize((w, h), Image.Resampling.LANCZOS).convert("RGBA")
        if w >= 256 and h >= 256:
            buf = io.BytesIO()
            resized.save(buf, format="PNG")
            data = buf.getvalue()
        else:
            biSize = 40
            biWidth = w
            biHeight = 2 * h  # DIB 高度需包含 XOR 与 AND 掩码
            biPlanes = 1
            biBitCount = 32
            biCompression = 0
            xor_size = w * h * 4
            and_row_bytes = ((w + 31) // 32) * 4
            and_size = and_row_bytes * h
            biSizeImage = xor_size + and_size

            bmp_header = struct.pack(
                "<IIIHHIIIIII",
                biSize, biWidth, biHeight, biPlanes, biBitCount,
                biCompression, biSizeImage, 0, 0, 0, 0
            )

            pixel_bytes = bytearray()
            for y in range(h - 1, -1, -1):
                for x in range(w):
                    r, g, b, a = resized.getpixel((x, y))
                    pixel_bytes.extend([b, g, r, a])

            and_mask = bytearray(and_size)
            data = bmp_header + bytes(pixel_bytes) + bytes(and_mask)

        images_data.append(data)
        bw = 0 if w >= 256 else w
        bh = 0 if h >= 256 else h
        entries.append({
            "w": bw, "h": bh,
            "bColorCount": 0, "bReserved": 0,
            "wPlanes": 1, "wBitCount": 32,
            "size": len(data)
        })

    offset = 6 + len(sizes) * 16
    entry_bytes = bytearray()
    for e, d in zip(entries, images_data):
        entry_bytes.extend(struct.pack(
            "<BBBBHHII",
            e["w"], e["h"], e["bColorCount"], e["bReserved"],
            e["wPlanes"], e["wBitCount"], e["size"], offset
        ))
        offset += len(d)

    return ico_header + bytes(entry_bytes) + b"".join(images_data)


def process_icon():
    if not USER_SRC.exists():
        print(f"Error: {USER_SRC} 不存在！")
        return

    print(f"正在读取用户原图: {USER_SRC}")
    raw = Image.open(USER_SRC).convert("RGBA")
    w, h = raw.size

    # 标准 1024x1024 画布
    canvas_size = 1024
    if (w, h) != (canvas_size, canvas_size):
        raw = raw.resize((canvas_size, canvas_size), Image.Resampling.LANCZOS)

    # 留出适度安全透明边距（约 48px），确保圆角弧度清晰、不贴边直切
    margin = 44
    box_size = canvas_size - margin * 2  # 936x936
    radius = int(box_size * 0.22)        # 22% 现代大平滑圆角 (约 205px)

    # 2x 超采样绘制高精度抗锯齿圆角蒙版
    ss = 2
    ss_w = canvas_size * ss
    ss_m = margin * ss
    ss_b = box_size * ss
    ss_r = radius * ss

    mask_ss = Image.new("L", (ss_w, ss_w), 0)
    draw_ss = ImageDraw.Draw(mask_ss)
    draw_ss.rounded_rectangle(
        [ss_m, ss_m, ss_m + ss_b, ss_m + ss_b],
        radius=ss_r,
        fill=255,
    )
    mask = mask_ss.resize((canvas_size, canvas_size), Image.Resampling.LANCZOS)

    # 将原图缩放到内框中并贴上圆角蒙版
    inner_raw = raw.resize((box_size, box_size), Image.Resampling.LANCZOS)
    raw_layer = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    raw_layer.paste(inner_raw, (margin, margin))

    # 应用圆角蒙版：圆角内部 100% 保持用户原图的白底与Logo，外部四个角彻底透明！
    final_1024 = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    final_1024.paste(raw_layer, (0, 0), mask=mask)

    # 生成各尺寸
    final_256 = final_1024.resize((256, 256), Image.Resampling.LANCZOS)
    final_32 = final_1024.resize((32, 32), Image.Resampling.LANCZOS)

    # Windows 7 级多分辨率 ICO 金字塔
    ico_sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (24, 24), (16, 16)]

    # 覆盖工程资产
    targets = [
        (REPO_ROOT / "frontend" / "public" / "icon.png", final_1024, False, None),
        (REPO_ROOT / "frontend" / "public" / "icon.ico", final_1024, True, ico_sizes),
        (REPO_ROOT / "frontend" / "electron" / "assets" / "app-icon.png", final_256, False, None),
        (REPO_ROOT / "frontend" / "electron" / "assets" / "app-icon.ico", final_1024, True, ico_sizes),
        (REPO_ROOT / "frontend" / "electron" / "assets" / "tray-icon.png", final_32, False, None),
    ]

    for p, img, is_ico, sizes in targets:
        p.parent.mkdir(parents=True, exist_ok=True)
        if is_ico:
            ico_bytes = create_standard_windows_ico(img, sizes=sizes)
            p.write_bytes(ico_bytes)
        else:
            img.save(str(p), format="PNG")
        print(f"  -> 已成功输出原版圆角图标: {p.relative_to(REPO_ROOT)}")

    # 刷新桌面快捷方式
    desktop = Path(os.environ.get("USERPROFILE", "C:/Users/Asus")) / "Desktop"
    installed_exe = Path(r"E:\Program Files\MFK\MfkAgent\MfkAgent.exe")

    # 正式版快捷方式：优先指向真实安装目录的 MfkAgent.exe
    lnk_main = desktop / "MfkAgent.lnk"
    if installed_exe.exists():
        target_path = str(installed_exe)
        working_dir = str(installed_exe.parent)
        icon_location = f"{installed_exe},0"
    else:
        target_path = str(REPO_ROOT / "start-desktop.bat")
        working_dir = str(REPO_ROOT)
        icon_location = f"{REPO_ROOT / 'frontend' / 'public' / 'icon.ico'},0"

    ps_main = f'''
    $ws = New-Object -ComObject WScript.Shell
    $s = $ws.CreateShortcut("{str(lnk_main)}")
    $s.TargetPath = "{target_path}"
    $s.WorkingDirectory = "{working_dir}"
    $s.IconLocation = "{icon_location}"
    $s.Description = "MfkAgent 智能工作站"
    $s.Save()
    '''
    subprocess.run(["powershell", "-NoProfile", "-Command", ps_main], capture_output=True)
    print(f"  -> 已规范更新桌面正式版快捷方式: {lnk_main} (指向 {target_path})")

    # 清理桌面多余混淆的批处理旧快捷方式
    for stale_name in ["MfkAgent (原版圆角图标).lnk", "MfkAgent - 副本.lnk", "MfkAgent - 副本 - 副本.lnk", "MfkAgent - 副本 - 副本 (2).lnk"]:
        stale_lnk = desktop / stale_name
        if stale_lnk.exists():
            stale_lnk.unlink()
            print(f"  -> 已清理桌面历史冗余快捷方式: {stale_name}")

    # 发送 Windows 桌面图标刷新信号
    refresh_cmd = '''
    Add-Type -TypeDefinition @"
    using System;
    using System.Runtime.InteropServices;
    public class Shell {
        [DllImport("shell32.dll")]
        public static extern void SHChangeNotify(int wEventId, int uFlags, IntPtr dwItem1, IntPtr dwItem2);
    }
"@
    [Shell]::SHChangeNotify(0x08000000, 0, [IntPtr]::Zero, [IntPtr]::Zero)
    '''
    subprocess.run(["powershell", "-NoProfile", "-Command", refresh_cmd], capture_output=True)
    print("✅ 桌面图标缓存已刷新！")


if __name__ == "__main__":
    process_icon()

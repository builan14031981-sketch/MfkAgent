from fastapi import APIRouter

router = APIRouter()

FONTS = [
    {
        "id": "system",
        "name": "系统默认",
        "family": "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
        "description": "使用操作系统默认字体",
    },
    {
        "id": "source-han-sans",
        "name": "思源黑体",
        "family": "'Source Han Sans SC', 'Noto Sans SC', sans-serif",
        "description": "Adobe 与 Google 合作开发的开源中文字体",
        "cdn": "https://cdn.jsdelivr.net/npm/source-han-sans-sc@2.004/variable/SourceHanSansSC-VF.otf.woff2",
    },
    {
        "id": "lxgw-wenkai",
        "name": "霞鹜文楷",
        "family": "'LXGW WenKai', serif",
        "description": "开源中文楷体字体，适合阅读",
        "cdn": "https://cdn.jsdelivr.net/npm/lxgw-wenkai-webfont@1.7.0/style.css",
    },
    {
        "id": "ibm-plex-sans",
        "name": "IBM Plex Sans",
        "family": "'IBM Plex Sans', sans-serif",
        "description": "IBM 开发的现代无衬线字体",
        "cdn": "https://cdn.jsdelivr.net/npm/@fontsource/ibm-plex-sans@5.0.0/400.css",
    },
]


@router.get("")
async def list_fonts():
    return {"fonts": FONTS}


@router.get("/{font_id}")
async def get_font(font_id: str):
    for font in FONTS:
        if font["id"] == font_id:
            return font
    return {"error": "Font not found"}

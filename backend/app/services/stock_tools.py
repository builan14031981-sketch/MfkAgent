# -*- coding: utf-8 -*-
"""query_market —— 免费实时行情查询工具（腾讯行情接口，无需 API Key）。

数据源：腾讯财经 qt.gtimg.cn（免费、无鉴权、UTF-8/GBK 返回）。
用途：查询 A 股指数与个股实时行情（现价、涨跌幅、今开、昨收、成交量、成交额）。

设计约束（对齐 policy.py 数字诚实约束）：
- 只返回接口真实返回的数值，接口拿不到就明确写"未获取到"。
- 不拼接、不猜测任何非接口字段。
"""

import asyncio
from typing import Any, Dict, List

try:
    from .tools import Tool, ToolResult
except ImportError:  # 直接运行调试时
    from tools import Tool, ToolResult

# 常见指数代码映射（用户说"大盘/上证指数/沪深300"等友好名 → 腾讯代码）
INDEX_ALIASES = {
    "上证": "sh000001", "上证指数": "sh000001", "沪指": "sh000001", "大盘": "sh000001",
    "深证": "sz399001", "深证成指": "sz399001", "深成指": "sz399001",
    "创业板": "sz399006", "创业板指": "sz399006", "创指": "sz399006",
    "沪深300": "sh000300", "hs300": "sh000300",
    "中证500": "sh000905", "zz500": "sh000905",
    "科创50": "sh000688",
    "恒生指数": "hkHSI", "恒指": "hkHSI",
    "道琼斯": "usDJI", "纳斯达克": "usIXIC", "标普500": "usINX",
}

# 常见个股前缀映射（用户说"茅台/比亚迪"等名字 → 默认沪市/深市代码需用户给代码或搜索）
# 说明：个股靠名字无法免费稳定解析，工具只接受代码（如 600519 / 000001）或指数名。
# 若用户只给股票名，返回提示引导使用 web_search 查代码后带代码查询。


def _normalize_symbol(sym: str) -> str:
    """把用户输入规范化为腾讯代码格式。"""
    s = sym.strip().lower()
    # 直接命中指数别名
    if s in INDEX_ALIASES:
        return INDEX_ALIASES[s]
    # 6 位数字代码：按规则加前缀（6 开头沪市 sh，0/3 开头深市 sz，4/8 开头北交所 bj，5 开头沪基金 sh）
    if s.isdigit() and len(s) == 6:
        if s.startswith("6"):
            return f"sh{s}"
        if s.startswith(("0", "3")):
            return f"sz{s}"
        if s.startswith(("4", "8")):
            return f"bj{s}"
        if s.startswith("5"):
            return f"sh{s}"
    # 已经带前缀
    if s.startswith(("sh", "sz", "bj", "hk", "us")):
        return s
    return s


def _parse_tencent_field(raw: str) -> Dict[str, str]:
    """解析腾讯行情 v_xxx=\"...\" 一行，按 ~ 分隔提取关键字段。

    腾讯指数/个股字段索引（~ 分隔）：
      1  名称
      2  代码
      3  当前价
      4  昨收
      5  今开
      6  成交量(手)
      31 涨跌额
      32 涨跌幅(%)
      33 最高
      34 最低
    """
    if "=" not in raw:
        return {}
    body = raw.split("=", 1)[1].strip().strip('"').strip(";")
    parts = body.split("~")
    if len(parts) < 6:
        return {}
    out: Dict[str, str] = {
        "name": parts[1],
        "code": parts[2],
        "price": parts[3],
        "prev_close": parts[4],
        "open": parts[5],
        "high": parts[33] if len(parts) > 33 else "",
        "low": parts[34] if len(parts) > 34 else "",
        "change": parts[31] if len(parts) > 31 else "",
        "change_pct": parts[32] if len(parts) > 32 else "",
        "volume": parts[6] if len(parts) > 6 else "",
    }
    return out


class QueryMarketTool(Tool):
    """查询 A 股指数/个股实时行情（腾讯免费接口，无需 API Key）。"""

    def __init__(self):
        super().__init__(
            name="query_market",
            description=(
                "查询 A 股指数或个股的实时行情（现价/涨跌幅/今开/昨收/最高/最低/成交量）。"
                "支持指数名（如：上证指数、深证成指、创业板指、沪深300、恒生指数、道琼斯）"
                "或 6 位股票代码（如 600519、000001，自动识别沪/深/北交所）。"
                "当用户问'XX 股票/指数现在多少'、'大盘涨跌'、'XX 行情'等实时价格类问题时使用；"
                "返回的是接口实时数据，比网页搜索更准确。个股建议用户提供 6 位代码。"
            ),
            parameters={
                "type": "object",
                "properties": {
                    "symbols": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "指数名或 6 位股票代码列表，一次最多 5 个。例如 [\"上证指数\", \"600519\"]",
                    },
                },
                "required": ["symbols"],
            },
        )

    async def execute(self, **kwargs) -> ToolResult:
        symbols: List[str] = kwargs.get("symbols") or []
        if not symbols:
            return ToolResult(success=False, output="", error="请提供要查询的指数名或股票代码")
        if len(symbols) > 5:
            symbols = symbols[:5]

        codes = [_normalize_symbol(s) for s in symbols]
        q = ",".join(codes)
        url = f"https://qt.gtimg.cn/q={q}"
        headers = {
            "Referer": "https://finance.qq.com/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        }

        try:
            from app.core.proxy import build_httpx_client
            async with build_httpx_client(timeout=15.0, headers=headers) as client:
                resp = await client.get(url)
                text = resp.text
                # 腾讯接口 GBK 编码
                try:
                    text = resp.content.decode("gbk", errors="ignore")
                except Exception:
                    pass
        except Exception as e:
            return ToolResult(success=False, output="", error=f"行情接口请求失败: {str(e)}")

        rows: List[str] = []
        for line in text.split(";"):
            line = line.strip()
            if not line or "=" not in line:
                continue
            f = _parse_tencent_field(line)
            if not f:
                continue
            name = f.get("name") or f.get("code") or "未知"
            price = f.get("price") or "未获取到"
            chg = f.get("change") or "未获取到"
            pct = f.get("change_pct") or "未获取到"
            rows.append(
                f"{name}({f.get('code','')})：现价 {price}，涨跌 {chg}（{pct}%），"
                f"今开 {f.get('open') or '未获取到'}，昨收 {f.get('prev_close') or '未获取到'}，"
                f"最高 {f.get('high') or '未获取到'}，最低 {f.get('low') or '未获取到'}"
            )

        if not rows:
            return ToolResult(
                success=False,
                output="",
                error=f"未获取到行情数据（请确认代码/指数名是否正确，如 600519、上证指数）。原始返回: {text[:120]}",
            )

        summary = "【实时行情】\n" + "\n".join(rows)
        summary += "\n数据来源：腾讯财经行情接口（免费实时）"
        return ToolResult(success=True, output=summary)


if __name__ == "__main__":
    # 本地调试：python -m app.services.stock_tools
    async def _main():
        t = QueryMarketTool()
        r = await t.execute(symbols=["上证指数", "600519", "000001"])
        print(r.success)
        print(r.output)
        if r.error:
            print("ERR:", r.error)

    asyncio.run(_main())

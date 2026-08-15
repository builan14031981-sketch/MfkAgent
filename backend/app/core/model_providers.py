"""模型 Provider 注册表 — 数据驱动，替代 api/models.py / services/model.py / 前端的硬编码。

用法：
    from app.core.model_providers import PROVIDERS, PROVIDER_MAP

设计原则：
- 纯数据模块，不依赖任何 app 内部模块，便于前端 / 后端共享读取
- 每个 provider 的 api_key 通过 settings 表 api_key_<id> 配置，api_base 可用 api_base_<id> 覆盖
- free 标识仅作前端徽标展示，不参与风险/成本判定
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ProviderModel:
    id: str          # 内部模型 ID（模型选择器 / ModelService.models 的 key）
    upstream: str    # 上游 API 模型名（透传给官方接口）
    display_name: str = ""  # 前端展示名，为空时用 id
    supports_vision: Optional[bool] = None  # 模型级视觉能力：None=未指定（走命名推测+Provider回退），True/False=显式覆盖
    context_window: int = 256000  # 模型最大上下文窗口（token 数），默认 256K；未知模型保持默认


@dataclass(frozen=True)
class ProviderDef:
    id: str                 # provider 唯一 ID（对应 ModelProvider 枚举值）
    name: str               # 展示名
    free: bool              # 是否有免费额度（仅展示）
    default_api_base: str   # 默认 OpenAI 兼容端点
    models: tuple           # tuple[ProviderModel, ...]
    env_key: str            # settings 中环境变量属性名（如 FREELLMAPI_API_KEY）
    description: str = ""
    website: str = ""       # 官网链接（免费模型展示快捷入口）
    supports_vision: bool = False  # Phase 2: 是否支持多模态图片（OpenAI 兼容 image_url + base64 data URI）


PROVIDERS: list[ProviderDef] = [
    ProviderDef(
        id="deepseek",
        name="DeepSeek",
        free=False,
        default_api_base="https://api.deepseek.com/v1",
        env_key="DEEPSEEK_API_KEY",
        description="专注代码与对话的高性能模型",
        models=(
            ProviderModel("deepseek-v4-flash", "deepseek-v4-flash", context_window=1_048_576),
            ProviderModel("deepseek-v4-pro", "deepseek-v4-pro", context_window=1_048_576),
        ),
    ),
    ProviderDef(
        id="qwen",
        name="通义千问（阿里）",
        free=True,
        default_api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
        env_key="QWEN_API_KEY",
        description="阿里云大模型，支持多种场景",
        website="https://dashscope.aliyun.com",
        supports_vision=False,  # Provider 级默认不支持视觉；VL 模型由模型级显式覆盖
        models=(
            # 2026-08 最新旗舰：Qwen3.8-Max（思考模式）、Qwen3.7-Max（1M 上下文）
            ProviderModel("qwen3.8-max", "qwen3.8-max", "Qwen3.8 Max", context_window=1_048_576),
            ProviderModel("qwen3.7-max", "qwen3.7-max", "Qwen3.7 Max", context_window=1_048_576),
            ProviderModel("qwen3.7-plus", "qwen3.7-plus", "Qwen3.7 Plus", context_window=131_072),
            ProviderModel("qwen-max", "qwen-max", "通义千问 Max", context_window=32_768),
            ProviderModel("qwen-plus", "qwen-plus", context_window=131_072),
            ProviderModel("qwen-flash", "qwen-flash", context_window=131_072),
            ProviderModel("qwen-math-turbo", "qwen-math-turbo", "Qwen Math Turbo", context_window=131_072),
            ProviderModel("qwen-mt-flash", "qwen-mt-flash", "Qwen MT Flash", context_window=131_072),
            ProviderModel("deepseek-r1-distill-qwen-7b", "deepseek-r1-distill-qwen-7b", "DeepSeek R1 蒸馏 7B", context_window=131_072),
            ProviderModel("glm-5", "glm-5", "GLM-5", context_window=128_000),
            # VL 视觉模型（显式标记 supports_vision=True）
            ProviderModel("qwen3-vl-plus", "qwen3-vl-plus", "Qwen3 VL Plus", supports_vision=True, context_window=131_072),
            ProviderModel("qwen3-vl-flash", "qwen3-vl-flash", "Qwen3 VL Flash", supports_vision=True, context_window=131_072),
            ProviderModel("qwen3-vl-235b-a22b-thinking", "qwen3-vl-235b-a22b-thinking", "Qwen3 VL 235B Thinking", supports_vision=True, context_window=131_072),
            ProviderModel("qwen3-vl-32b-thinking", "qwen3-vl-32b-thinking", "Qwen3 VL 32B Thinking", supports_vision=True, context_window=131_072),
            ProviderModel("qwen3-vl-30b-a3b-thinking", "qwen3-vl-30b-a3b-thinking", "Qwen3 VL 30B A3B Thinking", supports_vision=True, context_window=131_072),
        ),
    ),
    ProviderDef(
        id="google",
        name="Google Gemini",
        free=True,
        default_api_base="https://generativelanguage.googleapis.com/v1beta/openai",
        env_key="GOOGLE_API_KEY",
        description="免费额度，所有模型均支持函数调用",
        website="https://aistudio.google.com",
        supports_vision=True,  # Gemini OpenAI 兼容端点原生支持 image_url
        models=(
            # 2026-08 最新：Gemini 3.6 Flash（GA）、Gemini 3.5 Flash（GA）
            ProviderModel("gemini-3.6-flash", "gemini-3.6-flash", "Gemini 3.6 Flash", context_window=1_048_576),
            ProviderModel("gemini-3.5-flash", "gemini-3.5-flash", "Gemini 3.5 Flash", context_window=1_048_576),
            ProviderModel("gemini-3.5-flash-lite", "gemini-3.5-flash-lite", "Gemini 3.5 Flash Lite", context_window=1_048_576),
            ProviderModel("gemini-3.1-flash-lite", "gemini-3.1-flash-lite", "Gemini 3.1 Flash Lite", context_window=1_048_576),
        ),
    ),
    ProviderDef(
        id="glm",
        name="智谱 AI（GLM）",
        free=True,
        default_api_base="https://open.bigmodel.cn/api/paas/v4",
        env_key="GLM_API_KEY",
        description="清华系大模型，性能优异",
        website="https://open.bigmodel.cn",
        supports_vision=False,  # GLM-4 纯文本模型不支持视觉；无 VL 子模型注册
        models=(
            # 2026-08 最新：GLM-5.1 / GLM-5（Agent 旗舰），GLM-4.7-Flash（永久免费）
            ProviderModel("glm-5.1", "glm-5.1", "GLM-5.1", context_window=200_000),
            ProviderModel("glm-5", "glm-5", "GLM-5", context_window=200_000),
            ProviderModel("glm-4.7", "glm-4.7", "GLM-4.7", context_window=200_000),
            ProviderModel("glm-4.7-flash", "glm-4.7-flash", "GLM-4.7 Flash（永久免费）", context_window=200_000),
        ),
    ),
    ProviderDef(
        id="moonshot",
        name="Moonshot（月之暗面）",
        free=True,
        default_api_base="https://api.moonshot.cn/v1",
        env_key="MOONSHOT_API_KEY",
        description="支持超长上下文的模型",
        website="https://www.moonshot.cn",
        models=(
            # 2026-08 最新：Kimi K2.7 Code（编程 Agent 旗舰）、Kimi K2.6（通用）
            ProviderModel("kimi-k2.7-code", "kimi-k2.7-code", "Kimi K2.7 Code", context_window=262_144),
            ProviderModel("kimi-k2.6", "kimi-k2.6", "Kimi K2.6", context_window=262_144),
        ),
    ),
    ProviderDef(
        id="freellmapi",
        name="FreeLLMAPI（本地网关）",
        free=True,
        default_api_base="http://127.0.0.1:31415/v1",
        env_key="FREELLMAPI_API_KEY",
        description="本地免费聚合网关，需先启动网关服务",
        models=(
            ProviderModel("freellm-deepseek-v4-flash", "deepseek-v4-flash"),
            ProviderModel("freellm-qwen3-coder-30b", "qwen3-coder-30b"),
            ProviderModel("freellm-reka-edge", "reka-edge"),
            ProviderModel("freellm-reka-flash", "reka-flash"),
            ProviderModel("freellm-cydonia-24b-v4.3", "cydonia-24b-v4.3"),
            ProviderModel("freellm-auto", "auto"),
            ProviderModel("freellm-fusion", "fusion"),
        ),
    ),
    ProviderDef(
        id="mimo",
        name="小米 MiMo",
        free=False,
        default_api_base="https://token-plan-cn.xiaomimimo.com/v1",
        env_key="MIMO_API_KEY",
        description="token 套餐付费，未配置 Key 时不可见",
        models=(
            ProviderModel("mimo-v2.5-pro", "mimo-v2.5-pro"),
            ProviderModel("mimo-v2.5", "mimo-v2.5"),
        ),
    ),
    ProviderDef(
        id="wenxin",
        name="百度文心",
        free=True,
        default_api_base="https://qianfan.baidubce.com/v2",
        env_key="WENXIN_API_KEY",
        description="百度千帆大模型（默认值可覆盖）",
        website="https://qianfan.cloud.baidu.com",
        models=(
            ProviderModel("wenxin-ernie-5.0", "ernie-5.0", "文心 ERNIE 5.0", context_window=128_000),
            ProviderModel("wenxin-ernie-4.5-turbo", "ernie-4.5-turbo-128k", "文心 ERNIE 4.5 Turbo 128K", context_window=128_000),
        ),
    ),
    ProviderDef(
        id="spark",
        name="讯飞星火",
        free=True,
        default_api_base="https://spark-api-open.xf-yun.com/v1",
        env_key="SPARK_API_KEY",
        description="讯飞星火大模型（默认值可覆盖）",
        website="https://xinghuo.xfyun.cn",
        models=(
            ProviderModel("spark-4.0-ultra", "spark-4.0-ultra", "讯飞星火 4.0 Ultra"),
            ProviderModel("spark-x1", "spark-x1", "讯飞星火 X1 深度推理"),
        ),
    ),
    ProviderDef(
        id="minimax",
        name="MiniMax",
        free=True,
        default_api_base="https://api.minimax.chat/v1",
        env_key="MINIMAX_API_KEY",
        description="MiniMax 大模型（默认值可覆盖）",
        website="https://www.minimax.io",
        models=(
            ProviderModel("minimax-m2.7", "MiniMax-M2.7", "MiniMax M2.7", context_window=200_000),
            ProviderModel("minimax-m2.5", "MiniMax-M2.5", "MiniMax M2.5", context_window=196_608),
        ),
    ),
    ProviderDef(
        id="siliconflow",
        name="硅基流动",
        free=True,
        default_api_base="https://api.siliconflow.cn/v1",
        env_key="SILICONFLOW_API_KEY",
        description="聚合 DeepSeek/Qwen/GLM 等主流模型，一个 Key 通吃",
        website="https://siliconflow.cn",
        models=(
            ProviderModel("siliconflow-deepseek-v4-pro", "deepseek-ai/DeepSeek-V4-Pro", "硅基 DeepSeek-V4-Pro", context_window=1_048_576),
            ProviderModel("siliconflow-deepseek-v4-flash", "deepseek-ai/DeepSeek-V4-Flash", "硅基 DeepSeek-V4-Flash", context_window=1_048_576),
            ProviderModel("siliconflow-glm-z1-9b", "THUDM/GLM-Z1-9B-0414", "硅基 GLM-Z1-9B (免费)"),
        ),
    ),
]

PROVIDER_MAP: dict[str, ProviderDef] = {p.id: p for p in PROVIDERS}

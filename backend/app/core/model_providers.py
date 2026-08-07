"""模型 Provider 注册表 — 数据驱动，替代 api/models.py / services/model.py / 前端的硬编码。

用法：
    from app.core.model_providers import PROVIDERS, PROVIDER_MAP

设计原则：
- 纯数据模块，不依赖任何 app 内部模块，便于前端 / 后端共享读取
- 每个 provider 的 api_key 通过 settings 表 api_key_<id> 配置，api_base 可用 api_base_<id> 覆盖
- free 标识仅作前端徽标展示，不参与风险/成本判定
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderModel:
    id: str          # 内部模型 ID（模型选择器 / ModelService.models 的 key）
    upstream: str    # 上游 API 模型名（透传给官方接口）
    display_name: str = ""  # 前端展示名，为空时用 id


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


PROVIDERS: list[ProviderDef] = [
    ProviderDef(
        id="deepseek",
        name="DeepSeek",
        free=False,
        default_api_base="https://api.deepseek.com/v1",
        env_key="DEEPSEEK_API_KEY",
        description="专注代码与对话的高性能模型",
        models=(
            ProviderModel("deepseek-v4-flash", "deepseek-v4-flash"),
            ProviderModel("deepseek-v4-pro", "deepseek-v4-pro"),
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
        models=(
            ProviderModel("qwen-flash", "qwen-flash"),
            ProviderModel("qwen-plus", "qwen-plus"),
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
        models=(
            ProviderModel("gemini-3.5-flash", "gemini-3.5-flash"),
            ProviderModel("gemini-3-flash", "gemini-3-flash-preview"),
            ProviderModel("gemini-3.1-flash-lite", "gemini-3.1-flash-lite"),
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
        models=(
            ProviderModel("glm-4", "glm-4"),
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
            ProviderModel("moonshot-v1-8k", "moonshot-v1-8k"),
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
            ProviderModel("wenxin-ernie-4-turbo", "ernie-4.0-turbo-8k"),
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
            ProviderModel("spark-general-v3.5", "generalv3.5"),
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
            ProviderModel("minimax-text-01", "MiniMax-Text-01"),
        ),
    ),
    ProviderDef(
        id="baichuan",
        name="百川智能",
        free=True,
        default_api_base="https://api.baichuan-ai.com/v1",
        env_key="BAICHUAN_API_KEY",
        description="百川大模型（默认值可覆盖）",
        website="https://www.baichuan-ai.com",
        models=(
            ProviderModel("baichuan-4", "Baichuan4"),
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
            ProviderModel("siliconflow-deepseek-v4-pro", "deepseek-ai/DeepSeek-V4-Pro", "硅基 DeepSeek-V4-Pro"),
            ProviderModel("siliconflow-deepseek-v4-flash", "deepseek-ai/DeepSeek-V4-Flash", "硅基 DeepSeek-V4-Flash"),
            ProviderModel("siliconflow-glm-z1-9b", "THUDM/GLM-Z1-9B-0414", "硅基 GLM-Z1-9B (免费)"),
        ),
    ),
]

PROVIDER_MAP: dict[str, ProviderDef] = {p.id: p for p in PROVIDERS}

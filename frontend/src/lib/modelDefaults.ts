/**
 * 缺省模型 ID —— 前后端一致的兜底常量
 *
 * 2026-08-11 收敛：之前在 8 处散落硬编码 "qwen-flash" 字面量（前端 6 处 + 后端 1 处 + 1 个常量声明），
 * 一旦百炼改名或下架需全局搜索替换。统一从本文件导出。
 *
 * 与后端 `backend/app/core/model_providers.py` 中 `qwen` provider 的首个 `qwen-flash` 模型保持同步。
 * 若该模型下架/改名，需同步修改：
 *   1. backend/app/core/model_providers.py（ProviderModel 注册）
 *   2. 本文件 FALLBACK_MODEL_ID
 */
export const FALLBACK_MODEL_ID = "qwen-flash";

/**
 * 缺省模型 ID —— 前后端一致的兜底常量
 *
 * 2026-08-11 收敛：之前在 8 处散落硬编码 "qwen-flash" 字面量（前端 6 处 + 后端 1 处 + 1 个常量声明），
 * 一旦百炼改名或下架需全局搜索替换。统一从本文件导出。
 *
 * 仅作前端 UI 显示链最末兜底；发送链路已不引用本常量（发送一律走会话绑定模型，
 * 未绑定则交由后端 settings.default_model 决定）。2026-08-14 同步为与后端 default 一致的 kimi-k2.5。
 * 若默认模型调整，需同步：
 *   1. backend settings.default_model（get_default_model()）
 *   2. 本文件 FALLBACK_MODEL_ID
 */
export const FALLBACK_MODEL_ID = "kimi-k2.5";

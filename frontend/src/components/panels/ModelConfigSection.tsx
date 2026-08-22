"use client";

/**
 * ModelConfigSection —— 模型配置区块（已拆分）
 *
 * 原 2351 行巨型组件已拆分为 modelConfig/ 目录：
 *   - constants.ts：API Key 脱敏 + 公共样式常量
 *   - ProviderCard.tsx：Provider 卡片（模型三区块 / 一键拉取 / 连通性测试）
 *   - ModelProvidersBasic.tsx：模型基础区入口（BasicSettingsView 消费）
 *   - ModelAdvancedFields.tsx：模型高级区（自定义模型 / Base URL 覆盖 / 备用识图）
 *
 * 本文件保留为 re-export 桥接，BasicSettingsView / AdvancedSettingsView 无需改动。
 * 废弃的旧版 ModelConfigSection 组件已归档至 _backup/settings_maturity_20260818/。
 */
export { ModelProvidersBasic } from "./modelConfig/ModelProvidersBasic";
export { ModelAdvancedFields } from "./modelConfig/ModelAdvancedFields";

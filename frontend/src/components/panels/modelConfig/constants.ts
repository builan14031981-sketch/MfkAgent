import type { CSSProperties } from "react";

// ── 共享：API Key 脱敏 ──
/**
 * 将 API Key 明文转换为展示用脱敏文本。
 * 规则：保留前 3 位 + 后 4 位，中间替换为 ****。
 * 长度不足 8 时全显示 ****（防止推测出短 Key）。
 * 空值返回空字符串。
 *
 * 示例：
 *   sk-abcdefghijklmnopc718 → sk-****c718
 *   abc123                   → ****
 *   ""                       → ""
 */
export function maskApiKey(key: string): string {
  if (!key) return "";
  if (key.length < 8) return "****";
  return key.slice(0, 3) + "****" + key.slice(-4);
}

// ── 共享：模型配置表单公共样式（原 ModelConfigSection.tsx 模块级常量） ──

export const inputStyle: CSSProperties = {
  padding: "7px 10px",
  borderRadius: "var(--radius-sm)",
  border: "1px solid var(--border-primary)",
  background: "var(--bg-level-2)",
  fontSize: "13px",
  color: "var(--text-level-2)",
  outline: "none",
  width: "100%",
  boxSizing: "border-box",
};

export const primaryBtn: CSSProperties = {
  padding: "6px 16px",
  borderRadius: "var(--radius-sm)",
  border: "none",
  background: "var(--color-primary)",
  color: "#fff",
  cursor: "pointer",
  fontSize: "13px",
  fontWeight: "500",
};

export const secondaryBtn: CSSProperties = {
  padding: "6px 16px",
  borderRadius: "var(--radius-sm)",
  border: "1px solid var(--border-primary)",
  background: "transparent",
  cursor: "pointer",
  fontSize: "13px",
  color: "var(--text-level-2)",
};

export const iconBtn: CSSProperties = {
  padding: "5px",
  borderRadius: "var(--radius-sm)",
  border: "1px solid var(--border-primary)",
  background: "transparent",
  cursor: "pointer",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  color: "var(--text-level-2)",
  fontSize: "11px",
  minWidth: "30px",
};
"use client";

import { useState, useCallback } from "react";
import { Eye, EyeOff, Copy, Check, KeyRound, Loader2 } from "lucide-react";
import { apiGet } from "@/lib/api";

export interface ApiKeyInputProps {
  /** 当前输入值（受控） */
  value: string;
  /** 值变化回调 */
  onChange: (value: string) => void;
  /** 占位提示（未配置时显示，如 "sk-..."） */
  placeholder?: string;
  /** 是否禁用 */
  disabled?: boolean;
  /** 自定义容器样式 */
  style?: React.CSSProperties;
  /** 是否显示左侧 KeyRound 图标（默认显示） */
  showIcon?: boolean;
  /** 无障碍标签 */
  label?: string;
  /** 设置项 key：传入后点击小眼睛会调用 /api/settings/{key}/reveal 获取明文 */
  settingKey?: string;
}

/**
 * 公共 API Key 输入框组件（三处复用：主 Provider / 备用识图 / 自定义模型）。
 *
 * 功能：
 * 1. Eye / EyeOff 明密文切换 —— 默认密文（type=password），点击眼睛切明文。
 * 2. Copy 一键复制 —— 将当前输入值写入剪贴板，复制成功 1.5s 内显示 Check 反馈。
 * 3. 左侧 KeyRound 图标（可通过 showIcon 关闭）。
 *
 * 设计要点：
 * - 输入框本体与图标按钮在同一行内布局，自适应填充父容器宽度（flex:1）。
 * - 复制按钮在值为空时禁用，避免复制空串。
 * - 明密文切换（小眼睛）在值为空时禁用：value 为空时切换无可见效果。
 *   后端明文下发后，已配置的 Provider 打开编辑时 value 会回填真实 Key，
 *   小眼睛自动可用，用户可随时查看/核对已保存的明文 Key。
 * - 剪贴板 API 失败（如非 HTTPS / 无权限）静默降级，不抛错。
 */
export function ApiKeyInput({
  value,
  onChange,
  placeholder,
  disabled = false,
  style,
  showIcon = true,
  label,
  settingKey,
}: ApiKeyInputProps) {
  const [visible, setVisible] = useState(false);
  const [copied, setCopied] = useState(false);
  const [revealing, setRevealing] = useState(false);

  /** 判断当前值是否是脱敏后的（包含 ****） */
  const isMasked = value.includes("****");

  const handleToggleVisible = useCallback(async () => {
    // 如果当前是脱敏状态且有 settingKey，先从后端获取明文
    if (settingKey && isMasked && !visible) {
      setRevealing(true);
      try {
        const res = await apiGet<{ key: string; value: string }>(`/api/settings/${settingKey}/reveal`);
        if (res?.value) {
          onChange(res.value);
        }
      } catch (err) {
        console.error("Failed to reveal API key:", err);
      } finally {
        setRevealing(false);
      }
    }
    setVisible((v) => !v);
  }, [settingKey, isMasked, visible, onChange]);

  const handleCopy = useCallback(async () => {
    if (!value) return;
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(value);
      } else {
        // 降级方案：临时 textarea + execCommand（兼容非 HTTPS / 旧浏览器）
        const ta = document.createElement("textarea");
        ta.value = value;
        ta.style.position = "fixed";
        ta.style.opacity = "0";
        document.body.appendChild(ta);
        ta.select();
        try {
          document.execCommand("copy");
        } finally {
          document.body.removeChild(ta);
        }
      }
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // 静默降级：复制失败不阻塞输入
    }
  }, [value]);

  return (
    <div style={{
      display: "flex",
      alignItems: "center",
      gap: "4px",
      flex: 1,
      minWidth: 0,
      ...style,
    }}>
      {showIcon && (
        <KeyRound style={{
          width: "13px",
          height: "13px",
          color: "var(--text-level-4)",
          flexShrink: 0,
        }} />
      )}
      <input
        type={visible ? "text" : "password"}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        disabled={disabled}
        aria-label={label}
        style={{
          flex: 1,
          minWidth: 0,
          padding: "6px 8px",
          borderRadius: "var(--radius-sm)",
          border: "1px solid var(--border-primary)",
          background: "var(--bg-level-1)",
          fontSize: "13px",
          color: "var(--text-level-2)",
          outline: "none",
          fontFamily: "monospace",
        }}
      />
      {/* 明密文切换：value 为空时禁用，避免"空输入框 + 小眼睛"摆设误导 */}
      <button
        type="button"
        onClick={handleToggleVisible}
        disabled={disabled || !value || revealing}
        title={value ? (visible ? "隐藏" : "显示明文") : "请先输入 API Key"}
        style={{
          ...iconBtnStyle,
          opacity: (!value || disabled || revealing) ? 0.4 : 1,
          cursor: (!value || disabled || revealing) ? "not-allowed" : "pointer",
        }}
      >
        {revealing
          ? <Loader2 style={{ width: "14px", height: "14px", animation: "spin 1s linear infinite" }} />
          : visible
          ? <EyeOff style={{ width: "14px", height: "14px" }} />
          : <Eye style={{ width: "14px", height: "14px" }} />}
      </button>
      {/* 复制 */}
      <button
        type="button"
        onClick={handleCopy}
        disabled={disabled || !value}
        title="复制"
        style={{
          ...iconBtnStyle,
          opacity: (!value || disabled) ? 0.4 : 1,
          cursor: (!value || disabled) ? "not-allowed" : "pointer",
          color: copied ? "var(--color-success)" : "var(--text-level-3)",
        }}
      >
        {copied
          ? <Check style={{ width: "14px", height: "14px" }} />
          : <Copy style={{ width: "14px", height: "14px" }} />}
      </button>
    </div>
  );
}

const iconBtnStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  width: "28px",
  height: "28px",
  padding: 0,
  borderRadius: "var(--radius-sm)",
  border: "1px solid var(--border-primary)",
  background: "transparent",
  cursor: "pointer",
  color: "var(--text-level-3)",
  flexShrink: 0,
  transition: "color 0.15s ease, border-color 0.15s ease",
};

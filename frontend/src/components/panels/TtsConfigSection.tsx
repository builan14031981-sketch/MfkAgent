"use client";

/**
 * TtsConfigSection —— 语音朗读设置区块
 *
 * 支持双引擎：
 *   - edge: 微软 Edge TTS（免费，需代理）
 *   - volcengine: 火山引擎（字节跳动，国内直连，低时延）
 *
 * 含：总开关 / 引擎切换 / 自动朗读 / 音色选择器 / 语速 / 火山引擎凭证。
 */
import { useState, useRef, useEffect } from "react";
import { createPortal } from "react-dom";
import { Volume2, ChevronDown, Check, Key, AppWindow } from "lucide-react";
import { useTranslation } from "@/hooks/useTranslation";
import { SwitchButton } from "@/components/SwitchButton";

/** 引擎选项 */
const ENGINE_OPTIONS = [
  { value: "volcengine", label: "火山引擎（推荐）", desc: "国内直连，低时延，高自然度" },
  { value: "edge", label: "微软 Edge TTS", desc: "免费无 Key，需代理" },
];

/** 微软 Edge TTS 精选音色 */
const EDGE_VOICE_OPTIONS: Array<{ id: string; name: string; gender: string; style: string }> = [
  { id: "zh-CN-YunxiNeural", name: "云希", gender: "男", style: "阳光少年，推荐" },
  { id: "zh-CN-YunyangNeural", name: "云扬", gender: "男", style: "专业解说，新闻播报" },
  { id: "zh-CN-YunjianNeural", name: "云健", gender: "男", style: "沉稳有力" },
  { id: "zh-CN-YunxiaNeural", name: "云夏", gender: "男", style: "少年声线" },
  { id: "zh-CN-XiaoxiaoNeural", name: "晓晓", gender: "女", style: "温暖亲切，推荐女声" },
  { id: "zh-CN-XiaoyiNeural", name: "晓伊", gender: "女", style: "活泼可爱" },
  { id: "zh-CN-XiaohanNeural", name: "晓涵", gender: "女", style: "多情感风格" },
  { id: "zh-CN-XiaomengNeural", name: "晓梦", gender: "女", style: "温柔甜美" },
  { id: "zh-CN-XiaomoNeural", name: "晓墨", gender: "女", style: "沉稳知性" },
  { id: "zh-CN-XiaoruiNeural", name: "晓睿", gender: "女", style: "干练专业" },
];

/** 火山引擎精选音色（与后端 volcengine_tts.get_curated_voices 对齐） */
const VOLC_VOICE_OPTIONS: Array<{ id: string; name: string; gender: string; style: string }> = [
  { id: "zh_female_cancan_mars_bigtts", name: "灿灿", gender: "女", style: "活泼亲切，推荐" },
  { id: "zh_female_vv_mars_bigtts", name: "Vivi", gender: "女", style: "温柔自然" },
  { id: "zh_female_qingxinnvsheng_mars_bigtts", name: "清新女声", gender: "女", style: "清新干净" },
  { id: "zh_female_zhixingnvsheng_mars_bigtts", name: "知性女声", gender: "女", style: "知性沉稳" },
  { id: "zh_female_tianmeixiaoyuan_moon_bigtts", name: "甜美小源", gender: "女", style: "甜美可爱" },
  { id: "zh_female_linjianvhai_moon_bigtts", name: "邻家女孩", gender: "女", style: "亲切邻家" },
  { id: "zh_female_wenrouxiaoya_moon_bigtts", name: "温柔小雅", gender: "女", style: "温柔甜美" },
  { id: "zh_female_kailangjiejie_moon_bigtts", name: "开朗姐姐", gender: "女", style: "开朗明快" },
  { id: "zh_female_xiaohe_uranus_bigtts", name: "小何 2.0", gender: "女", style: "甜美活泼，2.0大模型" },
  { id: "zh_female_vv_uranus_bigtts", name: "Vivi 2.0", gender: "女", style: "温柔自然，2.0大模型" },
  { id: "zh_male_qingyiyuxuan_mars_bigtts", name: "阳光阿辰", gender: "男", style: "阳光青年，推荐男声" },
  { id: "zh_male_qingshuangnanda_mars_bigtts", name: "清爽男大", gender: "男", style: "清爽大学生" },
  { id: "zh_male_yangguangqingnian_moon_bigtts", name: "阳光青年", gender: "男", style: "阳光活力" },
  { id: "zh_male_ruyayichen_saturn_bigtts", name: "儒雅逸辰", gender: "男", style: "儒雅沉稳" },
  { id: "zh_male_m191_uranus_bigtts", name: "云舟 2.0", gender: "男", style: "清爽沉稳，2.0大模型" },
  { id: "zh_male_taocheng_uranus_bigtts", name: "小天 2.0", gender: "男", style: "清爽磁性，2.0大模型" },
];

/** 语速选项 */
const RATE_OPTIONS = [
  { value: "-20%", label: "慢速 0.8x" },
  { value: "-10%", label: "稍慢 0.9x" },
  { value: "+0%", label: "正常 1.0x" },
  { value: "+10%", label: "稍快 1.1x" },
  { value: "+20%", label: "快速 1.2x" },
];

interface TtsConfigSectionProps {
  settings: Record<string, string> | null;
  saving: string | null;
  onUpdate: (key: string, value: string) => void;
  t: (key: string) => string;
}

/** 音色选择器：类字体下拉交互 */
function VoicePicker({
  value,
  onChange,
  disabled,
  options,
  t,
}: {
  value: string;
  onChange: (id: string) => void;
  disabled: boolean;
  options: Array<{ id: string; name: string; gender: string; style: string }>;
  t: (key: string) => string;
}) {
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState({ top: 0, left: 0, width: 0 });
  const btnRef = useRef<HTMLButtonElement>(null);
  const popRef = useRef<HTMLDivElement>(null);

  const current = options.find((v) => v.id === value) ?? options[0];

  useEffect(() => {
    if (!open || !btnRef.current) return;
    const rect = btnRef.current.getBoundingClientRect();
    setPos({ top: rect.bottom + 4, left: rect.left, width: Math.max(rect.width, 260) });
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      const target = e.target as Node;
      if (popRef.current?.contains(target)) return;
      if (btnRef.current?.contains(target)) return;
      setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open]);

  return (
    <>
      <button
        ref={btnRef}
        type="button"
        disabled={disabled}
        onClick={() => setOpen((o) => !o)}
        style={{
          padding: "8px 12px",
          borderRadius: "var(--radius-sm)",
          border: "1px solid var(--border-primary)",
          background: "var(--bg-level-2)",
          fontSize: "13px",
          color: "var(--text-level-2)",
          outline: "none",
          cursor: disabled ? "not-allowed" : "pointer",
          opacity: disabled ? 0.6 : 1,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: "8px",
          minWidth: "200px",
        }}
      >
        <span style={{ display: "flex", alignItems: "center", gap: "6px", minWidth: 0 }}>
          <Volume2 style={{ width: "13px", height: "13px", color: "var(--text-level-4)", flexShrink: 0 }} />
          <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {current?.name ?? "请选择"}
            {current?.gender && (
              <span style={{ color: "var(--text-level-4)", fontSize: "11px", marginLeft: "4px" }}>
                {current.gender}
              </span>
            )}
          </span>
        </span>
        <ChevronDown style={{ width: "14px", height: "14px", color: "var(--text-level-4)", flexShrink: 0 }} />
      </button>

      {open && createPortal(
        <div
          ref={popRef}
          data-portal-popover
          style={{
            position: "fixed",
            top: pos.top,
            left: pos.left,
            width: pos.width,
            maxHeight: "360px",
            overflowY: "auto",
            padding: "6px",
            borderRadius: "var(--radius-xl)",
            background: "var(--bg-level-2)",
            border: "1px solid var(--border-secondary)",
            boxShadow: "var(--shadow-lg)",
            zIndex: 9999,
          }}
        >
          {options.map((opt) => {
            const active = opt.id === value;
            return (
              <button
                key={opt.id}
                type="button"
                onClick={() => {
                  onChange(opt.id);
                  setOpen(false);
                }}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "8px",
                  width: "100%",
                  padding: "7px 10px",
                  border: "none",
                  background: active ? "var(--bg-level-3)" : "transparent",
                  cursor: "pointer",
                  fontSize: "13px",
                  fontWeight: active ? 600 : 400,
                  color: active ? "var(--color-primary)" : "var(--text-level-2)",
                  borderRadius: "var(--radius-sm)",
                  textAlign: "left",
                }}
                onMouseEnter={(e) => { if (!active) e.currentTarget.style.background = "var(--bg-level-3)"; }}
                onMouseLeave={(e) => { if (!active) e.currentTarget.style.background = "transparent"; }}
              >
                <span style={{ width: "14px", flexShrink: 0 }}>
                  {active && <Check style={{ width: "14px", height: "14px" }} />}
                </span>
                <span style={{ flex: 1, minWidth: 0 }}>
                  <span style={{ fontWeight: 500 }}>{opt.name}</span>
                  <span style={{ color: "var(--text-level-4)", fontSize: "11px", marginLeft: "6px" }}>
                    {opt.gender}
                  </span>
                  <div style={{ fontSize: "11px", color: "var(--text-level-4)", marginTop: "1px" }}>
                    {opt.style}
                  </div>
                </span>
              </button>
            );
          })}
        </div>,
        document.body
      )}
    </>
  );
}

/** 文本输入框样式 */
const inputStyle: React.CSSProperties = {
  padding: "8px 10px",
  borderRadius: "var(--radius-sm)",
  border: "1px solid var(--border-primary)",
  background: "var(--bg-level-2)",
  fontSize: "13px",
  color: "var(--text-level-2)",
  outline: "none",
  width: "100%",
  fontFamily: "monospace",
};

export function TtsConfigSection({ settings, saving, onUpdate, t }: TtsConfigSectionProps) {
  const enabled = settings?.tts_enabled !== "false";
  const autoPlay = settings?.tts_auto_play === "true";
  const engine = settings?.tts_engine || "volcengine";
  const edgeVoice = settings?.tts_voice || "zh-CN-YunxiNeural";
  const volcVoice = settings?.volcengine_voice || "zh_female_cancan_mars_bigtts";
  const volcAppid = settings?.volcengine_appid || "";
  const volcToken = settings?.volcengine_access_token || "";
  const rate = settings?.tts_rate || "+0%";

  const isVolc = engine === "volcengine";
  const currentVoice = isVolc ? volcVoice : edgeVoice;
  const voiceOptions = isVolc ? VOLC_VOICE_OPTIONS : EDGE_VOICE_OPTIONS;
  const voiceKey = isVolc ? "volcengine_voice" : "tts_voice";

  // 火山引擎是否已配置凭证（用于判断音色选择器是否可用）
  const volcConfigured = isVolc && volcAppid.trim() !== "" && volcToken.trim() !== "";
  const voiceDisabled = !enabled || saving === voiceKey || (isVolc && !volcConfigured);

  return (
    <div style={{ marginBottom: "18px" }}>
      <div style={{ marginBottom: "10px" }}>
        <h3 style={{ fontSize: "14px", fontWeight: "500", color: "var(--text-level-1)", margin: 0, display: "flex", alignItems: "center", gap: "6px" }}>
          <Volume2 style={{ width: "15px", height: "15px", color: "var(--color-primary)" }} />
          {t("settings.tts.title")}
        </h3>
        <p style={{ fontSize: "12px", color: "var(--text-level-3)", margin: "2px 0 0 0" }}>
          {t("settings.tts.desc")}
        </p>
      </div>

      {/* 总开关 */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "12px" }}>
        <div>
          <h4 style={{ fontSize: "13px", fontWeight: "500", color: "var(--text-level-1)", margin: 0 }}>
            {t("settings.tts.enabled")}
          </h4>
          <p style={{ fontSize: "11px", color: "var(--text-level-4)", margin: "1px 0 0 0" }}>
            {t("settings.tts.enabledDesc")}
          </p>
        </div>
        <SwitchButton
          checked={enabled}
          disabled={saving === "tts_enabled"}
          onChange={(v) => onUpdate("tts_enabled", v ? "true" : "false")}
        />
      </div>

      {/* 引擎切换 */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "12px", opacity: enabled ? 1 : 0.4 }}>
        <div>
          <h4 style={{ fontSize: "13px", fontWeight: "500", color: "var(--text-level-1)", margin: 0, display: "flex", alignItems: "center", gap: "4px" }}>
            <AppWindow style={{ width: "12px", height: "12px", color: "var(--text-level-4)" }} />
            朗读引擎
          </h4>
          <p style={{ fontSize: "11px", color: "var(--text-level-4)", margin: "1px 0 0 0" }}>
            选择语音合成服务提供商
          </p>
        </div>
        <select
          value={engine}
          onChange={(e) => onUpdate("tts_engine", e.target.value)}
          disabled={!enabled || saving === "tts_engine"}
          style={{
            padding: "8px 12px",
            borderRadius: "var(--radius-sm)",
            border: "1px solid var(--border-primary)",
            background: "var(--bg-level-2)",
            fontSize: "13px",
            color: "var(--text-level-2)",
            outline: "none",
            minWidth: "180px",
            cursor: (!enabled || saving === "tts_engine") ? "not-allowed" : "pointer",
            opacity: (!enabled || saving === "tts_engine") ? 0.6 : 1,
          }}
        >
          {ENGINE_OPTIONS.map((e) => (
            <option key={e.value} value={e.value}>{e.label}</option>
          ))}
        </select>
      </div>

      {/* 火山引擎凭证 */}
      {isVolc && (
        <div style={{ marginBottom: "12px", padding: "12px", borderRadius: "var(--radius-md)", background: "var(--bg-level-2)", border: "1px solid var(--border-secondary)", opacity: enabled ? 1 : 0.4 }}>
          <div style={{ fontSize: "12px", fontWeight: "500", color: "var(--text-level-2)", marginBottom: "8px", display: "flex", alignItems: "center", gap: "4px" }}>
            <Key style={{ width: "12px", height: "12px" }} />
            火山引擎凭证
            {!volcConfigured && enabled && (
              <span style={{ color: "var(--color-warning)", fontSize: "11px", marginLeft: "6px" }}>未配置</span>
            )}
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
            <div>
              <label style={{ fontSize: "11px", color: "var(--text-level-4)", display: "block", marginBottom: "3px" }}>AppID</label>
              <input
                type="text"
                value={volcAppid}
                onChange={(e) => onUpdate("volcengine_appid", e.target.value)}
                disabled={!enabled || saving === "volcengine_appid"}
                placeholder="在火山引擎控制台 → 语音技术 → 应用管理 获取"
                style={inputStyle}
              />
            </div>
            <div>
              <label style={{ fontSize: "11px", color: "var(--text-level-4)", display: "block", marginBottom: "3px" }}>Access Token</label>
              <input
                type="password"
                value={volcToken}
                onChange={(e) => onUpdate("volcengine_access_token", e.target.value)}
                disabled={!enabled || saving === "volcengine_access_token"}
                placeholder="在火山引擎控制台 → 语音技术 → 应用管理 获取"
                style={inputStyle}
              />
            </div>
          </div>
          <p style={{ fontSize: "10px", color: "var(--text-level-4)", margin: "8px 0 0 0", lineHeight: 1.4 }}>
            开通方式：火山引擎控制台 → 语音技术 → 语音合成 → 创建应用 → 获取 AppID 和 Access Token。有免费试用额度。
          </p>
        </div>
      )}

      {/* 自动朗读 */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "12px", opacity: enabled ? 1 : 0.4 }}>
        <div>
          <h4 style={{ fontSize: "13px", fontWeight: "500", color: "var(--text-level-1)", margin: 0 }}>
            {t("settings.tts.autoPlay")}
          </h4>
          <p style={{ fontSize: "11px", color: "var(--text-level-4)", margin: "1px 0 0 0" }}>
            {t("settings.tts.autoPlayDesc")}
          </p>
        </div>
        <SwitchButton
          checked={autoPlay}
          disabled={!enabled || saving === "tts_auto_play"}
          onChange={(v) => onUpdate("tts_auto_play", v ? "true" : "false")}
        />
      </div>

      {/* 音色选择 */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "12px", opacity: enabled ? 1 : 0.4 }}>
        <div>
          <h4 style={{ fontSize: "13px", fontWeight: "500", color: "var(--text-level-1)", margin: 0 }}>
            {t("settings.tts.voice")}
          </h4>
          <p style={{ fontSize: "11px", color: "var(--text-level-4)", margin: "1px 0 0 0" }}>
            {isVolc && !volcConfigured ? "请先配置火山引擎凭证" : t("settings.tts.voiceDesc")}
          </p>
        </div>
        <VoicePicker
          value={currentVoice}
          onChange={(id) => onUpdate(voiceKey, id)}
          disabled={voiceDisabled}
          options={voiceOptions}
          t={t}
        />
      </div>

      {/* 语速 */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", opacity: enabled ? 1 : 0.4 }}>
        <div>
          <h4 style={{ fontSize: "13px", fontWeight: "500", color: "var(--text-level-1)", margin: 0 }}>
            {t("settings.tts.rate")}
          </h4>
          <p style={{ fontSize: "11px", color: "var(--text-level-4)", margin: "1px 0 0 0" }}>
            {t("settings.tts.rateDesc")}
          </p>
        </div>
        <select
          value={rate}
          onChange={(e) => onUpdate("tts_rate", e.target.value)}
          disabled={!enabled || saving === "tts_rate"}
          style={{
            padding: "8px 12px",
            borderRadius: "var(--radius-sm)",
            border: "1px solid var(--border-primary)",
            background: "var(--bg-level-2)",
            fontSize: "13px",
            color: "var(--text-level-2)",
            outline: "none",
            minWidth: "140px",
            cursor: (!enabled || saving === "tts_rate") ? "not-allowed" : "pointer",
            opacity: (!enabled || saving === "tts_rate") ? 0.6 : 1,
          }}
        >
          {RATE_OPTIONS.map((r) => (
            <option key={r.value} value={r.value}>{r.label}</option>
          ))}
        </select>
      </div>
    </div>
  );
}

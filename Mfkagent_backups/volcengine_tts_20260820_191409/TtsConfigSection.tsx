"use client";

/**
 * TtsConfigSection —— 语音朗读设置区块
 *
 * 基于微软 Edge TTS（神经引擎，免费无 Key），默认音色晓辰。
 * 含：总开关 / 自动朗读 / 音色选择器（类字体下拉交互）/ 语速。
 */
import { useState, useRef, useEffect } from "react";
import { createPortal } from "react-dom";
import { Volume2, ChevronDown, Check } from "lucide-react";
import { useTranslation } from "@/hooks/useTranslation";
import { SwitchButton } from "@/components/SwitchButton";

/** 精选中文音色列表（与后端 /api/tts/voices 对齐） */
const VOICE_OPTIONS: Array<{ id: string; name: string; gender: string; style: string }> = [
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
  { id: "zh-HK-WanLungNeural", name: "云龙", gender: "男", style: "粤语，香港" },
  { id: "zh-TW-YunJheNeural", name: "云哲", gender: "男", style: "国语，台湾" },
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

/** 音色选择器：类字体下拉交互（收起态仿 select，点击展开列表） */
function VoicePicker({
  value,
  onChange,
  disabled,
  t,
}: {
  value: string;
  onChange: (id: string) => void;
  disabled: boolean;
  t: (key: string) => string;
}) {
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState({ top: 0, left: 0, width: 0 });
  const btnRef = useRef<HTMLButtonElement>(null);
  const popRef = useRef<HTMLDivElement>(null);

  const current = VOICE_OPTIONS.find((v) => v.id === value) ?? VOICE_OPTIONS[0];

  useEffect(() => {
    if (!open || !btnRef.current) return;
    const rect = btnRef.current.getBoundingClientRect();
    setPos({ top: rect.bottom + 4, left: rect.left, width: Math.max(rect.width, 240) });
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
            {current.name}
            <span style={{ color: "var(--text-level-4)", fontSize: "11px", marginLeft: "4px" }}>
              {current.gender}
            </span>
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
            maxHeight: "320px",
            overflowY: "auto",
            padding: "6px",
            borderRadius: "var(--radius-xl)",
            background: "var(--bg-level-2)",
            border: "1px solid var(--border-secondary)",
            boxShadow: "var(--shadow-lg)",
            zIndex: 9999,
          }}
        >
          {VOICE_OPTIONS.map((opt) => {
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

export function TtsConfigSection({ settings, saving, onUpdate, t }: TtsConfigSectionProps) {
  const enabled = settings?.tts_enabled !== "false";
  const autoPlay = settings?.tts_auto_play === "true";
  const voice = settings?.tts_voice || "zh-CN-YunxiNeural";
  const rate = settings?.tts_rate || "+0%";

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
            {t("settings.tts.voiceDesc")}
          </p>
        </div>
        <VoicePicker
          value={voice}
          onChange={(id) => onUpdate("tts_voice", id)}
          disabled={!enabled || saving === "tts_voice"}
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

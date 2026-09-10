"use client";

import { useState } from "react";
import { ChevronDown, Image as ImageIcon, Eye, Sparkles } from "lucide-react";
import { useTranslation } from "@/hooks/useTranslation";
import { useProviderConfig } from "@/hooks/useProviderConfig";
import { VisionConfigSection } from "./VisionConfigSection";

interface MultimodalConfigSectionProps {
  settings: Record<string, string> | null;
  saving: string | null;
  onUpdate: (key: string, value: string) => void;
}

export function MultimodalConfigSection({ settings, saving, onUpdate }: MultimodalConfigSectionProps) {
  const { t } = useTranslation();
  const { hasVisionKey } = useProviderConfig();

  const [expanded, setExpanded] = useState(() => {
    try {
      return localStorage.getItem("mfk_multimodal_section_expanded") === "true";
    } catch {
      return false;
    }
  });

  const toggleExpanded = () => {
    setExpanded((prev) => {
      const next = !prev;
      try {
        localStorage.setItem("mfk_multimodal_section_expanded", String(next));
      } catch {
        /* noop */
      }
      return next;
    });
  };

  const imageGenModel = settings?.image_gen_model || "qwen-image-3.0-pro";
  const visionProvider = settings?.vision_provider || "";
  const visionModel = settings?.vision_model || "";
  const isVisionConfigured = !!(visionProvider && visionModel && hasVisionKey());

  const imageGenLabel =
    imageGenModel === "qwen-image-3.0-pro"
      ? "千问 3.0 Pro (高质量)"
      : imageGenModel === "qwen-image-3.0"
        ? "千问 3.0 (极速)"
        : imageGenModel;

  return (
    <div
      style={{
        border: "1px solid var(--border-primary)",
        borderRadius: "var(--radius-md)",
        background: "var(--bg-level-2)",
        overflow: "hidden",
        transition: "border-color var(--transition-fast)",
      }}
    >
      {/* ── 标题与摘要折叠行（始终可见）── */}
      <button
        type="button"
        onClick={toggleExpanded}
        aria-expanded={expanded}
        style={{
          width: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: "12px",
          padding: "12px 14px",
          border: "none",
          background: "transparent",
          cursor: "pointer",
          textAlign: "left",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "10px", minWidth: 0 }}>
          <Sparkles style={{ width: "16px", height: "16px", color: "var(--text-level-3)", flexShrink: 0 }} />
          <div style={{ minWidth: 0 }}>
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <span style={{ fontSize: "13px", fontWeight: 600, color: "var(--text-level-1)" }}>
                {t("settings.model.multimodal.title")}
              </span>
              <span
                style={{
                  fontSize: "11px",
                  padding: "1px 7px",
                  borderRadius: "999px",
                  background: isVisionConfigured
                    ? "rgba(16,185,129,0.12)"
                    : "rgba(107,114,128,0.12)",
                  color: isVisionConfigured ? "var(--color-success)" : "var(--text-level-4)",
                  fontWeight: 500,
                  lineHeight: 1.4,
                }}
              >
                {isVisionConfigured
                  ? t("settings.model.multimodal.badgeConfigured")
                  : t("settings.model.multimodal.badgeNotConfigured")}
              </span>
            </div>
            <p
              style={{
                fontSize: "12px",
                color: "var(--text-level-3)",
                margin: "2px 0 0 0",
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis",
              }}
            >
              生图：{imageGenLabel} · 识图：{isVisionConfigured ? `${visionProvider} (${visionModel})` : "未配置"}
            </p>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "6px", flexShrink: 0 }}>
          <span style={{ fontSize: "12px", color: "var(--text-level-3)" }}>
            {expanded ? t("settings.model.multimodal.collapse") : t("settings.model.multimodal.expand")}
          </span>
          <ChevronDown
            style={{
              width: "15px",
              height: "15px",
              color: "var(--text-level-4)",
              transform: expanded ? "rotate(180deg)" : "rotate(0deg)",
              transition: "transform var(--transition-fast)",
            }}
          />
        </div>
      </button>

      {/* ── 展开后的详细配置内容 ── */}
      {expanded && (
        <div
          style={{
            padding: "0 14px 14px",
            borderTop: "1px solid var(--border-secondary)",
            display: "flex",
            flexDirection: "column",
            gap: "14px",
          }}
        >
          {/* 文生图模型行 */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: "16px",
              paddingTop: "12px",
            }}
          >
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                <ImageIcon style={{ width: "14px", height: "14px", color: "var(--text-level-3)" }} />
                <span style={{ fontSize: "13px", fontWeight: 500, color: "var(--text-level-1)" }}>
                  {t("settings.model.imageGen.title")}
                </span>
              </div>
              <p style={{ fontSize: "12px", color: "var(--text-level-3)", margin: "2px 0 0 0" }}>
                {t("settings.model.imageGen.desc")}
              </p>
            </div>
            <select
              value={imageGenModel}
              className="mf-input"
              onChange={(e) => onUpdate("image_gen_model", e.target.value)}
              disabled={saving === "image_gen_model"}
              style={{
                padding: "6px 10px",
                borderRadius: "var(--radius-sm)",
                background: "var(--bg-level-1)",
                fontSize: "12px",
                color: "var(--text-level-2)",
                height: "32px",
                minWidth: "220px",
                flexShrink: 0,
              }}
            >
              <option value="qwen-image-3.0-pro">{t("settings.model.imageGen.pro")}</option>
              <option value="qwen-image-3.0">{t("settings.model.imageGen.flash")}</option>
            </select>
          </div>

          {/* 备用识图模型行 / 表单 */}
          <div style={{ borderTop: "1px solid var(--border-secondary)", paddingTop: "12px" }}>
            <div style={{ marginBottom: "10px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                <Eye style={{ width: "14px", height: "14px", color: "var(--text-level-3)" }} />
                <span style={{ fontSize: "13px", fontWeight: 500, color: "var(--text-level-1)" }}>
                  {t("settings.model.vision.title")}
                </span>
              </div>
              <p style={{ fontSize: "12px", color: "var(--text-level-3)", margin: "2px 0 0 0" }}>
                {t("settings.model.vision.desc")}
              </p>
            </div>
            <VisionConfigSection />
          </div>
        </div>
      )}
    </div>
  );
}

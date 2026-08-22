"use client";

import { useRef, useEffect, useState } from "react";
import { Plus, FileUp, Trash2, Clipboard, Sparkles, Check, X, Search } from "lucide-react";
import { useTranslation } from "@/hooks/useTranslation";
import type { SkillInfo } from "@/hooks/useSkills";
import {
  popoverStyle,
  popoverItemStyle,
  itemHoverBackground,
  pillActiveBackground,
  pillActiveColor,
  ghostPillHoverBackground,
  ghostPillHoverColor,
  ghostPillHoverShadow,
} from "./styles";

interface UploadMenuProps {
  open: boolean;
  onToggle: () => void;
  onPickFile: () => void;
  onClearContext: () => void;
  hasContext: boolean;
  onClose: () => void;

  /** 已启用的 Skill 列表：供「添加 Skill」会话级注入 */
  skills?: SkillInfo[];
  /** 会话级启用某个 Skill（把其 prompt 作为文档喂给当前会话） */
  onApplySkill?: (skill: SkillInfo) => void;
  /** 当前会话已启用的 Skill id 集合 */
  activeSkillIds?: Set<string>;
  /** 移除某个会话级 Skill */
  onRemoveSkill?: (skillId: string) => void;
  /** 粘贴剪贴板（文本/图片）到输入框 */
  onPasteClipboard?: () => void;
}

/** + 极简菜单按钮：上传文件 / 添加 Skill / 粘贴剪贴板 / 清空上下文 */
export function UploadMenu({
  open,
  onToggle,
  onPickFile,
  onClearContext,
  hasContext,
  onClose,
  skills,
  onApplySkill,
  activeSkillIds,
  onRemoveSkill,
  onPasteClipboard,
}: UploadMenuProps) {
  const { t } = useTranslation();
  const btnRef = useRef<HTMLButtonElement>(null);
  const popRef = useRef<HTMLDivElement>(null);
  const [skillSubOpen, setSkillSubOpen] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [skillQuery, setSkillQuery] = useState("");

  // 点击外部关闭
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      const target = e.target as Node;
      if (btnRef.current?.contains(target)) return;
      if (popRef.current?.contains(target)) return;
      onClose();
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open, onClose]);

  // 关闭菜单时重置确认/二级面板状态
  useEffect(() => {
    if (!open) {
      setConfirming(false);
      setSkillSubOpen(false);
      setSkillQuery("");
    }
  }, [open]);

  // 已安装（enabled）的 Skill 列表，供会话级注入使用
  const installedSkills = (skills ?? []).filter((s) => s.installed);

  // 本地模糊搜索：基于 name / description / category / tags，大小写不敏感（转小写 substring 命中即算）
  const skillLower = skillQuery.trim().toLowerCase();
  const filteredSkills = skillLower
    ? installedSkills.filter((s) =>
        [s.name, s.description, s.category, ...(s.tags ?? [])].some((v) =>
          String(v).toLowerCase().includes(skillLower)
        )
      )
    : installedSkills;

  return (
    <div style={{ position: "relative", flexShrink: 0 }}>
      <button
        ref={btnRef}
        data-upload-menu-trigger=""
        onClick={onToggle}
        title={t("chat.menu.uploadFile")}
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          width: "28px",
          height: "28px",
          padding: "0",
          borderRadius: "var(--radius-full)",
          border: "1px solid transparent",
          background: open ? pillActiveBackground : "transparent",
          cursor: "pointer",
          color: open ? pillActiveColor : "var(--text-level-4)",
          flexShrink: 0,
          outline: "none",
          transition: "all 0.2s ease-in-out",
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.background = ghostPillHoverBackground;
          e.currentTarget.style.color = ghostPillHoverColor;
          e.currentTarget.style.boxShadow = ghostPillHoverShadow;
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = open ? pillActiveBackground : "transparent";
          e.currentTarget.style.color = open ? pillActiveColor : "var(--text-level-4)";
          e.currentTarget.style.boxShadow = "none";
        }}
      >
        <Plus style={{
          width: "16px",
          height: "16px",
          transform: open ? "rotate(45deg)" : "rotate(0deg)",
          transition: "transform var(--transition-normal)",
        }} />
      </button>

      {open && (
        <div ref={popRef} style={popoverStyle}>
          <button
            onClick={() => { onClose(); onPickFile(); }}
            style={popoverItemStyle}
            onMouseEnter={(e) => { e.currentTarget.style.background = itemHoverBackground; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
          >
            <FileUp style={{ width: "15px", height: "15px", color: "var(--color-primary)", flexShrink: 0 }} />
            <span>{t("chat.menu.uploadFile")}</span>
          </button>

          {/* 粘贴剪贴板 */}
          <button
            onClick={() => { onClose(); onPasteClipboard?.(); }}
            style={popoverItemStyle}
            onMouseEnter={(e) => { e.currentTarget.style.background = itemHoverBackground; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
          >
            <Clipboard style={{ width: "15px", height: "15px", color: "var(--color-primary)", flexShrink: 0 }} />
            <span>{t("chat.menu.pasteClipboard")}</span>
          </button>

          {/* 添加 Skill：二级面板列出已安装 Skill，点选即会话级注入 */}
          <div style={{ position: "relative" }}>
            <button
              onClick={() => setSkillSubOpen((v) => !v)}
              style={{
                ...popoverItemStyle,
                justifyContent: "space-between",
                background: skillSubOpen ? "var(--bg-level-3)" : "transparent",
              }}
              onMouseEnter={(e) => { e.currentTarget.style.background = itemHoverBackground; }}
              onMouseLeave={(e) => { if (!skillSubOpen) e.currentTarget.style.background = "transparent"; }}
            >
              <span style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <Sparkles style={{ width: "15px", height: "15px", color: "var(--color-primary)", flexShrink: 0 }} />
                <span>{t("chat.menu.addSkill")}</span>
              </span>
              <span style={{ color: "var(--text-level-4)", fontSize: "11px" }}>
                {(activeSkillIds?.size ?? 0) > 0 ? activeSkillIds!.size : ""}
              </span>
            </button>

            {skillSubOpen && (
              <div
                style={{
                  position: "absolute",
                  left: "100%",
                  top: "-4px",
                  marginLeft: "4px",
                  minWidth: "200px",
                  maxHeight: "260px",
                  overflowY: "auto",
                  background: "var(--bg-level-1)",
                  border: "1px solid var(--border-primary)",
                  borderRadius: "var(--radius-md)",
                  boxShadow: "var(--shadow-lg)",
                  padding: "4px",
                  zIndex: 1000,
                }}
              >
                {installedSkills.length === 0 ? (
                  <div style={{ padding: "8px 10px", fontSize: "11px", color: "var(--text-level-4)", lineHeight: "1.5" }}>
                    {t("chat.menu.noInstalledSkills")}
                  </div>
                ) : (
                  <>
                    {/* 搜索框：按 name/description/category/tags 本地模糊过滤 */}
                    <div style={{ position: "relative", marginBottom: "4px" }}>
                      <Search style={{
                        position: "absolute",
                        left: "8px",
                        top: "50%",
                        transform: "translateY(-50%)",
                        width: "13px",
                        height: "13px",
                        color: "var(--text-level-4)",
                        pointerEvents: "none",
                      }} />
                      <input
                        value={skillQuery}
                        onChange={(e) => setSkillQuery(e.target.value)}
                        placeholder={t("chat.menu.skillSearch")}
                        style={{
                          width: "100%",
                          padding: "5px 8px 5px 26px",
                          borderRadius: "var(--radius-sm)",
                          border: "1px solid var(--border-primary)",
                          background: "var(--bg-level-2)",
                          color: "var(--text-level-1)",
                          fontSize: "12px",
                          outline: "none",
                          boxSizing: "border-box",
                        }}
                      />
                    </div>
                    <div style={{ padding: "2px 10px 6px", fontSize: "11px", color: "var(--text-level-4)" }}>
                      {t("chat.menu.installedSkills")}
                    </div>
                    {filteredSkills.length === 0 ? (
                      <div style={{ padding: "8px 10px", fontSize: "11px", color: "var(--text-level-4)", lineHeight: "1.5" }}>
                        {t("chat.menu.skillSearchEmpty")}
                      </div>
                    ) : (
                      filteredSkills.map((skill) => {
                        const active = activeSkillIds?.has(skill.id) ?? false;
                        return (
                          <button
                            key={skill.id}
                            onClick={() => {
                              onClose();
                              if (active) onRemoveSkill?.(skill.id);
                              else onApplySkill?.(skill);
                            }}
                            style={{
                              display: "flex",
                              alignItems: "center",
                              gap: "8px",
                              width: "100%",
                              padding: "6px 10px",
                              border: "none",
                              borderRadius: "var(--radius-sm)",
                              background: "transparent",
                              cursor: "pointer",
                              fontSize: "12px",
                              color: "var(--text-level-2)",
                              textAlign: "left",
                              outline: "none",
                            }}
                            onMouseEnter={(e) => { e.currentTarget.style.background = itemHoverBackground; }}
                            onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
                            title={skill.description}
                          >
                            <div style={{ flex: 1, minWidth: 0 }}>
                              <span style={{ display: "block", fontSize: "12px", color: "var(--text-level-1)" }}>{skill.name}</span>
                              <span style={{
                                display: "block",
                                fontSize: "10px",
                                color: "var(--text-level-4)",
                                overflow: "hidden",
                                textOverflow: "ellipsis",
                                whiteSpace: "nowrap",
                              }}>{skill.description}</span>
                            </div>
                            {active && <Check style={{ width: "13px", height: "13px", color: "var(--color-primary)", flexShrink: 0 }} />}
                          </button>
                        );
                      })
                    )}
                  </>
                )}
              </div>
            )}
          </div>

          <div style={{
            height: "1px",
            background: "var(--border-secondary)",
            margin: "4px 0",
          }} />

          {/* 清除上下文：真实清空对话历史，需二次确认 */}
          {confirming ? (
            <div style={{ padding: "8px 10px" }}>
              <div style={{ fontSize: "12px", fontWeight: "600", color: "var(--text-level-1)", marginBottom: "2px" }}>
                {t("chat.menu.confirmClearTitle")}
              </div>
              <div style={{ fontSize: "11px", color: "var(--text-level-3)", marginBottom: "8px", lineHeight: "1.5" }}>
                {t("chat.menu.confirmClearDesc")}
              </div>
              <div style={{ display: "flex", gap: "6px", justifyContent: "flex-end" }}>
                <button
                  onClick={() => setConfirming(false)}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "4px",
                    padding: "4px 10px",
                    borderRadius: "var(--radius-sm)",
                    border: "1px solid var(--border-primary)",
                    background: "transparent",
                    cursor: "pointer",
                    fontSize: "12px",
                    color: "var(--text-level-2)",
                  }}
                >
                  <X style={{ width: "12px", height: "12px" }} />
                  {t("chat.menu.cancel")}
                </button>
                <button
                  onClick={() => { setConfirming(false); onClose(); onClearContext(); }}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "4px",
                    padding: "4px 10px",
                    borderRadius: "var(--radius-sm)",
                    border: "1px solid var(--color-error)",
                    background: "var(--color-error)",
                    cursor: "pointer",
                    fontSize: "12px",
                    color: "#fff",
                  }}
                >
                  <Trash2 style={{ width: "12px", height: "12px" }} />
                  {t("chat.menu.confirm")}
                </button>
              </div>
            </div>
          ) : (
            <button
              onClick={() => { if (hasContext) setConfirming(true); }}
              disabled={!hasContext}
              style={{
                ...popoverItemStyle,
                color: hasContext ? "var(--color-error)" : "var(--text-level-4)",
                cursor: hasContext ? "pointer" : "not-allowed",
              }}
              onMouseEnter={(e) => { if (hasContext) e.currentTarget.style.background = itemHoverBackground; }}
              onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
            >
              <Trash2 style={{ width: "15px", height: "15px", color: hasContext ? "var(--color-error)" : "var(--text-level-4)", flexShrink: 0 }} />
              <span>{t("chat.menu.clearContext")}</span>
            </button>
          )}
        </div>
      )}
    </div>
  );
}
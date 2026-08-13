"use client";

import { useState } from "react";
import { FolderOpen, RotateCcw, Trash2, Archive as ArchiveIcon, FolderCog } from "lucide-react";
import { useArchive } from "@/hooks/useArchive";
import { useTranslation } from "@/hooks/useTranslation";
import { useSettingsStore } from "@/lib/store";
import { selectDirectory } from "@/lib/selectDirectory";

/**
 * ArchivePanel —— 设置中的「归档」管理面板
 * - 归档文件夹路径配置（可切换目录 / 恢复默认）
 * - 归档列表：项目与会话，可恢复（回主列表）或彻底删除（删归档文件 + 物理删库）
 */
export function ArchivePanel() {
  const { t } = useTranslation();
  const { data, loading, error, refetch, restoreProject, restoreChat, purgeProject, purgeChat } = useArchive();
  const { settings, updateSetting } = useSettingsStore();
  const [dirDraft, setDirDraft] = useState<string | null>(null);
  const [savingDir, setSavingDir] = useState(false);

  const archiveDir = data.archive_dir;
  const dirValue = dirDraft != null ? dirDraft : archiveDir;

  const handlePickDir = async () => {
    const dir = await selectDirectory();
    if (!dir) return;
    setDirDraft(dir);
  };

  const handleSaveDir = async () => {
    const val = (dirValue || "").trim();
    setSavingDir(true);
    try {
      await updateSetting("archive_dir", val);
      setDirDraft(null);
      await refetch();
    } catch (err) {
      console.error("Failed to save archive dir:", err);
    } finally {
      setSavingDir(false);
    }
  };

  const handleRestore = async (item: { type: "project" | "chat"; id: number }) => {
    try {
      if (item.type === "project") await restoreProject(item.id);
      else await restoreChat(item.id);
    } catch (err) {
      console.error("Failed to restore archive:", err);
    }
  };

  const handlePurge = async (item: { type: "project" | "chat"; id: number; name: string }) => {
    if (!window.confirm(t("settings.archive.purgeConfirm", { name: item.name }))) return;
    try {
      if (item.type === "project") await purgeProject(item.id);
      else await purgeChat(item.id);
    } catch (err) {
      console.error("Failed to purge archive:", err);
    }
  };

  const rowStyle: React.CSSProperties = {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    padding: "8px 10px",
    borderRadius: "var(--radius-md)",
    background: "var(--bg-level-2)",
    marginBottom: "6px",
  };

  const iconBtnStyle: React.CSSProperties = {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    width: "26px",
    height: "26px",
    padding: 0,
    border: "none",
    borderRadius: "var(--radius-sm)",
    background: "transparent",
    cursor: "pointer",
    flexShrink: 0,
  };

  return (
    <div>
      {/* ── 归档文件夹路径 ── */}
      <div style={{
        padding: "12px",
        borderRadius: "var(--radius-md)",
        background: "var(--bg-level-2)",
        marginBottom: "16px",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "8px" }}>
          <FolderCog style={{ width: "15px", height: "15px", color: "var(--text-level-3)" }} />
          <span style={{ fontSize: "13px", fontWeight: 600, color: "var(--text-level-2)" }}>
            {t("settings.archive.dirTitle")}
          </span>
        </div>
        <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
          <input
            value={dirValue}
            onChange={(e) => setDirDraft(e.target.value)}
            placeholder={t("settings.archive.dirDefaultHint")}
            style={{
              flex: 1,
              fontSize: "12px",
              padding: "6px 8px",
              borderRadius: "var(--radius-sm)",
              border: "1px solid var(--border-primary)",
              background: "var(--bg-level-1)",
              color: "var(--text-level-2)",
              outline: "none",
              minWidth: 0,
            }}
          />
          <button
            onClick={handlePickDir}
            title={t("settings.archive.pickDir")}
            style={iconBtnStyle}
            onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-level-3)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
          >
            <FolderOpen style={{ width: "15px", height: "15px", color: "var(--text-level-2)" }} />
          </button>
          <button
            onClick={handleSaveDir}
            disabled={savingDir}
            style={{
              padding: "6px 12px",
              fontSize: "12px",
              borderRadius: "var(--radius-sm)",
              border: "none",
              background: "var(--color-primary)",
              color: "#fff",
              cursor: savingDir ? "default" : "pointer",
              opacity: savingDir ? 0.6 : 1,
            }}
          >
            {t("common.save")}
          </button>
        </div>
        <p style={{ fontSize: "11px", color: "var(--text-level-4)", margin: "8px 0 0" }}>
          {t("settings.archive.dirHint")}
        </p>
      </div>

      {/* ── 归档列表 ── */}
      <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "8px" }}>
        <ArchiveIcon style={{ width: "15px", height: "15px", color: "var(--text-level-3)" }} />
        <span style={{ fontSize: "13px", fontWeight: 600, color: "var(--text-level-2)" }}>
          {t("settings.archive.listTitle")}
        </span>
      </div>

      {loading ? (
        <p style={{ color: "var(--text-level-3)", fontSize: "12px" }}>{t("common.loading")}</p>
      ) : error ? (
        <p style={{ color: "var(--color-error)", fontSize: "12px" }}>{error}</p>
      ) : data.items.length === 0 ? (
        <p style={{ color: "var(--text-level-4)", fontSize: "12px", padding: "12px 0" }}>
          {t("settings.archive.empty")}
        </p>
      ) : (
        data.items.map((item) => (
          <div key={`${item.type}-${item.id}`} style={rowStyle}>
            <span style={{
              fontSize: "10px",
              fontWeight: 600,
              padding: "2px 6px",
              borderRadius: "var(--radius-sm)",
              background: item.type === "project" ? "var(--bg-level-3)" : "transparent",
              border: "1px solid var(--border-primary)",
              color: "var(--text-level-3)",
              flexShrink: 0,
            }}>
              {item.type === "project" ? t("settings.archive.typeProject") : t("settings.archive.typeChat")}
            </span>
            <span style={{
              flex: 1,
              minWidth: 0,
              fontSize: "13px",
              color: "var(--text-level-1)",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }} title={item.name}>
              {item.name}
            </span>
            {item.archived_at && (
              <span style={{ fontSize: "11px", color: "var(--text-level-4)", flexShrink: 0 }}>
                {new Date(item.archived_at).toLocaleString()}
              </span>
            )}
            <button
              onClick={() => handleRestore(item)}
              title={t("settings.archive.restore")}
              style={iconBtnStyle}
              onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-level-3)"; e.currentTarget.style.color = "var(--color-primary)"; }}
              onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = "var(--text-level-2)"; }}
            >
              <RotateCcw style={{ width: "14px", height: "14px", color: "var(--color-primary)" }} />
            </button>
            <button
              onClick={() => handlePurge(item)}
              title={t("settings.archive.purge")}
              style={iconBtnStyle}
              onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-level-3)"; }}
              onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
            >
              <Trash2 style={{ width: "14px", height: "14px", color: "var(--color-error)" }} />
            </button>
          </div>
        ))
      )}
    </div>
  );
}

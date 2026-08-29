"use client";

import { useState, useEffect } from "react";
import { FolderOpen, RotateCcw, Trash2, Archive as ArchiveIcon, FolderCog, Image as ImageIcon, Database as DatabaseIcon, Save } from "lucide-react";
import { useArchive } from "@/hooks/useArchive";
import { useTranslation } from "@/hooks/useTranslation";
import { useSettingsStore } from "@/lib/store";
import { selectDirectory } from "@/lib/selectDirectory";
import { getDatabaseInfo, createDatabaseBackup, type DatabaseInfo } from "@/lib/api";

/**
 * ArchivePanel —— 设置中的「数据与存储」管理面板
 * - 数据位置总览（会话数据库路径/大小 + 备份）
 * - 图片保存位置（AI 生成图片落盘目录，相对项目根）
 * - 归档文件夹路径配置（可切换目录 / 恢复默认）
 * - 归档列表：项目与会话，可恢复（回主列表）或彻底删除（删归档文件 + 物理删库）
 */
export function ArchivePanel() {
  const { t } = useTranslation();
  const { data, loading, error, refetch, restoreProject, restoreChat, purgeProject, purgeChat } = useArchive();
  const { settings, updateSetting } = useSettingsStore();
  const [dirDraft, setDirDraft] = useState<string | null>(null);
  const [savingDir, setSavingDir] = useState(false);
  // 图片保存位置（image_output_dir，相对项目根；空 = 默认 output/generated_images）
  const [imgDirDraft, setImgDirDraft] = useState<string | null>(null);
  const [savingImgDir, setSavingImgDir] = useState(false);
  // 数据位置总览（后端 /api/backup/info）
  const [dbInfo, setDbInfo] = useState<DatabaseInfo | null>(null);
  const [dbInfoError, setDbInfoError] = useState(false);
  const [backingUp, setBackingUp] = useState(false);

  // 拉取数据位置总览（数据库路径/大小/备份目录/数量）；失败时标记 error，供界面显示"加载失败 + 重试"
  useEffect(() => {
    let cancelled = false;
    getDatabaseInfo()
      .then((info) => { if (!cancelled) setDbInfo(info); })
      .catch((err) => {
        if (!cancelled) {
          console.error("[ArchivePanel] getDatabaseInfo failed:", err);
          setDbInfoError(true);
        }
      });
    return () => { cancelled = true; };
  }, []);

  const handleBackup = async () => {
    setBackingUp(true);
    try {
      await createDatabaseBackup();
      const info = await getDatabaseInfo();
      setDbInfo(info);
      setDbInfoError(false);
    } catch (err) {
      console.error("Failed to create backup:", err);
    } finally {
      setBackingUp(false);
    }
  };

  const openInFolder = (path: string) => {
    if (typeof window !== "undefined" && window.electronAPI?.openInFolder) {
      window.electronAPI.openInFolder(path);
    }
  };

  // 数据位置重试：清空错误态后重新拉取（供"加载失败"提示上的重试按钮使用）
  const retryDbInfo = () => {
    setDbInfoError(false);
    getDatabaseInfo()
      .then((info) => setDbInfo(info))
      .catch((err) => {
        console.error("[ArchivePanel] getDatabaseInfo retry failed:", err);
        setDbInfoError(true);
      });
  };

  const fmtSize = (bytes: number) => {
    if (!bytes) return "-";
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  };

  const archiveDir = data.archive_dir;
  const dirValue = dirDraft != null ? dirDraft : archiveDir;
  const imgDirValue = imgDirDraft != null ? imgDirDraft : (settings?.image_output_dir ?? "");

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

  const handlePickImgDir = async () => {
    const dir = await selectDirectory();
    if (!dir) return;
    setImgDirDraft(dir);
  };

  const handleSaveImgDir = async () => {
    const val = (imgDirValue || "").trim();
    setSavingImgDir(true);
    try {
      await updateSetting("image_output_dir", val);
      setImgDirDraft(null);
    } catch (err) {
      console.error("Failed to save image output dir:", err);
    } finally {
      setSavingImgDir(false);
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
    cursor: "pointer",
    flexShrink: 0,
  };

  // 段标题 + 描述（统一紧凑风格：14px / 600，段标题醒目）
  const sectionTitleStyle: React.CSSProperties = {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    fontSize: "14px",
    fontWeight: 600,
    color: "var(--text-level-1)",
  };

  // 数据位置段内标签（统一 12px / 500，灰色）
  const dataRowLabelStyle: React.CSSProperties = {
    fontSize: 12,
    fontWeight: 500,
    color: "var(--text-level-3)",
    width: 64,
    flexShrink: 0,
  };

  // 段内分组容器：标题 + 内容
  const sectionStyle: React.CSSProperties = { padding: "12px 0" };

  // 段间分隔线（最后一段不画）
  const dividerStyle: React.CSSProperties = {
    height: "1px",
    background: "var(--border-primary)",
    margin: "0",
  };

  // 数据位置加载态：失败 → "加载失败 + 重试"；否则 → "加载中…"
  const dbFallback = dbInfoError ? (
    <span style={{ display: "flex", alignItems: "center", gap: 6, flex: 1, minWidth: 0 }}>
      <span style={{ fontSize: 11, color: "var(--color-error)", flexShrink: 0 }}>加载失败</span>
      <button
        onClick={retryDbInfo}
        className="mf-btn-secondary"
        style={{
          display: "inline-flex", alignItems: "center",
          padding: "2px 8px", fontSize: 11, borderRadius: "var(--radius-sm)",
          border: "1px solid var(--border-primary)",
          background: "var(--bg-level-1)",
          color: "var(--text-level-2)",
          cursor: "pointer",
          flexShrink: 0,
        }}
      >重试</button>
    </span>
  ) : (
    <span style={{ flex: 1, fontSize: 11, color: "var(--text-level-4)" }}>加载中…</span>
  );

  return (
    <div style={{
      padding: "4px 14px 14px",
      borderRadius: "var(--radius-md)",
      background: "var(--bg-level-2)",
    }}>
      {/* ── 数据位置总览：会话数据库 + 备份 ── */}
      <div style={sectionStyle}>
        <div style={{ ...sectionTitleStyle, marginBottom: "10px" }}>
          <DatabaseIcon style={{ width: "15px", height: "15px", color: "var(--text-level-3)" }} />
          数据位置
        </div>
        {/* 会话数据库行 */}
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: "8px" }}>
          <span style={dataRowLabelStyle}>会话数据库</span>
          {dbInfo ? (
            <>
              <code style={{
                flex: 1, minWidth: 0, fontSize: 12,
                fontFamily: "var(--font-family-mono, var(--font-mono, monospace))",
                color: "var(--text-level-2)",
                overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
              }} title={dbInfo.db_path}>{dbInfo.db_path}</code>
              <span style={{ fontSize: 12, fontWeight: 500, color: "var(--text-level-3)", fontVariantNumeric: "tabular-nums", flexShrink: 0 }}>
                {fmtSize(dbInfo.db_size)}
              </span>
              <button
                onClick={() => openInFolder(dbInfo.db_path)}
                title="在文件管理器中打开"
                className="mf-icon-btn"
                style={iconBtnStyle}
              >
                <FolderOpen style={{ width: 14, height: 14, color: "var(--text-level-2)" }} />
              </button>
            </>
          ) : (
            dbFallback
          )}
        </div>
        {/* 备份行 */}
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={dataRowLabelStyle}>数据库备份</span>
          {dbInfo ? (
            <>
              <span style={{
                flex: 1, minWidth: 0, fontSize: 12,
                overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                color: "var(--text-level-2)",
              }} title={dbInfo.backup_dir}>{dbInfo.backup_dir}</span>
              <span style={{ fontSize: 12, fontWeight: 500, color: "var(--text-level-3)", fontVariantNumeric: "tabular-nums", flexShrink: 0 }}>
                {dbInfo.backup_count} 份
              </span>
              <button
                onClick={handleBackup}
                disabled={backingUp}
                className="mf-btn-secondary"
                style={{
                  display: "flex", alignItems: "center", gap: 4,
                  padding: "4px 10px", fontSize: 11, borderRadius: "var(--radius-sm)",
                  border: "1px solid var(--color-primary)",
                  background: "var(--color-primary-lighter)",
                  color: "var(--color-primary)",
                  cursor: backingUp ? "default" : "pointer",
                  opacity: backingUp ? 0.6 : 1,
                  whiteSpace: "nowrap",
                  flexShrink: 0,
                }}
              >
                <Save style={{ width: 12, height: 12 }} />
                {backingUp ? "备份中…" : "一键备份"}
              </button>
            </>
          ) : (
            dbFallback
          )}
        </div>
      </div>

      <div style={dividerStyle} />

      {/* ── 图片保存位置（AI 生成图片落盘目录） ── */}
      <div style={sectionStyle}>
        <div style={{ ...sectionTitleStyle, marginBottom: "10px" }}>
          <ImageIcon style={{ width: "15px", height: "15px", color: "var(--text-level-3)" }} />
          {t("settings.archive.imageDirTitle")}
        </div>
        <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
          <input
            value={imgDirValue}
            onChange={(e) => setImgDirDraft(e.target.value)}
            placeholder={t("settings.archive.dirDefaultHint")}
            className="mf-input"
            style={{
              flex: 1,
              fontSize: "12px",
              padding: "6px 8px",
              borderRadius: "var(--radius-sm)",
              background: "var(--bg-level-1)",
              color: "var(--text-level-2)",
              minWidth: 0,
            }}
          />
          <button
            onClick={handlePickImgDir}
            title={t("settings.archive.pickDir")}
            className="mf-icon-btn"
            style={iconBtnStyle}
          >
            <FolderOpen style={{ width: "15px", height: "15px", color: "var(--text-level-2)" }} />
          </button>
          <button
            onClick={handleSaveImgDir}
            disabled={savingImgDir}
            className="mf-btn-primary"
            style={{
              padding: "6px 12px",
              fontSize: "12px",
              borderRadius: "var(--radius-sm)",
              border: "none",
              background: "var(--color-primary)",
              color: "#fff",
              cursor: savingImgDir ? "default" : "pointer",
              opacity: savingImgDir ? 0.6 : 1,
            }}
          >
            {t("common.save")}
          </button>
        </div>
        <p style={{ fontSize: "11px", color: "var(--text-level-4)", margin: "6px 0 0" }}>
          {t("settings.archive.imageDirHint")}
        </p>
      </div>

      <div style={dividerStyle} />

      {/* ── 归档文件夹路径 ── */}
      <div style={sectionStyle}>
        <div style={{ ...sectionTitleStyle, marginBottom: "10px" }}>
          <FolderCog style={{ width: "15px", height: "15px", color: "var(--text-level-3)" }} />
          {t("settings.archive.dirTitle")}
        </div>
        <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
          <input
            value={dirValue}
            onChange={(e) => setDirDraft(e.target.value)}
            placeholder={t("settings.archive.dirDefaultHint")}
            className="mf-input"
            style={{
              flex: 1,
              fontSize: "12px",
              padding: "6px 8px",
              borderRadius: "var(--radius-sm)",
              background: "var(--bg-level-1)",
              color: "var(--text-level-2)",
              minWidth: 0,
            }}
          />
          <button
            onClick={handlePickDir}
            title={t("settings.archive.pickDir")}
            className="mf-icon-btn"
            style={iconBtnStyle}
          >
            <FolderOpen style={{ width: "15px", height: "15px", color: "var(--text-level-2)" }} />
          </button>
          <button
            onClick={handleSaveDir}
            disabled={savingDir}
            className="mf-btn-primary"
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
        <p style={{ fontSize: "11px", color: "var(--text-level-4)", margin: "6px 0 0" }}>
          {t("settings.archive.dirHint")}
        </p>
      </div>

      <div style={dividerStyle} />

      {/* ── 归档列表 ── */}
      <div style={sectionStyle}>
        <div style={{ ...sectionTitleStyle, marginBottom: "8px" }}>
          <ArchiveIcon style={{ width: "15px", height: "15px", color: "var(--text-level-3)" }} />
          {t("settings.archive.listTitle")}
        </div>

        {loading ? (
          <p style={{ color: "var(--text-level-3)", fontSize: "12px" }}>{t("common.loading")}</p>
        ) : error ? (
          <p style={{ color: "var(--color-error)", fontSize: "12px" }}>{error}</p>
        ) : data.items.length === 0 ? (
          <p style={{ color: "var(--text-level-4)", fontSize: "12px" }}>
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
                className="mf-icon-btn"
                style={iconBtnStyle}
              >
                <RotateCcw style={{ width: 14, height: 14, color: "var(--color-primary)" }} />
              </button>
              <button
                onClick={() => handlePurge(item)}
                title={t("settings.archive.purge")}
                className="mf-icon-btn"
                style={iconBtnStyle}
              >
                <Trash2 style={{ width: 14, height: 14, color: "var(--color-error)" }} />
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

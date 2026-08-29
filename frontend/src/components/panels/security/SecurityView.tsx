"use client";

/**
 * SecurityView —— 安全中心（专业向安全可视化，紧凑布局）
 *
 * 结构：
 *   顶部：审批模式（始终可见）
 *   折叠区域「故障排查」：审批矩阵 | 审计日志 | 运行状态 | 应用日志
 * 纯只读消费后端 /api/security/*，不修改任何执行链。
 */
import { useEffect, useState, useCallback } from "react";
import {
  Shield, ShieldCheck, Zap, Check, Download, RefreshCw, Clock,
  HardDrive, Lock, Activity, Search, Terminal,
  AlertTriangle, XCircle, ChevronDown, ListChecks, FolderX,
} from "lucide-react";
import type { SettingsViewProps } from "../BasicSettingsView";
import {
  getSecurityPolicy, getSecurityStatus, getAuditLogs, getAuditExportUrl,
  getLogContent, getLogDownloadUrl, getApprovals, previewCommandRisk, getGuardrails,
} from "@/lib/api";
import type {
  PolicyData, SecurityStatus, AuditItem, PolicyAction,
  LogLine, ApprovalItem, ApprovalStatus, CommandRiskResult,
  RiskVerdict, RiskLevel, GuardrailsData, AllowedCommand,
} from "@/lib/api";

type TroubleshootTab = "matrix" | "audit" | "status" | "logs";
type GuardTab = "approvals" | "command-risk" | "guardrails";

const TROUBLESHOOT_TABS: { id: TroubleshootTab; labelKey: string }[] = [
  { id: "matrix", labelKey: "settings.security.matrix" },
  { id: "audit", labelKey: "settings.security.audit" },
  { id: "status", labelKey: "settings.security.status" },
  { id: "logs", labelKey: "settings.security.log.title" },
];

const GUARD_TABS: { id: GuardTab; labelKey: string }[] = [
  { id: "approvals", labelKey: "settings.security.approvals" },
  { id: "command-risk", labelKey: "settings.security.commandRisk" },
  { id: "guardrails", labelKey: "settings.security.guardrails" },
];

/** 权限模式全局预设（写 settings.agent_permission_mode；会话级可被聊天输入框权限胶囊覆盖） */
const PERMISSION_PRESETS: {
  id: "safe" | "standard" | "autonomous";
  label: string;
  desc: string;
  icon: typeof ShieldCheck;
}[] = [
  { id: "safe", label: "谨慎", desc: "关键操作都先问你", icon: ShieldCheck },
  { id: "standard", label: "标准", desc: "只读自动 · 写操作按规则审批", icon: Shield },
  { id: "autonomous", label: "自主", desc: "低风险操作自动执行", icon: Zap },
];

const ACTION_META: Record<PolicyAction, { text: string; color: string; bg: string }> = {
  allow:   { text: "放行", color: "#16a34a", bg: "rgba(22,163,74,0.12)" },
  approve: { text: "审批", color: "#d97706", bg: "rgba(217,119,6,0.12)" },
  block:   { text: "拦截", color: "#dc2626", bg: "rgba(220,38,38,0.12)" },
};

function Badge({ action }: { action: PolicyAction }) {
  const m = ACTION_META[action];
  return (
    <span style={{
      display: "inline-block", padding: "2px 8px", borderRadius: "var(--radius-sm)",
      fontSize: 11, fontWeight: 600, lineHeight: "18px",
      color: m.color, background: m.bg, whiteSpace: "nowrap",
    }}>{m.text}</span>
  );
}

// ───────────────────── 审批矩阵 ─────────────────────
function MatrixView() {
  const [data, setData] = useState<PolicyData | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const load = useCallback(() => {
    setErr(null);
    getSecurityPolicy().then(setData).catch((e) => setErr(String(e?.message ?? e)));
  }, []);
  useEffect(load, [load]);

  if (err) return <p style={{ fontSize: 12, color: "var(--color-error)" }}>加载失败: {err}</p>;
  if (!data) return <p style={{ fontSize: 12, color: "var(--text-level-3)" }}>加载中…</p>;

  const grouped: Record<string, typeof data.write_tools> = {};
  for (const t of data.write_tools) {
    if (!grouped[t.category]) grouped[t.category] = [];
    grouped[t.category].push(t);
  }

  return (
    <div>
      <p style={{ fontSize: 12, color: "var(--text-level-3)", margin: "0 0 8px 0", lineHeight: 1.4 }}>
        {data.note}
      </p>
      <div style={{ display: "flex", gap: 4, marginBottom: 8, fontSize: 11, color: "var(--text-level-4)" }}>
        <span style={{ width: 120 }}>工具</span>
        {data.modes.map((m) => (
          <span key={m} style={{ flex: 1, textAlign: "center" }}>{m}</span>
        ))}
      </div>
      {Object.entries(grouped).map(([cat, tools]) => (
        <div key={cat} style={{ marginBottom: 8 }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: "var(--text-level-3)", marginBottom: 4 }}>{cat}</div>
          {tools.map((tool) => (
            <div
              key={tool.name}
              title={tool.reason}
              style={{
                display: "flex", gap: 4, alignItems: "center",
                padding: "4px 0", borderBottom: "1px solid var(--border-primary)",
                fontSize: 12,
              }}
            >
              <span style={{ width: 120, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                color: "var(--text-level-2)" }}>
                {tool.name}
              </span>
              {data.modes.map((m) => (
                <span key={m} style={{ flex: 1, textAlign: "center" }}>
                  <Badge action={tool.actions[m] || "block"} />
                </span>
              ))}
            </div>
          ))}
        </div>
      ))}
      {/* 只读工具列表 */}
      <details style={{ marginTop: 8 }}>
        <summary style={{ fontSize: 12, cursor: "pointer", color: "var(--text-level-3)" }}>
          只读工具（{data.read_only_tools.length} 项，全部自动放行）
        </summary>
        <div style={{ display: "flex", flexWrap: "wrap", gap: "4px 8px", marginTop: 8, fontSize: 11, color: "var(--text-level-4)" }}>
          {data.read_only_tools.map((t) => <span key={t}>{t}</span>)}
        </div>
      </details>
    </div>
  );
}

// ───────────────────── 审计日志 ─────────────────────
function AuditView() {
  const [items, setItems] = useState<AuditItem[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [toolFilter, setToolFilter] = useState("");
  const [successFilter, setSuccessFilter] = useState<"" | "true" | "false">("");
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async (o: number) => {
    setErr(null);
    try {
      const page = await getAuditLogs({
        limit: 30, offset: o,
        tool_name: toolFilter || undefined,
        success: successFilter === "" ? undefined : successFilter === "true",
      });
      setItems(page.items);
      setTotal(page.total);
      setOffset(o);
    } catch (e: any) {
      setErr(String(e?.message ?? e));
    }
  }, [toolFilter, successFilter]);

  useEffect(() => { load(0); }, [load]);

  const fmt = (ms: number) => ms >= 1000 ? `${(ms / 1000).toFixed(1)}s` : `${ms}ms`;

  return (
    <div>
      {/* 筛选栏 */}
      <div style={{ display: "flex", gap: 4, marginBottom: 8, alignItems: "center" }}>
        <input
          placeholder="工具名筛选"
          value={toolFilter}
          onChange={(e) => setToolFilter(e.target.value)}
          style={{
            flex: 1, padding: "4px 8px", fontSize: 12, borderRadius: "var(--radius-sm)",
            border: "1px solid var(--border-primary)", background: "var(--bg-level-2)",
            color: "var(--text-level-2)", outline: "none",
          }}
        />
        <select
          value={successFilter}
          onChange={(e) => setSuccessFilter(e.target.value as any)}
          style={{
            padding: "4px 8px", fontSize: 12, borderRadius: "var(--radius-sm)",
            border: "1px solid var(--border-primary)", background: "var(--bg-level-2)",
            color: "var(--text-level-2)", outline: "none",
          }}
        >
          <option value="">全部</option>
          <option value="true">成功</option>
          <option value="false">失败</option>
        </select>
        <button onClick={() => load(0)} style={{
          padding: "4px 8px", fontSize: 12, borderRadius: "var(--radius-sm)",
          border: "1px solid var(--border-primary)", background: "var(--bg-level-2)",
          cursor: "pointer", color: "var(--text-level-2)", display: "flex", alignItems: "center", gap: 4,
        }}>
          <RefreshCw style={{ width: 12, height: 12 }} /> 刷新
        </button>
        <a
          href={getAuditExportUrl({
            tool_name: toolFilter || undefined,
            success: successFilter === "" ? undefined : successFilter === "true",
          })}
          download
          style={{
            padding: "4px 8px", fontSize: 12, borderRadius: "var(--radius-sm)",
            border: "1px solid var(--border-primary)", background: "var(--bg-level-2)",
            cursor: "pointer", color: "var(--text-level-2)", display: "flex", alignItems: "center", gap: 4,
            textDecoration: "none",
          }}
        >
          <Download style={{ width: 12, height: 12 }} /> 导出 CSV
        </a>
      </div>

      {err && <p style={{ fontSize: 12, color: "var(--color-error)" }}>{err}</p>}

      {items.length === 0 && !err && (
        <p style={{ fontSize: 12, color: "var(--text-level-3)" }}>暂无审计记录</p>
      )}

      {items.length > 0 && (
        <div style={{ fontSize: 11, lineHeight: 1.4 }}>
          <div style={{ display: "flex", gap: 4, padding: "4px 0", fontWeight: 600, color: "var(--text-level-3)",
            borderBottom: "1px solid var(--border-primary)" }}>
            <span style={{ width: 80 }}>时间</span>
            <span style={{ width: 80 }}>工具</span>
            <span style={{ flex: 1 }}>命令</span>
            <span style={{ width: 50, textAlign: "right" }}>耗时</span>
            <span style={{ width: 40, textAlign: "center" }}>结果</span>
          </div>
          {items.map((item) => (
            <div key={item.id} style={{
              display: "flex", gap: 4, padding: "4px 0", alignItems: "center",
              borderBottom: "1px solid var(--border-primary)",
              color: "var(--text-level-2)",
            }}>
              <span style={{ width: 80, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {item.created_at ? item.created_at.slice(11, 19) : "-"}
              </span>
              <span style={{ width: 80, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {item.tool_name}
              </span>
              <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {item.command}
              </span>
              <span style={{ width: 50, textAlign: "right", color: "var(--text-level-3)" }}>
                {fmt(item.duration_ms)}
              </span>
              <span style={{ width: 40, textAlign: "center" }}>
                {item.success
                  ? <Check style={{ width: 12, height: 12, color: "#16a34a" }} />
                  : <XCircle style={{ width: 12, height: 12, color: "#dc2626" }} />
                }
              </span>
            </div>
          ))}
          {/* 分页 */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 8 }}>
            <span style={{ fontSize: 11, color: "var(--text-level-3)" }}>
              共 {total} 条，当前 {offset + 1}–{offset + items.length}
            </span>
            <div style={{ display: "flex", gap: 4 }}>
              <button
                disabled={offset === 0}
                onClick={() => load(Math.max(0, offset - 30))}
                style={{
                  padding: "4px 8px", fontSize: 11, borderRadius: "var(--radius-sm)",
                  border: "1px solid var(--border-primary)", background: "var(--bg-level-2)",
                  cursor: offset === 0 ? "default" : "pointer", color: "var(--text-level-2)",
                }}
              >上一页</button>
              <button
                disabled={offset + 30 >= total}
                onClick={() => load(offset + 30)}
                style={{
                  padding: "4px 8px", fontSize: 11, borderRadius: "var(--radius-sm)",
                  border: "1px solid var(--border-primary)", background: "var(--bg-level-2)",
                  cursor: offset + 30 >= total ? "default" : "pointer", color: "var(--text-level-2)",
                }}
              >下一页</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ───────────────────── 运行状态 ─────────────────────
function StatusView() {
  const [data, setData] = useState<SecurityStatus | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const load = useCallback(() => {
    setErr(null);
    getSecurityStatus().then(setData).catch((e) => setErr(String(e?.message ?? e)));
  }, []);
  useEffect(load, [load]);

  if (err) return <p style={{ fontSize: 12, color: "var(--color-error)" }}>加载失败: {err}</p>;
  if (!data) return <p style={{ fontSize: 12, color: "var(--text-level-3)" }}>加载中…</p>;

  const rows: { label: string; value: string; icon: React.ReactNode }[] = [
    { label: "路径沙箱", value: data.sandbox_path_guard ? "已启用" : "未启用", icon: <Lock style={{ width: 14, height: 14 }} /> },
    { label: "禁执行目录", value: data.forbidden_dirs_enabled ? "已启用" : "未启用", icon: <Shield style={{ width: 14, height: 14 }} /> },
    { label: "磁盘配额", value: Object.entries(data.disk_quota_gb).map(([k, v]) => `${k} ≥${v}GB`).join(" · "), icon: <HardDrive style={{ width: 14, height: 14 }} /> },
    { label: "命令超时", value: `run_command ≤${data.run_command_timeout_sec}s · execute_command ≤${data.execute_command_timeout_sec}s`, icon: <Clock style={{ width: 14, height: 14 }} /> },
    { label: "输出上限", value: `≤${data.execute_command_output_chars} 字符`, icon: <Activity style={{ width: 14, height: 14 }} /> },
    { label: "Plan 只读", value: data.plan_readonly ? "是" : "否", icon: <Check style={{ width: 14, height: 14 }} /> },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      {rows.map((r) => (
        <div key={r.label} style={{
          display: "flex", alignItems: "center", gap: 8,
          padding: "4px 8px", borderRadius: "var(--radius-sm)",
          background: "var(--bg-level-2)", fontSize: 12,
        }}>
          <span style={{ color: "var(--text-level-3)", display: "flex" }}>{r.icon}</span>
          <span style={{ color: "var(--text-level-1)", fontWeight: 500, width: 80 }}>{r.label}</span>
          <span style={{ color: "var(--text-level-2)" }}>{r.value}</span>
        </div>
      ))}
    </div>
  );
}

// ───────────────────── 应用日志（LogViewer） ─────────────────────

function LogViewer({ t }: { t: (key: string) => string }) {
  const [lines, setLines] = useState<LogLine[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(100);
  const [level, setLevel] = useState<string>("");
  const [search, setSearch] = useState("");
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async (p: number) => {
    setErr(null);
    try {
      const data = await getLogContent({
        level: level || undefined,
        search: search || undefined,
        page: p,
        page_size: pageSize,
      });
      setLines(data.lines);
      setTotal(data.total);
      setPage(data.page);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }, [level, search, pageSize]);

  useEffect(() => { load(1); }, [load]);

  const totalPages = Math.ceil(total / pageSize);

  const levelColor: Record<string, string> = {
    ERROR: "#dc2626",
    WARNING: "#d97706",
    INFO: "var(--text-level-2)",
    DEBUG: "var(--text-level-4)",
  };

  const lg = (k: string) => t(`settings.security.log.${k}`);

  return (
    <div>
      {/* 工具栏 */}
      <div style={{ display: "flex", gap: 4, marginBottom: 8, alignItems: "center" }}>
        <select
          value={level}
          onChange={(e) => { setLevel(e.target.value); setPage(1); }}
          style={{
            padding: "4px 8px", fontSize: 12, borderRadius: "var(--radius-sm)",
            border: "1px solid var(--border-primary)", background: "var(--bg-level-2)",
            color: "var(--text-level-2)", outline: "none",
          }}
        >
          <option value="">{lg("levelAll")}</option>
          <option value="ERROR">{lg("levelError")}</option>
          <option value="WARNING">{lg("levelWarning")}</option>
          <option value="INFO">{lg("levelInfo")}</option>
          <option value="DEBUG">{lg("levelDebug")}</option>
        </select>
        <div style={{ position: "relative", flex: 1 }}>
          <Search style={{
            position: "absolute", left: 6, top: "50%", transform: "translateY(-50%)",
            width: 12, height: 12, color: "var(--text-level-4)",
          }} />
          <input
            placeholder={lg("search")}
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            style={{
              width: "100%", padding: "4px 8px 4px 24px", fontSize: 12,
              borderRadius: "var(--radius-sm)",
              border: "1px solid var(--border-primary)", background: "var(--bg-level-2)",
              color: "var(--text-level-2)", outline: "none", boxSizing: "border-box",
            }}
          />
        </div>
        <button onClick={() => load(page)} style={{
          padding: "4px 8px", fontSize: 12, borderRadius: "var(--radius-sm)",
          border: "1px solid var(--border-primary)", background: "var(--bg-level-2)",
          cursor: "pointer", color: "var(--text-level-2)", display: "flex", alignItems: "center", gap: 4,
        }}>
          <RefreshCw style={{ width: 12, height: 12 }} /> {lg("refresh")}
        </button>
        <a
          href={getLogDownloadUrl()}
          download
          style={{
            padding: "4px 8px", fontSize: 12, borderRadius: "var(--radius-sm)",
            border: "1px solid var(--border-primary)", background: "var(--bg-level-2)",
            cursor: "pointer", color: "var(--text-level-2)", display: "flex", alignItems: "center", gap: 4,
            textDecoration: "none",
          }}
        >
          <Download style={{ width: 12, height: 12 }} /> {lg("download")}
        </a>
      </div>

      {err && <p style={{ fontSize: 12, color: "var(--color-error)" }}>{lg("loadFailed")}: {err}</p>}

      {/* 日志内容 */}
      {lines.length === 0 && !err && (
        <p style={{ fontSize: 12, color: "var(--text-level-3)" }}>{lg("noLogs")}</p>
      )}

      {lines.length > 0 && (
        <div style={{
          fontSize: 11, fontFamily: "var(--font-mono, monospace)", lineHeight: 1.4,
          maxHeight: 360, overflowY: "auto",
          background: "var(--bg-level-2)", borderRadius: "var(--radius-sm)",
          border: "1px solid var(--border-primary)",
        }}>
          {lines.map((line, i) => (
            <div
              key={i}
              style={{
                padding: "2px 8px", whiteSpace: "pre-wrap", wordBreak: "break-all",
                borderBottom: "1px solid var(--border-primary)",
                background: line.level === "ERROR" ? "rgba(220,38,38,0.06)" : "transparent",
              }}
            >
              <span style={{ color: "var(--text-level-4)", marginRight: 8 }}>
                {line.timestamp}
              </span>
              <span style={{
                color: levelColor[line.level] || "var(--text-level-2)",
                fontWeight: line.level === "ERROR" ? 600 : 400,
                marginRight: 8,
              }}>
                {line.level}
              </span>
              <span style={{ color: "var(--text-level-2)" }}>
                {line.message}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* 分页 */}
      {total > 0 && (
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 8 }}>
          <span style={{ fontSize: 11, color: "var(--text-level-3)" }}>
            {lg("total").replace("{total}", String(total))}，第 {page}/{totalPages} 页
          </span>
          <div style={{ display: "flex", gap: 4 }}>
            <button
              disabled={page <= 1}
              onClick={() => load(page - 1)}
              style={{
                padding: "4px 8px", fontSize: 11, borderRadius: "var(--radius-sm)",
                border: "1px solid var(--border-primary)", background: "var(--bg-level-2)",
                cursor: page <= 1 ? "default" : "pointer", color: "var(--text-level-2)",
              }}
            >{lg("pagePrev")}</button>
            <button
              disabled={page >= totalPages}
              onClick={() => load(page + 1)}
              style={{
                padding: "4px 8px", fontSize: 11, borderRadius: "var(--radius-sm)",
                border: "1px solid var(--border-primary)", background: "var(--bg-level-2)",
                cursor: page >= totalPages ? "default" : "pointer", color: "var(--text-level-2)",
              }}
            >{lg("pageNext")}</button>
          </div>
        </div>
      )}
    </div>
  );
}

// ───────────────────── 审批记录 ─────────────────────

const APPROVAL_STATUS_META: Record<ApprovalStatus, { text: string; color: string; bg: string }> = {
  pending:   { text: "待审批", color: "#d97706", bg: "rgba(217,119,6,0.12)" },
  approve:   { text: "已批准", color: "#16a34a", bg: "rgba(22,163,74,0.12)" },
  deny:      { text: "已拒绝", color: "#dc2626", bg: "rgba(220,38,38,0.12)" },
  timeout:   { text: "已超时", color: "var(--text-level-3)", bg: "rgba(120,120,120,0.12)" },
  cancelled: { text: "已取消", color: "var(--text-level-3)", bg: "rgba(120,120,120,0.12)" },
};

const RISK_META: Record<RiskLevel, { text: string; color: string; bg: string }> = {
  read_only:  { text: "只读", color: "var(--text-level-3)", bg: "rgba(120,120,120,0.12)" },
  write:      { text: "写入", color: "#2563eb", bg: "rgba(37,99,235,0.12)" },
  destructive: { text: "破坏性", color: "#dc2626", bg: "rgba(220,38,38,0.12)" },
};

function MiniBadge({ text, color, bg }: { text: string; color: string; bg: string }) {
  return (
    <span style={{
      display: "inline-block", padding: "2px 8px", borderRadius: "var(--radius-sm)",
      fontSize: 11, fontWeight: 600, lineHeight: "18px",
      color, background: bg, whiteSpace: "nowrap",
    }}>{text}</span>
  );
}

function ApprovalsView({ t }: { t: (key: string) => string }) {
  const [items, setItems] = useState<ApprovalItem[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [statusFilter, setStatusFilter] = useState<"" | ApprovalStatus>("");
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async (o: number) => {
    setErr(null);
    try {
      const page = await getApprovals({
        limit: 30, offset: o,
        status: statusFilter || undefined,
      });
      setItems(page.items);
      setTotal(page.total);
      setOffset(o);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }, [statusFilter]);

  useEffect(() => { load(0); }, [load]);

  return (
    <div>
      {/* 状态筛选 */}
      <div style={{ display: "flex", gap: 4, marginBottom: 8, alignItems: "center" }}>
        {(["" as const, "pending", "approve", "deny", "timeout", "cancelled"] as ("" | ApprovalStatus)[]).map((s) => {
          const active = statusFilter === s;
          const label = s === "" ? t("settings.security.log.levelAll") : APPROVAL_STATUS_META[s].text;
          return (
            <button
              key={s || "all"}
              onClick={() => setStatusFilter(s as "" | ApprovalStatus)}
              style={{
                padding: "4px 8px", fontSize: 11, borderRadius: "var(--radius-sm)",
                border: "1px solid var(--border-primary)", cursor: "pointer",
                background: active ? "var(--color-primary)" : "var(--bg-level-2)",
                color: active ? "#fff" : "var(--text-level-2)",
                fontWeight: active ? 600 : 400,
                transition: "background var(--transition-fast), color var(--transition-fast)",
              }}
            >{label}</button>
          );
        })}
        <button onClick={() => load(offset)} style={{
          padding: "4px 8px", fontSize: 11, borderRadius: "var(--radius-sm)",
          border: "1px solid var(--border-primary)", background: "var(--bg-level-2)",
          cursor: "pointer", color: "var(--text-level-2)", display: "flex", alignItems: "center", gap: 4,
          marginLeft: "auto",
        }}>
          <RefreshCw style={{ width: 12, height: 12 }} /> {t("settings.security.log.refresh")}
        </button>
      </div>

      {err && <p style={{ fontSize: 12, color: "var(--color-error)" }}>{err}</p>}

      {items.length === 0 && !err && (
        <p style={{ fontSize: 12, color: "var(--text-level-3)" }}>
          {t("settings.security.noApprovals")}
        </p>
      )}

      {items.length > 0 && (
        <div style={{ fontSize: 11, lineHeight: 1.4 }}>
          <div style={{ display: "flex", gap: 4, padding: "4px 0", fontWeight: 600, color: "var(--text-level-3)",
            borderBottom: "1px solid var(--border-primary)" }}>
            <span style={{ width: 74 }}>{t("settings.security.colTime")}</span>
            <span style={{ width: 84 }}>{t("settings.security.colTool")}</span>
            <span style={{ flex: 1 }}>{t("settings.security.colCommand")}</span>
            <span style={{ width: 56, textAlign: "center" }}>{t("settings.security.colRisk")}</span>
            <span style={{ width: 60, textAlign: "center" }}>{t("settings.security.colStatus")}</span>
          </div>
          {items.map((item) => {
            const riskMeta = RISK_META[item.risk_level as RiskLevel] || RISK_META.read_only;
            const statusMeta = APPROVAL_STATUS_META[item.status];
            return (
              <div
                key={item.id}
                title={item.risk_reason || undefined}
                style={{
                  display: "flex", gap: 4, padding: "4px 0", alignItems: "center",
                  borderBottom: "1px solid var(--border-primary)",
                  color: "var(--text-level-2)",
                }}
              >
                <span style={{ width: 74, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {item.created_at ? item.created_at.slice(11, 19) : "-"}
                </span>
                <span style={{ width: 84, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {item.tool_name}
                </span>
                <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                  fontFamily: "var(--font-mono, monospace)" }}>
                  {item.command || "-"}
                </span>
                <span style={{ width: 56, textAlign: "center" }}>
                  <MiniBadge {...riskMeta} />
                </span>
                <span style={{ width: 60, textAlign: "center" }}>
                  <MiniBadge {...statusMeta} />
                </span>
              </div>
            );
          })}
          {/* 分页 */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 8 }}>
            <span style={{ fontSize: 11, color: "var(--text-level-3)" }}>
              {t("settings.security.log.total").replace("{total}", String(total))}，当前 {offset + 1}–{offset + items.length}
            </span>
            <div style={{ display: "flex", gap: 4 }}>
              <button
                disabled={offset === 0}
                onClick={() => load(Math.max(0, offset - 30))}
                style={{
                  padding: "4px 8px", fontSize: 11, borderRadius: "var(--radius-sm)",
                  border: "1px solid var(--border-primary)", background: "var(--bg-level-2)",
                  cursor: offset === 0 ? "default" : "pointer", color: "var(--text-level-2)",
                }}
              >{t("settings.security.log.pagePrev")}</button>
              <button
                disabled={offset + 30 >= total}
                onClick={() => load(offset + 30)}
                style={{
                  padding: "4px 8px", fontSize: 11, borderRadius: "var(--radius-sm)",
                  border: "1px solid var(--border-primary)", background: "var(--bg-level-2)",
                  cursor: offset + 30 >= total ? "default" : "pointer", color: "var(--text-level-2)",
                }}
              >{t("settings.security.log.pageNext")}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ───────────────────── 命令风险预览 ─────────────────────

const VERDICT_META: Record<RiskVerdict, { text: string; color: string; bg: string }> = {
  allow:            { text: "放行", color: "#16a34a", bg: "rgba(22,163,74,0.12)" },
  require_approval: { text: "需审批", color: "#d97706", bg: "rgba(217,119,6,0.12)" },
  high_risk:        { text: "高危·强制审批", color: "#dc2626", bg: "rgba(220,38,38,0.12)" },
  deny:             { text: "拦截", color: "#dc2626", bg: "rgba(220,38,38,0.12)" },
};

function CommandRiskView({ t }: { t: (key: string) => string }) {
  const [command, setCommand] = useState("");
  const [engine, setEngine] = useState<"run_command" | "execute_command">("run_command");
  const [mode, setMode] = useState<"build" | "plan">("build");
  const [result, setResult] = useState<CommandRiskResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const run = async () => {
    if (!command.trim()) return;
    setLoading(true);
    setErr(null);
    try {
      const res = await previewCommandRisk({ command, engine, mode });
      setResult(res);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      {/* 判定器 + 模式选择 */}
      <div style={{ display: "flex", gap: 4, marginBottom: 8, alignItems: "center" }}>
        <select
          value={engine}
          onChange={(e) => setEngine(e.target.value as any)}
          style={{
            padding: "4px 8px", fontSize: 12, borderRadius: "var(--radius-sm)",
            border: "1px solid var(--border-primary)", background: "var(--bg-level-2)",
            color: "var(--text-level-2)", outline: "none",
          }}
        >
          <option value="run_command">run_command</option>
          <option value="execute_command">execute_command</option>
        </select>
        <select
          value={mode}
          onChange={(e) => setMode(e.target.value as any)}
          style={{
            padding: "4px 8px", fontSize: 12, borderRadius: "var(--radius-sm)",
            border: "1px solid var(--border-primary)", background: "var(--bg-level-2)",
            color: "var(--text-level-2)", outline: "none",
          }}
        >
          <option value="build">Build</option>
          <option value="plan">Plan（只读）</option>
        </select>
        <div style={{ position: "relative", flex: 1 }}>
          <Terminal style={{
            position: "absolute", left: 6, top: "50%", transform: "translateY(-50%)",
            width: 12, height: 12, color: "var(--text-level-4)",
          }} />
          <input
            placeholder={t("settings.security.commandPlaceholder")}
            value={command}
            onChange={(e) => setCommand(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") run(); }}
            style={{
              width: "100%", padding: "4px 8px 4px 24px", fontSize: 12,
              borderRadius: "var(--radius-sm)",
              border: "1px solid var(--border-primary)", background: "var(--bg-level-2)",
              color: "var(--text-level-2)", outline: "none", boxSizing: "border-box",
              fontFamily: "var(--font-mono, monospace)",
            }}
          />
        </div>
        <button onClick={run} disabled={loading || !command.trim()} style={{
          padding: "4px 8px", fontSize: 12, borderRadius: "var(--radius-sm)",
          border: "none", cursor: "pointer",
          background: "var(--color-primary)", color: "#fff",
          fontWeight: 500, opacity: loading || !command.trim() ? 0.5 : 1,
        }}>
          {loading ? t("common.loading") : t("settings.security.preview")}
        </button>
      </div>

      {err && <p style={{ fontSize: 12, color: "var(--color-error)" }}>{err}</p>}

      {result && !err && (
        <div style={{
          marginTop: 4, padding: "8px 12px", borderRadius: "var(--radius-sm)",
          background: "var(--bg-level-2)", border: "1px solid var(--border-primary)",
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
            <MiniBadge {...VERDICT_META[result.verdict]} />
            <MiniBadge {...(RISK_META[result.risk_level] || RISK_META.read_only)} />
          </div>
          <div style={{ fontSize: 12, color: "var(--text-level-2)", fontFamily: "var(--font-mono, monospace)",
            marginBottom: 4, wordBreak: "break-all" }}>
            {result.command}
          </div>
          <div style={{ fontSize: 12, color: "var(--text-level-3)", lineHeight: 1.4 }}>
            {result.reason}
          </div>
        </div>
      )}
    </div>
  );
}

// ───────────────────── 防护清单 ─────────────────────

function GuardrailsView({ t }: { t: (key: string) => string }) {
  const [data, setData] = useState<GuardrailsData | null>(null);
  const [err, setErr] = useState<string | null>(null);
  // 三个 details 折叠态持久化（默认：命令白名单展开，工具列表折叠）
  const [cmdsOpen, setCmdsOpen] = useState(() => {
    try { return localStorage.getItem("mfk_guard_cmds_open") !== "0"; }
    catch { return true; }
  });
  const [toolsOpen, setToolsOpen] = useState(() => {
    try { return localStorage.getItem("mfk_guard_tools_open") === "1"; }
    catch { return false; }
  });
  const [writeToolsOpen, setWriteToolsOpen] = useState(() => {
    try { return localStorage.getItem("mfk_guard_write_tools_open") === "1"; }
    catch { return false; }
  });
  const load = useCallback(() => {
    setErr(null);
    getGuardrails().then(setData).catch((e) => setErr(e instanceof Error ? e.message : String(e)));
  }, []);
  useEffect(load, [load]);

  if (err) return <p style={{ fontSize: 12, color: "var(--color-error)" }}>加载失败: {err}</p>;
  if (!data) return <p style={{ fontSize: 12, color: "var(--text-level-3)" }}>{t("common.loading")}</p>;

  const fmtArgs = (c: AllowedCommand) =>
    c.allowed_args === null ? t("settings.security.anyArgs")
      : c.allowed_args.length === 0 ? t("settings.security.anyArgs")
      : c.allowed_args.join(" · ");

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {/* 禁执行目录 */}
      <div>
        <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, fontWeight: 600,
          color: "var(--text-level-1)", marginBottom: 4 }}>
          <FolderX style={{ width: 13, height: 13, color: "var(--text-level-3)" }} />
          {t("settings.security.forbiddenDirs")}
        </div>
        <div style={{
          display: "flex", flexWrap: "wrap", gap: 4,
          padding: "4px 8px", borderRadius: "var(--radius-sm)",
          background: "var(--bg-level-2)", border: "1px solid var(--border-primary)",
          fontSize: 11, color: "var(--text-level-2)", fontFamily: "var(--font-mono, monospace)",
        }}>
          {data.forbidden_dirs.length === 0
            ? <span style={{ color: "var(--text-level-3)" }}>{t("common.noData")}</span>
            : data.forbidden_dirs.map((d) => (
                <span key={d} style={{
                  padding: "2px 8px", borderRadius: "var(--radius-sm)", background: "rgba(220,38,38,0.08)",
                  color: "#dc2626",
                }}>{d}</span>
              ))}
        </div>
      </div>

      {/* 只读命令白名单 */}
      <details open={cmdsOpen} onToggle={(e) => {
        const v = e.currentTarget.open;
        setCmdsOpen(v);
        try { localStorage.setItem("mfk_guard_cmds_open", v ? "1" : "0"); } catch { /* noop */ }
      }}>
        <summary style={{ fontSize: 12, fontWeight: 600, color: "var(--text-level-1)", cursor: "pointer" }}>
          {t("settings.security.allowedCommands")}（{data.allowed_commands.length}）
        </summary>
        <div style={{
          marginTop: 4, padding: "4px 8px", borderRadius: "var(--radius-sm)",
          background: "var(--bg-level-2)", border: "1px solid var(--border-primary)",
          fontSize: 11, color: "var(--text-level-2)", fontFamily: "var(--font-mono, monospace)",
          display: "flex", flexDirection: "column", gap: 2, maxHeight: 160, overflowY: "auto",
        }}>
          {data.allowed_commands.map((c) => (
            <div key={c.command}>
              <span style={{ color: "#16a34a", fontWeight: 600 }}>{c.command}</span>
              <span style={{ color: "var(--text-level-3)" }}> {fmtArgs(c)}</span>
            </div>
          ))}
        </div>
      </details>

      {/* 只读工具 */}
      <details open={toolsOpen} onToggle={(e) => {
        const v = e.currentTarget.open;
        setToolsOpen(v);
        try { localStorage.setItem("mfk_guard_tools_open", v ? "1" : "0"); } catch { /* noop */ }
      }}>
        <summary style={{ fontSize: 12, fontWeight: 600, color: "var(--text-level-1)", cursor: "pointer" }}>
          {t("settings.security.readOnlyTools")}（{data.read_only_tools.length}）
        </summary>
        <div style={{
          marginTop: 4, display: "flex", flexWrap: "wrap", gap: "4px 8px",
          padding: "4px 8px", borderRadius: "var(--radius-sm)",
          background: "var(--bg-level-2)", border: "1px solid var(--border-primary)",
          fontSize: 11, color: "var(--text-level-2)", fontFamily: "var(--font-mono, monospace)",
        }}>
          {data.read_only_tools.map((tool) => <span key={tool}>{tool}</span>)}
        </div>
      </details>

      {/* 写入工具规则 */}
      <details open={writeToolsOpen} onToggle={(e) => {
        const v = e.currentTarget.open;
        setWriteToolsOpen(v);
        try { localStorage.setItem("mfk_guard_write_tools_open", v ? "1" : "0"); } catch { /* noop */ }
      }}>
        <summary style={{ fontSize: 12, fontWeight: 600, color: "var(--text-level-1)", cursor: "pointer" }}>
          {t("settings.security.writeTools")}（{data.write_tools.length}）
        </summary>
        <div style={{
          marginTop: 4, padding: "4px 8px", borderRadius: "var(--radius-sm)",
          background: "var(--bg-level-2)", border: "1px solid var(--border-primary)",
          fontSize: 11, color: "var(--text-level-2)", fontFamily: "var(--font-mono, monospace)",
          display: "flex", flexDirection: "column", gap: 4,
        }}>
          {data.write_tools.map((tool) => (
            <div key={tool.name} title={tool.reason} style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <span style={{ width: 120, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {tool.name}
              </span>
              <MiniBadge {...VERDICT_META[tool.verdict]} />
              <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                color: "var(--text-level-3)" }}>
                {tool.reason}
              </span>
            </div>
          ))}
        </div>
      </details>
    </div>
  );
}

// ───────────────────── 主入口 ─────────────────────
export function SecurityView(props: SettingsViewProps) {
  const { settings, saving, onUpdate, t } = props;
  const currentPermission = (settings?.agent_permission_mode as "safe" | "standard" | "autonomous") || "standard";
  // 折叠态持久化：默认展开，用户收起后写入 localStorage（"0" = 收起）
  const [open, setOpen] = useState(() => {
    try { return localStorage.getItem("mfk_security_troubleshoot_open") !== "0"; }
    catch { return true; }
  });
  const [troubleshootTab, setTroubleshootTab] = useState<TroubleshootTab>("matrix");
  const [guardOpen, setGuardOpen] = useState(() => {
    try { return localStorage.getItem("mfk_security_guard_open") !== "0"; }
    catch { return true; }
  });
  const [guardTab, setGuardTab] = useState<GuardTab>("approvals");

  return (
    <div>
      {/* 标题 */}
      <div style={{ marginBottom: 8 }}>
        <h3 style={{ fontSize: 14, fontWeight: 500, color: "var(--text-level-1)", margin: 0 }}>
          {t("settings.security.title")}
        </h3>
        <p style={{ fontSize: 12, color: "var(--text-level-3)", margin: "2px 0 0 0" }}>
          {t("settings.security.desc")}
        </p>
      </div>

      {/* 默认权限模式：全局预设卡（一键切换，会话级仍可在聊天输入框权限胶囊单独覆盖） */}
      <div style={{ marginBottom: "12px" }}>
        <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 8 }}>
          <h4 style={{ fontSize: 13, fontWeight: 500, color: "var(--text-level-1)", margin: 0 }}>
            默认权限模式
          </h4>
          <span style={{ fontSize: 11, color: "var(--text-level-4)" }}>
            每个对话也可在输入框权限胶囊单独切换
          </span>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          {PERMISSION_PRESETS.map((p) => {
            const active = currentPermission === p.id;
            const Icon = p.icon;
            return (
              <button
                key={p.id}
                onClick={() => onUpdate("agent_permission_mode", p.id)}
                disabled={saving === "agent_permission_mode"}
                aria-pressed={active}
                style={{
                  flex: 1,
                  display: "flex", flexDirection: "column", alignItems: "flex-start", gap: 2,
                  padding: "10px 12px",
                  borderRadius: "var(--radius-md)",
                  border: active ? "1.5px solid var(--color-primary)" : "1px solid var(--border-primary)",
                  background: active ? "var(--color-primary-lighter)" : "var(--bg-level-2)",
                  cursor: "pointer",
                  textAlign: "left",
                  opacity: saving === "agent_permission_mode" ? 0.6 : 1,
                  transition: "border-color var(--transition-fast), background var(--transition-fast)",
                }}
              >
                <span style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, fontWeight: 500,
                  color: active ? "var(--color-primary)" : "var(--text-level-1)" }}>
                  <Icon style={{ width: 14, height: 14, flexShrink: 0 }} />
                  {p.label}
                </span>
                <span style={{ fontSize: 11, color: "var(--text-level-3)", lineHeight: 1.4 }}>{p.desc}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* 审批模式为会话级（聊天界面权限胶囊），此处不再提供全局开关 */}

      {/* 分隔 */}
      <div style={{ height: 1, background: "var(--border-primary)", margin: "12px 0" }} />

      {/* 故障排查（折叠区域，仿字体选择字段交互：整行点击，箭头在右同一层级） */}
      <button
        type="button"
        onClick={() => setOpen((v) => {
          const next = !v;
          try { localStorage.setItem("mfk_security_troubleshoot_open", next ? "1" : "0"); } catch { /* noop */ }
          return next;
        })}
        style={{
          width: "100%",
          display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8,
          padding: "8px 12px",
          borderRadius: "var(--radius-sm)",
          border: "1px solid var(--border-primary)",
          background: "var(--bg-level-2)",
          cursor: "pointer",
          fontSize: "13px",
          fontWeight: 500,
          color: "var(--text-level-1)",
          transition: "border-color var(--transition-fast)",
        }}
      >
        <span style={{ display: "flex", alignItems: "center", gap: 6, minWidth: 0 }}>
          <AlertTriangle style={{ width: 14, height: 14, color: "var(--text-level-3)", flexShrink: 0 }} />
          <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {t("settings.security.troubleshoot")}
          </span>
        </span>
        <ChevronDown style={{
          width: 14, height: 14, flexShrink: 0, color: "var(--text-level-4)",
          transform: open ? "rotate(180deg)" : "rotate(0deg)",
          transition: "transform var(--transition-fast)",
        }} />
      </button>

      {open && (
        <div style={{ marginTop: 8, animation: "fadeIn 0.2s ease" }}>
          {/* 子 tab 导航 */}
          <div style={{ display: "flex", gap: 2, marginBottom: 8, padding: 3, borderRadius: "var(--radius-md)",
            background: "var(--bg-level-3)" }}>
            {TROUBLESHOOT_TABS.map((item) => {
              const active = troubleshootTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => setTroubleshootTab(item.id)}
                  style={{
                    flex: 1, padding: "4px 0", borderRadius: "calc(var(--radius-md) - 2px)",
                    border: "none", cursor: "pointer", fontSize: 12, fontWeight: active ? 600 : 400,
                    color: active ? "#fff" : "var(--text-level-3)",
                    background: active ? "var(--color-primary)" : "transparent",
                    transition: "background var(--transition-fast), color var(--transition-fast)",
                  }}
                >{t(item.labelKey)}</button>
              );
            })}
          </div>

          {/* 内容 */}
          {troubleshootTab === "matrix" && <MatrixView />}
          {troubleshootTab === "audit" && <AuditView />}
          {troubleshootTab === "status" && <StatusView />}
          {troubleshootTab === "logs" && <LogViewer t={t} />}
        </div>
      )}

      {/* 分隔 */}
      <div style={{ height: 1, background: "var(--border-primary)", margin: "12px 0" }} />

      {/* 安全防护（独立区块，仿字体选择字段交互；平时收起故障排查后无空隙） */}
      <button
        type="button"
        onClick={() => setGuardOpen((v) => {
          const next = !v;
          try { localStorage.setItem("mfk_security_guard_open", next ? "1" : "0"); } catch { /* noop */ }
          return next;
        })}
        style={{
          width: "100%",
          display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8,
          padding: "8px 12px",
          borderRadius: "var(--radius-sm)",
          border: "1px solid var(--border-primary)",
          background: "var(--bg-level-2)",
          cursor: "pointer",
          fontSize: "13px",
          fontWeight: 500,
          color: "var(--text-level-1)",
          transition: "border-color var(--transition-fast)",
        }}
      >
        <span style={{ display: "flex", alignItems: "center", gap: 6, minWidth: 0 }}>
          <Shield style={{ width: 14, height: 14, color: "var(--text-level-3)", flexShrink: 0 }} />
          <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {t("settings.security.guardSection")}
          </span>
        </span>
        <ChevronDown style={{
          width: 14, height: 14, flexShrink: 0, color: "var(--text-level-4)",
          transform: guardOpen ? "rotate(180deg)" : "rotate(0deg)",
          transition: "transform var(--transition-fast)",
        }} />
      </button>

      {guardOpen && (
        <div style={{ marginTop: 8, animation: "fadeIn 0.2s ease" }}>
          {/* 子 tab 导航 */}
          <div style={{ display: "flex", gap: 2, marginBottom: 8, padding: 3, borderRadius: "var(--radius-md)",
            background: "var(--bg-level-3)" }}>
            {GUARD_TABS.map((item) => {
              const active = guardTab === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => setGuardTab(item.id)}
                  style={{
                    flex: 1, padding: "4px 0", borderRadius: "calc(var(--radius-md) - 2px)",
                    border: "none", cursor: "pointer", fontSize: 12, fontWeight: active ? 600 : 400,
                    color: active ? "#fff" : "var(--text-level-3)",
                    background: active ? "var(--color-primary)" : "transparent",
                    transition: "background var(--transition-fast), color var(--transition-fast)",
                  }}
                >{t(item.labelKey)}</button>
              );
            })}
          </div>

          {/* 内容 */}
          {guardTab === "approvals" && <ApprovalsView t={t} />}
          {guardTab === "command-risk" && <CommandRiskView t={t} />}
          {guardTab === "guardrails" && <GuardrailsView t={t} />}
        </div>
      )}
    </div>
  );
}
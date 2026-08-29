"use client";
/** FeishuSettingsPanel —— 飞书集成配置面板（参考 PluginPanel 视觉模式）。
 *
 * 功能：输入飞书 App ID / App Secret，保存后测试连接，显示连接状态。
 * 配置保存到后端 .env，供 Agent 飞书工具（feishu_*）使用。
 */
import { useFeishu, FeishuTestResult } from "@/hooks/useFeishu";
import { Check, Loader2, Shield, RefreshCw, Send, Users } from "lucide-react";
import { useState } from "react";

const inputStyle: React.CSSProperties = {
  width: "100%",
  boxSizing: "border-box",
  padding: "6px 10px",
  marginTop: "4px",
  borderRadius: "var(--radius-sm)",
  background: "var(--bg-level-1)",
  fontSize: "13px",
  color: "var(--text-level-2)",
};

function StatusBadge({ state }: { state: "idle" | "success" | "error" | "loading" }) {
  const styles: Record<string, { label: string; color: string; bg: string }> = {
    idle: { label: "未连接", color: "var(--text-level-4)", bg: "var(--bg-level-3)" },
    success: { label: "已连接", color: "#fff", bg: "var(--color-success)" },
    error: { label: "连接失败", color: "var(--color-error)", bg: "var(--color-error-lighter)" },
    loading: { label: "连接中…", color: "var(--color-primary)", bg: "var(--color-primary-lighter)" },
  };
  const s = styles[state];
  return (
    <span style={{
      display: "inline-flex",
      alignItems: "center",
      gap: "5px",
      fontSize: "11px",
      padding: "1px 8px",
      borderRadius: "var(--radius-full)",
      color: s.color,
      background: s.bg,
      lineHeight: "16px",
      whiteSpace: "nowrap",
    }}>
      {state === "loading" && <Loader2 style={{ width: "11px", height: "11px", animation: "spin 1s linear infinite" }} />}
      {state === "success" && <Check style={{ width: "11px", height: "11px" }} />}
      {s.label}
    </span>
  );
}

export function FeishuSettingsPanel() {
  const {
    config, loading, saving, testing, error, testResult,
    chats, chatError, chatLoading,
    saveConfig, testConnection, fetchChats, sendTestMessage, setChatError,
  } = useFeishu();
  const [appId, setAppId] = useState("");
  const [appSecret, setAppSecret] = useState("");
  const [savedMsg, setSavedMsg] = useState(false);
  const [testText, setTestText] = useState("你好，这是 MfkAgent 通过飞书工具发送的测试消息");
  const [sendLoading, setSendLoading] = useState(false);
  const [sendOk, setSendOk] = useState<string | null>(null);

  // 首帧用当前配置回填隐藏/只读展示（secret 不回填，仅提示已配置）
  const currentAppId = config?.app_id || "";
  const hasSecret = config?.has_secret || false;

  const statusState: "idle" | "success" | "error" | "loading" =
    testing ? "loading"
    : testResult?.success ? "success"
    : testResult && !testResult.success ? "error"
    : error ? "error"
    : "idle";

  const handleSave = async () => {
    if (saving) return;
    // 允许仅保存 App ID；Secret 未填则保留旧值（后端覆盖逻辑用空值保护）
    const ok = await saveConfig({
      app_id: appId.trim() || currentAppId,
      app_secret: appSecret,
    });
    if (ok) {
      setSavedMsg(true);
      setAppSecret("");
      setTimeout(() => setSavedMsg(false), 2000);
    }
  };

  const handleTest = async () => {
    await testConnection();
  };

  return (
    <div>
      {/* 标题行 */}
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: "12px" }}>
        <div>
          <h3 style={{
            fontSize: "14px", fontWeight: "500", color: "var(--text-level-1)", margin: 0,
            display: "flex", alignItems: "center", gap: "8px",
          }}>
            <Shield style={{ width: "16px", height: "16px" }} />
            飞书集成
          </h3>
          <p style={{ fontSize: "12px", color: "var(--text-level-3)", margin: "4px 0 0 0" }}>
            配置飞书应用凭证，让 Agent 可读写你的多维表格。
          </p>
        </div>
        <StatusBadge state={statusState} />
      </div>

      {/* 配置表单 */}
      <div style={{
        marginTop: "12px",
        padding: "12px",
        borderRadius: "var(--radius-md)",
        background: "var(--bg-level-2)",
        border: "1px solid var(--border-primary)",
      }}>
        {loading ? (
          <p style={{ fontSize: "13px", color: "var(--text-level-3)" }}>加载配置中…</p>
        ) : (
          <>
            <div style={{ display: "flex", gap: "12px", marginBottom: "10px" }}>
              <label style={{ flex: "1 1 0", minWidth: 0, fontSize: "12px", color: "var(--text-level-3)" }}>
                App ID {currentAppId && !appId ? `（当前：${currentAppId}）` : ""} *
                <input
                  value={appId}
                  onChange={(e) => setAppId(e.target.value)}
                  placeholder="cli_a9xxxxxxxxxxxx"
                  className="mf-input"
                  style={inputStyle}
                />
              </label>
              <label style={{ flex: "1 1 0", minWidth: 0, fontSize: "12px", color: "var(--text-level-3)" }}>
                {hasSecret && !appSecret ? "App Secret（已配置，留空保留旧值）" : "App Secret"} *
                <input
                  type="password"
                  value={appSecret}
                  onChange={(e) => setAppSecret(e.target.value)}
                  placeholder={hasSecret ? "••••••••（已配置）" : "输入 App Secret"}
                  className="mf-input"
                  style={inputStyle}
                />
              </label>
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end", gap: "8px", marginTop: "8px" }}>
              <button
                onClick={handleTest}
                disabled={testing || (!currentAppId && !appId)}
                className="mf-btn-ghost"
                style={{
                  display: "flex", alignItems: "center", gap: "6px", padding: "7px 14px",
                  borderRadius: "var(--radius-sm)", border: "1px solid var(--border-primary)",
                  cursor: "pointer", fontSize: "13px",
                  color: "var(--text-level-2)",
                }}
              >
                {testing && <Loader2 style={{ width: "14px", height: "14px", animation: "spin 1s linear infinite" }} />}
                测试连接
              </button>
              <button
                onClick={handleSave}
                disabled={saving || !appId.trim()}
                className="mf-btn-primary"
                style={{
                  display: "flex", alignItems: "center", gap: "6px", padding: "7px 14px",
                  borderRadius: "var(--radius-sm)", border: "none",
                  background: "var(--color-primary)", color: "#fff",
                  cursor: "pointer", fontSize: "13px", fontWeight: "500",
                }}
              >
                <Check style={{ width: "14px", height: "14px" }} />
                {saving ? "保存中…" : savedMsg ? "已保存" : "保存配置"}
              </button>
            </div>

            {testResult && (
              <p style={{
                fontSize: "12px", margin: "8px 0 0 0",
                color: testResult.success ? "var(--color-success)" : "var(--color-error)",
              }}>
                {testResult.message}
              </p>
            )}
            {error && !testResult && (
              <p style={{ fontSize: "12px", margin: "8px 0 0 0", color: "var(--color-error)" }}>{error}</p>
            )}
            {testResult?.success && (
              <p style={{ fontSize: "12px", margin: "2px 0 0 0", color: "var(--color-success)" }}>
                凭证有效，Agent 可直接调用飞书工具读写已授权的多维表格。
              </p>
            )}
          </>
        )}
      </div>

      {/* 能力与测试区：连接成功后才展示 */}
      {testResult?.success && (
        <div style={{
          marginTop: "12px",
          padding: "12px",
          borderRadius: "var(--radius-md)",
          background: "var(--bg-level-2)",
          border: "1px solid var(--border-primary)",
        }}>
          <h4 style={{ fontSize: "13px", fontWeight: "500", color: "var(--text-level-1)", margin: "0 0 8px 0", display: "flex", alignItems: "center", gap: "6px" }}>
            <Users style={{ width: "14px", height: "14px" }} />
            Agent 可用能力
          </h4>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", marginBottom: "10px" }}>
            {["feishu_list_chats", "feishu_send_message", "feishu_send_image", "feishu_send_file",
              "feishu_list_bases", "feishu_query_records", "feishu_write_records", "feishu_create_base"].map((tool) => (
              <code key={tool} style={{
                fontSize: "11px", padding: "2px 8px", borderRadius: "var(--radius-sm)",
                background: "var(--bg-level-1)", border: "1px solid var(--border-primary)",
                color: "var(--text-level-2)",
              }}>{tool}</code>
            ))}
          </div>

          <div style={{ marginBottom: "8px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "6px" }}>
              <span style={{ fontSize: "12px", color: "var(--text-level-3)" }}>发送测试消息到群</span>
              <button
                onClick={async () => { await fetchChats(); }}
                disabled={chatLoading}
                className="mf-btn-ghost"
                style={btnGhostStyle}
              >
                {chatLoading
                  ? <Loader2 style={{ width: "12px", height: "12px", animation: "spin 1s linear infinite" }} />
                  : <RefreshCw style={{ width: "12px", height: "12px" }} />}
                获取群列表
              </button>
            </div>
            {chatError && (
              <p style={{ fontSize: "11px", color: "var(--color-error)", margin: "0 0 6px 0", wordBreak: "break-all" }}>
                {chatError}
              </p>
            )}
            {chats.length > 0 && (
              <>
                <select id="feishu-chat-select" value={""} onChange={(e) => { e.target.dataset.sel = e.target.value; }}
                  className="mf-input" style={{ ...inputStyle, marginTop: 0 }}>
                  <option value="">选择群…</option>
                  {chats.map((c) => (
                    <option key={c.chat_id} value={c.chat_id}>{c.name}（{c.chat_id}）</option>
                  ))}
                </select>
                <input
                  value={testText}
                  onChange={(e) => setTestText(e.target.value)}
                  placeholder="测试消息内容"
                  className="mf-input"
                  style={{ ...inputStyle, marginTop: "6px" }}
                />
                <button
                  disabled={sendLoading}
                  className="mf-btn-primary"
                  onClick={async () => {
                    const sel = document.getElementById("feishu-chat-select") as HTMLSelectElement | null;
                    const rid = sel?.dataset.sel;
                    if (!rid) { setSendOk(null); setChatError("请先选择目标群"); return; }
                    setSendLoading(true); setSendOk(null);
                    const ok = await sendTestMessage(rid, testText);
                    setSendLoading(false);
                    if (ok) { setSendOk("已发送"); setChatError(null); }
                  }}
                  style={{ ...btnPrimaryStyle, marginTop: "8px" }}
                >
                  {sendLoading
                    ? <Loader2 style={{ width: "13px", height: "13px", animation: "spin 1s linear infinite" }} />
                    : <Send style={{ width: "13px", height: "13px" }} />}
                  发送测试消息
                </button>
                {sendOk && (
                  <p style={{ fontSize: "11px", color: "var(--color-success)", margin: "6px 0 0 0" }}>{sendOk}</p>
                )}
              </>
            )}
            {chats.length === 0 && !chatError && (
              <p style={{ fontSize: "11px", color: "var(--text-level-4)", margin: "0" }}>
                点击"获取群列表"查看机器人所在群，或直接在聊天中让 Agent 发送（需要 im:chat / im:message 权限）。
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

const btnGhostStyle: React.CSSProperties = {
  display: "flex", alignItems: "center", gap: "5px", padding: "4px 10px",
  borderRadius: "var(--radius-sm)", border: "1px solid var(--border-primary)",
  cursor: "pointer", fontSize: "12px",
  color: "var(--text-level-2)",
};

const btnPrimaryStyle: React.CSSProperties = {
  display: "flex", alignItems: "center", gap: "6px", padding: "6px 14px",
  borderRadius: "var(--radius-sm)", border: "none",
  background: "var(--color-primary)", color: "#fff",
  cursor: "pointer", fontSize: "12px", fontWeight: "500",
};
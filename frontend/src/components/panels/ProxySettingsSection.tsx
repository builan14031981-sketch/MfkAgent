"use client";

/**
 * ProxySettingsSection —— 网络代理设置（VS Code 风格重构）
 *
 * 模式：自动（跟随系统）/ 手动指定 / 关闭。
 * - 统一两列设置行布局
 * - 连通性测试
 */
import { useState, useEffect } from "react";
import { CheckCircle2, XCircle, Loader2, Wifi } from "lucide-react";
import { apiGet, apiFetch } from "@/lib/api";

interface ProxySettingsSectionProps {
  settings: Record<string, string> | null;
  saving: string | null;
  onUpdate: (key: string, value: string) => void;
  t: (key: string) => string;
}

const MODES = [
  { value: "auto", labelKey: "settings.general.proxy.modeAuto" },
  { value: "manual", labelKey: "settings.general.proxy.modeManual" },
  { value: "off", labelKey: "settings.general.proxy.modeOff" },
] as const;

interface TestResult {
  ok: boolean;
  status_code: number;
  latency_ms: number;
  proxied: boolean;
  proxy: string | null;
  detail: string;
}

export function ProxySettingsSection({ settings, saving, onUpdate, t }: ProxySettingsSectionProps) {
  const [detect, setDetect] = useState<{ mode: string; proxy: string | null } | null>(null);
  const [testing, setTesting] = useState(false);
  const [testUrl, setTestUrl] = useState("https://github.com");
  const [testResult, setTestResult] = useState<TestResult | null>(null);

  const mode = settings?.proxy_mode || "auto";
  const proxyUrl = settings?.proxy_url || "";

  useEffect(() => {
    apiGet<{ mode: string; proxy: string | null }>("/api/proxy/detect")
      .then(setDetect)
      .catch(() => {});
  }, [settings?.proxy_mode, settings?.proxy_url]);

  const runTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const res = await apiFetch("/api/proxy/test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: testUrl }),
        timeout: 15000,
      });
      if (res.ok) {
        setTestResult((await res.json()) as TestResult);
      } else {
        setTestResult({
          ok: false,
          status_code: 0,
          latency_ms: 0,
          proxied: false,
          proxy: null,
          detail: t("settings.general.proxy.testFailed"),
        });
      }
    } catch (err) {
      setTestResult({
        ok: false,
        status_code: 0,
        latency_ms: 0,
        proxied: false,
        proxy: null,
        detail: String(err),
      });
    } finally {
      setTesting(false);
    }
  };

  return (
    <div style={{ padding: "8px 0 16px", borderBottom: "1px solid var(--border-secondary)" }}>
      {/* 模式选择行 */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: "16px",
          padding: "6px 0 10px",
        }}
      >
        <div style={{ flex: 1, minWidth: 0 }}>
          <h4 style={{ fontSize: "13px", fontWeight: 500, color: "var(--text-level-1)", margin: 0 }}>
            {t("settings.general.proxy.title")}
          </h4>
          <p style={{ fontSize: "12px", color: "var(--text-level-3)", margin: "2px 0 0 0" }}>
            {t("settings.general.proxy.desc")}
          </p>
        </div>

        <div
          style={{
            display: "flex",
            padding: "2px",
            borderRadius: "var(--radius-sm)",
            background: "var(--bg-level-2)",
            border: "1px solid var(--border-secondary)",
            flexShrink: 0,
          }}
        >
          {MODES.map((opt) => {
            const active = mode === opt.value;
            return (
              <button
                key={opt.value}
                type="button"
                onClick={() => onUpdate("proxy_mode", opt.value)}
                disabled={saving === "proxy_mode"}
                style={{
                  padding: "4px 12px",
                  borderRadius: "var(--radius-xs)",
                  border: "none",
                  cursor: "pointer",
                  fontSize: "12px",
                  whiteSpace: "nowrap",
                  background: active ? "var(--bg-level-1)" : "transparent",
                  color: active ? "var(--text-level-1)" : "var(--text-level-3)",
                  fontWeight: active ? 600 : 400,
                  boxShadow: active ? "var(--shadow-xs)" : "none",
                }}
              >
                {t(opt.labelKey)}
              </button>
            );
          })}
        </div>
      </div>

      {/* 手动模式：代理地址输入 */}
      {mode === "manual" && (
        <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "10px" }}>
          <input
            value={proxyUrl}
            onChange={(e) => onUpdate("proxy_url", e.target.value)}
            placeholder="http://127.0.0.1:7890"
            className="mf-input"
            style={{
              flex: 1,
              height: "32px",
              padding: "0 10px",
              borderRadius: "var(--radius-sm)",
              background: "var(--bg-level-2)",
              border: "1px solid var(--border-primary)",
              fontSize: "12px",
              color: "var(--text-level-2)",
              fontFamily: "monospace",
            }}
          />
        </div>
      )}

      {/* 当前生效检测与说明 */}
      {detect && (
        <div style={{ fontSize: "11px", color: "var(--text-level-3)", marginBottom: "8px" }}>
          <span style={{ color: "var(--text-level-2)", fontWeight: 500 }}>
            {t("settings.general.proxy.effective")}:
          </span>{" "}
          {detect.mode === "off"
            ? t("settings.general.proxy.effectiveOff")
            : detect.proxy
              ? `${detect.proxy}（${t(`settings.general.proxy.mode${detect.mode === "manual" ? "Manual" : "Auto"}`)}）`
              : t("settings.general.proxy.effectiveNone")}
        </div>
      )}

      {/* 测试连接工具条 */}
      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
        <input
          value={testUrl}
          onChange={(e) => setTestUrl(e.target.value)}
          placeholder="https://github.com"
          className="mf-input"
          style={{
            flex: 1,
            height: "30px",
            padding: "0 10px",
            borderRadius: "var(--radius-sm)",
            background: "var(--bg-level-2)",
            border: "1px solid var(--border-primary)",
            fontSize: "12px",
            color: "var(--text-level-2)",
            fontFamily: "monospace",
          }}
        />
        <button
          type="button"
          onClick={runTest}
          disabled={testing}
          style={{
            height: "30px",
            padding: "0 12px",
            borderRadius: "var(--radius-sm)",
            border: "1px solid var(--border-primary)",
            background: "var(--bg-level-1)",
            fontSize: "12px",
            color: "var(--text-level-2)",
            cursor: testing ? "not-allowed" : "pointer",
            display: "inline-flex",
            alignItems: "center",
            gap: "5px",
            whiteSpace: "nowrap",
          }}
        >
          {testing ? <Loader2 style={{ width: "12px", height: "12px", animation: "spin 1s linear infinite" }} /> : <Wifi style={{ width: "12px", height: "12px" }} />}
          {testing ? "测试中…" : "测试连接"}
        </button>
      </div>

      {/* 测试结果 */}
      {testResult && (
        <div
          style={{
            marginTop: "6px",
            fontSize: "11px",
            padding: "4px 8px",
            borderRadius: "var(--radius-sm)",
            background: testResult.ok ? "rgba(16,185,129,0.1)" : "rgba(239,68,68,0.1)",
            color: testResult.ok ? "var(--color-success)" : "var(--color-danger, #ef4444)",
            display: "flex",
            alignItems: "center",
            gap: "6px",
          }}
        >
          {testResult.ok ? (
            <>
              <CheckCircle2 style={{ width: "12px", height: "12px" }} />
              连接正常 · 延迟 {testResult.latency_ms}ms · {testResult.proxied ? `已代理 (${testResult.proxy})` : "直连"}
            </>
          ) : (
            <>
              <XCircle style={{ width: "12px", height: "12px" }} />
              {testResult.detail}
            </>
          )}
        </div>
      )}
    </div>
  );
}

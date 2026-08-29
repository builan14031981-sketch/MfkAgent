"use client";
/**
 * ProxySettingsSection —— 网络代理设置区块（通用 Tab 内）
 *
 * 三模式：自动（跟随系统代理）/ 手动指定 / 关闭。
 * - 手动时显示代理地址输入 + 直连白名单说明
 * - "测试连接"按钮：走与真实调用一致的 build_llm_client 链路测连通性
 * - "当前生效"只读展示：GET /api/proxy/detect 结果
 */
import { useState, useEffect } from "react";
import { Globe, CheckCircle2, XCircle, Loader2 } from "lucide-react";
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
        setTestResult({ ok: false, status_code: 0, latency_ms: 0, proxied: false, proxy: null, detail: t("settings.general.proxy.testFailed") });
      }
    } catch (err) {
      setTestResult({ ok: false, status_code: 0, latency_ms: 0, proxied: false, proxy: null, detail: String(err) });
    } finally {
      setTesting(false);
    }
  };

  return (
    <div style={{ marginBottom: "18px" }}>
      <div style={{ marginBottom: "10px" }}>
        <h3 style={{ fontSize: "14px", fontWeight: "500", color: "var(--text-level-1)", margin: 0, display: "flex", alignItems: "center", gap: "6px" }}>
          <Globe style={{ width: 14, height: 14, color: "var(--text-level-3)" }} />
          {t("settings.general.proxy.title")}
        </h3>
        <p style={{ fontSize: "12px", color: "var(--text-level-3)", margin: "2px 0 0 0" }}>
          {t("settings.general.proxy.desc")}
        </p>
      </div>

      {/* 三模式选择 */}
      <div style={{ display: "flex", padding: "3px", borderRadius: "var(--radius-sm)", background: "var(--bg-level-2)", marginBottom: "12px" }}>
        {MODES.map((opt) => {
          const active = mode === opt.value;
          return (
            <button
              key={opt.value}
              onClick={() => onUpdate("proxy_mode", opt.value)}
              disabled={saving === "proxy_mode"}
              style={{
                flex: 1, padding: "6px 14px", borderRadius: "var(--radius-xs)", border: "none",
                background: active ? "var(--bg-level-1)" : "transparent",
                cursor: "pointer", fontSize: "13px", whiteSpace: "nowrap",
                color: active ? "var(--text-level-1)" : "var(--text-level-3)",
                opacity: saving === "proxy_mode" ? 0.7 : 1,
              }}
            >
              {t(opt.labelKey)}
            </button>
          );
        })}
      </div>

      {/* 手动模式：代理地址输入 */}
      {mode === "manual" && (
        <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "12px" }}>
          <input
            value={proxyUrl}
            onChange={(e) => onUpdate("proxy_url", e.target.value)}
            placeholder="http://127.0.0.1:7890"
            className="mf-input"
            style={{
              flex: 1, padding: "8px 12px", borderRadius: "var(--radius-sm)",
              background: "var(--bg-level-2)",
              fontSize: "13px", color: "var(--text-level-2)",
              fontFamily: "monospace",
            }}
          />
        </div>
      )}

      {/* 当前生效 */}
      {detect && (
        <div style={{ marginBottom: "12px", fontSize: "12px", color: "var(--text-level-3)" }}>
          <span style={{ color: "var(--text-level-2)", fontWeight: 500 }}>{t("settings.general.proxy.effective")}:</span>{" "}
          {detect.mode === "off"
            ? t("settings.general.proxy.effectiveOff")
            : detect.proxy
              ? `${detect.proxy}（${t(`settings.general.proxy.mode${detect.mode === "manual" ? "Manual" : "Auto"}`)}）`
              : t("settings.general.proxy.effectiveNone")}
        </div>
      )}

      {/* 直连白名单说明 */}
      <p style={{ fontSize: "11px", color: "var(--text-level-4)", margin: "0 0 12px 0", lineHeight: 1.5 }}>
        {t("settings.general.proxy.noProxyHint")}
      </p>

      {/* 测试连接 */}
      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
        <input
          value={testUrl}
          onChange={(e) => setTestUrl(e.target.value)}
          placeholder="https://..."
          className="mf-input"
          style={{
            flex: 1, padding: "8px 12px", borderRadius: "var(--radius-sm)",
            background: "var(--bg-level-2)",
            fontSize: "13px", color: "var(--text-level-2)",
            fontFamily: "monospace",
          }}
        />
        <button
          onClick={runTest}
          disabled={testing}
          className="mf-btn-secondary"
          style={{
            display: "flex", alignItems: "center", gap: "6px", padding: "8px 14px",
            borderRadius: "var(--radius-sm)", border: "1px solid var(--color-primary)",
            background: "var(--color-primary-lighter)", color: "var(--color-primary)",
            cursor: testing ? "not-allowed" : "pointer", fontSize: "12px", fontWeight: 500,
            whiteSpace: "nowrap", opacity: testing ? 0.7 : 1,
          }}
        >
          {testing ? <Loader2 style={{ width: 13, height: 13, animation: "spin 1s linear infinite" }} /> : <CheckCircle2 style={{ width: 13, height: 13 }} />}
          {t("settings.general.proxy.test")}
        </button>
      </div>

      {/* 测试结果 */}
      {testResult && (
        <div style={{
          marginTop: "10px", padding: "8px 12px", borderRadius: "var(--radius-sm)",
          background: testResult.ok ? "color-mix(in srgb, var(--color-success) 8%, var(--bg-level-2))" : "color-mix(in srgb, var(--color-error) 8%, var(--bg-level-2))",
          border: `1px solid ${testResult.ok ? "var(--color-success)" : "var(--color-error)"}`,
          display: "flex", alignItems: "flex-start", gap: "8px", fontSize: "12px",
          color: testResult.ok ? "var(--text-level-1)" : "var(--text-level-2)",
        }}>
          {testResult.ok
            ? <CheckCircle2 style={{ width: 14, height: 14, color: "var(--color-success)", flexShrink: 0, marginTop: 1 }} />
            : <XCircle style={{ width: 14, height: 14, color: "var(--color-error)", flexShrink: 0, marginTop: 1 }} />}
          <span style={{ lineHeight: 1.5 }}>{testResult.detail}</span>
        </div>
      )}
    </div>
  );
}
"use client";

/**
 * PairSection —— 设置中的「连接手机」面板（安卓端 M1）
 *
 * 独立组件，供两处复用：
 * 1. SettingsPanel 内联渲染（activeSection === "pair"）—— 与其他设置项一致的接入方式
 * 2. /pair 独立路由（AppLayout 全屏页）—— 作为设置外的直达入口
 *
 * 流程：PC 打开 → POST /api/mobile/pair/start 拿配对码 + 二维码 payload
 *      → 手机 APP 扫码 → 自动探测可达 base + 提交配对码 → 换取长期 token
 * 配对码 5 分钟有效，本组件每 4 分钟自动刷新；设备列表支持吊销（token 立即失效）。
 */
import { useCallback, useEffect, useRef, useState } from "react";
import QRCode from "qrcode";
import { RefreshCw, Smartphone, Trash2, ShieldCheck } from "lucide-react";
import { apiGet, apiPost } from "@/lib/api";
import { useTranslation } from "@/hooks/useTranslation";

interface PairStartResponse {
  code: string;
  expires_in: number;
  port: number;
  lan_ips: string[];
  qr_payload: { v: number; code: string; bases: string[] };
}

interface PairedDevice {
  id: number;
  device_name: string;
  created_at: string | null;
  last_seen_at: string | null;
  revoked: boolean;
}

const REFRESH_INTERVAL_MS = 4 * 60 * 1000; // 配对码 5 分钟过期，提前 1 分钟刷新

export function PairSection() {
  const { t, locale } = useTranslation();
  const [pairInfo, setPairInfo] = useState<PairStartResponse | null>(null);
  const [qrDataUrl, setQrDataUrl] = useState<string | null>(null);
  const [devices, setDevices] = useState<PairedDevice[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busyDeviceId, setBusyDeviceId] = useState<number | null>(null);
  const [tick, setTick] = useState(0); // 手动刷新配对码
  const mountedRef = useRef(true);

  const formatTime = (iso: string | null): string => {
    if (!iso) return "—";
    try {
      return new Date(iso + "Z").toLocaleString(locale === "en-US" ? "en-US" : "zh-CN", { hour12: false });
    } catch {
      return iso;
    }
  };

  const loadPair = useCallback(async () => {
    setError(null);
    try {
      const info = await apiPost<PairStartResponse>("/api/mobile/pair/start", {});
      if (!mountedRef.current) return;
      setPairInfo(info);
      const url = await QRCode.toDataURL(JSON.stringify(info.qr_payload), {
        width: 320,
        margin: 1,
        errorCorrectionLevel: "M",
      });
      if (mountedRef.current) setQrDataUrl(url);
    } catch {
      if (mountedRef.current) {
        setError(t("settings.pair.error"));
        setPairInfo(null);
        setQrDataUrl(null);
      }
    }
  }, [t]);

  const loadDevices = useCallback(async () => {
    try {
      const list = await apiGet<PairedDevice[]>("/api/mobile/devices");
      if (mountedRef.current) setDevices(Array.isArray(list) ? list : []);
    } catch {
      /* 后端不可用时静默，配对卡片已展示错误 */
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    loadPair();
    loadDevices();
    const timer = setInterval(loadPair, REFRESH_INTERVAL_MS);
    return () => {
      mountedRef.current = false;
      clearInterval(timer);
    };
  }, [loadPair, loadDevices, tick]);

  const revoke = useCallback(async (id: number) => {
    setBusyDeviceId(id);
    try {
      await apiPost(`/api/mobile/devices/${id}/revoke`, {});
      await loadDevices();
    } catch {
      /* 吊销失败保持列表原状 */
    } finally {
      setBusyDeviceId(null);
    }
  }, [loadDevices]);

  const activeDevices = devices.filter((d) => !d.revoked);
  const revokedDevices = devices.filter((d) => d.revoked);

  return (
    <div>
      {/* 标题区 */}
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 8 }}>
        <Smartphone size={22} style={{ color: "var(--color-primary)" }} />
        <h2 style={{ fontSize: 18, fontWeight: 500, margin: 0, color: "var(--text-level-1)" }}>{t("settings.pair.title")}</h2>
      </div>
      <p style={{ fontSize: 13, color: "var(--text-level-4)", margin: "0 0 20px", lineHeight: 1.7 }}>
        {t("settings.pair.desc")}
      </p>

      {error && (
        <div style={{
          padding: "12px 16px", marginBottom: 20, borderRadius: 10, fontSize: 13, lineHeight: 1.7,
          border: "1px solid rgba(239,68,68,0.35)", background: "rgba(239,68,68,0.08)", color: "var(--text-level-2)",
        }}>
          {error}
        </div>
      )}

      <div style={{ display: "flex", gap: 20, flexWrap: "wrap", alignItems: "flex-start" }}>
        {/* 左：二维码卡片 */}
        <div style={{
          flex: "0 1 340px", minWidth: 280,
          border: "1px solid var(--border-primary)", borderRadius: 14,
          background: "var(--bg-level-1)", padding: 24, textAlign: "center",
        }}>
          <div style={{ fontSize: 14, fontWeight: 500, color: "var(--text-level-2)", marginBottom: 16 }}>
            {t("settings.pair.scanTitle")}
          </div>
          {qrDataUrl ? (
            <img
              src={qrDataUrl}
              alt={t("settings.pair.qrAlt")}
              width={256}
              height={256}
              style={{ borderRadius: 8, background: "#fff", padding: 8, display: "block", margin: "0 auto" }}
            />
          ) : (
            <div style={{
              width: 256, height: 256, margin: "0 auto", borderRadius: 8,
              background: "var(--bg-level-3)", display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 12, color: "var(--text-level-4)",
            }}>
              {error ? t("settings.pair.qrUnavailable") : t("settings.pair.qrGenerating")}
            </div>
          )}

          {pairInfo && (
            <>
              <div style={{ marginTop: 16, fontSize: 12, color: "var(--text-level-4)" }}>
                {t("settings.pair.manualHint")}
              </div>
              <div style={{
                marginTop: 8, fontSize: 30, fontWeight: 700, letterSpacing: 6,
                fontFamily: "var(--font-geist-mono), monospace", color: "var(--text-level-1)",
              }}>
                {pairInfo.code.slice(0, 3)} {pairInfo.code.slice(3)}
              </div>
              <div style={{ marginTop: 6, fontSize: 11, color: "var(--text-level-4)" }}>
                {t("settings.pair.connectAddr", {
                  addr: pairInfo.qr_payload.bases[0] ?? t("settings.pair.noLanIp", { port: String(pairInfo.port) }),
                })}
              </div>
            </>
          )}

          <button
            onClick={() => setTick((t) => t + 1)}
            style={{
              marginTop: 16, display: "inline-flex", alignItems: "center", gap: 6,
              padding: "8px 14px", minHeight: 36, borderRadius: 8, cursor: "pointer",
              border: "1px solid var(--border-primary)", background: "var(--bg-level-2)",
              color: "var(--text-level-3)", fontSize: 12,
            }}
          >
            <RefreshCw size={13} /> {t("settings.pair.refresh")}
          </button>
        </div>

        {/* 右：已配对设备 */}
        <div style={{
          flex: "1 1 380px", minWidth: 300,
          border: "1px solid var(--border-primary)", borderRadius: 14,
          background: "var(--bg-level-1)", padding: 24,
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
            <ShieldCheck size={18} style={{ color: "var(--color-primary)" }} />
            <span style={{ fontSize: 14, fontWeight: 500, color: "var(--text-level-2)" }}>
              {t("settings.pair.devicesTitle", { count: String(activeDevices.length) })}
            </span>
          </div>

          {devices.length === 0 ? (
            <div style={{ fontSize: 13, color: "var(--text-level-4)", padding: "16px 0" }}>
              {t("settings.pair.emptyDevices")}
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              {[...activeDevices, ...revokedDevices].map((d) => (
                <div key={d.id} style={{
                  display: "flex", alignItems: "center", gap: 12,
                  padding: "12px 14px", borderRadius: 10,
                  border: "1px solid var(--border-primary)", background: "var(--bg-level-2)",
                  opacity: d.revoked ? 0.5 : 1,
                }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 13, fontWeight: 500, color: "var(--text-level-1)" }}>
                      {d.device_name}
                      {d.revoked && (
                        <span style={{ marginLeft: 8, fontSize: 11, color: "var(--text-level-4)", fontWeight: 400 }}>
                          {t("settings.pair.revoked")}
                        </span>
                      )}
                    </div>
                    <div style={{ fontSize: 11, color: "var(--text-level-4)", marginTop: 3 }}>
                      {t("settings.pair.boundAt", {
                        created: formatTime(d.created_at),
                        seen: formatTime(d.last_seen_at),
                      })}
                    </div>
                  </div>
                  {!d.revoked && (
                    <button
                      onClick={() => revoke(d.id)}
                      disabled={busyDeviceId === d.id}
                      title={t("settings.pair.revokeTitle")}
                      style={{
                        display: "inline-flex", alignItems: "center", gap: 4,
                        padding: "7px 12px", minHeight: 34, borderRadius: 8, cursor: "pointer",
                        border: "1px solid rgba(239,68,68,0.4)", background: "transparent",
                        color: "#ef4444", fontSize: 12,
                      }}
                    >
                      <Trash2 size={13} /> {t("settings.pair.revoke")}
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}

          <div style={{ marginTop: 18, fontSize: 12, color: "var(--text-level-4)", lineHeight: 1.7 }}>
            {t("settings.pair.securityNote")}
          </div>
        </div>
      </div>
    </div>
  );
}

"use client";

/**
 * /pair — 连接手机（PC 端配对页，安卓端 M1）
 *
 * 流程：PC 打开本页 → POST /api/mobile/pair/start 拿配对码 + 二维码 payload
 *      → 手机 APP 扫码 → 自动探测可达 base + 提交配对码 → 换取长期 token
 * 配对码 5 分钟有效，本页每 4 分钟自动刷新；设备列表支持吊销（token 立即失效）。
 */
import { useCallback, useEffect, useRef, useState } from "react";
import QRCode from "qrcode";
import { RefreshCw, Smartphone, Trash2, ShieldCheck } from "lucide-react";
import { apiGet, apiPost } from "@/lib/api";

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

function formatTime(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso + "Z").toLocaleString("zh-CN", { hour12: false });
  } catch {
    return iso;
  }
}

export default function PairPage() {
  const [pairInfo, setPairInfo] = useState<PairStartResponse | null>(null);
  const [qrDataUrl, setQrDataUrl] = useState<string | null>(null);
  const [devices, setDevices] = useState<PairedDevice[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busyDeviceId, setBusyDeviceId] = useState<number | null>(null);
  const [tick, setTick] = useState(0); // 手动刷新配对码
  const mountedRef = useRef(true);

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
        setError("无法连接配对接口。请确认：① 后端已重启（本功能随安卓端 M1 新增）；② 如需手机连接，请用 start-mobile.bat 启动（监听 0.0.0.0）。");
        setPairInfo(null);
        setQrDataUrl(null);
      }
    }
  }, []);

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
    <div style={{
      height: "100%",
      overflowY: "auto",
      padding: "24px clamp(16px, 4vw, 48px)",
      background: "var(--bg-level-2)",
      color: "var(--text-level-2)",
    }}>
      <div style={{ maxWidth: 960, margin: "0 auto" }}>
        {/* 标题区 */}
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 8 }}>
          <Smartphone size={26} style={{ color: "var(--color-primary)" }} />
          <h1 style={{ fontSize: 22, fontWeight: 700, margin: 0, color: "var(--text-level-1)" }}>连接手机</h1>
        </div>
        <p style={{ fontSize: 13, color: "var(--text-level-4)", margin: "0 0 24px", lineHeight: 1.7 }}>
          用 MfkAgent 安卓 APP 扫描下方二维码，一次配对长期有效。配对凭证保存在手机安全存储中，可在下方随时吊销；
          电脑上的 API key 永远不会离开本机。
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
            <div style={{ fontSize: 14, fontWeight: 600, color: "var(--text-level-2)", marginBottom: 16 }}>
              手机 APP 扫码配对
            </div>
            {qrDataUrl ? (
              <img
                src={qrDataUrl}
                alt="配对二维码"
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
                {error ? "不可用" : "生成中…"}
              </div>
            )}

            {pairInfo && (
              <>
                <div style={{ marginTop: 16, fontSize: 12, color: "var(--text-level-4)" }}>
                  无法扫码？在手机上手动输入配对码
                </div>
                <div style={{
                  marginTop: 8, fontSize: 30, fontWeight: 700, letterSpacing: 6,
                  fontFamily: "var(--font-geist-mono), monospace", color: "var(--text-level-1)",
                }}>
                  {pairInfo.code.slice(0, 3)} {pairInfo.code.slice(3)}
                </div>
                <div style={{ marginTop: 6, fontSize: 11, color: "var(--text-level-4)" }}>
                  连接地址：{pairInfo.qr_payload.bases[0] ?? `（未检测到局域网 IP，端口 ${pairInfo.port}）`}
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
              <RefreshCw size={13} /> 刷新配对码
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
              <span style={{ fontSize: 14, fontWeight: 600, color: "var(--text-level-2)" }}>
                已配对设备（{activeDevices.length}）
              </span>
            </div>

            {devices.length === 0 ? (
              <div style={{ fontSize: 13, color: "var(--text-level-4)", padding: "16px 0" }}>
                还没有设备配对。扫码后设备会出现在这里。
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
                      <div style={{ fontSize: 13, fontWeight: 600, color: "var(--text-level-1)" }}>
                        {d.device_name}
                        {d.revoked && (
                          <span style={{ marginLeft: 8, fontSize: 11, color: "var(--text-level-4)", fontWeight: 400 }}>
                            已吊销
                          </span>
                        )}
                      </div>
                      <div style={{ fontSize: 11, color: "var(--text-level-4)", marginTop: 3 }}>
                        绑定于 {formatTime(d.created_at)} · 最近在线 {formatTime(d.last_seen_at)}
                      </div>
                    </div>
                    {!d.revoked && (
                      <button
                        onClick={() => revoke(d.id)}
                        disabled={busyDeviceId === d.id}
                        title="吊销该设备（token 立即失效）"
                        style={{
                          display: "inline-flex", alignItems: "center", gap: 4,
                          padding: "7px 12px", minHeight: 34, borderRadius: 8, cursor: "pointer",
                          border: "1px solid rgba(239,68,68,0.4)", background: "transparent",
                          color: "#ef4444", fontSize: 12,
                        }}
                      >
                        <Trash2 size={13} /> 吊销
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}

            <div style={{ marginTop: 18, fontSize: 12, color: "var(--text-level-4)", lineHeight: 1.7 }}>
              安全说明：token 只保存在手机安全存储，本页只展示设备与吊销入口；吊销后对应手机的所有请求立即返回 401，
              需重新扫码配对。远程关机/重启等操作会写入沙箱审计日志（安全中心可见）。
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

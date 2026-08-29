"use client";

/**
 * /connect — 手机端首启连接页（安卓端 M1）
 *
 * 仅在 Capacitor WebView 且尚未配对时由 AppLayout 引导进入。
 * 两种配对方式（对应规划文档决策 #5）：
 *   1. 扫码：PC 端 /pair 页展示二维码（payload JSON），手机相机扫码自动完成；
 *   2. 手动：输入 PC 局域网地址 + 6 位配对码。
 * 成功后 apiBase 与 token 写入 localStorage（lib/api.ts 全局生效），回首页。
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Camera, CameraResultType, CameraSource } from "@capacitor/camera";
import jsQR from "jsqr";
import { QrCode, Link2, CheckCircle2, Loader2 } from "lucide-react";
import { getDeviceApiBase, getDeviceToken, setDeviceApiBase, setDeviceToken } from "@/lib/api";

interface QrPayload {
  v: number;
  code: string;
  bases: string[];
}

type Phase = "idle" | "scanning" | "probing" | "confirming" | "done";

async function probeBase(base: string): Promise<boolean> {
  // 4s 超时 × 2 次尝试：WebView 网络栈冷启动的首次 fetch 可能超过 1.5s（模拟器/真机均现过）
  for (let attempt = 0; attempt < 2; attempt++) {
    try {
      const ctrl = new AbortController();
      const timer = setTimeout(() => ctrl.abort(), 4000);
      const res = await fetch(`${base}/health`, { signal: ctrl.signal });
      clearTimeout(timer);
      if (!res.ok) return false;
      const body = await res.json().catch(() => null);
      return !!body && body.status === "healthy";
    } catch {
      if (attempt === 1) return false;
      await new Promise((r) => setTimeout(r, 400));
    }
  }
  return false;
}

function randomDeviceName(): string {
  return `安卓-${Math.random().toString(36).slice(2, 6).toUpperCase()}`;
}

export default function ConnectPage() {
  const router = useRouter();
  const [phase, setPhase] = useState<Phase>("idle");
  const [message, setMessage] = useState<string | null>(null);
  const [baseInput, setBaseInput] = useState("");
  const [codeInput, setCodeInput] = useState("");
  const [nameInput, setNameInput] = useState("");
  const [connectedBase, setConnectedBase] = useState<string | null>(null);
  const nameAutoSet = useRef(false);

  useEffect(() => {
    const existing = getDeviceApiBase();
    if (existing) setConnectedBase(existing);
    if (!nameAutoSet.current) {
      setNameInput(randomDeviceName());
      nameAutoSet.current = true;
    }
  }, []);

  const finish = useCallback((base: string, token: string) => {
    setDeviceApiBase(base);
    setDeviceToken(token);
    setPhase("done");
    setConnectedBase(base);
    setTimeout(() => router.replace("/"), 900);
  }, [router]);

  const confirmWithBase = useCallback(async (base: string, code: string, deviceName: string) => {
    setPhase("confirming");
    setMessage(`连接 ${base} …`);
    try {
      const res = await fetch(`${base}/api/mobile/pair/confirm`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code, device_name: deviceName }),
      });
      const body = await res.json().catch(() => null);
      if (!res.ok || !body?.token) {
        setMessage(body?.detail || `配对失败（HTTP ${res.status}）`);
        setPhase("idle");
        return;
      }
      finish(base, body.token);
    } catch {
      setMessage("无法连接该地址，请检查网络与地址拼写");
      setPhase("idle");
    }
  }, [finish]);

  const connectManual = useCallback(async () => {
    setMessage(null);
    let base = baseInput.trim().replace(/\/+$/, "");
    if (base && !/^https?:\/\//.test(base)) base = `http://${base}`;
    const code = codeInput.trim();
    if (!base || !/^\d{6}$/.test(code)) {
      setMessage("请填写 PC 地址（如 192.168.1.5:8001）和 6 位配对码");
      return;
    }
    setPhase("probing");
    setMessage("探测电脑 …");
    if (!(await probeBase(base))) {
      setMessage("该地址不可达：确认手机与电脑在同一网络，且电脑用 start-mobile.bat 启动");
      setPhase("idle");
      return;
    }
    await confirmWithBase(base, code, nameInput.trim() || randomDeviceName());
  }, [baseInput, codeInput, nameInput, confirmWithBase]);

  const connectScan = useCallback(async () => {
    setMessage(null);
    try {
      setPhase("scanning");
      const photo = await Camera.getPhoto({
        source: CameraSource.Camera,
        quality: 90,
        width: 1280,
        resultType: CameraResultType.Uri,
      });
      if (!photo.webPath) throw new Error("empty");
      const img = new Image();
      const loaded = new Promise<void>((resolve, reject) => {
        img.onload = () => resolve();
        img.onerror = () => reject(new Error("load"));
      });
      img.src = photo.webPath;
      await loaded;
      const canvas = document.createElement("canvas");
      canvas.width = img.naturalWidth;
      canvas.height = img.naturalHeight;
      canvas.getContext("2d")!.drawImage(img, 0, 0);
      const data = canvas.getContext("2d")!.getImageData(0, 0, canvas.width, canvas.height);
      const result = jsQR(data.data, canvas.width, canvas.height);
      if (!result) {
        setMessage("未识别到二维码，请对准 PC 屏幕上的二维码重试");
        setPhase("idle");
        return;
      }
      const payload = JSON.parse(result.data) as QrPayload;
      if (payload?.v !== 1 || !payload.code || !Array.isArray(payload.bases) || payload.bases.length === 0) {
        setMessage("二维码内容不是 MfkAgent 配对信息");
        setPhase("idle");
        return;
      }
      setPhase("probing");
      setMessage("探测电脑 …");
      let target: string | null = null;
      for (const base of payload.bases) {
        if (await probeBase(base)) {
          target = base;
          break;
        }
      }
      if (!target) {
        setMessage("二维码中的地址均不可达：确认手机与电脑在同一网络");
        setPhase("idle");
        return;
      }
      await confirmWithBase(target, payload.code, nameInput.trim() || randomDeviceName());
    } catch (err) {
      const msg = String((err as { message?: string })?.message || err);
      setMessage(
        msg.includes("permission") || msg.includes("Permission")
          ? "相机权限被拒绝，请在系统设置中允许 MfkAgent 使用相机，或改用手动输入"
          : "扫码未完成，可重试或改用手动输入"
      );
      setPhase("idle");
    }
  }, [confirmWithBase, nameInput]);

  const busy = phase === "scanning" || phase === "probing" || phase === "confirming";

  return (
    <div style={{
      minHeight: "100dvh",
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      padding: "24px 20px calc(24px + env(safe-area-inset-bottom))",
      background: "var(--bg-level-2)",
      color: "var(--text-level-2)",
    }}>
      <div style={{ width: "100%", maxWidth: 420 }}>
        <div style={{ textAlign: "center", marginBottom: 28 }}>
          <div style={{ fontSize: 22, fontWeight: 700, color: "var(--text-level-1)" }}>连接你的电脑</div>
          <div style={{ fontSize: 13, color: "var(--text-level-4)", marginTop: 8, lineHeight: 1.7 }}>
            在 PC 上打开 <b>设置 → 连接手机</b>（/pair 页），然后扫码或手动输入连接信息。<br />
            一次配对长期有效。
          </div>
        </div>

        {connectedBase && (
          <div style={{
            display: "flex", alignItems: "center", gap: 10, marginBottom: 20,
            padding: "14px 16px", borderRadius: 12,
            border: "1px solid rgba(34,197,94,0.4)", background: "rgba(34,197,94,0.08)",
          }}>
            <CheckCircle2 size={20} style={{ color: "#22c55e", flexShrink: 0 }} />
            <div style={{ fontSize: 13 }}>
              <div style={{ fontWeight: 600, color: "var(--text-level-1)" }}>已配对</div>
              <div style={{ color: "var(--text-level-4)", fontSize: 12, marginTop: 2 }}>{connectedBase}</div>
            </div>
          </div>
        )}

        {/* 扫码入口（主推，决策 #5） */}
        <button
          onClick={connectScan}
          disabled={busy}
          style={{
            width: "100%", minHeight: 56, borderRadius: 14, cursor: busy ? "wait" : "pointer",
            display: "flex", alignItems: "center", justifyContent: "center", gap: 10,
            border: "none", background: "var(--color-primary)", color: "#fff",
            fontSize: 16, fontWeight: 600, padding: "12px 16px", opacity: busy ? 0.6 : 1,
          }}
        >
          {phase === "scanning" ? <Loader2 size={20} className="animate-spin" /> : <QrCode size={20} />}
          扫描电脑上的二维码
        </button>

        <div style={{ textAlign: "center", fontSize: 12, color: "var(--text-level-4)", margin: "16px 0" }}>
          ——— 或手动输入 ———
        </div>

        {/* 手动输入 */}
        <input
          value={baseInput}
          onChange={(e) => setBaseInput(e.target.value)}
          placeholder="PC 地址，如 192.168.1.5:8001"
          inputMode="url"
          autoCapitalize="off"
          autoCorrect="off"
          style={{
            width: "100%", boxSizing: "border-box", minHeight: 48, padding: "12px 14px",
            borderRadius: 12, border: "1px solid var(--border-primary)",
            background: "var(--bg-level-1)", color: "var(--text-level-1)",
            fontSize: 15, marginBottom: 10, outline: "none",
          }}
        />
        <input
          value={codeInput}
          onChange={(e) => setCodeInput(e.target.value.replace(/\D/g, "").slice(0, 6))}
          placeholder="6 位配对码"
          inputMode="numeric"
          pattern="[0-9]*"
          style={{
            width: "100%", boxSizing: "border-box", minHeight: 48, padding: "12px 14px",
            borderRadius: 12, border: "1px solid var(--border-primary)",
            background: "var(--bg-level-1)", color: "var(--text-level-1)",
            fontSize: 15, letterSpacing: 4, marginBottom: 10, outline: "none",
          }}
        />
        <input
          value={nameInput}
          onChange={(e) => setNameInput(e.target.value)}
          placeholder="设备名称（PC 端设备列表显示）"
          style={{
            width: "100%", boxSizing: "border-box", minHeight: 48, padding: "12px 14px",
            borderRadius: 12, border: "1px solid var(--border-primary)",
            background: "var(--bg-level-1)", color: "var(--text-level-1)",
            fontSize: 15, marginBottom: 14, outline: "none",
          }}
        />
        <button
          onClick={connectManual}
          disabled={busy}
          style={{
            width: "100%", minHeight: 52, borderRadius: 12, cursor: busy ? "wait" : "pointer",
            display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
            border: "1px solid var(--border-primary)", background: "var(--bg-level-1)",
            color: "var(--text-level-1)", fontSize: 15, fontWeight: 600, opacity: busy ? 0.6 : 1,
          }}
        >
          <Link2 size={17} />
          {phase === "probing" ? "探测中…" : phase === "confirming" ? "配对中…" : "连接电脑"}
        </button>

        {message && (
          <div style={{
            marginTop: 14, padding: "10px 14px", borderRadius: 10, fontSize: 13, lineHeight: 1.6,
            border: "1px solid var(--border-primary)", background: "var(--bg-level-1)",
            color: "var(--text-level-3)",
          }}>
            {message}
          </div>
        )}
      </div>
    </div>
  );
}

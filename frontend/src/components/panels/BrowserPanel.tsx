"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ArrowLeft, ArrowRight, Globe, RotateCw, Loader2 } from "lucide-react";
import { useTranslation } from "@/hooks/useTranslation";

interface BrowserPanelProps {
  /** 当前会话 id（保留参数：后续用于会话级浏览器状态/审计，不影响可用性） */
  chatId?: number | null;
  /** 当前绑定的项目路径（有项目时打开项目地址，无项目时显示欢迎页） */
  projectPath?: string | null;
}

/**
 * 浏览器内容区（右侧面板"浏览器"标签）。
 * - 内容区用 <iframe> 直接嵌入真实页面：可点击、可滚动、可输入，与真浏览器一致
 * - 缩放天然自适应面板宽度，无固定分辨率截图的拉伸/压缩问题
 * - 地址栏输入 URL 导航；刷新强制重载；后退/前进仅同源页面可用（跨源禁用并提示）
 * - 同源页面内点击链接后地址栏自动同步
 * - 外壳/标签栏/宽度/全屏由 DockPanel 承载
 */
export function BrowserPanel({ chatId: _chatId, projectPath }: BrowserPanelProps) {
  const { t } = useTranslation();

  const [addr, setAddr] = useState("");
  const [iframeSrc, setIframeSrc] = useState("");
  const [reloadKey, setReloadKey] = useState(0);
  const [loading, setLoading] = useState(false);

  const iframeRef = useRef<HTMLIFrameElement | null>(null);

  // 默认地址：有项目时用项目地址，无项目时显示欢迎页
  const defaultUrl = projectPath ? "http://localhost:3000" : "";

  // 规范化地址：补全 http://
  const normalize = useCallback(
    (raw: string) => {
      let s = (raw || "").trim();
      if (!s) return defaultUrl;
      if (!/^https?:\/\//i.test(s)) s = `http://${s}`;
      return s;
    },
    [defaultUrl]
  );

  // 同源判断（协议 + host + 端口一致才算，用于后退/前进可用性与地址栏同步）
  const isSameOrigin = useCallback((url: string) => {
    try {
      const a = new URL(url, window.location.origin);
      return a.origin === window.location.origin;
    } catch {
      return false;
    }
  }, []);

  const sameOrigin = useMemo(() => iframeSrc !== "" && isSameOrigin(iframeSrc), [iframeSrc, isSameOrigin]);

  // 导航到指定地址
  const navigate = useCallback(
    (raw: string) => {
      const target = normalize(raw);
      setAddr(target);
      setIframeSrc(target);
      setReloadKey((k) => k + 1);
      setLoading(true);
    },
    [normalize]
  );

  const onAddrSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      navigate(addr);
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [addr, navigate]
  );

  // 后退：仅同源可用（跨源受浏览器安全策略限制）
  const goBack = useCallback(() => {
    if (!sameOrigin || !iframeRef.current?.contentWindow) return;
    iframeRef.current.contentWindow.history.back();
  }, [sameOrigin]);

  // 前进：仅同源可用
  const goForward = useCallback(() => {
    if (!sameOrigin || !iframeRef.current?.contentWindow) return;
    iframeRef.current.contentWindow.history.forward();
  }, [sameOrigin]);

  // 刷新：同源直接 reload；跨源用 key 重建 iframe 强制重载
  const reload = useCallback(() => {
    if (!iframeSrc) return;
    setLoading(true);
    if (sameOrigin && iframeRef.current?.contentWindow) {
      iframeRef.current.contentWindow.location.reload();
    } else {
      setReloadKey((k) => k + 1);
    }
  }, [iframeSrc, sameOrigin]);

  // iframe 加载完成：结束 loading；同源时同步地址栏（点击链接后回填真实 URL）
  const onIframeLoad = useCallback(() => {
    setLoading(false);
    if (sameOrigin && iframeRef.current?.contentWindow) {
      try {
        const href = iframeRef.current.contentWindow.location.href;
        if (href && href !== addr) setAddr(href);
      } catch {
        /* 跨源读取被拒，忽略 */
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sameOrigin]);

  // 首次进入且尚未打开页面时，自动导航到默认地址
  useEffect(() => {
    if (!iframeSrc) {
      navigate(defaultUrl);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [defaultUrl]);

  // 无项目时显示欢迎页
  if (!projectPath) {
    return (
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          height: "100%",
          padding: "24px",
          textAlign: "center",
          color: "var(--text-level-3)",
        }}
      >
        <Globe style={{ width: 48, height: 48, marginBottom: 16, color: "var(--text-level-4)" }} />
        <p style={{ fontSize: "14px", margin: 0, lineHeight: 1.5 }}>
          {t("browser.needProject")}
        </p>
        <p style={{ fontSize: "12px", margin: "8px 0 0 0", color: "var(--text-level-4)", lineHeight: 1.5 }}>
          {t("browser.needProjectDesc")}
        </p>
      </div>
    );
  }

  return (
    <>
      {/* 地址栏 + 导航按钮 */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "4px",
          padding: "4px 8px",
          borderBottom: "1px solid var(--border-primary)",
          flexShrink: 0,
        }}
      >
        <button
          onClick={goBack}
          title={t("browser.back")}
          style={{
            ...toolBtnStyle,
            color: !sameOrigin ? "var(--text-level-5)" : "var(--text-level-3)",
            cursor: !sameOrigin ? "not-allowed" : "pointer",
          }}
          disabled={!sameOrigin}
        >
          <ArrowLeft style={{ width: 13, height: 13 }} />
        </button>
        <button
          onClick={goForward}
          title={t("browser.forward")}
          style={{
            ...toolBtnStyle,
            color: !sameOrigin ? "var(--text-level-5)" : "var(--text-level-3)",
            cursor: !sameOrigin ? "not-allowed" : "pointer",
          }}
          disabled={!sameOrigin}
        >
          <ArrowRight style={{ width: 13, height: 13 }} />
        </button>
        <button onClick={reload} title={t("browser.reload")} style={toolBtnStyle}>
          <RotateCw style={{ width: 13, height: 13 }} />
        </button>
        <form onSubmit={onAddrSubmit} style={{ flex: 1, display: "flex", minWidth: 0 }}>
          <div
            style={{
              flex: 1,
              display: "flex",
              alignItems: "center",
              gap: 6,
              background: "var(--bg-level-3)",
              borderRadius: "var(--radius-sm)",
              padding: "0 8px",
              border: "1px solid var(--border-primary)",
            }}
          >
            <Globe style={{ width: 12, height: 12, color: "var(--text-level-4)", flexShrink: 0 }} />
            <input
              value={addr}
              onChange={(e) => setAddr(e.target.value)}
              placeholder={t("browser.placeholder")}
              spellCheck={false}
              style={{
                flex: 1,
                minWidth: 0,
                height: 26,
                border: "none",
                background: "transparent",
                outline: "none",
                fontSize: 12,
                color: "var(--text-level-2)",
              }}
            />
          </div>
        </form>
      </div>

      {/* 页面区：真实 iframe 渲染 */}
      <div style={{ flex: 1, minHeight: 0, overflow: "hidden", position: "relative", background: "#fff" }}>
        {loading && (
          <div style={{ ...centerStyle, position: "absolute", inset: 0, zIndex: 2, background: "var(--bg-level-2)" }}>
            <Loader2 style={{ width: 18, height: 18, color: "var(--text-level-4)", animation: "spin 1s linear infinite" }} />
          </div>
        )}
        {!sameOrigin && iframeSrc && !loading && (
          <div
            style={{
              position: "absolute",
              top: 4,
              left: "50%",
              transform: "translateX(-50%)",
              zIndex: 2,
              maxWidth: "92%",
              background: "var(--bg-level-4)",
              borderRadius: "var(--radius-sm)",
              padding: "3px 10px",
              pointerEvents: "none",
            }}
          >
            <span
              style={{
                fontSize: 11,
                color: "var(--text-level-4)",
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis",
                display: "block",
              }}
            >
              {t("browser.crossOrigin")}
            </span>
          </div>
        )}
        {iframeSrc && (
          <iframe
            key={`${iframeSrc}#r${reloadKey}`}
            ref={iframeRef}
            src={iframeSrc}
            onLoad={onIframeLoad}
            title={addr}
            style={{ width: "100%", height: "100%", border: "none", display: "block" }}
            sandbox="allow-same-origin allow-scripts allow-forms allow-popups allow-modals allow-downloads"
          />
        )}
        {!iframeSrc && (
          <div style={{ ...centerStyle, position: "absolute", inset: 0, zIndex: 1, background: "var(--bg-level-2)" }}>
            <span style={{ fontSize: 12, color: "var(--text-level-3)" }}>{t("browser.loading")}</span>
          </div>
        )}
      </div>
    </>
  );
}

const toolBtnStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  width: 24,
  height: 24,
  borderRadius: "var(--radius-sm)",
  border: "none",
  background: "transparent",
  cursor: "pointer",
  color: "var(--text-level-3)",
  padding: 0,
  outline: "none",
  flexShrink: 0,
  transition: "background 0.15s, color 0.15s",
};

const centerStyle: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
};



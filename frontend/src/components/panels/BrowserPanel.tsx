"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ArrowLeft, ArrowRight, Globe, RotateCw, Loader2 } from "lucide-react";
import { useTranslation } from "@/hooks/useTranslation";
import { useSettingsStore } from "@/lib/store";

/** 页面加载超时（ms）：若 iframe 既无 load 也无错误事件，超过该时长判定加载失败 */
const LOAD_TIMEOUT = 15000;

interface BrowserPanelProps {
  /** 当前会话 id（保留参数：后续用于会话级浏览器状态/审计，不影响可用性） */
  chatId?: number | null;
  /** 当前绑定的项目路径（保留参数：兼容调用方，不再决定默认地址） */
  projectPath?: string | null;
}

/**
 * 浏览器内容区（右侧面板"浏览器"标签）。
 * - 默认地址来自设置「浏览器主页」：填了就自动打开，留空则显示引导页
 * - 内容区用 <iframe> 直接嵌入真实页面：可点击、可滚动、可输入，与真浏览器一致
 * - 地址栏输入 URL 导航；刷新强制重载；后退/前进仅同源页面可用（跨源禁用并提示）
 * - 同源页面内点击链接后地址栏自动同步
 */
export function BrowserPanel({ chatId: _chatId, projectPath: _projectPath }: BrowserPanelProps) {
  const { t } = useTranslation();
  const settings = useSettingsStore((s) => s.settings);
  // 浏览器主页（来自设置），留空 = 不启用
  const homepage = (settings?.browser_homepage ?? "").trim();

  const [addr, setAddr] = useState("");
  const [iframeSrc, setIframeSrc] = useState("");
  const [reloadKey, setReloadKey] = useState(0);
  const [loading, setLoading] = useState(false);
  const [loadFailed, setLoadFailed] = useState(false);

  const iframeRef = useRef<HTMLIFrameElement | null>(null);
  const loadTimeoutRef = useRef<number | null>(null);

  // 清除加载超时定时器
  const clearLoadTimeout = useCallback(() => {
    if (loadTimeoutRef.current !== null) {
      window.clearTimeout(loadTimeoutRef.current);
      loadTimeoutRef.current = null;
    }
  }, []);

  // 组件卸载时清理定时器
  useEffect(() => () => clearLoadTimeout(), []);

  // 规范化地址：补全 http://；空输入回落到主页（主页未设置则为空）
  const normalize = useCallback(
    (raw: string) => {
      let s = (raw || "").trim();
      if (!s) return homepage;
      if (!/^https?:\/\//i.test(s)) s = `http://${s}`;
      return s;
    },
    [homepage]
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

  // 导航到指定地址（空地址 = 回到引导页）
  const navigate = useCallback(
    (raw: string) => {
      const target = normalize(raw);
      setAddr(target);
      setIframeSrc(target);
      setReloadKey((k) => k + 1);
      clearLoadTimeout();
      setLoadFailed(false);
      if (target) {
        setLoading(true);
        // 兜底：加载可能永不触发（域名不存在/断网），超时后停止转圈并提示
        loadTimeoutRef.current = window.setTimeout(() => {
          setLoading(false);
          setLoadFailed(true);
        }, LOAD_TIMEOUT);
      } else {
        setLoading(false);
      }
    },
    [normalize, clearLoadTimeout]
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
    clearLoadTimeout();
    setLoading(true);
    setLoadFailed(false);
    if (sameOrigin && iframeRef.current?.contentWindow) {
      iframeRef.current.contentWindow.location.reload();
    } else {
      setReloadKey((k) => k + 1);
    }
    loadTimeoutRef.current = window.setTimeout(() => {
      setLoading(false);
      setLoadFailed(true);
    }, LOAD_TIMEOUT);
  }, [iframeSrc, sameOrigin, clearLoadTimeout]);

  // iframe 加载完成：结束 loading；同源时同步地址栏（点击链接后回填真实 URL）
  const onIframeLoad = useCallback(() => {
    clearLoadTimeout();
    setLoading(false);
    setLoadFailed(false);
    if (sameOrigin && iframeRef.current?.contentWindow) {
      try {
        const href = iframeRef.current.contentWindow.location.href;
        if (href && href !== addr) setAddr(href);
      } catch {
        /* 跨源读取被拒，忽略 */
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sameOrigin, clearLoadTimeout]);

  // 首次进入且尚未打开页面时，自动导航到主页（未设置主页则停在引导页）
  useEffect(() => {
    if (!iframeSrc && homepage) {
      navigate(homepage);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [homepage]);

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

      {/* 页面区：真实 iframe 渲染（未设置主页时显示引导页） */}
      <div style={{ flex: 1, minHeight: 0, overflow: "hidden", position: "relative", background: "#fff" }}>
        {loading && iframeSrc && (
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
        {loadFailed && iframeSrc && (
          <div
            style={{
              ...centerStyle,
              position: "absolute",
              inset: 0,
              zIndex: 3,
              background: "var(--bg-level-2)",
              flexDirection: "column",
              padding: "24px",
              textAlign: "center",
            }}
          >
            <p style={{ fontSize: 13, margin: "0 0 12px 0", color: "var(--text-level-3)", lineHeight: 1.5 }}>
              {t("browser.loadFailed")}
            </p>
            <button
              onClick={reload}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                padding: "6px 14px",
                borderRadius: "var(--radius-sm)",
                border: "1px solid var(--border-primary)",
                background: "var(--bg-level-3)",
                cursor: "pointer",
                fontSize: 12,
                color: "var(--text-level-2)",
              }}
            >
              <RotateCw style={{ width: 13, height: 13 }} />
              {t("browser.retry")}
            </button>
          </div>
        )}
        {!iframeSrc && (
          <div
            style={{
              ...centerStyle,
              position: "absolute",
              inset: 0,
              zIndex: 1,
              background: "var(--bg-level-2)",
              flexDirection: "column",
              padding: "24px",
              textAlign: "center",
            }}
          >
            <Globe style={{ width: 48, height: 48, marginBottom: 16, color: "var(--text-level-4)" }} />
            <p style={{ fontSize: "14px", margin: 0, lineHeight: 1.5 }}>
              {t("browser.needHomepage")}
            </p>
            <p style={{ fontSize: "12px", margin: "8px 0 0 0", color: "var(--text-level-4)", lineHeight: 1.5 }}>
              {t("browser.needHomepageDesc")}
            </p>
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
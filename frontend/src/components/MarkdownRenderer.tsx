"use client";

import { memo, useState, useMemo, useRef, useEffect, useCallback } from "react";
import { ChevronDown, ChevronUp, Copy, Check, FileText } from "lucide-react";
import { useTranslation } from "@/hooks/useTranslation";
import { isFilePath, useFilePathInteraction, CLOSE_FILE_CTX_MENU } from "@/hooks/useFilePathInteraction";

interface MarkdownRendererProps {
  content: string;
}

/** 代码块阈值：超过该行数默认折叠 */
const COLLAPSE_THRESHOLD = 15;

/** 总结/结论关键词（用于自动高亮检测） */
const SUMMARY_KEYWORDS = /^(总结|结论|摘要|关键要点|核心结论|Summary|Conclusion|Key Takeaways|TL;DR)[：:]/i;

/** 行内 Markdown 渲染：粗体 / 行内代码 / 文件路径检测 */
function renderInline(text: string): React.ReactNode[] {
  const nodes: React.ReactNode[] = [];
  const tokens = text.split(/(`[^`]+`|\*\*[^*]+\*\*)/g).filter((t) => t !== "");
  for (const token of tokens) {
    if (token.startsWith("`") && token.endsWith("`") && token.length > 1) {
      const inner = token.slice(1, -1);
      // 行内代码中的文件路径：渲染为可交互元素
      if (isFilePath(inner)) {
        nodes.push(<FilePathLink key={nodes.length} path={inner} isCode />);
      } else {
        nodes.push(
          <code key={nodes.length} className="md-code-inline">{inner}</code>
        );
      }
    } else if (token.startsWith("**") && token.endsWith("**") && token.length > 4) {
      nodes.push(<strong key={nodes.length} className="md-strong">{token.slice(2, -2)}</strong>);
    } else {
      // 纯文本：检测是否包含文件路径
      const pathParts = splitByFilePaths(token);
      if (pathParts.length === 1 && pathParts[0].type === "text") {
        nodes.push(token);
      } else {
        for (const part of pathParts) {
          if (part.type === "path") {
            nodes.push(<FilePathLink key={nodes.length} path={part.value} />);
          } else {
            nodes.push(part.value);
          }
        }
      }
    }
  }
  return nodes;
}

/** 从文本中拆分出文件路径片段 */
function splitByFilePaths(text: string): Array<{ type: "text" | "path"; value: string }> {
  // 匹配 Windows 绝对路径或含分隔符的相对路径（带文件扩展名）
  const pathPattern = /(?:[A-Za-z]:[\\/](?:[\w.-]+[\\/])*[\w.-]+\.[\w]+)|(?:[\w.-]+(?:[\\/][\w.-]+)+\.[\w]+)/g;
  const parts: Array<{ type: "text" | "path"; value: string }> = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = pathPattern.exec(text)) !== null) {
    const matched = match[0];
    if (!isFilePath(matched)) continue;
    // 前面的文本
    if (match.index > lastIndex) {
      parts.push({ type: "text", value: text.slice(lastIndex, match.index) });
    }
    parts.push({ type: "path", value: matched });
    lastIndex = match.index + matched.length;
  }
  // 剩余文本
  if (lastIndex < text.length) {
    parts.push({ type: "text", value: text.slice(lastIndex) });
  }
  return parts.length > 0 ? parts : [{ type: "text", value: text }];
}

/** 可交互的文件路径链接组件 */
function FilePathLink({ path, isCode = false }: { path: string; isCode?: boolean }) {
  const { resolvedPath, isFile, onDoubleClick, openInFolder, copyPath } = useFilePathInteraction(path);
  const [contextMenu, setContextMenu] = useState<{ x: number; y: number } | null>(null);
  const [copied, setCopied] = useState(false);

  const closeContextMenu = useCallback(() => setContextMenu(null), []);

  const handleContextMenu = useCallback((e: React.MouseEvent) => {
    if (!isFile || typeof window === "undefined") return;
    e.preventDefault();
    e.stopPropagation();
    // 广播关闭信号：关闭其他所有 FilePathLink 的右键菜单
    window.dispatchEvent(new CustomEvent(CLOSE_FILE_CTX_MENU));
    setContextMenu({ x: e.clientX, y: e.clientY });
  }, [isFile]);

  const handleCopyPath = useCallback(async () => {
    await copyPath();
    setCopied(true);
    setTimeout(() => setCopied(false), 1200);
    closeContextMenu();
  }, [copyPath, closeContextMenu]);

  const handleOpen = useCallback(async () => {
    await openInFolder();
    closeContextMenu();
  }, [openInFolder, closeContextMenu]);

  // 关闭菜单：监听 click + 全局互斥事件 + contextmenu（右键其他位置时）
  useEffect(() => {
    if (!contextMenu) return;
    const close = () => closeContextMenu();
    document.addEventListener("click", close);
    document.addEventListener("contextmenu", close);
    window.addEventListener(CLOSE_FILE_CTX_MENU, close);
    return () => {
      document.removeEventListener("click", close);
      document.removeEventListener("contextmenu", close);
      window.removeEventListener(CLOSE_FILE_CTX_MENU, close);
    };
  }, [contextMenu, closeContextMenu]);

  // 从路径中提取文件名用于显示
  const fileName = resolvedPath ? resolvedPath.split(/[\\/]/).pop() || resolvedPath : path;

  return (
    <>
      <span
        onDoubleClick={onDoubleClick}
        onContextMenu={handleContextMenu}
        title={isFile ? "双击打开文件位置 / 右键菜单" : path}
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: "2px",
          fontFamily: isCode ? "var(--font-geist-mono), var(--font-family)" : undefined,
          fontSize: isCode ? undefined : "0.95em",
          color: "var(--color-primary)",
          cursor: isFile ? "pointer" : "inherit",
          textDecoration: isFile ? "underline dotted" : undefined,
          textUnderlineOffset: "3px",
          borderRadius: "var(--radius-xs)",
          padding: isCode ? "0 4px" : undefined,
          background: isCode ? "var(--bg-level-3)" : undefined,
        }}
      >
        <FileText style={{ width: "12px", height: "12px", flexShrink: 0 }} />
        {isCode ? path : fileName}
      </span>
      {/* 右键菜单 */}
      {contextMenu && isFile && (
        <div
          style={{
            position: "fixed",
            left: contextMenu.x,
            top: contextMenu.y,
            zIndex: 9999,
            background: "var(--bg-level-2)",
            border: "1px solid var(--border-primary)",
            borderRadius: "var(--radius-md)",
            boxShadow: "var(--shadow-lg)",
            padding: "4px",
            minWidth: "160px",
          }}
        >
          <button
            onClick={handleOpen}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              width: "100%",
              padding: "6px 10px",
              border: "none",
              borderRadius: "var(--radius-sm)",
              background: "transparent",
              cursor: "pointer",
              fontSize: "12px",
              color: "var(--text-level-2)",
              textAlign: "left",
              outline: "none",
            }}
            onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-level-3)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
          >
            在文件管理器中打开
          </button>
          <button
            onClick={handleCopyPath}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              width: "100%",
              padding: "6px 10px",
              border: "none",
              borderRadius: "var(--radius-sm)",
              background: "transparent",
              cursor: "pointer",
              fontSize: "12px",
              color: copied ? "var(--color-copied)" : "var(--text-level-2)",
              textAlign: "left",
              outline: "none",
            }}
            onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-level-3)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
          >
            {copied ? "已复制" : "复制路径"}
          </button>
        </div>
      )}
    </>
  );
}

interface CodeBlockInfo {
  lang: string;
  code: string;
  isCollapsible: boolean;
  lineCount: number;
}

/** 解析 ``` 代码块 */
function parseCodeBlock(meta: string, code: string): CodeBlockInfo {
  const lang = meta.trim().split(/\s+/)[0] || "text";
  const codeTrimmed = code.replace(/\n$/, "");
  const lineCount = codeTrimmed === "" ? 0 : codeTrimmed.split("\n").length;
  return {
    lang,
    code: codeTrimmed,
    lineCount,
    isCollapsible: lineCount > COLLAPSE_THRESHOLD,
  };
}

/** 判断段落是否为总结/结论块 */
function isSummaryParagraph(text: string): boolean {
  return SUMMARY_KEYWORDS.test(text);
}

/**
 * Markdown 渲染器（Typography 增强版）：
 * - 标题层级优化（h1-h6 带底部边框、渐进字号）
 * - 引用块（> 前缀）
 * - 加粗强调优化
 * - 代码块字体优化（Cascadia Code 优先）
 * - 总结/结论内容自动高亮
 * - 有序列表 / 无序列表
 * - 分隔线
 */
export const MarkdownRenderer = memo(function MarkdownRenderer({ content }: MarkdownRendererProps) {
  const { t } = useTranslation();
  const blocks = useMemo(() => {
    const lines = content.split("\n");
    const out: React.ReactNode[] = [];
    let i = 0;
    let key = 0;
    let inCode = false;
    let codeBuffer: string[] = [];
    let codeMeta = "";
    let paragraph: string[] = [];
    let inQuote = false;
    let quoteLines: string[] = [];

    const flushParagraph = () => {
      if (paragraph.length > 0) {
        const text = paragraph.join(" ");
        if (isSummaryParagraph(text)) {
          out.push(
            <div key={key++} className="md-summary">{renderInline(text)}</div>
          );
        } else {
          out.push(
            <p key={key++} className="md-paragraph">{renderInline(text)}</p>
          );
        }
        paragraph = [];
      }
    };

    const flushQuote = () => {
      if (quoteLines.length > 0) {
        out.push(
          <blockquote key={key++} className="md-quote">
            {quoteLines.map((ql, qi) => (
              <p key={qi} style={{ margin: qi > 0 ? "4px 0 0 0" : "0" }}>{renderInline(ql)}</p>
            ))}
          </blockquote>
        );
        quoteLines = [];
        inQuote = false;
      }
    };

    while (i < lines.length) {
      const line = lines[i];

      // 代码块内
      if (inCode) {
        if (/^```/.test(line.trimStart())) {
          inCode = false;
          const info = parseCodeBlock(codeMeta, codeBuffer.join("\n"));
          out.push(
            <CodeBlock key={key++} info={info} t={t} />
          );
          codeBuffer = [];
          codeMeta = "";
        } else {
          codeBuffer.push(line);
        }
        i++;
        continue;
      }

      // 代码块开始
      if (/^```/.test(line.trimStart())) {
        flushQuote();
        flushParagraph();
        inCode = true;
        codeMeta = line.replace(/^```/, "").trim();
        i++;
        continue;
      }

      const trimmed = line.trim();

      // 空行：结束引用块或段落
      if (trimmed === "") {
        if (inQuote) {
          flushQuote();
        }
        flushParagraph();
        i++;
        continue;
      }

      // 分隔线
      if (/^(-{3,}|\*{3,})$/.test(trimmed)) {
        flushQuote();
        flushParagraph();
        out.push(<hr key={key++} className="md-hr" />);
        i++;
        continue;
      }

      // 引用块（> 前缀）
      const quoteMatch = /^>\s?(.*)$/.exec(line);
      if (quoteMatch) {
        flushParagraph();
        inQuote = true;
        quoteLines.push(quoteMatch[1] || "");
        i++;
        continue;
      }

      // 非引用行：结束引用块
      if (inQuote) {
        flushQuote();
      }

      // 标题
      const heading = /^(#{1,6})\s+(.+)$/.exec(trimmed);
      if (heading) {
        flushParagraph();
        const level = heading[1].length;
        const sizeClass = `md-h${level}`;
        out.push(
          <div key={key++} className={`md-heading ${sizeClass}`}>
            {renderInline(heading[2])}
          </div>
        );
        i++;
        continue;
      }

      // 有序列表
      const orderedItem = /^\s*(\d+)\.\s+(.+)$/.exec(trimmed);
      if (orderedItem) {
        flushParagraph();
        out.push(
          <div key={key++} className="md-ordered-item">
            <span style={{ color: "var(--text-level-3)", flexShrink: 0, minWidth: "20px" }}>{orderedItem[1]}.</span>
            <span>{renderInline(orderedItem[2])}</span>
          </div>
        );
        i++;
        continue;
      }

      // 无序列表
      const listItem = /^\s*[-*+]\s+(.+)$/.exec(trimmed);
      if (listItem) {
        flushParagraph();
        out.push(
          <div key={key++} className="md-list-item">
            <span style={{ color: "var(--text-level-4)", flexShrink: 0 }}>•</span>
            <span>{renderInline(listItem[1])}</span>
          </div>
        );
        i++;
        continue;
      }

      // 普通段落
      paragraph.push(line.trim());
      i++;
    }

    // 处理尾部未闭合的引用块 / 代码块 / 段落
    if (inQuote) flushQuote();
    if (inCode && codeBuffer.length > 0) {
      const info = parseCodeBlock(codeMeta, codeBuffer.join("\n"));
      out.push(<CodeBlock key={key++} info={info} t={t} />);
    }
    flushParagraph();

    return out;
  }, [content, t]);

  return (
    <div style={{ fontSize: "14px", lineHeight: 1.625, color: "var(--text-level-2)", wordBreak: "break-word" }}>
      {blocks.length === 0 ? content : blocks}
    </div>
  );
});

interface CodeBlockProps {
  info: CodeBlockInfo;
  t: (key: string) => string;
}

/** 代码块：Action Bar（语言 | 行数 | 折叠 | 复制），超过阈值默认折叠 */
function CodeBlock({ info, t }: CodeBlockProps) {
  const [collapsed, setCollapsed] = useState(info.isCollapsible);
  const [copied, setCopied] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const cancelReset = () => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  };

  const resetSoon = () => {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => setCopied(false), 1200);
  };

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(info.code);
      setCopied(true);
      cancelReset();
    } catch {
      // Clipboard unavailable
    }
  };

  useEffect(() => () => {
    if (timerRef.current) clearTimeout(timerRef.current);
  }, []);

  return (
    <div className="md-code-block">
      {/* Action Bar */}
      <div className="md-code-bar">
        <code style={{ fontSize: "11px", color: "var(--color-primary)", fontWeight: 500 }}>{info.lang}</code>
        <span style={{ color: "var(--text-level-4)" }}>{info.lineCount} lines</span>
        <span style={{ flex: 1 }} />
        {info.isCollapsible && (
          <button
            onClick={() => setCollapsed((v) => !v)}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "4px",
              padding: "2px 8px",
              borderRadius: "var(--radius-sm)",
              border: "none",
              background: "transparent",
              cursor: "pointer",
              fontSize: "11px",
              color: "var(--text-level-3)",
              outline: "none",
            }}
            onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-level-2)"; e.currentTarget.style.color = "var(--text-level-1)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = "var(--text-level-3)"; }}
          >
            {collapsed ? <ChevronDown style={{ width: "12px", height: "12px" }} /> : <ChevronUp style={{ width: "12px", height: "12px" }} />}
            {collapsed ? t("chat.codeExpand") : t("chat.codeCollapse")}
          </button>
        )}
        <button
          onClick={handleCopy}
          onMouseEnter={(e) => { cancelReset(); e.currentTarget.style.background = "var(--bg-level-2)"; }}
          onMouseLeave={(e) => { resetSoon(); e.currentTarget.style.background = "transparent"; }}
          style={{
            display: "flex",
            alignItems: "center",
            gap: "4px",
            padding: "2px 8px",
            borderRadius: "var(--radius-sm)",
            border: "none",
            background: "transparent",
            cursor: "pointer",
            fontSize: "11px",
            color: copied ? "var(--color-copied)" : "var(--text-level-3)",
            outline: "none",
          }}
        >
          {copied ? <Check style={{ width: "12px", height: "12px" }} /> : <Copy style={{ width: "12px", height: "12px" }} />}
          {copied ? t("chat.codeCopied") : t("chat.codeCopy")}
        </button>
      </div>
      {/* 代码内容 */}
      <pre className="md-code-pre">
        {collapsed ? (
          <code>
            {info.code.split("\n").slice(0, 1).join("\n")}
            {"\n"}
            <span style={{ color: "var(--text-level-4)", fontStyle: "italic" }}>… {t("chat.codeCollapsedHint")}</span>
          </code>
        ) : (
          <code>{info.code}</code>
        )}
      </pre>
    </div>
  );
}
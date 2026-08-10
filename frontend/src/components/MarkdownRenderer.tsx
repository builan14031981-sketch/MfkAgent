"use client";

import { memo, useState, useMemo, useRef, useEffect } from "react";
import { ChevronDown, ChevronUp, Copy, Check } from "lucide-react";
import { useTranslation } from "@/hooks/useTranslation";

interface MarkdownRendererProps {
  content: string;
}

/** 代码块阈值：超过该行数默认折叠 */
const COLLAPSE_THRESHOLD = 15;

/** 总结/结论关键词（用于自动高亮检测） */
const SUMMARY_KEYWORDS = /^(总结|结论|摘要|关键要点|核心结论|Summary|Conclusion|Key Takeaways|TL;DR)[：:]/i;

/** 行内 Markdown 渲染：粗体 / 行内代码 */
function renderInline(text: string): React.ReactNode[] {
  const nodes: React.ReactNode[] = [];
  const tokens = text.split(/(`[^`]+`|\*\*[^*]+\*\*)/g).filter((t) => t !== "");
  for (const token of tokens) {
    if (token.startsWith("`") && token.endsWith("`") && token.length > 1) {
      nodes.push(
        <code key={nodes.length} className="md-code-inline">{token.slice(1, -1)}</code>
      );
    } else if (token.startsWith("**") && token.endsWith("**") && token.length > 4) {
      nodes.push(<strong key={nodes.length} className="md-strong">{token.slice(2, -2)}</strong>);
    } else {
      nodes.push(token);
    }
  }
  return nodes;
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
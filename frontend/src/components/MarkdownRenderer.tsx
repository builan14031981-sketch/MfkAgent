"use client";

import { useState, useMemo } from "react";
import { ChevronDown, ChevronUp, Copy, Check } from "lucide-react";
import { useTranslation } from "@/hooks/useTranslation";

interface MarkdownRendererProps {
  content: string;
}

/** 代码块阈值：超过该行数默认折叠 */
const COLLAPSE_THRESHOLD = 15;

/** 极简行内 Markdown：粗体 / 行内代码 */
function renderInline(text: string): React.ReactNode[] {
  const nodes: React.ReactNode[] = [];
  // 按行内代码 / 粗体分块（代码优先，避免被粗体误伤）
  const tokens = text.split(/(`[^`]+`|\*\*[^*]+\*\*)/g).filter((t) => t !== "");
  for (const token of tokens) {
    if (token.startsWith("`") && token.endsWith("`") && token.length > 1) {
      nodes.push(
        <code key={nodes.length} style={{
          fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
          fontSize: "0.9em",
          background: "var(--bg-level-3)",
          padding: "2px 5px",
          borderRadius: "var(--radius-xs)",
          color: "var(--color-primary)",
        }}>{token.slice(1, -1)}</code>
      );
    } else if (token.startsWith("**") && token.endsWith("**") && token.length > 4) {
      nodes.push(<strong key={nodes.length} style={{ fontWeight: 600 }}>{token.slice(2, -2)}</strong>);
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

/** 解析一个 ``` 代码块 */
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

/**
 * 极简 Markdown 渲染器（自写轻量版）：
 * - 代码块：Action Bar（语言 | 行数 | 折叠/展开 | 复制），超过 15 行默认折叠
 * - 行内代码 / 粗体 / 标题 / 无序列表 / 分隔线
 */
export function MarkdownRenderer({ content }: MarkdownRendererProps) {
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

    const flushParagraph = () => {
      if (paragraph.length > 0) {
        out.push(
          <p key={key++} style={{ margin: "0 0 8px 0" }}>{renderInline(paragraph.join(" "))}</p>
        );
        paragraph = [];
      }
    };

    while (i < lines.length) {
      const line = lines[i];

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

      if (/^```/.test(line.trimStart())) {
        flushParagraph();
        inCode = true;
        codeMeta = line.replace(/^```/, "").trim();
        i++;
        continue;
      }

      const trimmed = line.trim();
      if (trimmed === "") {
        flushParagraph();
        i++;
        continue;
      }
      // 分隔线
      if (/^(-{3,}|\*{3,})$/.test(trimmed)) {
        flushParagraph();
        out.push(<hr key={key++} style={{ border: "none", borderTop: "1px solid var(--border-secondary)", margin: "12px 0" }} />);
        i++;
        continue;
      }
      // 标题
      const heading = /^(#{1,6})\s+(.+)$/.exec(trimmed);
      if (heading) {
        flushParagraph();
        const level = heading[1].length;
        const size = level === 1 ? "20px" : level === 2 ? "17px" : level === 3 ? "15px" : "14px";
        out.push(
          <div key={key++} style={{ fontSize: size, fontWeight: 600, margin: "12px 0 8px 0", color: "var(--text-level-1)", lineHeight: 1.4 }}>
            {renderInline(heading[2])}
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
          <div key={key++} style={{ display: "flex", gap: "8px", margin: "0 0 4px 0", fontSize: "14px", lineHeight: 1.625 }}>
            <span style={{ color: "var(--text-level-4)", flexShrink: 0 }}>•</span>
            <span>{renderInline(listItem[1])}</span>
          </div>
        );
        i++;
        continue;
      }
      // 普通段落（合并连续行）
      paragraph.push(line.trim());
      i++;
    }

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
}

interface CodeBlockProps {
  info: CodeBlockInfo;
  t: (key: string) => string;
}

/** 长代码块：顶部 Action Bar（语言 | 行数 | 折叠 | 复制），默认折叠 */
function CodeBlock({ info, t }: CodeBlockProps) {
  const [collapsed, setCollapsed] = useState(info.isCollapsible);
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(info.code);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard unavailable
    }
  };

  return (
    <div style={{
      margin: "0 0 8px 0",
      borderRadius: "var(--radius-md)",
      border: "1px solid var(--border-primary)",
      overflow: "hidden",
      background: "var(--bg-level-3)",
    }}>
      {/* Action Bar */}
      <div style={{
        display: "flex",
        alignItems: "center",
        gap: "8px",
        padding: "4px 10px",
        background: "var(--bg-level-4)",
        borderBottom: "1px solid var(--border-primary)",
        fontSize: "11px",
        color: "var(--text-level-3)",
        userSelect: "none",
      }}>
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
            color: copied ? "var(--color-success)" : "var(--text-level-3)",
            outline: "none",
          }}
          onMouseEnter={(e) => { e.currentTarget.style.background = "var(--bg-level-2)"; }}
          onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
        >
          {copied ? <Check style={{ width: "12px", height: "12px" }} /> : <Copy style={{ width: "12px", height: "12px" }} />}
          {copied ? t("chat.codeCopied") : t("chat.codeCopy")}
        </button>
      </div>
      {/* 代码内容：折叠时只显示首行 + 省略提示 */}
      <pre style={{
        margin: 0,
        padding: "8px 10px",
        overflowX: "auto",
        fontSize: "12px",
        lineHeight: 1.5,
        fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
        color: "var(--text-level-2)",
      }}>
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

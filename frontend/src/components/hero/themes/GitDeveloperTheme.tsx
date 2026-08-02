"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import type { HeroThemeProps } from "@/themes/types";
import { TypewriterLine } from "../shared";

const GRAY = "#9ca3af";
const GREEN = "#22c55e";
const ORANGE = "#f97316";
const BRANCH = `*
*
*
*  feat: awaken MfkAgent AI (HEAD -> main)
| *
| *  feat: init agent core
|/
*  initial commit`;

/** Theme 4: Git Developer — git commit + build success + 程序员彩蛋 */
export function GitDeveloperTheme({ title, welcome, subtext, animated }: HeroThemeProps) {
  const [buildDone, setBuildDone] = useState(false);
  const showBuild = animated ? buildDone : true;

  useEffect(() => {
    const t = setTimeout(() => setBuildDone(true), 6400);
    return () => clearTimeout(t);
  }, []);

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      style={{
        width: "100%",
        maxWidth: "640px",
        margin: "0 auto",
        borderRadius: "12px",
        border: "1px solid var(--border-primary)",
        background: "var(--bg-level-3)",
        boxShadow: "var(--shadow-md)",
        overflow: "hidden",
        fontFamily: "var(--font-geist-mono), ui-monospace, 'Courier New', monospace",
        textAlign: "left",
      }}
    >
      {/* 窗口标题栏（macOS 风格） */}
      <div style={{
        display: "flex",
        alignItems: "center",
        gap: "8px",
        padding: "8px 14px",
        borderBottom: "1px solid var(--border-primary)",
        background: "var(--bg-level-2)",
      }}>
        <span style={{ width: 10, height: 10, borderRadius: "50%", background: "#ff5f56" }} />
        <span style={{ width: 10, height: 10, borderRadius: "50%", background: "#ffbd2e" }} />
        <span style={{ width: 10, height: 10, borderRadius: "50%", background: "#27c93f" }} />
        <span style={{ flex: 1, textAlign: "center", fontSize: 12, color: "var(--text-level-3)" }}>git — mfkagent</span>
      </div>

      <div style={{ padding: "18px 22px 22px", fontSize: 13, lineHeight: 1.9 }}>
        <TypewriterLine text={`$ git init --agent=mfkagent`} delay={200} speed={22} color={GRAY} animated={animated} />
        <TypewriterLine text={`$ git commit -m "feat: awaken MfkAgent AI"`} delay={900} speed={22} color={GRAY} animated={animated} />
        <TypewriterLine text={`[main a1b2c3d] feat: awaken MfkAgent AI`} delay={1700} speed={18} color={GREEN} animated={animated} />
        <TypewriterLine text=" 8 files changed, 2048 insertions(+), 0 deletions(-)" delay={2400} speed={14} color={GRAY} animated={animated} />

        {/* ASCII 分支图 + 大标题 */}
        <div style={{ display: "flex", gap: 18, margin: "10px 0 8px", minHeight: 110 }}>
          <pre style={{
            margin: 0,
            fontSize: 12,
            lineHeight: 1.45,
            color: ORANGE,
            whiteSpace: "pre",
          }}>{BRANCH}</pre>
          <div style={{ display: "flex", flexDirection: "column", justifyContent: "center" }}>
            <div style={{ fontSize: 30, fontWeight: 700, color: "var(--text-level-1)", letterSpacing: "-0.02em" }}>{title}</div>
            {welcome && (
              <div style={{ fontSize: 13, color: "var(--text-level-3)", marginTop: 6 }}>
                <TypewriterLine text={`commit message: ${welcome}`} delay={3100} speed={16} color="var(--text-level-3)" block={false} animated={animated} />
              </div>
            )}
          </div>
        </div>

        {/* Build Success */}
        {showBuild && (
          <div style={{ marginTop: 4 }}>
            <TypewriterLine text="✔ Build successful — production ready" delay={5500} speed={18} color={GREEN} animated={animated} />
            <TypewriterLine text="C:\projects\mfkagent> npm run dev  ··· ✓ ready" delay={6300} speed={18} color={GRAY} animated={animated} />
            {/* 程序员彩蛋 */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 7 }}
              style={{ marginTop: 10, fontSize: 12, color: "var(--text-level-4)", fontFamily: "var(--font-family)" }}
            >
              <span>git blame: the AI wrote itself · </span>
              <span style={{ textDecoration: "line-through" }}>it&apos;s not a bug</span>
              <span> — it&apos;s a feature.</span>
            </motion.div>
          </div>
        )}

        {animated && (
          <div style={{ marginTop: 10, fontSize: 13, color: GREEN, display: "flex", gap: 6, alignItems: "center" }}>
            <span>$</span>
            <span style={{ display: "inline-block", width: 10, height: 15, background: GREEN, animation: "heroCursor 1s steps(1) infinite" }} />
          </div>
        )}
        {!animated && subtext && (
          <div style={{ fontSize: 12, color: "var(--text-level-4)" }}>{subtext}</div>
        )}
      </div>
    </motion.div>
  );
}

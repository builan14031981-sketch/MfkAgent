"use client";

interface StaticTitleProps {
  title: string;
  welcome: string;
  subtext: string;
}

/** 关闭动画时的静态标题（与原有首页样式一致） */
export function StaticTitle({ title, welcome, subtext }: StaticTitleProps) {
  return (
    <div style={{ textAlign: "center" }}>
      <h1 style={{
        fontSize: 44,
        fontWeight: 600,
        letterSpacing: "-0.02em",
        color: "var(--text-level-1)",
        margin: 0,
      }}>{title}</h1>
      {welcome && (
        <p style={{
          fontSize: 16,
          color: "var(--text-level-3)",
          marginTop: 12,
          marginBottom: 0,
        }}>{welcome}</p>
      )}
      {subtext && (
        <p style={{
          fontSize: 12,
          color: "var(--text-level-4)",
          marginTop: 6,
          marginBottom: 0,
          fontFamily: "var(--font-family)",
        }}>{subtext}</p>
      )}
    </div>
  );
}

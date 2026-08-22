"use client";

/**
 * IconPlayground —— 图标方案独立测试台（阶段三）
 *
 * 用途：将 8 个场景选中的纯线条 SVG 方案，放入「模拟真实业务场景」中渲染上身效果，
 * 用于对比与挑选。与生产业务组件完全隔离，不修改任何现有代码。
 *
 * 规范：viewBox="0 0 24 24" / fill="none" / stroke="currentColor"
 *       / strokeWidth="1.5" / round 端点 / 纯线条极简几何。
 *
 * 路由：/icon-test
 */

import type { CSSProperties, ReactNode } from "react";

/* ── 线条图标基础壳（统一规范） ─────────────────────────────── */
function Icon({ children, size = 18, color }: { children: ReactNode; size?: number; color?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      style={{ color, flexShrink: 0 }}
    >
      {children}
    </svg>
  );
}

/* ── 场景 1 · 任务进度徽章（方案 A 圆环） ───────────────────── */
const RingDone = () => (
  <Icon><circle cx="12" cy="12" r="9" strokeWidth="1.5" fill="none" /><path d="M8 12l3 3 5-5" /></Icon>
);
const RingFail = () => (
  <Icon><circle cx="12" cy="12" r="9" strokeWidth="1.5" fill="none" /><path d="M9 9l6 6M15 9l-6 6" /></Icon>
);
const RingRun = () => (
  <Icon><circle cx="12" cy="12" r="9" strokeWidth="1.5" fill="none" strokeDasharray="40 16" /><circle cx="12" cy="12" r="2" fill="currentColor" /></Icon>
);
const RingPending = () => (
  <Icon><circle cx="12" cy="12" r="7" strokeWidth="1.5" fill="none" /><circle cx="12" cy="12" r="2" fill="currentColor" opacity="0.4" /></Icon>
);

/* ── 场景 2 · Agent 运行状态（方案 A 脉冲环） ────────────────── */
const PulseWorking = () => (
  <Icon><circle cx="12" cy="12" r="8" opacity="0.3" /><circle cx="12" cy="12" r="5" strokeDasharray="16 15" /></Icon>
);
const PulseDone = () => (
  <Icon><circle cx="12" cy="12" r="7" /><path d="M8 12l3 3 5-5" /></Icon>
);
const PulseError = () => (
  <Icon><circle cx="12" cy="12" r="7" /><path d="M12 8v4M12 16v-.5" /></Icon>
);

/* ── 场景 3 · 审批卡片（方案 C 印章） ───────────────────────── */
const StampPending = () => (
  <Icon><circle cx="12" cy="12" r="8" /><path d="M12 8v4M12 16v-.5" /></Icon>
);
const StampApprove = () => (
  <Icon><circle cx="12" cy="12" r="8" /><path d="M9 12l2 2 4-4" /></Icon>
);
const StampReject = () => (
  <Icon><circle cx="12" cy="12" r="8" /><path d="M9 9l6 6M15 9l-6 6" /></Icon>
);
const StampHighRisk = () => (
  <Icon><polygon points="12,4 17,8 17,14 12,18 7,14 7,8" /><path d="M12 8v4M12 15v-.5" /></Icon>
);

/* ── 场景 4 · 工具行内状态（方案 A 细圆环） ─────────────────── */
const MiniOk = () => (
  <Icon size={14}><circle cx="12" cy="12" r="8" opacity="0.3" /><path d="M9 12l2 2 4-4" /></Icon>
);
const MiniFail = () => (
  <Icon size={14}><circle cx="12" cy="12" r="8" opacity="0.3" /><path d="M10 10l4 4M14 10l-4 4" /></Icon>
);
const MiniCancel = () => (
  <Icon size={14}><circle cx="12" cy="12" r="8" opacity="0.3" /><line x1="8" y1="8" x2="16" y2="16" opacity="0.5" /></Icon>
);

/* ── 场景 5 · 工具日志图标（方案 C 代码风格） ───────────────── */
const CodePr = () => (
  <Icon><path d="M10 8l-4 4 4 4" /><path d="M14 8l4 4-4 4" /><line x1="4" y1="4" x2="20" y2="20" opacity="0.3" /></Icon>
);
const CodeIssue = () => (
  <Icon><circle cx="12" cy="12" r="8" /><line x1="8" y1="8" x2="16" y2="16" /><line x1="16" y1="8" x2="8" y2="16" /></Icon>
);
const CodeDelegate = () => (
  <Icon><path d="M4 4l7 7-7 7" /><path d="M12 4l7 7-7 7" /><line x1="12" y1="4" x2="12" y2="18" opacity="0.3" /></Icon>
);
const CodeApprove = () => (
  <Icon><path d="M12 3l7 4v5c0 4-3 7-7 8-4-1-7-4-7-8V7z" /><line x1="12" y1="8" x2="12" y2="14" /><circle cx="12" cy="16" r="1" fill="currentColor" /></Icon>
);

/* ── 场景 6 · 记忆类型图标（方案 C 抽象线） ─────────────────── */
const MemChat = () => (
  <Icon size={15}><path d="M3 12a4 4 0 0 1 6-3.5" /><path d="M21 12a4 4 0 0 0-6-3.5" /><line x1="12" y1="3" x2="12" y2="21" /><circle cx="12" cy="8" r="2" fill="currentColor" opacity="0.5" /></Icon>
);
const MemPref = () => (
  <Icon size={15}><polygon points="12,4 14,10 20,10 15,14 17,20 12,16 7,20 9,14 4,10 10,10" /></Icon>
);
const MemProject = () => (
  <Icon size={15}><path d="M4 20V4a2 2 0 0 1 2-2h8l6 6v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2z" /><line x1="14" y1="2" x2="14" y2="8" /><line x1="8" y1="13" x2="16" y2="13" /><line x1="8" y1="17" x2="16" y2="17" /></Icon>
);
const MemTask = () => (
  <Icon size={15}><rect x="5" y="4" width="14" height="16" rx="2" /><line x1="9" y1="12" x2="15" y2="12" /><line x1="9" y1="15" x2="13" y2="15" /></Icon>
);
const MemEvent = () => (
  <Icon size={15}><rect x="3" y="4" width="18" height="16" rx="2" /><line x1="3" y1="10" x2="21" y2="10" /><line x1="8" y1="2" x2="8" y2="6" /><line x1="16" y1="2" x2="16" y2="6" /></Icon>
);
const MemKnow = () => (
  <Icon size={15}><path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1 0-5H20" /><line x1="8" y1="7" x2="14" y2="7" /></Icon>
);
const MemDecision = () => (
  <Icon size={15}><path d="M5 12l4-4 4 4" /><line x1="13" y1="8" x2="19" y2="8" /><line x1="5" y1="16" x2="19" y2="16" /></Icon>
);
const MemTemp = () => (
  <Icon size={15}><circle cx="12" cy="12" r="9" /><line x1="12" y1="7" x2="12" y2="12" /><line x1="12" y1="12" x2="15" y2="15" /></Icon>
);

/* ── 场景 7 · 子代理身份（方案 C 抽象几何） ─────────────────── */
const SubReview = () => (
  <Icon><polygon points="12,3 20,8 20,16 12,21 4,16 4,8" /><path d="M9 11l2 2 4-4" /></Icon>
);
const SubResearch = () => (
  <Icon><polygon points="12,5 16,10 22,10 18,15 20,21 12,18 4,21 6,15 2,10 8,10" /><circle cx="12" cy="13" r="2" fill="currentColor" opacity="0.4" /></Icon>
);
const SubAnalyst = () => (
  <Icon><polygon points="12,4 18,7 18,14 12,17 6,14 6,7" /><line x1="8" y1="10" x2="16" y2="10" /><line x1="8" y1="13" x2="14" y2="13" /></Icon>
);
const SubBadge = () => (
  <Icon size={12}><polygon points="12,4 18,7 18,14 12,17 6,14 6,7" strokeDasharray="3 3" /><circle cx="12" cy="10.5" r="2" fill="currentColor" /></Icon>
);

/* ── 场景 8 · 消息大纲（方案 A 极简） ───────────────────────── */
const OulBody = () => (
  <Icon size={14}><line x1="4" y1="6" x2="20" y2="6" /><line x1="4" y1="10" x2="20" y2="10" /><line x1="4" y1="14" x2="20" y2="14" /><line x1="4" y1="18" x2="14" y2="18" /></Icon>
);
const OulThink = () => (
  <Icon size={14}><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 3" /></Icon>
);
const OulTool = () => (
  <Icon size={14}><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.6-3.6a1 1 0 0 0 0-1.4l-1.6-1.6a1 1 0 0 0-1.4 0z" /><path d="M11 8H5a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h9a2 2 0 0 0 2-2v-6" /></Icon>
);
const OulMemo = () => (
  <Icon size={14}><path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z" /></Icon>
);
const OulQuote = () => (
  <Icon size={14}><path d="M3 21c3 0 7-1 7-8V5c0-1.25-.756-2.017-2-2H4c-.5 0-1 .5-1 1v14z" /><path d="M21 21c-3 0-7-1-7-8V5c0-1.25.756-2.017 2-2h4c.5 0 1 .5 1 1v14z" /></Icon>
);

/* ── 模拟场景容器样式常量 ───────────────────────────────────── */
const card: CSSProperties = {
  background: "var(--bg-level-3)",
  border: "1px solid var(--border-primary)",
  borderRadius: "var(--radius-md)",
  padding: "6px 10px",
};
const row: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "8px",
  padding: "2px 0",
};
const badge: CSSProperties = {
  fontSize: "10px",
  fontWeight: 600,
  padding: "1px 7px",
  borderRadius: "var(--radius-xs)",
  background: "color-mix(in srgb, var(--text-level-4) 12%, transparent)",
  color: "var(--text-level-2)",
  whiteSpace: "nowrap",
};
const pill: CSSProperties = {
  fontSize: "10px",
  fontWeight: 600,
  padding: "2px 9px",
  borderRadius: "var(--radius-full)",
  whiteSpace: "nowrap",
};
const sceneSection: CSSProperties = {
  border: "1px solid var(--border-primary)",
  borderRadius: "var(--radius-lg)",
  background: "var(--bg-level-2)",
  padding: "10px",
  marginBottom: "8px",
};
const sceneTitle: CSSProperties = {
  fontSize: "13px",
  fontWeight: 600,
  color: "var(--text-level-1)",
  display: "flex",
  alignItems: "center",
  gap: "8px",
  marginBottom: "6px",
};
const chosenTag: CSSProperties = {
  fontSize: "10px",
  fontWeight: 600,
  color: "var(--color-primary)",
  background: "var(--color-primary-light)",
  padding: "1px 8px",
  borderRadius: "var(--radius-full)",
};

/* ── 页面 ────────────────────────────────────────────────────── */
export default function IconTestPage() {
  return (
    <div style={{ height: "100%", overflowY: "auto", lineHeight: "1.3", maxWidth: 860, margin: "0 auto", padding: "20px 20px 40px" }}>
      <h1 style={{ fontSize: 18, fontWeight: 700, color: "var(--text-level-1)", marginBottom: 2 }}>图标方案测试台</h1>
      <p style={{ fontSize: 12, color: "var(--text-level-3)", marginBottom: 12 }}>
        viewBox 24 · strokeWidth 1.5 · round · 纯线条 · 与生产组件隔离（不修改任何现有代码）
      </p>

      {/* ===== 场景 1 ===== */}
      <section style={sceneSection}>
        <div style={sceneTitle}>场景 1 · 任务进度徽章 <span style={chosenTag}>方案 A</span></div>
        <div style={card}>
          <div style={{ ...row, color: "var(--text-level-2)" }}>
            <span style={{ color: "var(--color-success)" }}><RingDone /></span>
            <span style={badge}>代码审查员</span>
            <span style={{ fontSize: 12, color: "var(--text-level-3)" }}>审查 git diff · 3 个文件</span>
          </div>
          <div style={{ ...row, color: "var(--text-level-2)" }}>
            <span style={{ color: "var(--color-primary)" }}><RingRun /></span>
            <span style={badge}>后端</span>
            <span style={{ fontSize: 12, color: "var(--text-level-3)" }}>运行 pytest · 任务 2/5</span>
          </div>
          <div style={{ ...row, color: "var(--text-level-2)" }}>
            <span style={{ color: "var(--color-error)" }}><RingFail /></span>
            <span style={badge}>前端</span>
            <span style={{ fontSize: 12, color: "var(--text-level-3)" }}>构建 dist · 失败</span>
          </div>
          <div style={{ ...row, color: "var(--text-level-2)" }}>
            <span style={{ color: "var(--text-level-4)" }}><RingPending /></span>
            <span style={badge}>分析</span>
            <span style={{ fontSize: 12, color: "var(--text-level-3)" }}>等待执行 · 任务 4/5</span>
          </div>
        </div>
      </section>

      {/* ===== 场景 2 ===== */}
      <section style={sceneSection}>
        <div style={sceneTitle}>场景 2 · Agent 运行状态 <span style={chosenTag}>方案 A</span></div>
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <div style={card}>
            <div style={row}>
              <span style={{ color: "var(--color-primary)" }}><PulseWorking /></span>
              <span style={{ fontSize: 13, fontWeight: 600, color: "var(--color-primary)" }}>多智能体协调器</span>
              <span style={pill as CSSProperties}>任务 2/5</span>
              <span style={{ fontSize: 12, color: "var(--text-level-3)", marginLeft: "auto" }}>正在生成测试用例…</span>
            </div>
          </div>
          <div style={card}>
            <div style={row}>
              <span style={{ color: "var(--color-success)" }}><PulseDone /></span>
              <span style={{ fontSize: 13, fontWeight: 600, color: "var(--color-success)" }}>代码审查员</span>
              <span style={{ fontSize: 12, color: "var(--text-level-3)", marginLeft: "auto" }}>审查完成，未发现问题</span>
            </div>
          </div>
          <div style={card}>
            <div style={row}>
              <span style={{ color: "var(--color-error)" }}><PulseError /></span>
              <span style={{ fontSize: 13, fontWeight: 600, color: "var(--color-error)" }}>网络调研员</span>
              <span style={{ fontSize: 12, color: "var(--text-level-3)", marginLeft: "auto" }}>调研失败，网络超时</span>
            </div>
          </div>
        </div>
      </section>

      {/* ===== 场景 3 ===== */}
      <section style={sceneSection}>
        <div style={sceneTitle}>场景 3 · 审批卡片 <span style={chosenTag}>方案 C</span></div>
        <div style={card}>
          <div style={row}>
            <span style={{ color: "var(--color-warning)" }}><StampPending /></span>
            <span style={{ fontSize: 13, fontWeight: 600, color: "var(--text-level-1)" }}>等待审批</span>
            <span style={{ ...pill, background: "color-mix(in srgb, var(--color-error) 14%, transparent)", color: "var(--color-error)" }}>高风险</span>
          </div>
          <div style={{ ...row, paddingLeft: 28 }}>
            <code style={{ fontSize: 12, color: "var(--text-level-2)", fontFamily: "var(--font-geist-mono), monospace" }}>$ npm install</code>
          </div>
          <div style={{ ...row, paddingLeft: 28, gap: 8 }}>
            <span style={{ color: "var(--color-success)" }}><StampApprove /></span>
            <span style={{ fontSize: 12, color: "var(--text-level-3)" }}>同意</span>
            <span style={{ color: "var(--color-error)", marginLeft: 12 }}><StampReject /></span>
            <span style={{ fontSize: 12, color: "var(--text-level-3)" }}>拒绝</span>
          </div>
        </div>
      </section>

      {/* ===== 场景 4 ===== */}
      <section style={sceneSection}>
        <div style={sceneTitle}>场景 4 · 工具行内状态 <span style={chosenTag}>方案 A</span></div>
        <div style={card}>
          <div style={row}>
            <span style={{ color: "var(--color-info)" }}><CodePr /></span>
            <code style={{ fontSize: 12, color: "var(--text-level-2)", fontFamily: "var(--font-geist-mono), monospace" }}>write_file · src/utils.ts</code>
            <span style={{ marginLeft: "auto", color: "var(--color-success)" }}><MiniOk /></span>
          </div>
          <div style={row}>
            <span style={{ color: "var(--color-warning)" }}><CodePr /></span>
            <code style={{ fontSize: 12, color: "var(--color-error)", fontFamily: "var(--font-geist-mono), monospace" }}>$ npm run build</code>
            <span style={{ marginLeft: "auto", color: "var(--color-error)" }}><MiniFail /></span>
          </div>
          <div style={row}>
            <span style={{ color: "var(--color-info)" }}><CodePr /></span>
            <code style={{ fontSize: 12, color: "var(--text-level-3)", fontFamily: "var(--font-geist-mono), monospace" }}>search_files · query=&quot;api&quot;</code>
            <span style={{ marginLeft: "auto", color: "var(--text-level-4)" }}><MiniCancel /></span>
          </div>
        </div>
      </section>

      {/* ===== 场景 5 ===== */}
      <section style={sceneSection}>
        <div style={sceneTitle}>场景 5 · 工具日志图标 <span style={chosenTag}>方案 C</span></div>
        <div style={card}>
          <div style={row}>
            <span style={{ color: "var(--color-info)" }}><CodePr /></span>
            <span style={{ fontSize: 12, color: "var(--text-level-2)" }}>git merge · feature/notify</span>
          </div>
          <div style={row}>
            <span style={{ color: "var(--color-info)" }}><CodeIssue /></span>
            <span style={{ fontSize: 12, color: "var(--text-level-2)" }}>github_list_issues · open=3</span>
          </div>
          <div style={row}>
            <span style={{ color: "var(--color-primary)" }}><CodeDelegate /></span>
            <span style={{ fontSize: 12, color: "var(--text-level-2)" }}>delegate_sub_agent · 代码审查员</span>
          </div>
          <div style={row}>
            <span style={{ color: "var(--color-warning)" }}><CodeApprove /></span>
            <span style={{ fontSize: 12, color: "var(--text-level-2)" }}>approve · npm install</span>
          </div>
        </div>
      </section>

      {/* ===== 场景 6 ===== */}
      <section style={sceneSection}>
        <div style={sceneTitle}>场景 6 · 记忆类型图标 <span style={chosenTag}>方案 C</span></div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {[
            { icon: <MemChat />, label: "对话", c: "var(--color-primary)" },
            { icon: <MemPref />, label: "偏好", c: "var(--color-warning)" },
            { icon: <MemProject />, label: "项目", c: "var(--color-info)" },
            { icon: <MemTask />, label: "任务", c: "var(--color-success)" },
            { icon: <MemEvent />, label: "事件", c: "var(--color-warning)" },
            { icon: <MemKnow />, label: "知识", c: "var(--color-primary)" },
            { icon: <MemDecision />, label: "决策", c: "var(--color-error)" },
            { icon: <MemTemp />, label: "临时", c: "var(--text-level-4)" },
          ].map((m) => (
            <span key={m.label} style={{ display: "inline-flex", alignItems: "center", gap: 5, padding: "3px 9px", borderRadius: "var(--radius-full)", background: "var(--bg-level-3)", border: "1px solid var(--border-primary)" }}>
              <span style={{ color: m.c }}>{m.icon}</span>
              <span style={{ fontSize: 11, color: "var(--text-level-2)" }}>{m.label}</span>
            </span>
          ))}
        </div>
      </section>

      {/* ===== 场景 7 ===== */}
      <section style={sceneSection}>
        <div style={sceneTitle}>场景 7 · 子代理身份 <span style={chosenTag}>方案 C</span></div>
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <div style={card}>
            <div style={row}>
              <span style={{ color: "var(--color-primary)" }}><SubReview /></span>
              <span style={{ fontSize: 12, fontWeight: 600, color: "var(--text-level-1)" }}>代码审查员</span>
              <span style={{ fontSize: 11, color: "var(--text-level-3)", marginLeft: "auto", display: "inline-flex", alignItems: "center", gap: 4 }}>
                <SubBadge />子代理
              </span>
            </div>
          </div>
          <div style={card}>
            <div style={row}>
              <span style={{ color: "var(--color-warning)" }}><SubResearch /></span>
              <span style={{ fontSize: 12, fontWeight: 600, color: "var(--text-level-1)" }}>网络调研员</span>
              <span style={{ fontSize: 11, color: "var(--text-level-3)", marginLeft: "auto", display: "inline-flex", alignItems: "center", gap: 4 }}>
                <SubBadge />子代理
              </span>
            </div>
          </div>
          <div style={card}>
            <div style={row}>
              <span style={{ color: "var(--color-info)" }}><SubAnalyst /></span>
              <span style={{ fontSize: 12, fontWeight: 600, color: "var(--text-level-1)" }}>文件分析师</span>
              <span style={{ fontSize: 11, color: "var(--text-level-3)", marginLeft: "auto", display: "inline-flex", alignItems: "center", gap: 4 }}>
                <SubBadge />子代理
              </span>
            </div>
          </div>
        </div>
      </section>

      {/* ===== 场景 8 ===== */}
      <section style={sceneSection}>
        <div style={sceneTitle}>场景 8 · 消息大纲 <span style={chosenTag}>方案 A</span></div>
        <div style={card}>
          {[
            { icon: <OulBody />, label: "正文 · 实现说明", active: true },
            { icon: <OulThink />, label: "思考 · 权衡方案", active: false },
            { icon: <OulTool />, label: "工具 · 执行命令", active: false },
            { icon: <OulMemo />, label: "记忆 · 已保存", active: false },
            { icon: <OulQuote />, label: "引用 · 规格段落", active: false },
          ].map((o) => (
            <div key={o.label} style={{ ...row, padding: "3px 0", color: o.active ? "var(--color-primary)" : "var(--text-level-4)" }}>
              {o.icon}
              <span style={{ fontSize: 12, color: o.active ? "var(--color-primary)" : "var(--text-level-3)" }}>{o.label}</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

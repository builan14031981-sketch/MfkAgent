"use client";

/**
 * ToolCall / Approval —— 工具调用聚合摘要 & 审批卡片 最小测试台
 *
 * 用途：用本地模拟数据直接渲染生产组件（ToolCallGroup / ApprovalCard），
 * 以便在浏览器中直观验证：
 *  - 多工具完成后按操作类型聚合的摘要（如「已编辑 3 个文件，读取 1 个文件」），点击组头展开/折叠；
 *  - 审批卡片的胶囊同意/拒绝按钮（图标文字对齐、hover 态）。
 * 与生产业务完全隔离，不修改任何现有代码。路由：/tool-test
 */

import { useState, type CSSProperties } from "react";
import { ToolCallGroup, type ToolCall } from "@/components/ToolCallGroup";
import { ApprovalCard } from "@/components/ApprovalCard";
import type { ApprovalRequest } from "@/types/runtime";

/* ── 模拟数据 · 文件操作组（多工具完成 → 聚合摘要） ─────────── */
const fileTools: ToolCall[] = [
  {
    tool: "write_file",
    tool_call_id: "w1",
    status: "success",
    input: { relative_path: "src/api/server.ts" },
    result: "已写入 12 行",
    duration_ms: 320,
  },
  {
    tool: "write_file",
    tool_call_id: "w2",
    status: "success",
    input: { relative_path: "src/api/client.ts" },
    result: "已写入 8 行",
    duration_ms: 210,
  },
  {
    tool: "write_file",
    tool_call_id: "w3",
    status: "success",
    input: { relative_path: "src/lib/utils.ts" },
    result: "已写入 5 行",
    duration_ms: 180,
  },
  {
    tool: "read_file",
    tool_call_id: "r1",
    status: "success",
    input: { relative_path: "README.md" },
    result: "读取 42 行",
    duration_ms: 90,
  },
];

/* ── 模拟数据 · 命令 + Git 组（混合分类） ───────────────────── */
const cmdTools: ToolCall[] = [
  {
    tool: "run_command",
    tool_call_id: "c1",
    status: "success",
    input: { command: "npm run lint" },
    result: "Lint 通过",
    duration_ms: 1500,
  },
  {
    tool: "run_command",
    tool_call_id: "c2",
    status: "success",
    input: { command: "npm test" },
    result: "8 passed",
    duration_ms: 2400,
  },
  {
    tool: "git_status",
    tool_call_id: "g1",
    status: "success",
    input: {},
    result: "M src/api/server.ts",
    duration_ms: 120,
  },
];

/* ── 模拟数据 · 流式中组（单行 spinner） ───────────────────── */
const runningTools: ToolCall[] = [
  {
    tool: "search_files",
    tool_call_id: "s1",
    status: "success",
    input: { query: "api" },
    result: "2 个文件",
    duration_ms: 60,
  },
  {
    tool: "web_search",
    tool_call_id: "s2",
    status: "running",
    input: { query: "MfkAgent" },
  },
];

/* ── 模拟数据 · 审批卡片 ────────────────────────────────────── */
const approvalDestructive: ApprovalRequest = {
  approval_id: "a1",
  tool_call_id: "tc1",
  tool: "execute_command",
  command: "rm -rf dist/ && npm run build",
  risk_level: "destructive",
  risk_reason: "该命令会先删除 dist 目录下的所有文件且无法恢复，属于最高风险操作。",
};

const approvalWrite: ApprovalRequest = {
  approval_id: "a2",
  tool_call_id: "tc2",
  tool: "execute_command",
  command: "npm install",
  risk_level: "write",
  risk_reason: "该命令会写入 node_modules 目录并修改项目依赖，需要你的确认。",
};

const sectionStyle: CSSProperties = {
  border: "1px solid var(--border-primary)",
  borderRadius: "var(--radius-lg)",
  background: "var(--bg-level-2)",
  padding: "12px",
  marginBottom: "10px",
};

const sectionTitle: CSSProperties = {
  fontSize: "13px",
  fontWeight: 600,
  color: "var(--text-level-1)",
  marginBottom: "8px",
};

const hint: CSSProperties = {
  fontSize: "11px",
  color: "var(--text-level-4)",
  marginBottom: "8px",
};

export default function ToolTestPage() {
  const [resolved, setResolved] = useState<Record<string, "approved" | "rejected">>({});

  const resolve = (id: string, action: "approved" | "rejected") => {
    setResolved((s) => ({ ...s, [id]: action }));
  };

  return (
    <div
      style={{
        height: "100%",
        overflowY: "auto",
        lineHeight: "1.4",
        maxWidth: 860,
        margin: "0 auto",
        padding: "20px 20px 40px",
      }}
    >
      <h1 style={{ fontSize: 18, fontWeight: 700, color: "var(--text-level-1)", marginBottom: 2 }}>
        工具调用 & 审批 · 最小测试台
      </h1>
      <p style={{ fontSize: 12, color: "var(--text-level-3)", marginBottom: 12 }}>
        直接渲染生产组件（ToolCallGroup / ApprovalCard），与现有业务完全隔离
      </p>

      {/* ===== 工具调用聚合摘要 ===== */}
      <section style={sectionStyle}>
        <div style={sectionTitle}>工具调用聚合摘要</div>

        <div style={hint}>文件操作组（多工具完成 → 默认折叠，点击展开/折叠）：</div>
        <ToolCallGroup tools={fileTools} streaming={false} />

        <div style={{ ...hint, marginTop: 14 }}>命令 + Git 混合组（分类统计）：</div>
        <ToolCallGroup tools={cmdTools} streaming={false} />

        <div style={{ ...hint, marginTop: 14 }}>流式中组（单行 spinner，逐工具切换）：</div>
        <ToolCallGroup tools={runningTools} streaming={true} />
      </section>

      {/* ===== 审批卡片 ===== */}
      <section style={sectionStyle}>
        <div style={sectionTitle}>审批卡片（胶囊同意/拒绝按钮）</div>

        <div style={hint}>破坏性（红色脉冲边框 + 盾牌）：</div>
        {resolved[approvalDestructive.approval_id] ? (
          <div
            style={{
              fontSize: "12px",
              color: "var(--text-level-3)",
              padding: "10px 14px",
              borderRadius: "var(--radius-md)",
              background: "var(--bg-level-3)",
              border: "1px solid var(--border-primary)",
            }}
          >
            {resolved[approvalDestructive.approval_id] === "approved" ? "已批准 ✅" : "已拒绝 ❌"}
          </div>
        ) : (
          <ApprovalCard
            approval={approvalDestructive}
            onApprove={() => resolve(approvalDestructive.approval_id, "approved")}
            onDeny={() => resolve(approvalDestructive.approval_id, "rejected")}
          />
        )}

        <div style={{ ...hint, marginTop: 14 }}>写入操作（黄色警告边框）：</div>
        {resolved[approvalWrite.approval_id] ? (
          <div
            style={{
              fontSize: "12px",
              color: "var(--text-level-3)",
              padding: "10px 14px",
              borderRadius: "var(--radius-md)",
              background: "var(--bg-level-3)",
              border: "1px solid var(--border-primary)",
            }}
          >
            {resolved[approvalWrite.approval_id] === "approved" ? "已批准 ✅" : "已拒绝 ❌"}
          </div>
        ) : (
          <ApprovalCard
            approval={approvalWrite}
            onApprove={() => resolve(approvalWrite.approval_id, "approved")}
            onDeny={() => resolve(approvalWrite.approval_id, "rejected")}
          />
        )}
      </section>
    </div>
  );
}

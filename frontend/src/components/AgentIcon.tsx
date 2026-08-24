"use client";

import type { CSSProperties, ReactElement } from "react";
import { GeneralA, GeneralC } from "./agent-icons/general";
import { CoderC } from "./agent-icons/coder";
import { FrontendUiA } from "./agent-icons/frontend_ui";
import { GC } from "./agent-icons/g";
import { ProductA } from "./agent-icons/product";
import { SparkA } from "./agent-icons/spark";
import { PianaiA } from "./agent-icons/pianai";
import { WriterA } from "./agent-icons/writer";
import { CodeReviewC } from "./agent-icons/codeReviewer";
import { ResearcherC } from "./agent-icons/researcher";
import { FileAnalystB } from "./agent-icons/fileAnalyst";
import { BackendA } from "./agent-icons/backend";
import { AnalystC } from "./agent-icons/analyst";
import { MentorA } from "./agent-icons/mentor";
import { PersonalA } from "./agent-icons/personal";
import { ResearchC } from "./agent-icons/research";
import { GptA } from "./agent-icons/gpt";
import { PresentationA } from "./agent-icons/presentation";

type IconComponent = () => ReactElement;

/**
 * 生产 Agent 图标：agent.id / avatar 语义值 → 选定的新线条图标方案。
 * 统一走 agent-icons 的 24×24 / 1.5 细线 / round 规范，替换原 Lucide 图标。
 * 未知 id 回退到 general(C 意象抽象)，保证界面始终有图标。
 */
const AGENT_ICONS: Record<string, IconComponent> = {
  // ── 核心 Agent（按用户选定方案） ─────────────────────────
  general: GeneralA, // A 字母变形
  coder: CoderC, // C 终端窗口
  frontend_ui: FrontendUiA, // A 色环+笔杆
  g: GC, // C 盾心字母 G
  product: ProductA, // A 罗盘
  spark: SparkA, // A 歪斜闪电+星芒（抽象搞怪）
  pianai: PianaiA, // A 闪闪发光的心
  writer: WriterA, // A 笔尖
  writer_narrative: WriterA, // 作家 → 关联笔神 A
  backend: BackendA, // A 双机架
  analyst: AnalystC, // C 数据节点
  mentor: MentorA, // A 大脑
  personal: PersonalA, // A 人形
  research: ResearchC, // C 放大镜+十字（调研）
  gpt: GptA, // A 对话气泡
  sub_code_reviewer: CodeReviewC, // C 文档+聚焦镜
  sub_researcher: ResearcherC, // C 网络节点
  sub_file_analyst: FileAnalystB, // B 方形文件夹+对勾（1:1）
  warm: PianaiA, // 暖阳 → 关联偏爱 A（温暖之心）
  rational: AnalystC, // 理性 → 关联数据节点
  defense_ppt_expert: PresentationA, // 答辩PPT专家 → 演示屏
  // ── 后端 Agent.avatar 语义值（seed 归一化后的 icon 字段） ──
  code: CoderC,
  palette: FrontendUiA,
  server: BackendA,
  sparkles: GeneralA,
  search: ResearchC,
  pen: WriterA,
  book: WriterA,
  shield: GC,
  compass: ProductA,
  brain: MentorA,
  user: PersonalA,
  zap: SparkA,
  heart: PianaiA,
  target: AnalystC,
  globe: ResearcherC,
  file: FileAnalystB,
  presentation: PresentationA,
};

interface AgentIconProps {
  id?: string;
  icon?: string;
  size?: number;
  strokeWidth?: number;
  style?: CSSProperties;
}

/**
 * Agent 专属线条图标：根据 agent.id / avatar 语义值映射渲染。
 * 未知 id 回退到 general（C 意象抽象），保证界面始终有图标。
 * 注意：strokeWidth 仅透传样式，新图标固定 1.5 细线规范。
 */
export function AgentIcon({ id, icon, size = 16, strokeWidth = 1.75, style }: AgentIconProps) {
  const Icon = (icon && AGENT_ICONS[icon]) || (id && AGENT_ICONS[id]) || GeneralC;
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        width: size,
        height: size,
        fontSize: size,
        flexShrink: 0,
        ...style,
      }}
      aria-hidden
    >
      <Icon />
    </span>
  );
}
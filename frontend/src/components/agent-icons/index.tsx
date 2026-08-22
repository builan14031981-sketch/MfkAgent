import type { CSSProperties, ReactElement } from "react";
import type { AgentIconScheme } from "./base";
import { GeneralA, GeneralB, GeneralC } from "./general";
import { CoderA, CoderB, CoderC } from "./coder";
import { FrontendUiA, FrontendUiB, FrontendUiC } from "./frontend_ui";
import { GA, GB, GC } from "./g";
import { ProductA, ProductB, ProductC } from "./product";
import { SparkA, SparkB, SparkC } from "./spark";
import { PianaiA, PianaiB, PianaiC } from "./pianai";
import { WriterA, WriterB, WriterC } from "./writer";
import { CodeReviewA, CodeReviewB, CodeReviewC } from "./codeReviewer";
import { ResearcherA, ResearcherB, ResearcherC } from "./researcher";
import { FileAnalystA, FileAnalystB, FileAnalystC } from "./fileAnalyst";
import { BackendA, BackendB, BackendC } from "./backend";
import { AnalystA, AnalystB, AnalystC } from "./analyst";
import { MentorA, MentorB, MentorC } from "./mentor";
import { PersonalA, PersonalB, PersonalC } from "./personal";
import { ResearchA, ResearchB, ResearchC } from "./research";
import { GptA, GptB, GptC } from "./gpt";

type IconComponent = () => ReactElement;

/** 每个 Agent 的三套方案（A 极简几何 / B 功能隐喻 / C 意象抽象） */
export const AGENT_ICON_SCHEMES: Record<string, Record<AgentIconScheme, IconComponent>> = {
  general: { A: GeneralA, B: GeneralB, C: GeneralC },
  coder: { A: CoderA, B: CoderB, C: CoderC },
  frontend_ui: { A: FrontendUiA, B: FrontendUiB, C: FrontendUiC },
  g: { A: GA, B: GB, C: GC },
  product: { A: ProductA, B: ProductB, C: ProductC },
  spark: { A: SparkA, B: SparkB, C: SparkC },
  pianai: { A: PianaiA, B: PianaiB, C: PianaiC },
  writer: { A: WriterA, B: WriterB, C: WriterC },
  sub_code_reviewer: { A: CodeReviewA, B: CodeReviewB, C: CodeReviewC },
  sub_researcher: { A: ResearcherA, B: ResearcherB, C: ResearcherC },
  sub_file_analyst: { A: FileAnalystA, B: FileAnalystB, C: FileAnalystC },
  backend: { A: BackendA, B: BackendB, C: BackendC },
  analyst: { A: AnalystA, B: AnalystB, C: AnalystC },
  mentor: { A: MentorA, B: MentorB, C: MentorC },
  personal: { A: PersonalA, B: PersonalB, C: PersonalC },
  research: { A: ResearchA, B: ResearchB, C: ResearchC },
  gpt: { A: GptA, B: GptB, C: GptC },
};

/** 展示元数据（供测试台/下拉框使用） */
export const AGENT_META: Record<string, { name: string; desc: string; schemeNote: string }> = {
  general: {
    name: "AnGent",
    desc: "默认通用助手 · 星芒聚合",
    schemeNote: "A 同心圆+十字 · B 四角星 · C 双轨道环绕",
  },
  coder: {
    name: "开发者",
    desc: "软件开发 · 尖括号",
    schemeNote: "A 双括号 · B 括号+光标 · C 终端窗口",
  },
  frontend_ui: {
    name: "前端工程师",
    desc: "UI 实现 · 色环",
    schemeNote: "A 色环+笔杆 · B 画笔起笔 · C 分层画布",
  },
  g: {
    name: "G 审查官",
    desc: "治理审查 · 盾牌 · Governance",
    schemeNote: "A 盾形 · B 盾+对勾 · C 盾心字母 G",
  },
  product: {
    name: "产品策略师",
    desc: "产品方向 · 罗盘",
    schemeNote: "A 罗盘+针 · B 方向箭头 · C 目标瞄准",
  },
  spark: {
    name: "Spark",
    desc: "高能量伙伴 · 闪电 · 抽象搞怪",
    schemeNote: "A 歪斜闪电+星芒 · B 火花炸裂 · C 闪电+能量天线",
  },
  pianai: {
    name: "Pianai",
    desc: "偏爱伙伴 · 双心",
    schemeNote: "A 主实心+虚线陪心 · B 心+对话尾+星 · C 双心外倾（一实一虚）",
  },
  writer: {
    name: "笔神",
    desc: "写作表达 · 钢笔",
    schemeNote: "A 笔尖 · B 完整钢笔 · C 完整羽毛笔",
  },
  sub_code_reviewer: {
    name: "代码审查员",
    desc: "子代理 · 只读审查",
    schemeNote: "A 文档+对勾 · B 代码+对勾 · C 文档+聚焦镜",
  },
  sub_researcher: {
    name: "网络调研员",
    desc: "子代理 · 联网调研",
    schemeNote: "A 地球 · B 轨道 · C 网络节点",
  },
  sub_file_analyst: {
    name: "文件分析师",
    desc: "子代理 · 文件分析 · 1:1",
    schemeNote: "A 文档折角 · B 方形文件夹+对勾 · C 堆叠文档",
  },
  backend: {
    name: "后端 AI",
    desc: "服务器 · 后端工程",
    schemeNote: "A 双机架 · B 服务器+指示灯 · C 三线接口",
  },
  analyst: {
    name: "分析师",
    desc: "数据洞察 · 图表",
    schemeNote: "A 柱状图 · B 趋势折线 · C 数据节点",
  },
  mentor: {
    name: "理性导师",
    desc: "引导思考 · 大脑",
    schemeNote: "A 大脑 · B 四角星·引导 · C 时钟罗盘",
  },
  personal: {
    name: "个人助理",
    desc: "个性化服务 · 用户",
    schemeNote: "A 人形 · B 人形+星 · C 瞄准",
  },
  research: {
    name: "调研员",
    desc: "联网搜索 · 洞察",
    schemeNote: "A 放大镜 · B 放大镜+对勾 · C 放大镜+十字",
  },
  gpt: {
    name: "默认助手",
    desc: "通用对话 · 消息",
    schemeNote: "A 对话气泡+文字 · B 气泡+光标 · C 圆环气泡",
  },
};

export const AGENT_IDS = Object.keys(AGENT_ICON_SCHEMES);

interface AgentIconProps {
  id: string;
  scheme?: AgentIconScheme; // 默认 A（极简几何，最稳）
  size?: number; // 像素尺寸（也即 fontSize）
  className?: string;
  style?: CSSProperties;
}

/**
 * Agent 线条图标渲染器：按 agent_id + scheme 渲染。
 * 仅用于测试台的同源新图标；生产 AgentIcon 仍走 Lucide，集成时替换。
 */
export function AgentIcon({ id, scheme = "A", size = 16, className, style }: AgentIconProps) {
  const agent = AGENT_ICON_SCHEMES[id];
  const Icon = (agent && agent[scheme]) || GeneralA;
  return (
    <span
      className={className}
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
    >
      <Icon />
    </span>
  );
}
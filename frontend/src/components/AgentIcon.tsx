"use client";

import { Code2, Palette, Server, Sparkles, BarChart2, PenTool, Bot, MessageCircle, Shield, Compass, Brain, User, Zap } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { CSSProperties } from "react";

const AGENT_ICONS: Record<string, LucideIcon> = {
  coder: Code2,
  reviewer: Code2,
  frontend_ui: Palette,
  backend: Server,
  general: Sparkles,
  analyst: BarChart2,
  writer: PenTool,
  gpt: MessageCircle,
  g: Shield,
  product: Compass,
  mentor: Brain,
  personal: User,
  spark: Zap,
  // 后端 Agent.avatar 语义值（seed 归一化后的 icon 字段）也映射到同一套图标
  code: Code2,
  palette: Palette,
  server: Server,
  sparkles: Sparkles,
  search: BarChart2,
  pen: PenTool,
  shield: Shield,
  compass: Compass,
  brain: Brain,
  user: User,
  zap: Zap,
  heart: MessageCircle,
  target: BarChart2,
  bot: Bot,
};

interface AgentIconProps {
  id?: string;
  icon?: string;
  size?: number;
  strokeWidth?: number;
  style?: CSSProperties;
}

/**
 * Agent 专属 Lucide 线条图标：根据 agent.id 映射渲染。
 * 未知 id 回退到 Bot 图标，保证界面始终有图标。
 */
export function AgentIcon({ id, icon, size = 16, strokeWidth = 1.75, style }: AgentIconProps) {
  const Icon = (icon && AGENT_ICONS[icon]) || (id && AGENT_ICONS[id]) || Bot;
  return <Icon size={size} strokeWidth={strokeWidth} style={style} />;
}

import type { HeroTheme, ThemeCategory } from "./types";
import { CyberTerminalTheme } from "@/components/hero/themes/CyberTerminalTheme";
import { Bit8BootTheme } from "@/components/hero/themes/Bit8BootTheme";
import { AIAwakeningTheme } from "@/components/hero/themes/AIAwakeningTheme";
import { GitDeveloperTheme } from "@/components/hero/themes/GitDeveloperTheme";
import { RetroDosTheme } from "@/components/hero/themes/RetroDosTheme";
import { StaticTitle } from "@/components/hero/StaticTitle";
import { LinuxKernelTheme } from "@/components/hero/themes/LinuxKernelTheme";
import { AssemblyCodeTheme } from "@/components/hero/themes/AssemblyCodeTheme";
import { VscodeIdeTheme } from "@/components/hero/themes/VscodeIdeTheme";
import { GitCommitTheme } from "@/components/hero/themes/GitCommitTheme";
import { MatrixDataTheme } from "@/components/hero/themes/MatrixDataTheme";
import { CrtMonitorTheme } from "@/components/hero/themes/CrtMonitorTheme";
import { MechanicalTerminalTheme } from "@/components/hero/themes/MechanicalTerminalTheme";
import { OpenSourceTheme } from "@/components/hero/themes/OpenSourceTheme";
import { BlueprintEngineeringTheme } from "@/components/hero/themes/BlueprintEngineeringTheme";
import { NeuralNetworkTheme } from "@/components/hero/themes/NeuralNetworkTheme";
import { AgentInitTheme } from "@/components/hero/themes/AgentInitTheme";
import { QuantumCoreTheme } from "@/components/hero/themes/QuantumCoreTheme";

/**
 * Hero 主题分类（完整列表分组用，20+ 主题时的扩展基础）。
 * 界面上的分类名优先走 locales（home.hero.categories.{id}）。
 */
export const THEME_CATEGORIES: ThemeCategory[] = [
  { id: "classic", label: "Classic" },
  { id: "terminal", label: "Terminal" },
  { id: "retro", label: "Retro" },
  { id: "cinematic", label: "Cinematic" },
  { id: "developer", label: "Developer" },
];

/**
 * Hero 主题注册表：
 * 新主题只需在此追加一条记录即可被 ThemeManager 识别。
 */
export const HERO_THEMES: HeroTheme[] = [
  // ===== 原有主题 =====
  { id: "classic", name: "Classic", category: "classic", accent: "#0071e3", component: StaticTitle },
  { id: "cyber-terminal", name: "Cyber Terminal", category: "terminal", accent: "#00ff9c", component: CyberTerminalTheme },
  { id: "8bit-boot", name: "8-Bit Boot", category: "retro", accent: "#22c55e", component: Bit8BootTheme },
  { id: "ai-awakening", name: "AI Awakening", category: "cinematic", accent: "#8b5cf6", component: AIAwakeningTheme },
  { id: "git-developer", name: "Git Developer", category: "developer", accent: "#f97316", component: GitDeveloperTheme },
  { id: "retro-dos", name: "Retro DOS", category: "retro", accent: "#38bdf8", component: RetroDosTheme },

  // ===== A. 开发者文化 =====
  { id: "linux-kernel", name: "Linux Kernel", category: "developer", accent: "#a3e635", component: LinuxKernelTheme },
  { id: "assembly-code", name: "Assembly Code", category: "developer", accent: "#f87171", component: AssemblyCodeTheme },
  { id: "vscode-ide", name: "VS Code / IDE", category: "developer", accent: "#007acc", component: VscodeIdeTheme },
  { id: "git-commit", name: "Git Commit", category: "developer", accent: "#f97316", component: GitCommitTheme },
  { id: "open-source", name: "Open Source", category: "developer", accent: "#3b82f6", component: OpenSourceTheme },
  { id: "mechanical-terminal", name: "Mechanical Terminal", category: "terminal", accent: "#d4a574", component: MechanicalTerminalTheme },

  // ===== B. 计算机历史 / 复古 =====
  { id: "crt-monitor", name: "CRT Monitor", category: "retro", accent: "#facc15", component: CrtMonitorTheme },

  // ===== C. AI 未来感 =====
  { id: "matrix-data", name: "Matrix Data", category: "cinematic", accent: "#00ff41", component: MatrixDataTheme },
  { id: "neural-network", name: "Neural Network", category: "cinematic", accent: "#8b5cf6", component: NeuralNetworkTheme },
  { id: "agent-init", name: "Agent Init", category: "cinematic", accent: "#06b6d4", component: AgentInitTheme },
  { id: "quantum-core", name: "Quantum Core", category: "cinematic", accent: "#00ffff", component: QuantumCoreTheme },

  // ===== D. 品牌视觉 / 工程 =====
  { id: "blueprint-engineering", name: "Blueprint Engineering", category: "developer", accent: "#60a5fa", component: BlueprintEngineeringTheme },
];

export function getHeroTheme(id: string | null | undefined): HeroTheme | undefined {
  if (!id) return undefined;
  return HERO_THEMES.find((t) => t.id === id);
}

export function pickRandomHeroTheme(pool?: HeroTheme[]): HeroTheme {
  const candidates = pool && pool.length > 0 ? pool : HERO_THEMES;
  const index = Math.floor(Math.random() * candidates.length);
  return candidates[index];
}

export function nextHeroTheme(current: HeroTheme | undefined): HeroTheme {
  if (!current) return HERO_THEMES[0];
  const index = HERO_THEMES.findIndex((t) => t.id === current.id);
  return HERO_THEMES[(index + 1) % HERO_THEMES.length];
}

import type { HeroTheme, ThemeCategory } from "./types";
import { CyberTerminalTheme } from "@/components/hero/themes/CyberTerminalTheme";
import { AIAwakeningTheme } from "@/components/hero/themes/AIAwakeningTheme";
import { GitDeveloperTheme } from "@/components/hero/themes/GitDeveloperTheme";
import { RetroDosTheme } from "@/components/hero/themes/RetroDosTheme";
import { AssemblyCodeTheme } from "@/components/hero/themes/AssemblyCodeTheme";
import { VscodeIdeTheme } from "@/components/hero/themes/VscodeIdeTheme";
import { OpenSourceTheme } from "@/components/hero/themes/OpenSourceTheme";
import { NeuralNetworkTheme } from "@/components/hero/themes/NeuralNetworkTheme";
import { QuantumCoreTheme } from "@/components/hero/themes/QuantumCoreTheme";
import { AgentInitTheme } from "@/components/hero/themes/AgentInitTheme";
import { BlueprintEngineeringTheme } from "@/components/hero/themes/BlueprintEngineeringTheme";
import { AppleMinimalTheme } from "@/components/hero/themes/AppleMinimalTheme";
import { FutureOsTheme } from "@/components/hero/themes/FutureOsTheme";
import { PixelRpgTheme } from "@/components/hero/themes/PixelRpgTheme";
import { NeoBrutalismTheme } from "@/components/hero/themes/NeoBrutalismTheme";
import { CyberpunkNeonTheme } from "@/components/hero/themes/CyberpunkNeonTheme";
import { RetroTerminalTheme } from "@/components/hero/themes/RetroTerminalTheme";
import { VaporwaveTheme } from "@/components/hero/themes/VaporwaveTheme";
import { GlitchArtTheme } from "@/components/hero/themes/GlitchArtTheme";
import { ClaymorphismTheme } from "@/components/hero/themes/ClaymorphismTheme";
import { BauhausTheme } from "@/components/hero/themes/BauhausTheme";
import { WabiSabiTheme } from "@/components/hero/themes/WabiSabiTheme";
import { MetroTheme } from "@/components/hero/themes/MetroTheme";
import { SteampunkTheme } from "@/components/hero/themes/SteampunkTheme";
import { NeumorphismTheme } from "@/components/hero/themes/NeumorphismTheme";
import { EditorialTheme } from "@/components/hero/themes/EditorialTheme";
import { RetroConsoleTheme } from "@/components/hero/themes/RetroConsoleTheme";
import { Win9xDesktopTheme } from "@/components/hero/themes/Win9xDesktopTheme";
import { GameBoyTheme } from "@/components/hero/themes/GameBoyTheme";

/**
 * Hero 主题分类（完整列表分组用，20+ 主题时的扩展基础）。
 * 界面上的分类名优先走 locales（home.hero.categories.{id}）。
 */
export const THEME_CATEGORIES: ThemeCategory[] = [
  { id: "classic", label: "Classic" },
  { id: "terminal", label: "Terminal" },
  { id: "system", label: "System" },
  { id: "retro", label: "Retro" },
  { id: "developer", label: "Developer" },
  { id: "cinematic", label: "Cinematic" },
  { id: "ai", label: "AI Future" },
  { id: "design", label: "Design" },
];

/**
 * Hero 主题注册表：
 * 新主题只需在此追加一条记录即可被 ThemeManager 识别。
 */
export const HERO_THEMES: HeroTheme[] = [
  // ===== Terminal 终端 =====
  { id: "cyber-terminal", name: "Cyber Terminal", category: "terminal", accent: "#00ff9c", component: CyberTerminalTheme },
  { id: "retro-terminal", name: "Retro Terminal", category: "terminal", accent: "#00FF00", component: RetroTerminalTheme },

  // ===== Retro 复古 =====
  { id: "retro-dos", name: "Retro DOS", category: "retro", accent: "#38bdf8", component: RetroDosTheme },
  { id: "pixel-rpg", name: "Pixel RPG", category: "retro", accent: "#2ECC71", component: PixelRpgTheme },
  { id: "retro-console", name: "Retro Console", category: "retro", accent: "#E60012", component: RetroConsoleTheme },
  { id: "game-boy", name: "Game Boy", category: "retro", accent: "#8BAC0F", component: GameBoyTheme },
  { id: "steampunk", name: "Steampunk", category: "retro", accent: "#CD7F32", component: SteampunkTheme },

  // ===== Developer 开发者 =====
  { id: "git-developer", name: "Git Developer", category: "developer", accent: "#f97316", component: GitDeveloperTheme },
  { id: "assembly-code", name: "Assembly Code", category: "developer", accent: "#f87171", component: AssemblyCodeTheme },
  { id: "vscode-ide", name: "VS Code IDE", category: "developer", accent: "#3b82f6", component: VscodeIdeTheme },
  { id: "open-source", name: "Open Source", category: "developer", accent: "#6366f1", component: OpenSourceTheme },

  // ===== Cinematic 影院 / 视觉氛围 =====
  { id: "ai-awakening", name: "AI Awakening", category: "cinematic", accent: "#8b5cf6", component: AIAwakeningTheme },
  { id: "cyberpunk-neon", name: "Cyberpunk Neon", category: "cinematic", accent: "#FF00FF", component: CyberpunkNeonTheme },
  { id: "vaporwave", name: "Vaporwave", category: "cinematic", accent: "#B57EDC", component: VaporwaveTheme },
  { id: "glitch-art", name: "Glitch Art", category: "cinematic", accent: "#00F0FF", component: GlitchArtTheme },

  // ===== AI 未来感 =====
  { id: "neural-network", name: "Neural Network", category: "ai", accent: "#a78bfa", component: NeuralNetworkTheme },
  { id: "quantum-core", name: "Quantum Core", category: "ai", accent: "#c084fc", component: QuantumCoreTheme },
  { id: "agent-init", name: "Agent Init", category: "ai", accent: "#34d399", component: AgentInitTheme },

  // ===== Design 设计 / 品牌视觉 =====
  { id: "blueprint-engineering", name: "Blueprint Engineering", category: "design", accent: "#60a5fa", component: BlueprintEngineeringTheme },
  { id: "apple-minimal", name: "Apple Minimal", category: "design", accent: "#e5e5e5", component: AppleMinimalTheme },
  { id: "future-os", name: "Future OS", category: "design", accent: "#818cf8", component: FutureOsTheme },
  { id: "neo-brutalism", name: "Neo-Brutalism", category: "design", accent: "#FFE83C", component: NeoBrutalismTheme },
  { id: "claymorphism", name: "Claymorphism", category: "design", accent: "#B3E5FC", component: ClaymorphismTheme },
  { id: "bauhaus", name: "Bauhaus", category: "design", accent: "#E3000F", component: BauhausTheme },
  { id: "wabi-sabi", name: "Wabi-Sabi", category: "design", accent: "#6B7B3A", component: WabiSabiTheme },
  { id: "neumorphism", name: "Neumorphism", category: "design", accent: "#E0E5EC", component: NeumorphismTheme },
  { id: "editorial", name: "Editorial", category: "design", accent: "#C62828", component: EditorialTheme },

  // ===== System 系统 UI =====
  { id: "win9x-desktop", name: "Win9x Desktop", category: "system", accent: "#C0C0C0", component: Win9xDesktopTheme },
  { id: "metro", name: "Metro", category: "system", accent: "#00A4EF", component: MetroTheme },
];

export function getHeroTheme(id: string | null | undefined): HeroTheme | undefined {
  if (!id) return undefined;
  return HERO_THEMES.find((t) => t.id === id);
}

/**
 * 已接入「可交互快捷指令」的主题 id 集合：
 * 这些主题内部已把 home.quickStarts 渲染为主题化按钮/菜单，首页无需再展示独立快捷指令行。
 */
export const INTERACTIVE_HERO_THEME_IDS: ReadonlySet<string> = new Set([
  "retro-console",
  "win9x-desktop",
  "game-boy",
]);

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

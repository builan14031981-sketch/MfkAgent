import type { LucideIcon } from "lucide-react";
import {
  FileCode,
  FileText,
  Search,
  Terminal,
  GitBranch,
  Bookmark,
  Globe,
  Clock,
  Braces,
} from "lucide-react";

export interface ToolMetaEntry {
  icon: LucideIcon;
  color: string;
  title: (args: Record<string, unknown>, tool: string) => string;
}

function argStr(args: Record<string, unknown>, key: string): string {
  const v = args[key];
  if (typeof v === "string") return v;
  if (typeof v === "number") return String(v);
  return "";
}

const COMMAND_HINT = "var(--color-warning)";

export const TOOL_META: Record<string, ToolMetaEntry> = {
  write_file: {
    icon: FileCode,
    color: "var(--color-success)",
    title: (a) => argStr(a, "relative_path") || argStr(a, "path") || "写入文件",
  },
  read_file: {
    icon: FileText,
    color: "var(--color-info)",
    title: (a) => argStr(a, "relative_path") || argStr(a, "path") || "读取文件",
  },
  list_files: {
    icon: FileText,
    color: "var(--color-info)",
    title: () => "列出目录",
  },
  list_directory: {
    icon: FileText,
    color: "var(--color-info)",
    title: (a) => argStr(a, "path") || "列出目录",
  },
  search_files: {
    icon: Search,
    color: "var(--color-info)",
    title: (a) => `搜索 "${argStr(a, "query")}"`,
  },
  run_command: {
    icon: Terminal,
    color: COMMAND_HINT,
    title: (a) => (argStr(a, "command") ? `$ ${argStr(a, "command")}` : "执行命令"),
  },
  web_search: {
    icon: Globe,
    color: "var(--color-info)",
    title: (a) => `搜索 "${argStr(a, "query")}"`,
  },
  fetch_url: {
    icon: Globe,
    color: "var(--color-info)",
    title: (a) => argStr(a, "url") || "获取网页",
  },
  add_memory: {
    icon: Bookmark,
    color: COMMAND_HINT,
    title: (a) => {
      const content = argStr(a, "content");
      return content ? `记住: ${content.slice(0, 40)}` : "添加记忆";
    },
  },
  get_datetime: {
    icon: Clock,
    color: "var(--color-info)",
    title: () => "获取当前时间",
  },
  format_json: {
    icon: Braces,
    color: "var(--color-info)",
    title: () => "格式化 JSON",
  },
};

const DEFAULT_TOOL_META: ToolMetaEntry = {
  icon: FileText,
  color: "var(--color-info)",
  title: (_a, tool) => tool,
};

const GIT_META: ToolMetaEntry = {
  icon: GitBranch,
  color: "var(--color-info)",
  title: (a) => {
    const sub = Object.keys(a).length > 0 ? Object.entries(a).map(([k, v]) => `${k}=${String(v)}`).join(", ") : "";
    return sub ? `git ${sub}` : "git 操作";
  },
};

export function resolveToolMeta(
  tool: string,
  args?: Record<string, unknown>
): { icon: LucideIcon; color: string; title: string } {
  const cleanTool = tool || "";
  const meta =
    cleanTool.startsWith("git_")
      ? GIT_META
      : TOOL_META[cleanTool] ?? DEFAULT_TOOL_META;
  let title: string;
  try {
    title = meta.title(args ?? {}, cleanTool);
  } catch {
    title = cleanTool;
  }
  return { icon: meta.icon, color: meta.color, title };
}

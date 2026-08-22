import { Svg } from "./base";

/** research · 调研员 — 形象：放大镜 / 搜索 / 洞察 */
export function ResearchA() {
  return (
    <Svg title="调研员 A">
      <circle cx="10.5" cy="10.5" r="6" />
      <path d="M15 15l5 5" />
    </Svg>
  );
}

export function ResearchB() {
  return (
    <Svg title="调研员 B">
      <circle cx="10.5" cy="10.5" r="6" />
      <path d="M15 15l5 5" />
      <path d="M8 10.5l2 2 3-3" />
    </Svg>
  );
}

export function ResearchC() {
  return (
    <Svg title="调研员 C">
      <circle cx="10.5" cy="10.5" r="6" />
      <path d="M15 15l5 5" />
      <path d="M10.5 7v7M7 10.5h7" />
    </Svg>
  );
}
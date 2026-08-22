import { Svg } from "./base";

/** sub_researcher · 网络调研员 — 形象：地球 / 轨道 / 网络节点 */
export function ResearcherA() {
  return (
    <Svg title="网络调研员 A">
      <circle cx="12" cy="12" r="8" />
      <ellipse cx="12" cy="12" rx="3.5" ry="8" />
      <path d="M4 12h16" />
      <path d="M5.5 8a6.5 5 0 0 0 13 0" />
    </Svg>
  );
}

export function ResearcherB() {
  return (
    <Svg title="网络调研员 B">
      <circle cx="12" cy="12" r="6.5" />
      <ellipse cx="12" cy="12" rx="9.5" ry="3.5" transform="rotate(-20 12 12)" />
      <circle cx="18.5" cy="9" r="1.3" />
    </Svg>
  );
}

export function ResearcherC() {
  return (
    <Svg title="网络调研员 C">
      <circle cx="6" cy="7" r="2" />
      <circle cx="18" cy="7" r="2" />
      <circle cx="12" cy="17" r="2" />
      <path d="M8 7h8M8 8l3 7M16 8l-3 7" />
    </Svg>
  );
}
import { Svg } from "./base";

/** analyst · 分析师 — 形象：柱状图 / 趋势 / 数据洞察 */
export function AnalystA() {
  return (
    <Svg title="分析师 A">
      <path d="M4 20h16" />
      <path d="M6.5 20v-6M12 20v-10M17.5 20V6" />
    </Svg>
  );
}

export function AnalystB() {
  return (
    <Svg title="分析师 B">
      <path d="M4 20h16" />
      <path d="M6 16l4-4 3 3 5-6" />
      <path d="M15 9h3v3" />
    </Svg>
  );
}

export function AnalystC() {
  return (
    <Svg title="分析师 C">
      <circle cx="5" cy="17" r="2" />
      <circle cx="12" cy="9" r="2" />
      <circle cx="19" cy="15" r="2" />
      <path d="M6.5 15.5L10.5 10.5M13.5 10.5l3.5 3" />
    </Svg>
  );
}
import { Svg } from "./base";

/** g · G 审查官 — 形象：盾牌 / 校验 / 把关 */
export function GA() {
  return (
    <Svg title="G 审查官 A">
      <path d="M12 3l8 3v5c0 4.5-3.5 8-8 10-4.5-2-8-5.5-8-10V6z" />
    </Svg>
  );
}

export function GB() {
  return (
    <Svg title="G 审查官 B">
      <path d="M12 3l8 3v5c0 4.5-3.5 8-8 10-4.5-2-8-5.5-8-10V6z" />
      <path d="M9 12.5l2.5 2.5 4-4.5" />
    </Svg>
  );
}

export function GC() {
  return (
    <Svg title="G 审查官 C">
      {/* 盾牌 · 治理审查 */}
      <path d="M12 3l8 3v5c0 4.5-3.5 8-8 10-4.5-2-8-5.5-8-10V6z" />
      {/* 盾心嵌入字母 G（Governance 首字母） */}
      <path d="M14.5 11.5h-3a2.3 2.3 0 1 0 0 4.6h3v-2h-3" />
    </Svg>
  );
}
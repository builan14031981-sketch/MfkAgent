import { Svg } from "./base";

/** sub_code_reviewer · 代码审查员 — 形象：文档审查 / 代码 + 对勾 / 聚焦 */
export function CodeReviewA() {
  return (
    <Svg title="代码审查员 A">
      <path d="M7 3h7l4 4v14H7z" />
      <path d="M14 3v4h4" />
      <path d="M9.5 13.5l2 2 3.5-4" />
    </Svg>
  );
}

export function CodeReviewB() {
  return (
    <Svg title="代码审查员 B">
      <path d="M8 7L4.5 12 8 17" />
      <path d="M16 7l3.5 5L16 17" />
      <path d="M10 14l2 2 3.5-3.5" />
    </Svg>
  );
}

export function CodeReviewC() {
  return (
    <Svg title="代码审查员 C">
      <path d="M8 6h6l3 3v9H8z" />
      <path d="M14 6v3h3" />
      <circle cx="14.5" cy="12.5" r="3.5" />
      <path d="M17 15l2.5 2.5" />
    </Svg>
  );
}
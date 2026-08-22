import { Svg } from "./base";

/** AnGent · 通用助手 — 方案 A
 *  圆润的 "An" 字标：A 整体左移 1.5u 与 n 留出 2.6u 间距，圆顶 Q 弧，宽拱 n
 *  参考现代品牌字标设计（如 Stripe, Figma 风格） */
export function GeneralA() {
  return (
    <Svg title="AnGent">
      {/* 大写 A：圆顶 + 左移，与 n 留可见间隙 */}
      <path d="M4 19 L7 8 Q7.7 5.5 8.4 8 L11.4 19" />
      {/* A 横 */}
      <path d="M6 14.5 H9.4" />
      {/* 小写 n：保持原宽（不缩小），T 连续圆拱 */}
      <path d="M14 19V14Q14 10 17 10T20 14V19" />
    </Svg>
  );
}

export function GeneralB() {
  return (
    <Svg title="AnGent B">
      <path d="M12 3l1.5 7.5L21 12l-7.5 1.5L12 21l-1.5-7.5L3 12l7.5-1.5z" />
    </Svg>
  );
}

export function GeneralC() {
  return (
    <Svg title="AnGent C">
      <circle cx="12" cy="12" r="1.6" />
      <ellipse cx="12" cy="12" rx="9" ry="4" transform="rotate(45 12 12)" />
      <ellipse cx="12" cy="12" rx="9" ry="4" transform="rotate(-45 12 12)" />
    </Svg>
  );
}
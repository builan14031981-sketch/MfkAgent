import { Svg } from "./base";

/** product · 产品策略师 — 形象：罗盘 / 方向针 / 目标 */
export function ProductA() {
  return (
    <Svg title="产品策略师 A">
      <circle cx="12" cy="12" r="8" />
      <path d="M12 7.5l2.5 4.5-2.5 4.5-2.5-4.5z" />
    </Svg>
  );
}

export function ProductB() {
  return (
    <Svg title="产品策略师 B">
      <circle cx="12" cy="12" r="8" />
      <path d="M12 5v9" />
      <path d="M8.5 10.5l3.5 4 3.5-4" />
    </Svg>
  );
}

export function ProductC() {
  return (
    <Svg title="产品策略师 C">
      <circle cx="12" cy="12" r="8" />
      <circle cx="12" cy="12" r="3.5" />
      <path d="M12 2v3M12 19v3M2 12h3M19 12h3" />
    </Svg>
  );
}
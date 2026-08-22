import { Svg } from "./base";

/** personal · 个人助理 — 形象：人形 / 用户 / 个性化 */
export function PersonalA() {
  return (
    <Svg title="个人助理 A">
      <circle cx="12" cy="8" r="3.5" />
      <path d="M5 20c0-3.5 3-5.5 7-5.5s7 2 7 5.5" />
    </Svg>
  );
}

export function PersonalB() {
  return (
    <Svg title="个人助理 B">
      <circle cx="12" cy="8" r="3.5" />
      <path d="M5 20c0-3.5 3-5.5 7-5.5s7 2 7 5.5" />
      <path d="M17 5l3 3M20 5l-3 3" />
    </Svg>
  );
}

export function PersonalC() {
  return (
    <Svg title="个人助理 C">
      <path d="M9 4h6M12 4v6M4 12h16M12 10v10" />
      <circle cx="12" cy="15" r="3" />
    </Svg>
  );
}
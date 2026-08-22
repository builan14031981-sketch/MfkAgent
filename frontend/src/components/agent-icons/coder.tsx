import { Svg } from "./base";

/** coder · 开发者 — 形象：尖括号 `</>` 与光标 */
export function CoderA() {
  return (
    <Svg title="开发者 A">
      <path d="M8 7L3.5 12 8 17" />
      <path d="M16 7l4.5 5L16 17" />
    </Svg>
  );
}

export function CoderB() {
  return (
    <Svg title="开发者 B">
      <path d="M9 7L4.5 12 9 17" />
      <path d="M15 7l4.5 5L15 17" />
      <path d="M12 5.5v13" />
    </Svg>
  );
}

export function CoderC() {
  return (
    <Svg title="开发者 C">
      <rect x="4" y="5" width="16" height="14" rx="2" />
      <path d="M9 8.5L6.5 12 9 15.5" />
    </Svg>
  );
}
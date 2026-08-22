import { Svg } from "./base";

/** mentor · 理性导师 — 形象：大脑 / 引导 / 灯塔 */
export function MentorA() {
  return (
    <Svg title="理性导师 A">
      <path d="M12 4a4 4 0 0 0-4 4c0 1.5-.5 2-1.5 2.5A3.5 3.5 0 0 0 8 17h8a3.5 3.5 0 0 0 1.5-6.5C16.5 10 16 9.5 16 8a4 4 0 0 0-4-4z" />
      <path d="M12 4v14M9 21h6" />
    </Svg>
  );
}

export function MentorB() {
  return (
    <Svg title="理性导师 B">
      <path d="M12 3l2 6 6 2-6 2-2 6-2-6-6-2 6-2z" />
      <path d="M12 3v18" />
    </Svg>
  );
}

export function MentorC() {
  return (
    <Svg title="理性导师 C">
      <circle cx="12" cy="12" r="8" />
      <path d="M12 8v4l3 2" />
    </Svg>
  );
}
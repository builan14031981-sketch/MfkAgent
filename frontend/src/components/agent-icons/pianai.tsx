import { Svg } from "./base";

/** pianai · 偏爱 — 形象：主实心 + 右上方更小的虚线陪心（偏爱=双心） */
export function PianaiA() {
  return (
    <Svg title="Pianai A">
      {/* 主爱心（实线）：居中，偏左下方一点，视觉重心稳 */}
      <path d="M12.5 19C7.5 15 4.8 11.8 4.8 8.8A4.2 4.2 0 0 1 12.5 6.9a4.2 4.2 0 0 1 7.7 1.9c0 3-2.7 6.2-7.7 10.2z" />
      {/* 陪心（虚线）：右上方小小的，表达relation/偏爱 */}
      <path d="M18.2 6.4c-1.2-1-2.4-.4-2.4.9 0 1 1.2 1.9 2.4 2.9 1.2-1 2.4-1.9 2.4-2.9 0-1.3-1.2-1.9-2.4-.9z" strokeDasharray="1.6 1.2" />
    </Svg>
  );
}

export function PianaiB() {
  return (
    <Svg title="Pianai B">
      {/* 心形 + 对话尾 + 右上小星 */}
      <path d="M12 18.5C6.5 14 3.5 10.5 3.5 7A4.5 4.5 0 0 1 12 5.5a4.5 4.5 0 0 1 8.5 1.5c0 3.5-3 7-8.5 11.5z" />
      <path d="M13 18l3 3-2.5 0" />
      <path d="M17.5 6.5l.6.6M17.5 5.9v.6M17.5 6.5l-.6.6" />
    </Svg>
  );
}

export function PianaiC() {
  return (
    <Svg title="Pianai C">
      {/* 双心外倾：左心（实线 · 被选中）逆时针 -12°，右心（虚线 · 未选中）顺时针 +12° */}
      <g transform="rotate(-12 7 12)">
        <path d="M7 16C4.5 13 3 11 3 9.5A2 2 0 0 1 7 8A2 2 0 0 1 11 9.5C11 11 9.5 13 7 16z" />
      </g>
      <g transform="rotate(12 17 12)">
        <path d="M17 16C14.5 13 13 11 13 9.5A2 2 0 0 1 17 8A2 2 0 0 1 21 9.5C21 11 19.5 13 17 16z" strokeDasharray="2 1.5" />
      </g>
    </Svg>
  );
}
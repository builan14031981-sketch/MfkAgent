import { Svg } from "./base";

/** writer · 笔神 — 形象：钢笔尖 / 笔触 / 羽毛 */
export function WriterA() {
  return (
    <Svg title="笔神 A">
      <path d="M7 20l3-15L12 4l2 1 3 15-5-3z" />
      <path d="M12 4v9" />
    </Svg>
  );
}

export function WriterB() {
  return (
    <Svg title="笔神 B">
      {/* 完整钢笔：斜笔身 + 笔尖 + 墨迹 */}
      <path d="M5 21l3-1L18.5 9.5l-2-2L6.5 18.5z" />
      <path d="M14.5 9.5l3 3" />
      <path d="M4.5 8q3.5-1.5 6 .5" />
    </Svg>
  );
}

export function WriterC() {
  return (
    <Svg title="笔神 C">
      {/* 完整羽毛笔：羽杆 + 羽枝 + 笔尖 */}
      <path d="M6 20C9 15 13 9 18.5 4.5l1 1L13 20" />
      <path d="M7 16.5c3 0 5-1.5 6-4M9 12.5c2.5 0 4-1 5-3M11 8.5c1.5 0 2.5-.5 3-1.5" />
      <path d="M18.5 4.5l1 1-2.5 3" />
    </Svg>
  );
}
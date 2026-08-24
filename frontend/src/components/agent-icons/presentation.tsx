import { Svg } from "./base";

/** defense_ppt_expert · 答辩PPT专家 — 形象：投影演示屏 + 要点图表 */
export function PresentationA() {
  return (
    <Svg title="答辩PPT专家">
      {/* 演示屏画框 */}
      <rect x="3" y="3" width="18" height="12" rx="1.5" />
      {/* 支架底座 */}
      <path d="M12 15v6" />
      <path d="M8 21h8" />
      {/* 演示内容：标题线与重点条 */}
      <path d="M7 7h10" />
      <path d="M7 10h5" />
      <circle cx="15.5" cy="10.5" r="1" fill="currentColor" />
    </Svg>
  );
}

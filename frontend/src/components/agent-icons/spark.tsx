import { Svg } from "./base";

/** spark · Spark — 形象：闪电 / 火花 / 能量脉冲 */
export function SparkA() {
  return (
    <Svg title="Spark A">
      {/* 搞怪：歪斜厚闪电 + 右上漫画星芒 + 左下漂浮小点 */}
      <path d="M13.5 2l-8 11h5l-1 9 8-12h-5z" />
      <path d="M19 3.5l.9.9M19 2.6v.9M19 3.5l-.9.9" />
      <circle cx="3.5" cy="6" r="1" />
    </Svg>
  );
}

export function SparkB() {
  return (
    <Svg title="Spark B">
      <path d="M12 3l1.5 7.5L21 12l-7.5 1.5L12 21l-1.5-7.5L3 12l7.5-1.5z" />
      <path d="M17 5l2-2M19 7l2-2" />
    </Svg>
  );
}

export function SparkC() {
  return (
    <Svg title="Spark C">
      {/* 搞怪：胖闪电 + 头顶一对能量天线卷须 */}
      <path d="M13 2.5L6 13h5l-1 8.5L17 11h-5z" />
      <path d="M18.5 3.5c0 1.6-1 2.4-2.3 2.8M18.5 3.5c0-1.6 1-2.4 2.3-2.8" />
    </Svg>
  );
}
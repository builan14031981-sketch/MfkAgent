import { Svg } from "./base";

/** sub_file_analyst · 文件分析师 — 形象：文档折角 / 目录树 / 堆叠文件 */
export function FileAnalystA() {
  return (
    <Svg title="文件分析师 A">
      <path d="M7 3h7l4 4v14H7z" />
      <path d="M14 3v4h4" />
    </Svg>
  );
}

export function FileAnalystB() {
  return (
    <Svg title="文件分析师 B">
      {/* 1:1 方形文件夹 + 分析对勾 */}
      <path d="M3.5 7a2 2 0 0 1 2-2h4l2 2h7a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2z" />
      <path d="M10 13l2 2 3.5-3.5" />
    </Svg>
  );
}

export function FileAnalystC() {
  return (
    <Svg title="文件分析师 C">
      <path d="M9 5h5l3 3v11H9z" />
      <path d="M14 5v3h3" />
      <path d="M6 8h5l3 3v8H6z" />
      <path d="M11 8v3h3" />
    </Svg>
  );
}
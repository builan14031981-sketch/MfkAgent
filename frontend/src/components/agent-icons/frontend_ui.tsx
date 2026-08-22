import { Svg } from "./base";

/** frontend_ui · 前端工程师 — 形象：色环 / 调色盘 / 分层画布 */
export function FrontendUiA() {
  return (
    <Svg title="前端工程师 A">
      <circle cx="12" cy="12" r="8" />
      <circle cx="12" cy="12" r="3.5" />
      <path d="M16 16l4 4" />
    </Svg>
  );
}

export function FrontendUiB() {
  return (
    <Svg title="前端工程师 B">
      <path d="M4 20l10-10" />
      <path d="M14 10l3 3-2 2-3-3" />
      <path d="M3 9q3-2 6 0t6 0" />
    </Svg>
  );
}

export function FrontendUiC() {
  return (
    <Svg title="前端工程师 C">
      <rect x="4" y="4" width="16" height="5" rx="1.5" />
      <rect x="4" y="11" width="16" height="5" rx="1.5" />
      <rect x="6" y="16" width="12" height="4" rx="1.5" />
    </Svg>
  );
}
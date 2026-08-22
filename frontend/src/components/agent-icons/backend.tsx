import { Svg } from "./base";

/** backend · 后端 AI — 形象：服务器 / 机架 / 机关机械 */
export function BackendA() {
  return (
    <Svg title="后端 AI A">
      <rect x="4" y="4" width="16" height="7" rx="1.5" />
      <rect x="4" y="13" width="16" height="7" rx="1.5" />
      <circle cx="7.5" cy="7.5" r="0.8" />
      <circle cx="7.5" cy="16.5" r="0.8" />
    </Svg>
  );
}

export function BackendB() {
  return (
    <Svg title="后端 AI B">
      <rect x="4" y="3" width="16" height="18" rx="2" />
      <path d="M8 7h8M8 11h5" />
      <circle cx="7.5" cy="16.5" r="1" />
      <circle cx="12" cy="16.5" r="1" />
      <circle cx="16.5" cy="16.5" r="1" />
    </Svg>
  );
}

export function BackendC() {
  return (
    <Svg title="后端 AI C">
      <path d="M4 6h16M4 12h16M4 18h16" />
      <circle cx="8" cy="6" r="1" />
      <circle cx="8" cy="12" r="1" />
      <circle cx="8" cy="18" r="1" />
    </Svg>
  );
}
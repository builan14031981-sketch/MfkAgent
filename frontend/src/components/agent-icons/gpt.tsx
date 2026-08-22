import { Svg } from "./base";

/** gpt · 默认助手 — 形象：对话气泡 / 消息 / 通用问答 */
export function GptA() {
  return (
    <Svg title="默认助手 A">
      <path d="M4 6h16v10H9l-5 4z" />
      <path d="M8 10h8M8 12.5h5" />
    </Svg>
  );
}

export function GptB() {
  return (
    <Svg title="默认助手 B">
      <path d="M4 6h16v10H9l-5 4z" />
      <path d="M12 8v3M12 13.5v-.5" />
    </Svg>
  );
}

export function GptC() {
  return (
    <Svg title="默认助手 C">
      <circle cx="12" cy="12" r="8" />
      <path d="M8 10h8M8 13h5" />
    </Svg>
  );
}
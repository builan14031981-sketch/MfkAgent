import re

def main():
    filepath = "frontend/src/hooks/useChatStream.ts"
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # The goal is to partition actual streaming text to the correct agent.
    # Currently useChatStream just appends all text to the last "text" segment in timeline,
    # or creates a new "text" segment if the last wasn't text.
    # We should add logic where, if the last event is a roundtable speaker change, we create a new text segment
    # tied to that speaker, and give it an agent_id.

    # 查找 `case "text":` 的逻辑，目前是:
    #             store.updateSession(targetChatId, (prev) => {
    #               const last = prev.timeline[prev.timeline.length - 1];
    #               if (last && last.type === "text") {
    #                 const next = prev.timeline.slice();
    #                 next[next.length - 1] = { ...last, content: last.content + chunk };
    #                 return { timeline: next };
    #               }
    #               return { timeline: [...prev.timeline, { id: `text-${Date.now()}-${Math.random()}`, type: "text" as const, content: chunk }] };
    #             });

    # 我们需要在 text 块里记录 agent_id, 并在 MessageList 里让每一个 agent 显示气泡
    # 首先，在 useChatStream.ts 中添加对 current_speaker_id 的记录。

    # 我们可以通过 `roundtable_speaker_start` 获取到当前的 speaker。
    # 把它存到 useRef 里。

    pattern = re.compile(
        r'(refs\.firstText = true;\n\s*if \(refs\.agentStateTimer\) \{\n\s*clearTimeout\(refs\.agentStateTimer\);\n\s*refs\.agentStateTimer = null;\n\s*\})',
        re.DOTALL
    )
    # 我们加一个 refs.currentSpeaker = null
    replacement = r'\1\n      refs.currentSpeaker = null;'
    content = pattern.sub(replacement, content)

    # 我们要在 resetStreaming 里也加 `refs.currentSpeaker = null;`
    # 不好改，我们不如不放在 refs，而是利用 store 存当前 speaker，或者直接从 timeline 里找最近的一个 speaker

    # TextEvent 需要加 agent_id 字段
    # 这可以在 timeline 寻找最后一个 `roundtable_speaker_start` 找到 agent_id。
    pass

if __name__ == "__main__":
    main()

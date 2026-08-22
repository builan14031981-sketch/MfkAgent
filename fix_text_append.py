import re

def main():
    filepath = "frontend/src/hooks/useChatStream.ts"
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    pattern = re.compile(
        r'(store\.updateSession\(targetChatId, \(prev\) => \{\n\s*const last = prev\.timeline\[prev\.timeline\.length - 1\];\n\s*if \(last && last\.type === "text"\) \{\n\s*const next = prev\.timeline\.slice\(\);\n\s*next\[next\.length - 1\] = \{ \.\.\.last, content: last\.content \+ chunk \};\n\s*return \{ timeline: next \};\n\s*\}\n\s*return \{ timeline: \[\.\.\.prev\.timeline, \{ id: `text-\$\{Date\.now\(\)\}-\$\{Math\.random\(\)\}`, type: "text" as const, content: chunk \}\] \};\n\s*\}\);)',
        re.DOTALL
    )

    replacement = r'''store.updateSession(targetChatId, (prev) => {
              // 寻找最新的 speaker
              let currentSpeakerId: string | undefined;
              let currentSpeakerName: string | undefined;
              for (let i = prev.timeline.length - 1; i >= 0; i--) {
                const s = prev.timeline[i];
                if (s.type === "roundtable_speaker_start") {
                  currentSpeakerId = s.agent_id;
                  currentSpeakerName = s.agent_name;
                  break;
                }
              }

              const last = prev.timeline[prev.timeline.length - 1];
              if (last && last.type === "text" && last.agent_id === currentSpeakerId) {
                const next = prev.timeline.slice();
                next[next.length - 1] = { ...last, content: last.content + chunk };
                return { timeline: next };
              }
              return {
                timeline: [...prev.timeline, {
                  id: `text-${Date.now()}-${Math.random()}`,
                  type: "text" as const,
                  content: chunk,
                  agent_id: currentSpeakerId,
                  agent_name: currentSpeakerName
                }]
              };
            });'''

    new_content = pattern.sub(replacement, content)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(new_content)
    print("Fixed text appending logic in useChatStream.ts")

if __name__ == "__main__":
    main()

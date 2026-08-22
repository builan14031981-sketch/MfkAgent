import re

def main():
    filepath = "frontend/src/components/MessageList.tsx"
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # 替换 text 的渲染，如果是 roundtable 的 text, 让它有一个左侧 avatar 或者用 AgentIcon
    # 查找:
    # case "text":
    #   return <MarkdownRenderer key={seg.id} content={seg.content} />;

    pattern = re.compile(
        r'(case "text":\s+return <MarkdownRenderer key=\{seg\.id\} content=\{seg\.content\} />;)',
        re.DOTALL
    )

    replacement = r'''case "text":
                      if (seg.agent_id) {
                        return (
                          <div key={seg.id} style={{ display: "flex", gap: "12px", marginTop: "12px" }}>
                            <div style={{ flexShrink: 0, marginTop: "4px" }}>
                              <AgentIcon id={seg.agent_id} size={24} />
                            </div>
                            <div style={{ flex: 1, minWidth: 0 }}>
                              <div style={{ fontSize: "12px", fontWeight: 600, color: "var(--text-level-3)", marginBottom: "4px" }}>
                                {seg.agent_name || "Agent"}
                              </div>
                              <MarkdownRenderer content={seg.content} />
                            </div>
                          </div>
                        );
                      }
                      return <MarkdownRenderer key={seg.id} content={seg.content} />;'''

    new_content = pattern.sub(replacement, content)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(new_content)
    print("Fixed text rendering in MessageList.tsx")

if __name__ == "__main__":
    main()

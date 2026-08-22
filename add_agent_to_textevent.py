import re

def main():
    filepath = "frontend/src/types/runtime.ts"
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    pattern = re.compile(r'(export interface TextEvent extends RuntimeEventBase \{\n\s*type: "text";\n\s*content: string;)(\n\})', re.DOTALL)
    replacement = r'\1\n  agent_id?: string;\n  agent_name?: string;\2'
    content = pattern.sub(replacement, content)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print("Updated TextEvent in runtime.ts")

if __name__ == "__main__":
    main()

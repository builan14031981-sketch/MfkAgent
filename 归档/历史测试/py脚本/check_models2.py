import requests
import json

API = "http://127.0.0.1:8001"

print("=== Available Models ===")
try:
    r = requests.get(API + "/api/models", timeout=5)
    print("Status:", r.status_code)
    data = r.json()
    print("Type:", type(data).__name__)
    if isinstance(data, dict):
        print("Keys:", list(data.keys())[:15])
        # Try known patterns
        for k in ("models", "items", "data", "list"):
            if k in data and isinstance(data[k], list):
                lst = data[k]
                print("Found list in", k, ", len=", len(lst))
                for m in lst[:15]:
                    if isinstance(m, dict):
                        print("  -", m.get("id"), "name=", m.get("name"), "enabled=", m.get("enabled"))
                    else:
                        print("  -", str(m)[:100])
                break
        else:
            print("Full dict (truncated):", json.dumps(data, ensure_ascii=False)[:1500])
    elif isinstance(data, list):
        print("List, len=", len(data))
        for m in data[:15]:
            if isinstance(m, dict):
                print("  -", m.get("id"), m.get("name"), "prov=", m.get("provider_id"))
            else:
                print("  ", str(m)[:100])
    else:
        print("Raw:", str(data)[:800])
except Exception as e:
    import traceback
    traceback.print_exc()
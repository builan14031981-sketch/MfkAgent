import requests
import json

API = "http://127.0.0.1:8001"

# Try different endpoints
for path in ["/api/models/models", "/api/providers", "/api/models/providers", "/api/models/config"]:
    try:
        r = requests.get(API + path, timeout=5)
        print(f"GET {path} => {r.status_code}")
        if r.status_code == 200:
            try:
                d = r.json()
                if isinstance(d, list):
                    print("  List len:", len(d))
                    for x in d[:10]:
                        if isinstance(x, dict): print("  ", json.dumps(x, ensure_ascii=False)[:120])
                        else: print("  ", str(x)[:100])
                elif isinstance(d, dict):
                    txt = json.dumps(d, ensure_ascii=False)
                    if len(txt) > 2000: txt = txt[:2000] + "..."
                    print("  Dict:", txt)
            except: print("  Raw text:", r.text[:800])
        else:
            print("  Body:", r.text[:300])
    except Exception as e:
        print(f"  FAIL {path}: {str(e)[:200]}")
    print()
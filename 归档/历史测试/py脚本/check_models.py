import requests
import json

API = "http://127.0.0.1:8001"

print("=== Available Models ===")
try:
    r = requests.get(API + "/api/models", timeout=5)
    models = r.json()
    print("Count:", len(models))
    for m in models[:20]:
        print("  -", m.get("id"), "|", m.get("name"), "|provider=", m.get("provider_id"), "|enabled=", m.get("enabled"))
except Exception as e:
    print("Failed:", str(e)[:300])

print("")
print("=== Providers ===")
try:
    r2 = requests.get(API + "/api/providers", timeout=5)
    provs = r2.json()
    for p in provs[:15]:
        print("  ", p.get("id"), "key_configured=", p.get("has_key"), p.get("name"))
except Exception as e:
    print("Providers failed:", str(e)[:200])

# -*- coding: utf-8 -*-
"""诊断：检查 PROVIDERS 与 model_service.models 中 glm 相关模型。"""
import sys, os
sys.path.insert(0, r"E:\智慧项目\Mfkagent\backend")
os.chdir(r"E:\智慧项目\Mfkagent\backend")

from app.core.model_providers import PROVIDERS
print("=== PROVIDERS 中 glm provider 定义 ===")
for p in PROVIDERS:
    if p.id == "glm":
        for m in p.models:
            print(f"  id={m.id!r} upstream={m.upstream!r} name={m.display_name!r}")

from app.services.model import model_service
print()
print("=== model_service.models 中 glm/GLM 相关 key ===")
for mid, cfg in model_service.models.items():
    if "glm" in mid.lower() or "glm" in cfg.provider.value:
        print(f"  {mid!r} provider={cfg.provider.value} model_name={cfg.model_name!r} has_key={bool(cfg.api_key)}")

print()
print("=== model_service.models 总数 ===", len(model_service.models))
print()
print("=== get_available_models() ===")
for m in model_service.get_available_models():
    print("  ", m)

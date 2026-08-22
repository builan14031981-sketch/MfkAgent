import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, 'backend')

from app.core.database import SessionLocal
from app.models.agent import Agent
from app.models.persona import PersonaTemplate
from app.core.persona_engine import build_persona_context, load_expression_knowledge, get_profile_config
from app.core.agent_runtime.expressions import get_expression_prompt
from app.core.persona import loader as knowledge

db = SessionLocal()
try:
    agent = db.query(Agent).filter(Agent.agent_id == 'pianai').first()
    tmpl = db.query(PersonaTemplate).filter(PersonaTemplate.agent_id == 'pianai').first()
    expr_k = load_expression_knowledge(agent.expression_profile, db=db)
    print('=== expression_profile:', agent.expression_profile)
    print('=== profile_config:', json.dumps(get_profile_config(agent.expression_profile), default=lambda o: o.__dict__, ensure_ascii=False))
    ctx = build_persona_context(agent, tmpl, expr_k, user_message='今天好累')
    print('=== ⑥b expression prompt ===')
    print(get_expression_prompt(agent.expression_profile) or '(EMPTY)')
    print()
    print('=== ⑥c persona_text ===')
    print(ctx.persona_text or '(EMPTY)')
    print()
    print('=== ⑥d expression_text ===')
    print(ctx.expression_text or '(EMPTY)')
    print()
    print('=== ⑥e behavior_text ===')
    print(ctx.behavior_text or '(EMPTY)')
    print()
    print('=== ⑥f budget_text ===')
    print(ctx.budget_text)
    print()
    print('=== ⑥h restrictions_text ===')
    print(ctx.restrictions_text)
    print()
    print('=== has_persona:', ctx.has_persona)
finally:
    db.close()

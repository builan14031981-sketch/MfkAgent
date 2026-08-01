from fastapi import APIRouter
from app.services.greetings import get_random_greeting, get_greetings

router = APIRouter()


@router.get("/greeting")
async def system_greeting():
    """返回一条随机的主页欢迎语（极客文案）。"""
    greeting = get_random_greeting()
    if not greeting:
        return {"text": "Agent is alive!", "subtext": "欢迎语资源暂未加载。"}
    return greeting


@router.get("/greetings/count")
async def greeting_count():
    """返回欢迎语库条目数（调试用）。"""
    return {"count": len(get_greetings())}

import asyncio, httpx
from app.core.config import settings

MOBILE = "18757073254"

async def main():
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post("https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                         json={"app_id": settings.FEISHU_APP_ID, "app_secret": settings.FEISHU_APP_SECRET})
        token = r.json()["tenant_access_token"]
        h = {"Authorization": f"Bearer {token}"}

        # 1) 手机号 → open_id / user_id
        u = await c.post("https://open.feishu.cn/open-apis/contact/v3/users/batch_get_id",
                         params={"user_id_type": "open_id"},
                         json={"mobiles": [MOBILE], "emails": []}, headers=h)
        print("lookup:", u.status_code, u.text[:400])
        users = u.json().get("data", {}).get("user_list", [])
        if not users:
            print("未找到用户"); return
        open_id = users[0].get("user_id")
        print("open_id:", open_id)

        # 2) 建群：你当群主 + 你是初始成员（机器人也在群里）
        body = {"name": "MfkAgent 飞书群",
                "description": "MfkAgent Agent 自动发送消息的专属群",
                "owner_id": open_id,
                "user_id_list": [open_id],
                "settings": {"add_member_permission": "all_members"}}
        cr = await c.post("https://open.feishu.cn/open-apis/im/v1/chats",
                          params={"user_id_type": "open_id"},
                          json=body, headers=h)
        print("create:", cr.status_code, cr.text[:500])

asyncio.run(main())
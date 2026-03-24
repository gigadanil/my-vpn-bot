import aiohttp
import uuid
import json
from config import settings

BASE = settings.THREE_XUI_URL.rstrip("/")


async def _get_session_cookie() -> str:
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{BASE}/login",
            json={"username": settings.THREE_XUI_USER, "password": settings.THREE_XUI_PASS},
            ssl=False
        ) as resp:
            cookies = resp.cookies
            return cookies.get("3x-ui", {}).value if "3x-ui" in cookies else ""


async def create_client(tg_id: int, duration_days: int, gb_limit: int = 0) -> tuple[str, str]:
    """
    Creates a new client in 3x-ui.
    Returns (client_id, subscription_url)
    """
    cookie = await _get_session_cookie()
    client_id = str(uuid.uuid4())
    expire_ms = int(__import__("time").time() * 1000) + duration_days * 86400 * 1000

    client = {
        "id": client_id,
        "alterId": 0,
        "email": f"tg_{tg_id}_{client_id[:8]}",
        "limitIp": 2,
        "totalGB": gb_limit * 1024 ** 3,
        "expiryTime": expire_ms,
        "enable": True,
        "tgId": str(tg_id),
        "subId": client_id.replace("-", "")[:16],
    }

    async with aiohttp.ClientSession(cookies={"3x-ui": cookie}) as session:
        async with session.post(
            f"{BASE}/panel/api/inbounds/addClient",
            json={"id": settings.THREE_XUI_INBOUND_ID, "settings": json.dumps({"clients": [client]})},
            ssl=False
        ) as resp:
            data = await resp.json()
            if not data.get("success"):
                raise Exception(f"3x-ui error: {data}")

    sub_url = f"{BASE}/sub/{client['subId']}"
    return client_id, sub_url


async def delete_client(client_id: str):
    cookie = await _get_session_cookie()
    async with aiohttp.ClientSession(cookies={"3x-ui": cookie}) as session:
        await session.post(
            f"{BASE}/panel/api/inbounds/{settings.THREE_XUI_INBOUND_ID}/delClient/{client_id}",
            ssl=False
        )


async def extend_client(client_id: str, duration_days: int):
    """Extend existing client expiry."""
    cookie = await _get_session_cookie()
    expire_ms = int(__import__("time").time() * 1000) + duration_days * 86400 * 1000

    async with aiohttp.ClientSession(cookies={"3x-ui": cookie}) as session:
        # Get current client info
        async with session.get(
            f"{BASE}/panel/api/inbounds/getClientTraffics/{client_id}",
            ssl=False
        ) as resp:
            data = await resp.json()

        client = data.get("obj", {})
        client["expiryTime"] = expire_ms

        await session.post(
            f"{BASE}/panel/api/inbounds/updateClient/{client_id}",
            json={"id": settings.THREE_XUI_INBOUND_ID, "settings": json.dumps({"clients": [client]})},
            ssl=False
        )

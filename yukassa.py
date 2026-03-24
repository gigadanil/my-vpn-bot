import aiohttp
import uuid
from config import settings


async def create_payment(amount: float, description: str, return_url: str) -> tuple[str, str]:
    """
    Returns (payment_id, confirmation_url)
    """
    idempotency_key = str(uuid.uuid4())

    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://api.yookassa.ru/v2/payments",
            json={
                "amount": {"value": f"{amount:.2f}", "currency": "RUB"},
                "confirmation": {"type": "redirect", "return_url": return_url},
                "capture": True,
                "description": description,
            },
            headers={"Idempotence-Key": idempotency_key},
            auth=aiohttp.BasicAuth(settings.YUKASSA_SHOP_ID, settings.YUKASSA_SECRET_KEY),
        ) as resp:
            data = await resp.json()
            return data["id"], data["confirmation"]["confirmation_url"]


async def check_payment(payment_id: str) -> str:
    """Returns payment status: pending / succeeded / canceled"""
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"https://api.yookassa.ru/v2/payments/{payment_id}",
            auth=aiohttp.BasicAuth(settings.YUKASSA_SHOP_ID, settings.YUKASSA_SECRET_KEY),
        ) as resp:
            data = await resp.json()
            return data.get("status", "pending")

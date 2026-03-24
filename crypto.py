import aiohttp
from config import settings

CRYPTO_API = "https://pay.crypt.bot/api"


async def create_invoice(amount: float, asset: str = "USDT", description: str = "") -> tuple[str, str]:
    """
    Returns (invoice_id, pay_url)
    """
    async with aiohttp.ClientSession(headers={"Crypto-Pay-API-Token": settings.CRYPTO_BOT_TOKEN}) as session:
        async with session.post(
            f"{CRYPTO_API}/createInvoice",
            json={
                "asset": asset,
                "amount": str(amount),
                "description": description,
                "expires_in": 3600,
            }
        ) as resp:
            data = await resp.json()
            inv = data["result"]
            return str(inv["invoice_id"]), inv["pay_url"]


async def check_invoice(invoice_id: str) -> str:
    """Returns: active / paid / expired"""
    async with aiohttp.ClientSession(headers={"Crypto-Pay-API-Token": settings.CRYPTO_BOT_TOKEN}) as session:
        async with session.get(
            f"{CRYPTO_API}/getInvoices",
            params={"invoice_ids": invoice_id}
        ) as resp:
            data = await resp.json()
            items = data.get("result", {}).get("items", [])
            if items:
                return items[0].get("status", "active")
            return "active"

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    BOT_TOKEN: str
    THREE_XUI_URL: str          # e.g. https://your-panel.com:2053
    THREE_XUI_USER: str
    THREE_XUI_PASS: str
    THREE_XUI_INBOUND_ID: int = 1

    YUKASSA_SHOP_ID: str = ""
    YUKASSA_SECRET_KEY: str = ""

    CRYPTO_BOT_TOKEN: str = ""  # @CryptoBot token

    ADMIN_IDS: str = ""         # comma-separated telegram IDs

    DB_PATH: str = "data/bot.db"

    @property
    def admin_list(self) -> list[int]:
        return [int(i.strip()) for i in self.ADMIN_IDS.split(",") if i.strip()]

    class Config:
        env_file = ".env"


settings = Settings()

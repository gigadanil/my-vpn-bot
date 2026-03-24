import aiosqlite
from config import settings

DB = settings.DB_PATH


async def init_db():
    async with aiosqlite.connect(DB) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                tg_id INTEGER UNIQUE NOT NULL,
                username TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                trial_used INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY,
                tg_id INTEGER NOT NULL,
                plan_name TEXT NOT NULL,
                duration_days INTEGER NOT NULL,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,
                xui_client_id TEXT,
                config_link TEXT
            );

            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY,
                tg_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                currency TEXT NOT NULL,
                provider TEXT NOT NULL,
                payment_id TEXT,
                status TEXT DEFAULT 'pending',
                plan_name TEXT,
                duration_days INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        await db.commit()


async def get_user(tg_id: int) -> dict | None:
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE tg_id=?", (tg_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def create_user(tg_id: int, username: str):
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (tg_id, username) VALUES (?, ?)",
            (tg_id, username)
        )
        await db.commit()


async def get_active_sub(tg_id: int) -> dict | None:
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM subscriptions WHERE tg_id=? AND expires_at > datetime('now') ORDER BY expires_at DESC LIMIT 1",
            (tg_id,)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def create_subscription(tg_id: int, plan_name: str, duration_days: int,
                               xui_client_id: str, config_link: str):
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            """INSERT INTO subscriptions (tg_id, plan_name, duration_days, expires_at, xui_client_id, config_link)
               VALUES (?, ?, ?, datetime('now', ? || ' days'), ?, ?)""",
            (tg_id, plan_name, duration_days, str(duration_days), xui_client_id, config_link)
        )
        await db.commit()


async def trial_used(tg_id: int) -> bool:
    async with aiosqlite.connect(DB) as db:
        async with db.execute("SELECT trial_used FROM users WHERE tg_id=?", (tg_id,)) as cur:
            row = await cur.fetchone()
            return bool(row[0]) if row else False


async def mark_trial_used(tg_id: int):
    async with aiosqlite.connect(DB) as db:
        await db.execute("UPDATE users SET trial_used=1 WHERE tg_id=?", (tg_id,))
        await db.commit()


async def create_payment(tg_id: int, amount: float, currency: str, provider: str,
                          payment_id: str, plan_name: str, duration_days: int) -> int:
    async with aiosqlite.connect(DB) as db:
        cur = await db.execute(
            """INSERT INTO payments (tg_id, amount, currency, provider, payment_id, plan_name, duration_days)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (tg_id, amount, currency, provider, payment_id, plan_name, duration_days)
        )
        await db.commit()
        return cur.lastrowid


async def confirm_payment(payment_id: str, provider: str):
    async with aiosqlite.connect(DB) as db:
        await db.execute(
            "UPDATE payments SET status='paid' WHERE payment_id=? AND provider=?",
            (payment_id, provider)
        )
        await db.commit()


async def get_payment(payment_id: str, provider: str) -> dict | None:
    async with aiosqlite.connect(DB) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM payments WHERE payment_id=? AND provider=?",
            (payment_id, provider)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def get_all_users() -> list[int]:
    async with aiosqlite.connect(DB) as db:
        async with db.execute("SELECT tg_id FROM users") as cur:
            rows = await cur.fetchall()
            return [r[0] for r in rows]

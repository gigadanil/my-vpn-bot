import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from bot.config import settings

logging.basicConfig(level=logging.INFO)
bot = Bot(token=settings.BOT_TOKEN)
dp = Dispatcher()

@dp.message(Command('start'))
async def start_handler(message: types.Message):
    await message.answer(' ! , !   .')

async def main():
    print('---   ---')
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
cat <<EOF > ~/my-vpn-bot/bot/handlers/admin.py
from aiogram import Router, types
from aiogram.filters import Command

router = Router()

# Замени на свой ID (можно узнать у @userinfobot)
ADMIN_ID = 5118431735 

@router.message(Command("admin"))
async def admin_panel(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("🔧 Добро пожаловать в панель управления Shadow Net!\n\nЗдесь будет статистика и управление ключами.")
    else:
        await message.answer("У вас нет прав доступа к этой команде.")
EOF

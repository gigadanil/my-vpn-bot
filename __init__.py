import logging
from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import services.db as db
from services.plans import PLANS, TRIAL_DAYS
from services.xui import create_client
from services.yukassa import create_payment as yk_create, check_payment as yk_check
from services.crypto import create_invoice, check_invoice
from bot.keyboards import (
    main_menu, plans_keyboard, payment_method_keyboard,
    pay_link_keyboard, admin_keyboard
)
from config import settings

logger = logging.getLogger(__name__)
router = Router()


class BroadcastState(StatesGroup):
    waiting_text = State()


# ─── /start ───────────────────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(msg: Message):
    await db.create_user(msg.from_user.id, msg.from_user.username or "")
    await msg.answer(
        "👋 Привет! Я бот для подключения к <b>VPN</b>.\n\n"
        "🔒 Надёжное соединение, высокая скорость, неограниченный трафик.\n\n"
        "Выбери действие ниже 👇",
        parse_mode="HTML",
        reply_markup=main_menu()
    )


# ─── Моя подписка ─────────────────────────────────────────────────────────────

@router.message(F.text == "🌐 Моя подписка")
async def my_sub(msg: Message):
    sub = await db.get_active_sub(msg.from_user.id)
    if not sub:
        await msg.answer(
            "❌ У тебя нет активной подписки.\n\nНажми <b>Купить VPN</b> чтобы оформить.",
            parse_mode="HTML"
        )
        return

    await msg.answer(
        f"✅ <b>Подписка активна</b>\n\n"
        f"📦 Тариф: {sub['plan_name']}\n"
        f"⏳ Истекает: {sub['expires_at'][:10]}\n\n"
        f"🔗 <b>Ссылка для подключения:</b>\n<code>{sub['config_link']}</code>",
        parse_mode="HTML"
    )


# ─── Купить ───────────────────────────────────────────────────────────────────

@router.message(F.text == "💳 Купить VPN")
async def buy_vpn(msg: Message):
    await msg.answer("Выбери тариф:", reply_markup=plans_keyboard())


@router.callback_query(F.data == "back_plans")
async def back_to_plans(cb: CallbackQuery):
    await cb.message.edit_text("Выбери тариф:", reply_markup=plans_keyboard())


@router.callback_query(F.data.startswith("plan_"))
async def choose_plan(cb: CallbackQuery):
    plan_idx = int(cb.data.split("_")[1])
    plan = PLANS[plan_idx]
    await cb.message.edit_text(
        f"📦 <b>{plan['name']}</b>\n"
        f"💰 {plan['price_rub']}₽ / {plan['price_usdt']} USDT\n\n"
        f"Выбери способ оплаты:",
        parse_mode="HTML",
        reply_markup=payment_method_keyboard(plan_idx)
    )


# ─── ЮKassa ───────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("pay_yukassa_"))
async def pay_yukassa(cb: CallbackQuery):
    if not settings.YUKASSA_SHOP_ID:
        await cb.answer("ЮKassa не настроена", show_alert=True)
        return

    plan_idx = int(cb.data.split("_")[2])
    plan = PLANS[plan_idx]

    try:
        payment_id, url = await yk_create(
            amount=plan["price_rub"],
            description=f"VPN {plan['name']}",
            return_url="https://t.me/"
        )
        await db.create_payment(
            tg_id=cb.from_user.id,
            amount=plan["price_rub"],
            currency="RUB",
            provider="yukassa",
            payment_id=payment_id,
            plan_name=plan["name"],
            duration_days=plan["duration_days"]
        )
        await cb.message.edit_text(
            f"💳 <b>Оплата через ЮKassa</b>\n\n"
            f"Тариф: {plan['name']}\n"
            f"Сумма: {plan['price_rub']}₽\n\n"
            f"Нажми кнопку и оплати, затем нажми <b>Я оплатил</b>.",
            parse_mode="HTML",
            reply_markup=pay_link_keyboard(url, payment_id, "yukassa")
        )
    except Exception as e:
        logger.error(f"YooKassa error: {e}")
        await cb.answer("Ошибка создания платежа", show_alert=True)


# ─── Крипто ───────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("pay_crypto_"))
async def pay_crypto(cb: CallbackQuery):
    if not settings.CRYPTO_BOT_TOKEN:
        await cb.answer("Крипто-оплата не настроена", show_alert=True)
        return

    plan_idx = int(cb.data.split("_")[2])
    plan = PLANS[plan_idx]

    try:
        invoice_id, url = await create_invoice(
            amount=plan["price_usdt"],
            asset="USDT",
            description=f"VPN {plan['name']}"
        )
        await db.create_payment(
            tg_id=cb.from_user.id,
            amount=plan["price_usdt"],
            currency="USDT",
            provider="crypto",
            payment_id=str(invoice_id),
            plan_name=plan["name"],
            duration_days=plan["duration_days"]
        )
        await cb.message.edit_text(
            f"₿ <b>Оплата криптой</b>\n\n"
            f"Тариф: {plan['name']}\n"
            f"Сумма: {plan['price_usdt']} USDT\n\n"
            f"Нажми кнопку для оплаты через @CryptoBot, затем нажми <b>Я оплатил</b>.",
            parse_mode="HTML",
            reply_markup=pay_link_keyboard(url, str(invoice_id), "crypto")
        )
    except Exception as e:
        logger.error(f"Crypto error: {e}")
        await cb.answer("Ошибка создания инвойса", show_alert=True)


# ─── Проверка оплаты ──────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("check_"))
async def check_payment(cb: CallbackQuery):
    _, provider, payment_id = cb.data.split("_", 2)

    await cb.answer("Проверяю оплату...")

    try:
        if provider == "yukassa":
            status = await yk_check(payment_id)
            paid = status == "succeeded"
        else:
            status = await check_invoice(payment_id)
            paid = status == "paid"
    except Exception as e:
        logger.error(f"Check payment error: {e}")
        await cb.message.answer("⚠️ Ошибка проверки. Попробуй позже.")
        return

    if not paid:
        await cb.message.answer("⏳ Оплата ещё не поступила. Попробуй через минуту.")
        return

    # Get payment info from DB
    payment = await db.get_payment(payment_id, provider)
    if not payment:
        await cb.message.answer("⚠️ Платёж не найден в базе.")
        return

    if payment["status"] == "paid":
        await cb.message.answer("✅ Подписка уже активирована!")
        return

    # Activate subscription
    try:
        client_id, config_link = await create_client(
            tg_id=cb.from_user.id,
            duration_days=payment["duration_days"]
        )
        await db.create_subscription(
            tg_id=cb.from_user.id,
            plan_name=payment["plan_name"],
            duration_days=payment["duration_days"],
            xui_client_id=client_id,
            config_link=config_link
        )
        await db.confirm_payment(payment_id, provider)

        await cb.message.answer(
            f"🎉 <b>Подписка активирована!</b>\n\n"
            f"📦 Тариф: {payment['plan_name']}\n\n"
            f"🔗 <b>Ссылка для подключения:</b>\n<code>{config_link}</code>\n\n"
            f"📖 Нажми <b>Инструкция</b> чтобы узнать как подключиться.",
            parse_mode="HTML",
            reply_markup=main_menu()
        )
    except Exception as e:
        logger.error(f"Activation error: {e}")
        await cb.message.answer("⚠️ Ошибка активации. Напиши в поддержку.")


@router.callback_query(F.data == "cancel_payment")
async def cancel_payment(cb: CallbackQuery):
    await cb.message.edit_text("❌ Оплата отменена.", reply_markup=None)


# ─── Пробный период ───────────────────────────────────────────────────────────

@router.message(F.text == "🎁 Пробный период")
async def trial(msg: Message):
    used = await db.trial_used(msg.from_user.id)
    if used:
        await msg.answer("❌ Ты уже использовал пробный период.")
        return

    sub = await db.get_active_sub(msg.from_user.id)
    if sub:
        await msg.answer("У тебя уже есть активная подписка.")
        return

    try:
        client_id, config_link = await create_client(
            tg_id=msg.from_user.id,
            duration_days=TRIAL_DAYS
        )
        await db.create_subscription(
            tg_id=msg.from_user.id,
            plan_name=f"Пробный ({TRIAL_DAYS} дня)",
            duration_days=TRIAL_DAYS,
            xui_client_id=client_id,
            config_link=config_link
        )
        await db.mark_trial_used(msg.from_user.id)

        await msg.answer(
            f"🎁 <b>Пробный период активирован на {TRIAL_DAYS} дня!</b>\n\n"
            f"🔗 <b>Ссылка для подключения:</b>\n<code>{config_link}</code>\n\n"
            f"📖 Нажми <b>Инструкция</b> чтобы подключиться.",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Trial error: {e}")
        await msg.answer("⚠️ Ошибка. Напиши в поддержку.")


# ─── Инструкция ───────────────────────────────────────────────────────────────

@router.message(F.text == "📖 Инструкция")
async def instruction(msg: Message):
    await msg.answer(
        "📖 <b>Как подключиться к VPN</b>\n\n"
        "<b>Android / iOS:</b>\n"
        "1. Установи приложение <b>v2rayNG</b> (Android) или <b>Streisand</b> (iOS)\n"
        "2. Нажми + → Импорт из буфера обмена\n"
        "3. Вставь свою ссылку подключения\n\n"
        "<b>Windows / Mac:</b>\n"
        "1. Установи <b>Hiddify</b> или <b>v2rayN</b>\n"
        "2. Добавь подписку → вставь свою ссылку\n\n"
        "🔗 Свою ссылку найдёшь в разделе <b>Моя подписка</b>",
        parse_mode="HTML"
    )


# ─── Поддержка ────────────────────────────────────────────────────────────────

@router.message(F.text == "💬 Поддержка")
async def support(msg: Message):
    await msg.answer(
        "💬 <b>Поддержка</b>\n\n"
        "Если есть вопросы или проблемы — напиши нашему менеджеру:\n"
        "@your_support_username",  # поменяй на свой
        parse_mode="HTML"
    )


# ─── Админ ────────────────────────────────────────────────────────────────────

@router.message(Command("admin"))
async def admin_panel(msg: Message):
    if msg.from_user.id not in settings.admin_list:
        return
    await msg.answer("🔧 Панель администратора", reply_markup=admin_keyboard())


@router.callback_query(F.data == "admin_stats")
async def admin_stats(cb: CallbackQuery):
    if cb.from_user.id not in settings.admin_list:
        return
    users = await db.get_all_users()
    await cb.message.answer(f"📊 Всего пользователей: {len(users)}")


@router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_start(cb: CallbackQuery, state: FSMContext):
    if cb.from_user.id not in settings.admin_list:
        return
    await cb.message.answer("✏️ Введи текст рассылки:")
    await state.set_state(BroadcastState.waiting_text)


@router.message(BroadcastState.waiting_text)
async def admin_broadcast_send(msg: Message, state: FSMContext):
    await state.clear()
    users = await db.get_all_users()
    ok, fail = 0, 0
    for tg_id in users:
        try:
            await msg.bot.send_message(tg_id, msg.text)
            ok += 1
        except Exception:
            fail += 1
    await msg.answer(f"📢 Отправлено: {ok}, ошибок: {fail}")

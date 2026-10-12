import asyncio
import os
import re
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

STAR_PRICE = 230
STAR_PACKAGES = [50, 100, 250, 500, 1000]

# Укажи свои актуальные данные для оплаты
CARD_NUMBER = "5614686100717373"
CARD_HOLDER = "Valatova.S."

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


class OrderState(StatesGroup):
    waiting_username = State()


# Временное хранение корзины в памяти
user_carts = {}
pending_orders = {}


def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="⭐ Купить Telegram Stars",
            callback_data="stars"
        )],
        [InlineKeyboardButton(
            text="💎 Telegram Premium",
            callback_data="premium"
        )],
        [InlineKeyboardButton(
            text="🛟 Поддержка",
            callback_data="support"
        )],
    ])


def stars_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=f"⭐ {amount} Stars — {amount * STAR_PRICE:,} сум",
                callback_data=f"buy:{amount}"
            )
        ]
        for amount in STAR_PACKAGES
    ] + [[
        InlineKeyboardButton(text="⬅️ Назад", callback_data="home")
    ]])


@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "🌌 Добро пожаловать в Nebula Stars!\n\n"
        "Выбери, что хочешь приобрести:",
        reply_markup=main_menu()
    )


@dp.message(Command("cancel"))
async def cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "❌ Действие отменено.",
        reply_markup=main_menu()
    )


@dp.callback_query(F.data == "home")
async def home(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "🌌 Главное меню Nebula Stars:",
        reply_markup=main_menu()
    )
    await callback.answer()


@dp.callback_query(F.data == "stars")
async def show_stars(callback: CallbackQuery):
    await callback.message.edit_text(
        "⭐ Выбери количество Telegram Stars:\n\n"
        f"Цена: {STAR_PRICE} сум за 1 звезду.",
        reply_markup=stars_menu()
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("buy:"))
async def choose_stars(callback: CallbackQuery, state: FSMContext):
    amount = int(callback.data.split(":")[1])

    await state.update_data(stars_amount=amount)
    await state.set_state(OrderState.waiting_username)

    await callback.message.answer(
        f"⭐ Ты выбрал: {amount} Telegram Stars.\n"
        f"💰 Стоимость: {amount * STAR_PRICE:,} сум.\n\n"
        "👤 Теперь отправь юзернейм Telegram человека, "
        "которому нужно отправить звёзды.\n\n"
        "Например: @username\n\n"
        "Если покупаешь для себя, отправь свой юзернейм.\n"
        "Для отмены напиши /cancel"
    )
    await callback.answer()


@dp.message(OrderState.waiting_username)
async def get_username(message: Message, state: FSMContext):
    username = message.text.strip() if message.text else ""

    # Проверяем формат Telegram username
    username = username.removeprefix("@")

    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{4,31}", username):
        await message.answer(
            "❌ Похоже, юзернейм введён неправильно.\n\n"
            "Отправь username без пробелов, например:\n"
            "@username123\n\n"
            "Юзернейм должен содержать от 5 до 32 символов "
            "и начинаться с буквы."
        )
        return

    data = await state.get_data()
    amount = data["stars_amount"]
    total = amount * STAR_PRICE

    order_id = f"{message.from_user.id}_{message.message_id}"

    order = {
        "user_id": message.from_user.id,
        "buyer": message.from_user.full_name,
        "buyer_username": message.from_user.username or "не указан",
        "recipient": f"@{username}",
        "amount": amount,
        "total": total,
    }

    pending_orders[order_id] = order

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="💳 Показать реквизиты",
            callback_data=f"card:{order_id}"
        )],
        [InlineKeyboardButton(
            text="❌ Отменить заказ",
            callback_data=f"cancelorder:{order_id}"
        )],
    ])

    await message.answer(
        "✅ Проверь заказ:\n\n"
        f"⭐ Количество: {amount} Stars\n"
        f"👤 Получатель: @{username}\n"
        f"💰 К оплате: {total:,} сум\n\n"
        "Нажми кнопку ниже, чтобы посмотреть реквизиты.",
        reply_markup=keyboard
    )

    if ADMIN_ID:
        await bot.send_message(
            ADMIN_ID,
            "🛒 НОВЫЙ ЗАКАЗ NEBULA STARS\n\n"
            f"🆔 Заказ: {order_id}\n"
            f"👤 Покупатель: {order['buyer']}\n"
            f"🔗 Username покупателя: @{order['buyer_username']}\n"
            f"🎯 Получатель Stars: {order['recipient']}\n"
            f"⭐ Количество: {amount} Stars\n"
            f"💰 Сумма: {total:,} сум\n"
            f"🆔 Telegram ID: {order['user_id']}"
        )

    await state.clear()


@dp.callback_query(F.data.startswith("card:"))
async def show_card(callback: CallbackQuery):
    order_id = callback.data.split(":", 1)[1]
    order = pending_orders.get(order_id)

    if not order or order["user_id"] != callback.from_user.id:
        await callback.answer("Заказ не найден.", show_alert=True)
        return

    await callback.message.answer(
        "💳 Реквизиты для оплаты:\n\n"
        f"Номер карты: {CARD_NUMBER}\n"
        f"Получатель: {CARD_HOLDER}\n\n"
        f"Сумма: {order['total']:,} сум\n\n"
        "После оплаты нажми кнопку «Я оплатил».",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="✅ Я оплатил",
                callback_data=f"paid:{order_id}"
            )]
        ])
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("paid:"))
async def paid(callback: CallbackQuery):
    order_id = callback.data.split(":", 1)[1]
    order = pending_orders.get(order_id)

    if not order or order["user_id"] != callback.from_user.id:
        await callback.answer("Заказ не найден.", show_alert=True)
        return

    if ADMIN_ID:
        await bot.send_message(
            ADMIN_ID,
            "💸 КЛИЕНТ СООБЩИЛ ОБ ОПЛАТЕ\n\n"
            f"🆔 Заказ: {order_id}\n"
            f"👤 Покупатель: {order['buyer']}\n"
            f"🎯 Получатель: {order['recipient']}\n"
            f"⭐ Количество: {order['amount']} Stars\n"
            f"💰 Сумма: {order['total']:,} сум\n\n"
            "Проверь поступление денег вручную."
        )

    await callback.message.answer(
        "✅ Сообщение об оплате отправлено администратору!\n\n"
        "Заказ будет обработан после проверки оплаты."
    )
    await callback.answer("Уведомление отправлено!")


@dp.callback_query(F.data.startswith("cancelorder:"))
async def cancel_order(callback: CallbackQuery):
    order_id = callback.data.split(":", 1)[1]
    order = pending_orders.get(order_id)

    if not order or order["user_id"] != callback.from_user.id:
        await callback.answer("Заказ не найден.", show_alert=True)
        return

    del pending_orders[order_id]
    await callback.message.answer("❌ Заказ отменён.")
    await callback.answer()


@dp.callback_query(F.data == "premium")
async def premium(callback: CallbackQuery):
    await callback.message.answer(
        "💎 Telegram Premium\n\n"
        "Цены на Premium пока настраиваются.\n"
        "Напиши администратору для уточнения."
    )
    await callback.answer()


@dp.callback_query(F.data == "support")
async def support(callback: CallbackQuery):
    await callback.message.answer(
        "🛟 Поддержка Nebula Stars\n\n"
        "Напиши администратору, если нужна помощь."
    )
    await callback.answer()


async def main():
    if not BOT_TOKEN:
        raise ValueError("Не найден BOT_TOKEN в файле .env")

    print("Nebula Stars запущен!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
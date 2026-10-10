import asyncio
import logging
import os
from datetime import datetime, timezone
from html import escape

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "").strip()
if not TOKEN or not ADMIN_CHAT_ID:
    raise RuntimeError("Заполни BOT_TOKEN и ADMIN_CHAT_ID в файле .env")
ADMIN_CHAT_ID = int(ADMIN_CHAT_ID)

logging.basicConfig(level=logging.INFO)
bot = Bot(TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

class Form(StatesGroup):
    description = State()
    link = State()
    contact = State()
    confirm = State()

def menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🐞 Сообщить о баге", callback_data="type:bug")],
        [InlineKeyboardButton(text="🚨 Отправить жалобу", callback_data="type:complaint")],
        [InlineKeyboardButton(text="💡 Предложить улучшение", callback_data="type:idea")],
        [InlineKeyboardButton(text="📋 Как это работает?", callback_data="help")],
        [InlineKeyboardButton(text="🌐 Открыть RECORN", url="https://recorn.vercel.app")],
    ])

def cancel_kb():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="❌ Отмена")]], resize_keyboard=True)

def confirm_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Отправить", callback_data="send"),
         InlineKeyboardButton(text="✏️ Заполнить заново", callback_data="restart")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="cancel")]
    ])

def esc(value):
    return escape(str(value or ""), quote=True)

@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        f"🖤 <b>RECORN • ЦЕНТР ОБРАТНОЙ СВЯЗИ</b>\n"
        f"<i>Привет, {esc(message.from_user.first_name or 'игрок')}!</i>\n\n"
        "Нашёл баг, хочешь пожаловаться или предложить идею? "
        "Напиши нам — команда RECORN получит обращение.\n\n"
        "Выбери действие:",
        reply_markup=menu()
    )

@dp.message(Command("help"))
async def help_cmd(message: Message):
    await message.answer("✨ <b>Как отправить обращение</b>\n\n"
        "1. Выбери тип обращения.\n2. Опиши ситуацию.\n"
        "3. При желании добавь ссылку.\n4. Проверь и отправь.\n\n"
        "Не отправляй пароли и коды входа.")

@dp.callback_query(F.data == "help")
async def help_cb(call: CallbackQuery):
    await call.message.answer("💡 <b>Совет</b>\nДля бага укажи шаги, после которых он появляется, и что ожидалось. "
                              "Для жалобы напиши, что случилось и где. Не присылай пароли или коды.")
    await call.answer()

@dp.callback_query(F.data.startswith("type:"))
async def choose_type(call: CallbackQuery, state: FSMContext):
    key = call.data.split(":", 1)[1]
    labels = {"bug": "🐞 Баг", "complaint": "🚨 Жалоба", "idea": "💡 Идея"}
    if key not in labels:
        await call.answer("Неизвестный тип", show_alert=True)
        return
    await state.clear()
    await state.update_data(category=labels[key], category_key=key)
    await state.set_state(Form.description)
    await call.message.answer(f"{labels[key]}\n\n✍️ <b>Опиши обращение одним сообщением.</b> Минимум 10 символов.",
                              reply_markup=cancel_kb())
    await call.answer()

@dp.message(F.text == "❌ Отмена")
async def cancel_text(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Обращение отменено. Если понадобится — я здесь 🖤", reply_markup=menu())

@dp.message(Form.description)
async def get_description(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if len(text) < 10:
        await message.answer("Добавь немного деталей — минимум 10 символов.")
        return
    if len(text) > 3500:
        await message.answer("Слишком длинно. Сократи описание до 3500 символов.")
        return
    await state.update_data(description=text)
    await state.set_state(Form.link)
    await message.answer("🔗 <b>Есть ссылка на страницу или доказательство?</b> Отправь ссылку http(s):// или напиши «Нет».",
                         reply_markup=cancel_kb())

@dp.message(Form.link)
async def get_link(message: Message, state: FSMContext):
    value = (message.text or "").strip()
    if value.lower() in {"нет", "no", "-", "нету"}:
        value = "Не указана"
    elif not (value.startswith("https://") or value.startswith("http://")):
        await message.answer("Нужна полная ссылка с https:// или http://, либо напиши «Нет».")
        return
    await state.update_data(link=value)
    await state.set_state(Form.contact)
    await message.answer("👤 <b>Оставить контакт для уточнений?</b> Напиши @username или «Нет». Это необязательно.",
                         reply_markup=cancel_kb())

@dp.message(Form.contact)
async def get_contact(message: Message, state: FSMContext):
    contact = (message.text or "").strip()
    if contact.lower() in {"нет", "no", "-", "нету"}:
        contact = "Не указан"
    if len(contact) > 100:
        await message.answer("Контакт слишком длинный. Напиши @username или «Нет».")
        return
    await state.update_data(contact=contact)
    data = await state.get_data()
    preview = ("🧾 <b>ПРОВЕРЬ ОБРАЩЕНИЕ</b>\n\n"
               f"<b>Тип:</b> {esc(data['category'])}\n"
               f"<b>Описание:</b>\n{esc(data['description'])}\n\n"
               f"<b>Ссылка:</b> {esc(data['link'])}\n"
               f"<b>Контакт:</b> {esc(contact)}\n\nВсё верно?")
    await state.set_state(Form.confirm)
    await message.answer(preview, reply_markup=confirm_kb())

@dp.callback_query(Form.confirm, F.data == "send")
async def send_report(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user = call.from_user
    username = "@" + esc(user.username) if user.username else "не указан"
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    admin_text = ("📨 <b>НОВОЕ ОБРАЩЕНИЕ • RECORN</b>\n━━━━━━━━━━━━━━━━━━\n"
                  f"<b>Тип:</b> {esc(data.get('category'))}\n"
                  f"<b>Описание:</b>\n{esc(data.get('description'))}\n\n"
                  f"<b>Ссылка:</b> {esc(data.get('link'))}\n"
                  f"<b>Контакт:</b> {esc(data.get('contact'))}\n"
                  "━━━━━━━━━━━━━━━━━━\n"
                  f"<b>Telegram:</b> {username}\n<b>User ID:</b> <code>{user.id}</code>\n"
                  f"<b>Время:</b> {timestamp}")
    try:
        await bot.send_message(ADMIN_CHAT_ID, admin_text)
    except Exception:
        logging.exception("Could not deliver report")
        await call.message.answer("⚠️ Не удалось доставить обращение. Проверь настройки бота и попробуй позже.")
        await call.answer()
        return
    await state.clear()
    await call.message.answer("✅ <b>Обращение отправлено!</b>\n\nСпасибо, что помогаешь сделать RECORN лучше 🖤",
                              reply_markup=menu())
    await call.answer("Отправлено!")

@dp.callback_query(Form.confirm, F.data == "restart")
async def restart(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    await state.update_data(category=data.get("category", "🐞 Баг"),
                            category_key=data.get("category_key", "bug"))
    await state.set_state(Form.description)
    await call.message.answer("✏️ Заполним заново. Опиши обращение (минимум 10 символов).", reply_markup=cancel_kb())
    await call.answer()

@dp.callback_query(Form.confirm, F.data == "cancel")
async def cancel_cb(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.answer("Обращение отменено. Можешь создать новое в любое время.", reply_markup=menu())
    await call.answer("Отменено")

@dp.message()
async def fallback(message: Message):
    await message.answer("Выбери действие в меню или введи /start.", reply_markup=menu())

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

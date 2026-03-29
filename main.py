import asyncio
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
TRELLO_API_KEY = os.getenv("TRELLO_API_KEY")
TRELLO_TOKEN = os.getenv("TRELLO_TOKEN")

TRELLO_LISTS = {
    "low":    os.getenv("TRELLO_LIST_LOW"),
    "medium": os.getenv("TRELLO_LIST_MEDIUM"),
    "high":   os.getenv("TRELLO_LIST_HIGH"),
}

TELEGRAM_ID_PREFIX = "TELEGRAM_USER_ID:"

# ====== ИНИЦИАЛИЗАЦИЯ ======
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# ====== СОСТОЯНИЯ FSM ======
class TaskForm(StatesGroup):
    waiting_for_title = State()
    waiting_for_description = State()
    waiting_for_image = State()
    waiting_for_priority = State()


# ====== КЛАВИАТУРЫ ======
def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📝 Новая задача")],
            [KeyboardButton(text="📋 Мои обращения")],
            [KeyboardButton(text="❓ Помощь")],
        ],
        resize_keyboard=True,
    )


def cancel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True,
    )


def skip_image_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="⏩ Пропустить")],
            [KeyboardButton(text="❌ Отмена")],
        ],
        resize_keyboard=True,
    )


def priority_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🟢 Низкий")],
            [KeyboardButton(text="🟡 Средний")],
            [KeyboardButton(text="🔴 Высокий")],
            [KeyboardButton(text="❌ Отмена")],
        ],
        resize_keyboard=True,
    )


# ====== РАБОТА С TRELLO ======
async def create_trello_card(
    title: str,
    description: str,
    priority: str,
    user_id: int,
    username: str,
    full_name: str,
    date_str: str,
    priority_label: str,
    image_data: bytes | None = None,
    image_filename: str | None = None,
) -> dict:
    """
    Создаёт карточку в Trello.
    Если передана картинка — прикрепляет её как вложение.
    """

    label_colors = {
        "low": "green",
        "medium": "yellow",
        "high": "red",
    }

    full_description = (
        f"## Обращение из Telegram\n\n"
        f"**Пользователь:** @{username} "
        f"(ID: {user_id})\n"
        f"**Имя:** {full_name}\n"
        f"**Дата:** {date_str}\n"
        f"**Приоритет:** {priority_label}\n\n"
        f"---\n\n"
        f"### Описание проблемы:\n"
        f"{description}\n\n"
        f"---\n"
        f"{TELEGRAM_ID_PREFIX}{user_id}"
    )

    list_id = TRELLO_LISTS[priority]

    url = "https://api.trello.com/1/cards"
    params = {
        "key": TRELLO_API_KEY,
        "token": TRELLO_TOKEN,
        "idList": list_id,
        "name": title,
        "desc": full_description,
        "pos": "top",
    }

    async with aiohttp.ClientSession() as session:
        # 1. Создаём карточку
        async with session.post(url, params=params) as resp:
            card = await resp.json()
            card_id = card["id"]

        # 2. Добавляем цветную метку
        label_url = f"https://api.trello.com/1/cards/{card_id}/labels"
        label_params = {
            "key": TRELLO_API_KEY,
            "token": TRELLO_TOKEN,
            "color": label_colors[priority],
        }
        async with session.post(label_url, params=label_params):
            pass

        # 3. Прикрепляем картинку если есть
        if image_data and image_filename:
            attach_url = (
                f"https://api.trello.com/1/cards/{card_id}/attachments"
            )
            attach_params = {
                "key": TRELLO_API_KEY,
                "token": TRELLO_TOKEN,
            }

            form = aiohttp.FormData()
            form.add_field(
                "file",
                image_data,
                filename=image_filename,
                content_type="image/jpeg",
            )

            async with session.post(
                attach_url, params=attach_params, data=form
            ):
                pass

    return card


async def get_user_cards(user_id: int) -> dict:
    """
    Получает карточки из всех трёх списков и фильтрует
    по наличию TELEGRAM_USER_ID:<user_id> в описании.
    """

    search_tag = f"{TELEGRAM_ID_PREFIX}{user_id}"
    result = {"low": [], "medium": [], "high": []}

    async with aiohttp.ClientSession() as session:
        for priority, list_id in TRELLO_LISTS.items():
            url = f"https://api.trello.com/1/lists/{list_id}/cards"
            params = {
                "key": TRELLO_API_KEY,
                "token": TRELLO_TOKEN,
                "fields": "name,shortUrl,desc,dateLastActivity",
            }
            async with session.get(url, params=params) as resp:
                cards = await resp.json()

                for card in cards:
                    if search_tag in card.get("desc", ""):
                        result[priority].append(card)

    return result


# ====== ОБРАБОТЧИКИ БОТА ======

@dp.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "👋 Добро пожаловать в службу поддержки!\n\n"
        "🚗 Онлайн-сервис ретуширования автомобилей\n\n"
        "Я помогу создать обращение или проверить статус ваших задач.",
        reply_markup=main_keyboard(),
    )


# ---- Создание задачи ----

@dp.message(F.text == "📝 Новая задача")
async def new_task(message: types.Message, state: FSMContext):
    await message.answer(
        "✨ Создание нового обращения\n\n"
        "📌 *Шаг 1/4:*\n"
        "Введите краткий заголовок задачи:\n\n"
        "_Например: Артефакты при экспорте в PNG_",
        parse_mode="Markdown",
        reply_markup=cancel_keyboard(),
    )
    await state.set_state(TaskForm.waiting_for_title)


# -- Отмена на любом шаге --

@dp.message(TaskForm.waiting_for_title, F.text == "❌ Отмена")
@dp.message(TaskForm.waiting_for_description, F.text == "❌ Отмена")
@dp.message(TaskForm.waiting_for_image, F.text == "❌ Отмена")
@dp.message(TaskForm.waiting_for_priority, F.text == "❌ Отмена")
async def cancel_any(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Отменено.", reply_markup=main_keyboard())


# -- Шаг 1: Заголовок --

@dp.message(TaskForm.waiting_for_title)
async def process_title(message: types.Message, state: FSMContext):
    await state.update_data(task_title=message.text)
    await message.answer(
        "📌 *Шаг 2/4:*\n"
        "Подробно опишите проблему:\n\n"
        "_Что произошло? Что ожидали? "
        "Какие шаги привели к ошибке?_",
        parse_mode="Markdown",
        reply_markup=cancel_keyboard(),
    )
    await state.set_state(TaskForm.waiting_for_description)


# -- Шаг 2: Описание --

@dp.message(TaskForm.waiting_for_description)
async def process_description(message: types.Message, state: FSMContext):
    await state.update_data(task_description=message.text)
    await message.answer(
        "📌 *Шаг 3/4:*\n"
        "Прикрепите скриншот или фото проблемы\n\n"
        "📎 Отправьте картинку или нажмите *⏩ Пропустить*",
        parse_mode="Markdown",
        reply_markup=skip_image_keyboard(),
    )
    await state.set_state(TaskForm.waiting_for_image)


# -- Шаг 3: Картинка (опционально) --

@dp.message(TaskForm.waiting_for_image, F.text == "⏩ Пропустить")
async def skip_image(message: types.Message, state: FSMContext):
    await state.update_data(image_file_id=None)
    await message.answer(
        "📌 *Шаг 4/4:*\n"
        "Укажите приоритет:\n\n"
        "🟢 Низкий — пожелание, улучшение\n"
        "🟡 Средний — ошибка, но можно работать\n"
        "🔴 Высокий — критическая ошибка, работа невозможна",
        parse_mode="Markdown",
        reply_markup=priority_keyboard(),
    )
    await state.set_state(TaskForm.waiting_for_priority)


@dp.message(TaskForm.waiting_for_image, F.photo)
async def process_image(message: types.Message, state: FSMContext):
    # Берём фото в максимальном разрешении (последний элемент)
    photo = message.photo[-1]
    await state.update_data(image_file_id=photo.file_id)
    await message.answer(
        "✅ Фото прикреплено!\n\n"
        "📌 *Шаг 4/4:*\n"
        "Укажите приоритет:\n\n"
        "🟢 Низкий — пожелание, улучшение\n"
        "🟡 Средний — ошибка, но можно работать\n"
        "🔴 Высокий — критическая ошибка, работа невозможна",
        parse_mode="Markdown",
        reply_markup=priority_keyboard(),
    )
    await state.set_state(TaskForm.waiting_for_priority)


@dp.message(TaskForm.waiting_for_image)
async def wrong_image(message: types.Message):
    await message.answer(
        "Пожалуйста, отправьте *фото* или нажмите *⏩ Пропустить*",
        parse_mode="Markdown",
    )


# -- Шаг 4: Приоритет и создание карточки --

@dp.message(TaskForm.waiting_for_priority)
async def process_priority(message: types.Message, state: FSMContext):
    priority_map = {
        "🟢 Низкий": "low",
        "🟡 Средний": "medium",
        "🔴 Высокий": "high",
    }

    priority = priority_map.get(message.text)
    if not priority:
        await message.answer("Пожалуйста, выберите приоритет кнопкой.")
        return

    data = await state.get_data()
    title = data["task_title"]
    description = data["task_description"]
    image_file_id = data.get("image_file_id")

    # Скачиваем картинку из Telegram если есть
    image_data = None
    image_filename = None
    if image_file_id:
        file = await bot.get_file(image_file_id)
        from io import BytesIO
        buffer = BytesIO()
        await bot.download_file(file.file_path, buffer)
        image_data = buffer.getvalue()
        image_filename = f"screenshot_{message.from_user.id}.jpg"

    try:
        card = await create_trello_card(
            title=title,
            description=description,
            priority=priority,
            user_id=message.from_user.id,
            username=message.from_user.username or "нет",
            full_name=message.from_user.full_name,
            date_str=message.date.strftime("%d.%m.%Y %H:%M"),
            priority_label=message.text,
            image_data=image_data,
            image_filename=image_filename,
        )

        list_names = {
            "low": "🟢 Low Priority",
            "medium": "🟡 Medium Priority",
            "high": "🔴 High Priority",
        }

        result_text = (
            f"✅ *Задача создана!*\n\n"
            f"📋 *Заголовок:* {title}\n"
            f"📝 *Описание:* {description[:100]}"
        )
        if len(description) > 100:
            result_text += "..."
        result_text += (
            f"\n📎 *Фото:* {'прикреплено' if image_file_id else 'нет'}\n"
            f"⚡ *Приоритет:* {message.text}\n"
            f"📂 *Список:* {list_names[priority]}\n"
            f"🔗 *Ссылка:* {card.get('shortUrl', 'N/A')}\n\n"
            f"Мы рассмотрим обращение в ближайшее время!"
        )

        await message.answer(
            result_text,
            parse_mode="Markdown",
            reply_markup=main_keyboard(),
        )
    except Exception as e:
        await message.answer(
            f"❌ Ошибка при создании задачи: {str(e)}\n"
            f"Попробуйте позже.",
            reply_markup=main_keyboard(),
        )

    await state.clear()


# ---- Мои обращения ----

@dp.message(F.text == "📋 Мои обращения")
async def list_my_tasks(message: types.Message):
    try:
        user_cards = await get_user_cards(message.from_user.id)

        total = sum(len(v) for v in user_cards.values())
        if total == 0:
            await message.answer(
                "📭 У вас нет активных обращений.\n\n"
                "Нажмите «📝 Новая задача», чтобы создать.",
                reply_markup=main_keyboard(),
            )
            return

        text = "📋 *Ваши обращения:*\n\n"

        if user_cards["high"]:
            text += "🔴 *Высокий приоритет:*\n"
            for i, card in enumerate(user_cards["high"], 1):
                text += f"  {i}. [{card['name']}]\n"
            text += "\n"

        if user_cards["medium"]:
            text += "🟡 *Средний приоритет:*\n"
            for i, card in enumerate(user_cards["medium"], 1):
                text += f"  {i}. [{card['name']}]\n"
            text += "\n"

        if user_cards["low"]:
            text += "🟢 *Низкий приоритет:*\n"
            for i, card in enumerate(user_cards["low"], 1):
                text += f"  {i}. [{card['name']}])\n"

        text += f"\n📊 *Всего ваших обращений:* {total}"

        await message.answer(
            text,
            parse_mode="Markdown",
            disable_web_page_preview=True,
            reply_markup=main_keyboard(),
        )

    except Exception as e:
        await message.answer(
            f"❌ Ошибка: {str(e)}",
            reply_markup=main_keyboard(),
        )


# ---- Помощь ----

@dp.message(F.text == "❓ Помощь")
async def help_cmd(message: types.Message):
    await message.answer(
        "🚗 *Онлайн-сервис ретуширования автомобилей*\n\n"
        "Через этот бот вы можете:\n"
        "📝 Создать обращение — оно попадёт в Trello\n"
        "📋 Посмотреть свои активные обращения\n\n"
        "При создании обращения:\n"
        "1️⃣ Введите заголовок\n"
        "2️⃣ Опишите проблему подробно\n"
        "3️⃣ Прикрепите скриншот (необязательно)\n"
        "4️⃣ Выберите приоритет\n\n"
        "Задачи распределяются по приоритету:\n"
        "🟢 Низкий — пожелания, улучшения\n"
        "🟡 Средний — ошибки средней важности\n"
        "🔴 Высокий — критические проблемы\n\n"
        "Каждое обращение обрабатывается командой разработки.\n"
        "Статус задачи можно отслеживать по ссылке в Trello.",
        parse_mode="Markdown",
        reply_markup=main_keyboard(),
    )


# ====== ЗАПУСК ======
async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

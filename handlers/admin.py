import os
import asyncio
import random
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import config
from core.engine import get_sessions, send_story_with_init

router = Router()


class TaskSetup(StatesGroup):
    waiting_media = State()
    waiting_users = State()
    waiting_link = State()


def main_kb():
    return types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text="📝 Создать рассылку")]],
        resize_keyboard=True
    )


def task_kb(media=False, users=False, link=False):
    m_icon = "✅" if media else "🔴"
    u_icon = "✅" if users else "🔴"
    l_icon = "✅" if link else "🔴"

    kb = [
        [types.InlineKeyboardButton(text=f"{m_icon} Загрузить Фото/Видео", callback_data="upload_media")],
        [types.InlineKeyboardButton(text=f"{u_icon} Загрузить Базу (.txt)", callback_data="upload_users")],
        [types.InlineKeyboardButton(text=f"{l_icon} Ссылка-кнопка", callback_data="set_link")],
    ]
    if media and users:
        kb.append([types.InlineKeyboardButton(text="🚀 ЗАПУСК", callback_data="start_run")])
    return types.InlineKeyboardMarkup(inline_keyboard=kb)


@router.message(Command("start"))
async def cmd_start(message: types.Message):
    if message.from_user.id != config.ADMIN_ID:
        return
    await message.answer("👋 Бот готов к работе.", reply_markup=main_kb())


@router.message(F.text == "📝 Создать рассылку")
async def new_task(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("⚙️ Настройка задачи:", reply_markup=task_kb())


# 1. МЕДИА
@router.callback_query(F.data == "upload_media")
async def ask_media(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("📸 Пришлите Фото или Видео (до 10 МБ).")
    await state.set_state(TaskSetup.waiting_media)


@router.message(TaskSetup.waiting_media)
async def get_media(message: types.Message, state: FSMContext):
    file_id = None
    file_name = "task_media"

    if message.photo:
        file_id = message.photo[-1].file_id
        file_name += ".jpg"
    elif message.video:
        file_id = message.video.file_id
        file_name += ".mp4"
    elif message.document:
        if 'image' in (message.document.mime_type or ''):
            file_name += ".jpg"
        elif 'video' in (message.document.mime_type or ''):
            file_name += ".mp4"
        else:
            await message.answer("❌ Только фото или видео!")
            return
        file_id = message.document.file_id
    else:
        await message.answer("❌ Пришлите медиафайл.")
        return

    path = os.path.join(config.DOWNLOADS_DIR, file_name)
    await message.bot.download(file_id, path)

    await state.update_data(media_path=path, media_ready=True)
    data = await state.get_data()
    await message.answer("✅ Файл сохранен!",
                         reply_markup=task_kb(True, data.get("users_ready"), data.get("link_ready")))
    await state.set_state(None)


# 2. БАЗА
@router.callback_query(F.data == "upload_users")
async def ask_users(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("👥 Пришлите .txt файл с юзернеймами.")
    await state.set_state(TaskSetup.waiting_users)


@router.message(TaskSetup.waiting_users, F.document)
async def get_users_file(message: types.Message, state: FSMContext):
    status = await message.answer("⏳ Скачиваю...")
    path = os.path.join(config.DOWNLOADS_DIR, "users.txt")
    await message.bot.download(message.document, path)

    count = 0
    with open(path, encoding='utf-8', errors='ignore') as f:
        for _ in f:
            count += 1

    await state.update_data(users_ready=True)
    data = await state.get_data()
    await status.delete()
    await message.answer(f"✅ База: {count} строк",
                         reply_markup=task_kb(data.get("media_ready"), True, data.get("link_ready")))
    await state.set_state(None)


# 3. ССЫЛКА
@router.callback_query(F.data == "set_link")
async def ask_link(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("🔗 Пришлите ссылку для кнопки.")
    await state.set_state(TaskSetup.waiting_link)


@router.message(TaskSetup.waiting_link)
async def get_link(message: types.Message, state: FSMContext):
    link = message.text.split()[0]
    await state.update_data(link_url=link, link_ready=True)
    data = await state.get_data()
    await message.answer(f"✅ Ссылка: {link}",
                         reply_markup=task_kb(data.get("media_ready"), data.get("users_ready"), True))
    await state.set_state(None)


# 4. ЗАПУСК (всё в одной кнопке)
@router.callback_query(F.data == "start_run")
async def start_run(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    sessions = await get_sessions()

    if not sessions:
        await call.message.answer("❌ Нет сессий в data/sessions")
        return

    media_path = data.get('media_path')
    if not media_path or not os.path.exists(media_path):
        await call.message.answer("❌ Файл медиа потерян. Загрузите снова.")
        return

    with open(os.path.join(config.DOWNLOADS_DIR, "users.txt"), 'r', encoding='utf-8', errors='ignore') as f:
        users = [line.strip().replace('@', '') for line in f if line.strip()]

    if not users:
        await call.message.answer("❌ База пуста")
        return

    chunk_size = getattr(config, 'MAX_TAGS_PER_STORY', 3)
    chunks = [users[i:i + chunk_size] for i in range(0, len(users), chunk_size)]

    total_chunks = len(chunks)
    await call.message.answer(
        f"🚀 Старт!\n"
        f"👥 Пользователей: {len(users)}\n"
        f"📸 Историй будет: {total_chunks}\n"
        f"📱 Аккаунтов: {len(sessions)}\n"
        f"⏱ TTL пауза: {getattr(config, 'TTL_TO_PUBLISH_DELAY', 300)}с"
    )

    success = 0
    idx = 0
    total_notified = 0

    for chunk_num, chunk in enumerate(chunks, 1):
        current_sess = sessions[idx % len(sessions)]
        idx += 1

        await call.message.answer(
            f"📤 [{chunk_num}/{total_chunks}] Обработка: {', '.join('@' + u for u in chunk)}"
        )

        result = await send_story_with_init(
            current_sess, chunk,
            media_path, data.get('link_url')
        )

        if result and result.get('success'):
            success += len(chunk)
            story_id = result.get('story_id')
            notified_count = result.get('notified_count', 0)
            total_notified += notified_count
            init_count = result.get('dialogs_initiated', 0)

            await call.message.answer(
                f"✅ [{chunk_num}/{total_chunks}] Готово!\n"
                f"   📸 Story ID: {story_id}\n"
                f"   🔗 TTL диалогов: {init_count}\n"
                f"   👥 Отмечено: {len(chunk)}\n"
                f"   🔔 Уведомлений: {notified_count}"
            )
        else:
            error_msg = result.get('error', 'unknown') if result else 'no result'
            await call.message.answer(
                f"❌ [{chunk_num}/{total_chunks}] Ошибка: {error_msg}"
            )

        # Задержка между историями (кроме последней)
        if chunk_num < total_chunks:
            min_delay = getattr(config, 'MIN_DELAY', 600)
            max_delay = getattr(config, 'MAX_DELAY', 1200)
            delay = random.randint(min_delay, max_delay)
            await call.message.answer(f"⏳ Пауза {delay}с перед следующей историей...")
            await asyncio.sleep(delay)

    await call.message.answer(
        f"🏁 Всё готово!\n"
        f"✅ Отмечено: {success}/{len(users)}\n"
        f"🔔 Уведомлений: {total_notified}"
    )
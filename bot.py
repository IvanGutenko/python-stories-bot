import asyncio
import logging
from aiogram import Bot, Dispatcher
from handlers import admin
import config
import os

async def main():
    # Создаем папки если нет
    if not os.path.exists(config.DOWNLOADS_DIR):
        os.makedirs(config.DOWNLOADS_DIR)
    
    logging.basicConfig(level=logging.INFO)
    
    bot = Bot(token=config.BOT_TOKEN)
    dp = Dispatcher()
    
    dp.include_router(admin.router)
    
    print("🤖 Бот запущен...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

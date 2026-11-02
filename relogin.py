import asyncio
import python_socks
from telethon import TelegramClient
import config

# Настройки прокси из конфига
proxy_settings = None
if getattr(config, 'USE_PROXY', False):
    p_type = python_socks.ProxyType.SOCKS5 if config.PROXY_TYPE == 'socks5' else python_socks.ProxyType.HTTP
    proxy_settings = {
        'proxy_type': p_type,
        'addr': config.PROXY_IP,
        'port': int(config.PROXY_PORT),
        'username': config.PROXY_USER,
        'password': config.PROXY_PASS,
        'rdns': True
    }

# ВАЖНО: Тут мы используем новые API_ID/HASH из config.py
# И параметры эмуляции iPhone
client = TelegramClient(
    'data/sessions/acc1', 
    config.API_ID, 
    config.API_HASH,
    proxy=proxy_settings,
    device_model="iPhone 15 Pro",
    system_version="17.4.1",
    app_version="10.12.0",
    lang_code="en",
    system_lang_code="en-US"
)

async def main():
    print(f"🔄 Входим с API_ID: {config.API_ID} (Официальный iOS)...")
    await client.start()
    me = await client.get_me()
    print(f"✅ УСПЕХ! Сессия создана: {me.first_name} (@{me.username})")

if __name__ == '__main__':
    client.loop.run_until_complete(main())

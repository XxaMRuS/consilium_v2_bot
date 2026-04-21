# python wait_and_run.py Бонус: скрипт, который сам проверит разблокировку и запустит бота
import time
import requests
import subprocess
from datetime import datetime

KEYS = [
    "aa7085293ca645279d7d58a0504cf2e3.3rhvPjsTy1FylWVO",
    "702cec973e194cc7b84d4069a9f96dbc.n8l2NW8BsPV3ZUnl",
    "9b68f742ac674b238e81cd6ecb1a96fa.cda9SnozSuqAvdYC"
]

def check_key(key):
    url = "https://api.z.ai/api/anthropic/v1/messages"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    payload = {"model": "glm-4.7", "max_tokens": 1, "messages": [{"role": "user", "content": "hi"}]}
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=5)
        return r.status_code == 200
    except:
        return False

print(f"🔍 Мониторинг ключей... Жду разблокировки")
print(f"🎯 Ожидаемое время: 2026-04-20 03:55:02")
print(f"🔄 Проверка каждые 10 минут\n")

while True:
    for i, key in enumerate(KEYS, 1):
        if check_key(key):
            print(f"✅ Ключ #{i} РАЗБЛОКИРОВАН в {datetime.now()}")
            print(f"🚀 Запускаю бота...")
            subprocess.run(["python", "bot.py"])
            exit(0)
        else:
            print(f"⏳ Ключ #{i} ещё в лимите ({datetime.now()})")
    print(f"💤 Следующая проверка через 10 минут...")
    print("-" * 50)
    time.sleep(600)
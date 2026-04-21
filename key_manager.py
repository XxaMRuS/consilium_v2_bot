# python key_manager.py
import subprocess
import sys
import time
import requests
from typing import Optional

# Список всех ключей в порядке приоритета
KEYS = [
    "aa7085293ca645279d7d58a0504cf2e3.3rhvPjsTy1FylWVO",
    "702cec973e194cc7b84d4069a9f96dbc.n8l2NW8BsPV3ZUnl",
    "5633c51edf9d4c05bfa952f8d59c3909.lHpgJG1xnhu6gHSb",
    "9b68f742ac674b238e81cd6ecb1a96fa.cda9SnozSuqAvdYC",
]

ENDPOINT = "https://api.z.ai/api/anthropic"

def check_key(key: str) -> bool:
    """Проверяет, работает ли ключ (отправляет тестовый запрос)."""
    try:
        response = requests.post(
            f"{ENDPOINT}/v1/messages",
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            json={"model": "glm-4.7", "max_tokens": 1, "messages": [{"role": "user", "content": "hi"}]},
            timeout=5,
        )
        return response.status_code == 200
    except Exception:
        return False

def get_active_key() -> Optional[str]:
    """Возвращает первый работающий ключ или None."""
    for key in KEYS:
        if check_key(key):
            return key
    return None

def run_claude_with_key(key: str):
    """Запускает Claude Code с указанным ключом."""
    env = {
        "ANTHROPIC_AUTH_TOKEN": key,
        "ANTHROPIC_BASE_URL": ENDPOINT,
        "API_TIMEOUT_MS": "3000000",
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
    }
    # Запускаем claude, дожидаемся его завершения
    proc = subprocess.Popen(["claude"], env={**os.environ, **env})
    proc.wait()
    return proc.returncode

if __name__ == "__main__":
    import os
    while True:
        key = get_active_key()
        if not key:
            print("❌ Нет работающих ключей. Ждём 5 минут...")
            time.sleep(300)
            continue

        print(f"✅ Используем ключ: {key[:10]}...")
        ret = run_claude_with_key(key)
        # Если claude завершился с ошибкой 429 (Too Many Requests) или 401 (Unauthorized), переключаем ключ
        if ret in (429, 401):
            print(f"⚠️ Ключ {key[:10]}... исчерпан. Ищем следующий...")
            # Убираем текущий ключ из списка, чтобы он не выбирался снова
            KEYS.remove(key)
            continue
        # При любом другом коде возврата просто перезапускаем с тем же ключом (на случай временного сбоя)
        print("🔄 Перезапуск с тем же ключом...")
        time.sleep(2)
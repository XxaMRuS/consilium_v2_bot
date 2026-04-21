import requests
import json
import time

# Твои ключи
KEYS = [
    "aa7085293ca645279d7d58a0504cf2e3.3rhvPjsTy1FylWVO",
    "702cec973e194cc7b84d4069a9f96dbc.n8l2NW8BsPV3ZUnl",
    "5633c51edf9d4c05bfa952f8d59c3909.lHpgJG1xnhu6gHSb",
    "9b68f742ac674b238e81cd6ecb1a96fa.cda9SnozSuqAvdYC"
]

BASE_URL = "https://api.z.ai/api/anthropic/v1/messages"


def check_key(api_key):
    """Проверяет один ключ и возвращает статус"""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    payload = {
        "model": "glm-4.7",
        "max_tokens": 10,
        "messages": [
            {"role": "user", "content": "Say 'OK'"}
        ]
    }

    try:
        start = time.time()
        response = requests.post(
            BASE_URL,
            headers=headers,
            json=payload,
            timeout=10
        )
        elapsed = round(time.time() - start, 2)

        if response.status_code == 200:
            return {
                "status": "✅ РАБОТАЕТ",
                "code": 200,
                "time": elapsed,
                "detail": "Ключ активен"
            }
        elif response.status_code == 401:
            return {
                "status": "❌ НЕВАЛИДНЫЙ",
                "code": 401,
                "time": elapsed,
                "detail": "Неверный формат или ключ заблокирован"
            }
        elif response.status_code == 403:
            return {
                "status": "❌ ДОСТУП ЗАПРЕЩЁН",
                "code": 403,
                "time": elapsed,
                "detail": "Ключ не имеет прав или закончился баланс"
            }
        elif response.status_code == 429:
            return {
                "status": "⚠️ ЛИМИТ",
                "code": 429,
                "time": elapsed,
                "detail": "Слишком много запросов / превышен лимит"
            }
        else:
            return {
                "status": "⚠️ НЕИЗВЕСТНО",
                "code": response.status_code,
                "time": elapsed,
                "detail": response.text[:100]
            }

    except requests.exceptions.Timeout:
        return {
            "status": "⏰ ТАЙМАУТ",
            "code": None,
            "time": 10,
            "detail": "Сервер не ответил за 10 секунд"
        }
    except requests.exceptions.ConnectionError:
        return {
            "status": "🌐 НЕТ СОЕДИНЕНИЯ",
            "code": None,
            "time": None,
            "detail": "Не удаётся подключиться к api.z.ai"
        }
    except Exception as e:
        return {
            "status": "💥 ОШИБКА",
            "code": None,
            "time": None,
            "detail": str(e)[:100]
        }


def main():
    print("=" * 60)
    print("🔍 ДИАГНОСТИКА КЛЮЧЕЙ z.ai (Anthropic API)")
    print("=" * 60)
    print()

    working_keys = []

    for i, key in enumerate(KEYS, 1):
        print(f"📡 Проверка ключа #{i}: {key[:20]}...")
        result = check_key(key)

        print(f"   Статус: {result['status']}")
        print(f"   HTTP код: {result['code']}")
        print(f"   Время: {result['time']} сек")
        print(f"   Детали: {result['detail']}")
        print()

        if result['status'] == "✅ РАБОТАЕТ":
            working_keys.append(key)

    print("=" * 60)
    print("📊 ИТОГ:")
    print(f"   Всего ключей: {len(KEYS)}")
    print(f"   Рабочих: {len(working_keys)}")

    if working_keys:
        print(f"\n✅ Активные ключи:")
        for idx, key in enumerate(working_keys, 1):
            print(f"   {idx}. {key}")
        print("\n💡 Используй команду:")
        print(f"   $env:ANTHROPIC_AUTH_TOKEN='{working_keys[0]}'")
    else:
        print("\n❌ НЕТ РАБОЧИХ КЛЮЧЕЙ!")
        print("\nВозможные причины:")
        print("   1. Закончился баланс на z.ai")
        print("   2. Ключи были отозваны или истекли")
        print("   3. Изменился эндпоинт API")
        print("   4. Нужна оплата/пополнение")

    print("=" * 60)


if __name__ == "__main__":
    main()
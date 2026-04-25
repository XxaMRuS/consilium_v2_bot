# -*- coding: utf-8 -*-
"""
AI-система для фитнес-бота с fallback на бесплатные API
Только бесплатные API с автоматическим переключением
"""
import os
import logging
import aiohttp
import base64
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

logger = logging.getLogger(__name__)

# API ключи из переменных окружения
YANDEX_API_KEY = os.getenv("YANDEX_API_KEY")
YANDEX_FOLDER_ID = os.getenv("YANDEX_FOLDER_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Логирование загрузки ключей
logger.info(f"🔍 AI API Keys статус:")
logger.info(f"  YANDEX_API_KEY: {'✅' if YANDEX_API_KEY else '❌'}")
logger.info(f"  GROQ_API_KEY: {'✅' if GROQ_API_KEY else '❌'}")
logger.info(f"  GEMINI_API_KEY: {'✅' if GEMINI_API_KEY else '❌'}")
logger.info(f"  OPENROUTER_API_KEY: {'✅' if OPENROUTER_API_KEY else '❌'}")
logger.info(f"  DEEPSEEK_API_KEY: {'✅' if DEEPSEEK_API_KEY else '❌'}")
logger.info(f"  OPENAI_API_KEY: {'✅' if OPENAI_API_KEY else '❌'}")

# Бесплатные модели OpenRouter (для fallback)
FREE_MODELS = [
    "google/gemma-2-9b-it:free",
    "meta-llama/llama-3.1-8b-instruct:free",
    "microsoft/phi-3-medium-128k-instruct:free"
]

# Таймауты для API
API_TIMEOUT = 10  # секунд
API_TIMEOUT_PHOTO = 15  # для фото (дольше)


# ==================== GROQ - ОСНОВНОЙ (БЕСПЛАТНЫЙ) ====================

class GroqRecommender:
    """
    Groq - основной AI (бесплатный, очень быстрый)
    Приоритет №1 в системе fallback
    """

    def __init__(self):
        self.api_key = GROQ_API_KEY
        self.model = "llama-3.3-70b-versatile"  # Актуальная модель
        self.name = "Groq"

    async def get_quick_recommendation(self, user_data: dict, current_workout: dict) -> str:
        """Даёт мгновенную рекомендацию"""
        if not self.api_key:
            raise Exception("Groq API не подключён")

        try:
            prompt = self._create_prompt(user_data, current_workout)

            response = await self._send_request(prompt)
            logger.info(f"✅ {self.name} успешен")
            return response

        except Exception as e:
            logger.error(f"❌ {self.name} ошибка: {e}")
            raise

    async def get_training_advice(self, user_data: dict, question: str) -> str:
        """Даёт совет по тренировке"""
        if not self.api_key:
            raise Exception("Groq API не подключён")

        try:
            prompt = self._create_advice_prompt(user_data, question)
            response = await self._send_request(prompt)
            logger.info(f"✅ {self.name} успешен")
            return response

        except Exception as e:
            logger.error(f"❌ {self.name} ошибка: {e}")
            raise

    def _create_prompt(self, user_data: dict, current_workout: dict) -> str:
        """Создаёт prompt для быстрой рекомендации"""
        name = user_data.get('first_name', 'Друг')
        level = user_data.get('user_group', 'newbie')
        last_workout = current_workout.get('last_exercise', 'Нет тренировок')
        streak = current_workout.get('streak', 0)

        return f"""Ты - мотивационный фитнес-коуч. Дай БЫСТРУЮ рекомендацию (1 предложение).

Пользователь: {name}
Уровень: {level}
Последнее упражнение: {last_workout}
Серия тренировок: {streak} дней

Дай мотивирующую рекомендацию на сегодня!"""

    def _create_advice_prompt(self, user_data: dict, question: str) -> str:
        """Создаёт prompt для совета"""
        name = user_data.get('first_name', 'Друг')
        level = user_data.get('user_group', 'newbie')

        level_names = {
            'newbie': 'новичок',
            'beginner': 'начинающий',
            'intermediate': 'средний уровень',
            'advanced': 'продвинутый'
        }

        return f"""Ты - опытный фитнес-тренер. Дай краткий и мотивирующий совет (2-3 предложения).

Пользователь: {name}
Уровень: {level_names.get(level, 'новичок')}

Вопрос: {question}

Дай практический ответ!"""

    async def _send_request(self, prompt: str) -> str:
        """Отправляет запрос к Groq API"""
        url = "https://api.groq.com/openai/v1/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        data = {
            "messages": [{"role": "user", "content": prompt}],
            "model": self.model,
            "temperature": 0.8,
            "max_tokens": 150
        }

        timeout = aiohttp.ClientTimeout(total=API_TIMEOUT)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, headers=headers, json=data) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Groq API error {response.status}: {error_text}")
                    raise Exception(f"Groq API error {response.status}: {error_text}")
                result = await response.json()

        if 'choices' in result and len(result['choices']) > 0:
            return result['choices'][0]['message']['content']
        else:
            raise Exception("Неверный ответ от API")


# ==================== OPENROUTER - FALLBACK 1 ====================

class OpenRouterCoach:
    """
    OpenRouter с бесплатными моделями
    Fallback при ошибке Groq
    """

    def __init__(self):
        self.api_key = OPENROUTER_API_KEY
        self.models = FREE_MODELS
        self.name = "OpenRouter"

    async def get_quick_recommendation(self, user_data: dict, current_workout: dict) -> str:
        """Даёт рекомендацию через бесплатные модели"""
        if not self.api_key:
            raise Exception("OpenRouter API не подключён")

        # Пробуем каждую модель по очереди
        last_error = None
        for model in self.models:
            try:
                prompt = self._create_prompt(user_data, current_workout)
                response = await self._try_model(model, prompt)
                logger.info(f"✅ {self.name} ({model}) успешен")
                return response

            except Exception as e:
                last_error = e
                logger.warning(f"⚠️ {self.name} ({model}) не сработал: {e}")
                continue

        raise Exception(f"Все модели {self.name} недоступны: {last_error}")

    async def get_training_advice(self, user_data: dict, question: str) -> str:
        """Даёт совет через бесплатные модели"""
        if not self.api_key:
            raise Exception("OpenRouter API не подключён")

        last_error = None
        for model in self.models:
            try:
                prompt = self._create_advice_prompt(user_data, question)
                response = await self._try_model(model, prompt)
                logger.info(f"✅ {self.name} ({model}) успешен")
                return response

            except Exception as e:
                last_error = e
                logger.warning(f"⚠️ {self.name} ({model}) не сработал: {e}")
                continue

        raise Exception(f"Все модели {self.name} недоступны: {last_error}")

    def _create_prompt(self, user_data: dict, current_workout: dict) -> str:
        """Создаёт prompt"""
        name = user_data.get('first_name', 'Друг')
        last_workout = current_workout.get('last_exercise', 'Нет тренировок')
        streak = current_workout.get('streak', 0)

        return f"""Ты - фитнес-коуч. Дай краткую рекомендацию (1 предложение).

Пользователь: {name}
Последнее упражнение: {last_workout}
Серия: {streak} дней

Мотивируй!"""

    def _create_advice_prompt(self, user_data: dict, question: str) -> str:
        """Создаёт prompt для совета"""
        name = user_data.get('first_name', 'Друг')

        return f"""Ты - фитнес-тренер. Дай краткий совет (2-3 предложения).

Пользователь: {name}

Вопрос: {question}

Дай практический ответ!"""

    async def _try_model(self, model: str, prompt: str) -> str:
        """Пробует конкретную модель"""
        url = "https://openrouter.ai/api/v1/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:8000",
            "X-Title": "Fitness Bot"
        }

        data = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": 150
        }

        timeout = aiohttp.ClientTimeout(total=API_TIMEOUT)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, headers=headers, json=data) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"OpenRouter {model} error {response.status}: {error_text}")
                    raise Exception(f"OpenRouter {model} error {response.status}: {error_text}")
                result = await response.json()

        if 'choices' in result and len(result['choices']) > 0:
            return result['choices'][0]['message']['content']
        else:
            raise Exception("Неверный ответ от API")


# ==================== YANDEXGPT - FALLBACK 2 ====================

class YandexCoach:
    """
    YandexGPT - fallback при ошибках OpenRouter
    Бесплатный лимит (Алиса)
    """

    def __init__(self):
        self.api_key = YANDEX_API_KEY
        self.folder_id = YANDEX_FOLDER_ID
        self.model = f"gpt://{self.folder_id}/yandexgpt/latest"
        self.name = "YandexGPT"

    async def get_training_advice(self, user_data: dict, question: str) -> str:
        """Даёт совет через YandexGPT"""
        if not self.api_key:
            raise Exception("Yandex API не подключён")

        try:
            prompt = self._create_advice_prompt(user_data, question)
            response = await self._send_request(prompt)
            logger.info(f"✅ {self.name} успешен")
            return response

        except Exception as e:
            logger.error(f"❌ {self.name} ошибка: {e}")
            raise

    def _create_advice_prompt(self, user_data: dict, question: str) -> str:
        """Создаёт prompt"""
        name = user_data.get('first_name', 'Друг')
        level = user_data.get('user_group', 'newbie')

        level_names = {
            'newbie': 'новичок',
            'beginner': 'начинающий',
            'intermediate': 'средний уровень',
            'advanced': 'продвинутый'
        }

        return f"""Ты - фитнес-тренер. Дай краткий совет (2-3 предложения).

Пользователь: {name}
Уровень: {level_names.get(level, 'новичок')}

Вопрос: {question}

Дай практический ответ!"""

    async def _send_request(self, prompt: str) -> str:
        """Отправляет запрос к YandexGPT API"""
        url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"

        headers = {
            "Authorization": f"Api-Key {self.api_key}",
            "Content-Type": "application/json"
        }

        data = {
            "modelUri": self.model,
            "completionOptions": {
                "stream": False,
                "temperature": 0.7,
                "maxTokens": 500
            },
            "messages": [
                {
                    "role": "user",
                    "text": prompt
                }
            ]
        }

        timeout = aiohttp.ClientTimeout(total=API_TIMEOUT)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, headers=headers, json=data) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"YandexGPT error {response.status}: {error_text}")
                    raise Exception(f"YandexGPT error {response.status}: {error_text}")
                result = await response.json()

        if 'result' in result and 'alternatives' in result['result'] and len(result['result']['alternatives']) > 0:
            return result['result']['alternatives'][0]['message']['text']
        else:
            raise Exception("Неверный ответ от API")


# ==================== GEMINI - АНАЛИЗ ФОТО ====================

class GeminiPhotoAnalyzer:
    """
    Gemini - анализ фото тренировок
    Fallback для анализа изображений
    """

    def __init__(self):
        self.api_key = GEMINI_API_KEY
        self.name = "Gemini"

    async def analyze_photo(self, photo_data: bytes, exercise_name: str) -> str:
        """Анализирует фото с тренировкой"""
        if not self.api_key:
            raise Exception("Gemini API не подключён")

        try:
            base64_image = base64.b64encode(photo_data).decode('utf-8')
            prompt = self._create_photo_prompt(exercise_name)

            response = await self._send_request(base64_image, prompt)
            logger.info(f"✅ {self.name} успешен")
            return response

        except Exception as e:
            logger.error(f"❌ {self.name} ошибка: {e}")
            raise

    def _create_photo_prompt(self, exercise_name: str) -> str:
        """Создаёт prompt для анализа фото"""
        return f"""Проанализируй технику выполнения упражнения: "{exercise_name}"

Дай краткий анализ:
1. Правильность позиции (✅ хорошо / ❌ исправить)
2. Конкретные советы по улучшению
3. Оценка от 1 до 10

Ответ в формате:
🔍 Анализ: [текст]
💡 Советы: [текст]
⭐ Оценка: [число]/10
"""

    async def _send_request(self, base64_image: str, prompt: str) -> str:
        """Отправляет запрос к Gemini API"""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={self.api_key}"

        headers = {"Content-Type": "application/json"}

        data = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": "image/jpeg",
                                "data": base64_image
                            }
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 500
            }
        }

        timeout = aiohttp.ClientTimeout(total=API_TIMEOUT_PHOTO)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, headers=headers, json=data) as response:
                response.raise_for_status()
                result = await response.json()

        if 'candidates' in result and len(result['candidates']) > 0:
            return result['candidates'][0]['content']['parts'][0]['text']
        else:
            raise Exception("Неверный ответ от API")


# ==================== СИСТЕМА FALLBACK ====================

class AICoachSystem:
    """
    Общая система AI-тренера с автоматическим fallback
    Только бесплатные API!
    """

    def __init__(self):
        self.groq = GroqRecommender()
        self.openrouter = OpenRouterCoach()
        self.yandex = YandexCoach()
        self.gemini = GeminiPhotoAnalyzer()

    async def get_quick_recommendation(self, user_data: dict, current_workout: dict) -> str:
        """
        Быстрая рекомендация с fallback

        Приоритет:
        1. YandexGPT (основной)
        2. Groq (быстрый)
        3. OpenRouter (бесплатные модели)
        """
        # Пробуем YandexGPT (приоритет №1)
        try:
            return await self.yandex.get_training_advice(user_data, "Дай быструю мотивацию на сегодня")
        except Exception as e:
            logger.warning(f"⚠️ YandexGPT не сработал: {e}, пробуем Groq...")

        # Пробуем Groq
        try:
            return await self.groq.get_quick_recommendation(user_data, current_workout)
        except Exception as e:
            logger.warning(f"⚠️ Groq не сработал: {e}, пробуем OpenRouter...")

        # Пробуем OpenRouter
        try:
            return await self.openrouter.get_quick_recommendation(user_data, current_workout)
        except Exception as e:
            logger.error(f"❌ Все AI недоступны: {e}")
            return "⚠️ Все AI-сервисы暂时 недоступны. Попробуйте позже!"

    async def get_training_advice(self, user_data: dict, question: str) -> str:
        """
        Совет по тренировке с fallback

        Приоритет:
        1. YandexGPT (основной)
        2. Groq (быстрый и качественный)
        3. OpenRouter (бесплатные модели)
        """
        # Пробуем YandexGPT (приоритет №1)
        try:
            return await self.yandex.get_training_advice(user_data, question)
        except Exception as e:
            logger.warning(f"⚠️ YandexGPT не сработал: {e}, пробуем Groq...")

        # Пробуем Groq
        try:
            return await self.groq.get_training_advice(user_data, question)
        except Exception as e:
            logger.warning(f"⚠️ Groq не сработал: {e}, пробуем OpenRouter...")

        # Пробуем OpenRouter
        try:
            return await self.openrouter.get_training_advice(user_data, question)
        except Exception as e:
            logger.error(f"❌ Все AI недоступны: {e}")
            return "⚠️ Все AI-сервисы暂时 недоступны. Попробуйте позже!"

    async def analyze_workout_photo(self, photo_data: bytes, exercise_name: str) -> str:
        """
        Анализ фото с fallback

        Приоритет:
        1. Gemini (основной для фото)
        """
        try:
            return await self.gemini.analyze_photo(photo_data, exercise_name)
        except Exception as e:
            logger.error(f"❌ Gemini не сработал: {e}")
            return "⚠️ Не удалось проанализировать фото. Попробуйте позже."

    async def analyze_user_progress(self, user_data: dict, workout_history: list) -> str:
        """
        Анализ прогресса с fallback

        Приоритет:
        1. YandexGPT (основной)
        2. Groq (быстрый)
        3. OpenRouter (бесплатные модели)
        """
        # Формируем prompt для анализа прогресса
        prompt = self._create_progress_prompt(user_data, workout_history)

        # Пробуем YandexGPT (приоритет №1)
        try:
            return await self.yandex._send_request(prompt)
        except Exception as e:
            logger.warning(f"⚠️ YandexGPT не сработал для прогресса: {e}, пробуем Groq...")

        # Пробуем Groq
        try:
            return await self.groq._send_request(prompt)
        except Exception as e:
            logger.warning(f"⚠️ Groq не сработал для прогресса: {e}, пробуем OpenRouter...")

        # Пробуем OpenRouter
        try:
            return await self.openrouter._try_model(self.openrouter.models[0], prompt)
        except Exception as e:
            logger.error(f"❌ Все AI недоступны для анализа прогресса: {e}")
            return "⚠️ Не удалось проанализировать прогресс. Попробуйте позже."

    def _create_progress_prompt(self, user_data: dict, workout_history: list) -> str:
        """Создаёт prompt для анализа прогресса"""
        name = user_data.get('first_name', 'Друг')
        score = user_data.get('score', 0)
        workout_count = len(workout_history)

        # Формируем статистику
        if workout_history:
            last_7_days = sum(1 for w in workout_history if self._is_last_days(w.get('date', ''), 7))
            last_30_days = sum(1 for w in workout_history if self._is_last_days(w.get('date', ''), 30))
        else:
            last_7_days = 0
            last_30_days = 0

        return f"""Ты - аналитик фитнес-прогресса. Проанализируй прогресс.

Имя: {name}
Очки: {score}
Всего тренировок: {workout_count}
За последние 7 дней: {last_7_days} тренировок
За последние 30 дней: {last_30_days} тренировок

Дай анализ:
1. Текущий прогресс
2. Сильные стороны
3. Что улучшить

Ответ краткий, 3-4 предложения."""

    def _is_last_days(self, date_str: str, days: int) -> bool:
        """Проверяет, была ли тренировка в последние N дней"""
        try:
            workout_date = datetime.strptime(date_str, '%Y-%m-%d')
            delta = datetime.now() - workout_date
            return delta.days <= days
        except:
            return False

    def is_available(self) -> dict:
        """Проверяет доступность AI-систем"""
        return {
            "groq": bool(self.groq.api_key),
            "openrouter": bool(self.openrouter.api_key),
            "yandex": bool(self.yandex.api_key),
            "gemini": bool(self.gemini.api_key),  # Включаем если есть ключ
            "deepseek": bool(DEEPSEEK_API_KEY),
            "openai": bool(OPENAI_API_KEY)
        }


# Глобальный экземпляр
ai_coach = AICoachSystem()

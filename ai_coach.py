# -*- coding: utf-8 -*-
"""
AI-система для фитнес-бота
Использует YandexGPT, Gemini, Groq, DeepSeek
"""
import os
import logging
import requests
import base64
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# API ключи из переменных окружения
YANDEX_API_KEY = os.getenv("YANDEX_API_KEY")
YANDEX_FOLDER_ID = os.getenv("YANDEX_FOLDER_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")


# ==================== YANDEX GPT - УМНЫЙ ТРЕНЕР ====================

class YandexCoach:
    """Умный тренер-помощник на YandexGPT"""

    def __init__(self):
        self.api_key = YANDEX_API_KEY
        self.folder_id = YANDEX_FOLDER_ID
        self.model = "gpt://" + self.folder_id + "/yandexgpt/latest"

    async def get_advice(self, user_data: dict, question: str) -> str:
        """
        Даёт персональный совет по тренировке

        Args:
            user_data: Данные пользователя (имя, уровень, цели)
            question: Вопрос пользователя

        Returns:
            str: Ответ от YandexGPT
        """
        if not self.api_key:
            return "⚠️ Yandex API не подключён"

        try:
            # Формируем контекст
            context = self._get_user_context(user_data)

            # Формируем prompt
            prompt = f"""
Ты - опытный фитнес-тренер. Пользователь просит совета.

{context}

Вопрос: {question}

Дай краткий, мотивирующий и практичный ответ (2-3 предложения).
"""

            # Отправляем запрос к YandexGPT
            response = await self._send_request(prompt)

            return response

        except Exception as e:
            logger.error(f"Ошибка YandexGPT: {e}")
            return "⚠️ Не удалось получить совет от тренера. Попробуйте позже."

    def _get_user_context(self, user_data: dict) -> str:
        """Формирует контекст о пользователе"""
        name = user_data.get('first_name', 'Друг')
        level = user_data.get('user_group', 'newbie')
        score = user_data.get('score', 0)

        level_names = {
            'newbie': 'новичок',
            'beginner': 'начинающий',
            'intermediate': 'средний уровень',
            'advanced': 'продвинутый'
        }

        return f"""
Пользователь: {name}
Уровень: {level_names.get(level, 'новичок')}
Очки: {score}
"""

    async def _send_request(self, prompt: str) -> str:
        """Отправляет запрос к YandexGPT API"""
        url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"

        headers = {
            "Authorization": f"Api-Key {self.api_key}",
            "Content-Type": "application/json"
        }

        data = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "text": prompt
                }
            ],
            "temperature": 0.7,
            "max_tokens": 500
        }

        response = requests.post(url, headers=headers, json=data, timeout=10)
        response.raise_for_status()

        result = response.json()

        # Извлекаем ответ
        if 'choices' in result and len(result['choices']) > 0:
            return result['choices'][0]['message']['text']
        else:
            return "Не удалось получить ответ"


# ==================== GEMINI - АНАЛИЗ ФОТО ====================

class GeminiPhotoAnalyzer:
    """Анализ фото тренировок с Gemini"""

    def __init__(self):
        self.api_key = GEMINI_API_KEY

    async def analyze_photo(self, photo_data: bytes, exercise_name: str) -> str:
        """
        Анализирует фото с тренировкой

        Args:
            photo_data: Данные фото (bytes)
            exercise_name: Название упражнения

        Returns:
            str: Анализ техники
        """
        if not self.api_key:
            return "⚠️ Gemini API не подключён"

        try:
            # Конвертируем фото в base64
            base64_image = base64.b64encode(photo_data).decode('utf-8')

            # Формируем prompt
            prompt = f"""
Проанализируй технику выполнения упражнения: "{exercise_name}"

Дай краткий анализ:
1. Правильность позиции (✅ хорошо / ❌ исправить)
2. Конкретные советы по улучшению
3. Оценка от 1 до 10

Ответ в формате:
🔍 Анализ: [текст]
💡 Советы: [текст]
⭐ Оценка: [число]/10
"""

            # Отправляем запрос к Gemini
            response = await self._send_request(base64_image, prompt)

            return response

        except Exception as e:
            logger.error(f"Ошибка Gemini: {e}")
            return "⚠️ Не удалось проанализировать фото. Попробуйте позже."

    async def _send_request(self, base64_image: str, prompt: str) -> str:
        """Отправляет запрос к Gemini API"""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={self.api_key}"

        headers = {
            "Content-Type": "application/json"
        }

        data = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": prompt
                        },
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

        response = requests.post(url, headers=headers, json=data, timeout=15)
        response.raise_for_status()

        result = response.json()

        # Извлекаем ответ
        if 'candidates' in result and len(result['candidates']) > 0:
            return result['candidates'][0]['content']['parts'][0]['text']
        else:
            return "Не удалось получить анализ"


# ==================== GROQ - МГНОВЕННЫЕ РЕКОМЕНДАЦИИ ====================

class GroqRecommender:
    """Мгновенные рекомендации на Groq"""

    def __init__(self):
        self.api_key = GROQ_API_KEY
        self.model = "llama3-70b-8192"  # Быстрая модель

    async def get_quick_recommendation(self, user_data: dict, current_workout: dict) -> str:
        """
        Даёт мгновенную рекомендацию

        Args:
            user_data: Данные пользователя
            current_workout: Текущая тренировка

        Returns:
            str: Рекомендация
        """
        if not self.api_key:
            return "⚠️ Groq API не подключён"

        try:
            # Формируем prompt
            prompt = self._create_recommendation_prompt(user_data, current_workout)

            # Отправляем запрос
            response = await self._send_request(prompt)

            return response

        except Exception as e:
            logger.error(f"Ошибка Groq: {e}")
            return "⚠️ Не удалось получить рекомендацию"

    def _create_recommendation_prompt(self, user_data: dict, current_workout: dict) -> str:
        """Создаёт prompt для рекомендации"""
        name = user_data.get('first_name', 'Друг')
        level = user_data.get('user_group', 'newbie')
        last_workout = current_workout.get('last_exercise', 'Нет данных')
        streak = current_workout.get('streak', 0)

        return f"""
Ты - мотивационный фитнес-коуч. Дай БЫСТРУЮ рекомендацию (1 предложение).

Пользователь: {name}
Уровень: {level}
Последнее упражнение: {last_workout}
Серия тренировок: {streak} дней

Дай мотивирующую рекомендацию на сегодня!
"""

    async def _send_request(self, prompt: str) -> str:
        """Отправляет запрос к Groq API"""
        url = "https://api.groq.com/openai/v1/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        data = {
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "model": self.model,
            "temperature": 0.8,
            "max_tokens": 100
        }

        response = requests.post(url, headers=headers, json=data, timeout=5)
        response.raise_for_status()

        result = response.json()

        if 'choices' in result and len(result['choices']) > 0:
            return result['choices'][0]['message']['content']
        else:
            return "Продолжай в том же духе!"


# ==================== DEEPSEEK - АНАЛИЗ ПРОГРЕССА ====================

class DeepSeekAnalyzer:
    """Анализ прогресса с DeepSeek"""

    def __init__(self):
        self.api_key = DEEPSEEK_API_KEY

    async def analyze_progress(self, user_data: dict, workout_history: list) -> str:
        """
        Анализирует прогресс пользователя

        Args:
            user_data: Данные пользователя
            workout_history: История тренировок

        Returns:
            str: Анализ прогресса
        """
        if not self.api_key:
            return "⚠️ DeepSeek API не подключён"

        try:
            # Формируем prompt
            prompt = self._create_progress_prompt(user_data, workout_history)

            # Отправляем запрос
            response = await self._send_request(prompt)

            return response

        except Exception as e:
            logger.error(f"Ошибка DeepSeek: {e}")
            return "⚠️ Не удалось проанализировать прогресс"

    def _create_progress_prompt(self, user_data: dict, workout_history: list) -> str:
        """Создаёт prompt для анализа прогресса"""
        name = user_data.get('first_name', 'Друг')
        score = user_data.get('score', 0)
        workout_count = len(workout_history)

        # Формируем статистику
        if workout_history:
            last_7_days = sum(1 for w in workout_history if self._is_last_days(w['date'], 7))
            last_30_days = sum(1 for w in workout_history if self._is_last_days(w['date'], 30))
        else:
            last_7_days = 0
            last_30_days = 0

        return f"""
Ты - аналитик фитнес-прогресса. Проанализируй прогресс пользователя.

Имя: {name}
Очки: {score}
Всего тренировок: {workout_count}
За последние 7 дней: {last_7_days} тренировок
За последние 30 дней: {last_30_days} тренировок

Дай анализ:
1. Текущий прогресс (улучшение/стагнация)
2. Сильные стороны
3. Что улучшить
4. Мотивационное сообщение

Ответ краткий, 3-4 предложения.
"""

    def _is_last_days(self, date_str, days):
        """Проверяет, была ли тренировка в последние N дней"""
        try:
            workout_date = datetime.strptime(date_str, '%Y-%m-%d')
            delta = datetime.now() - workout_date
            return delta.days <= days
        except:
            return False

    async def _send_request(self, prompt: str) -> str:
        """Отправляет запрос к DeepSeek API"""
        url = "https://api.deepseek.com/v1/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        data = {
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "model": "deepseek-chat",
            "temperature": 0.7,
            "max_tokens": 500
        }

        response = requests.post(url, headers=headers, json=data, timeout=10)
        response.raise_for_status()

        result = response.json()

        if 'choices' in result and len(result['choices']) > 0:
            return result['choices'][0]['message']['content']
        else:
            return "Продолжай тренироваться регулярно!"


# ==================== ОБЩИЙ ИНТЕРФЕЙС ====================

class AICoachSystem:
    """Общая система AI-тренера"""

    def __init__(self):
        self.yandex = YandexCoach()
        self.gemini = GeminiPhotoAnalyzer()
        self.groq = GroqRecommender()
        self.deepseek = DeepSeekAnalyzer()

    async def get_training_advice(self, user_data: dict, question: str) -> str:
        """Получает совет от YandexGPT"""
        return await self.yandex.get_advice(user_data, question)

    async def analyze_workout_photo(self, photo_data: bytes, exercise_name: str) -> str:
        """Анализирует фото с Gemini"""
        return await self.gemini.analyze_photo(photo_data, exercise_name)

    async def get_quick_recommendation(self, user_data: dict, current_workout: dict) -> str:
        """Получает быструю рекомендацию от Groq"""
        return await self.groq.get_quick_recommendation(user_data, current_workout)

    async def analyze_user_progress(self, user_data: dict, workout_history: list) -> str:
        """Анализирует прогресс с DeepSeek"""
        return await self.deepseek.analyze_progress(user_data, workout_history)

    def is_available(self) -> dict:
        """Проверяет доступность AI-систем"""
        return {
            "yandex": bool(self.yandex.api_key),
            "gemini": bool(self.gemini.api_key),
            "groq": bool(self.groq.api_key),
            "deepseek": bool(self.deepseek.api_key)
        }


# Глобальный экземпляр
ai_coach = AICoachSystem()

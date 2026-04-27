#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Minimal REST API for VK Mini App prototype
Uses existing database functions without modifying current code
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Optional
from pydantic import BaseModel
import logging
import os

# Импортируем СУЩЕСТВУЮЩИЕ функции из database_postgres
from database_postgres import (
    get_user_info,
    get_user_scoreboard_total,
    get_user_coin_balance,
    get_fun_fuel_balance,
    get_exercises,
    get_exercise_by_id,
    get_all_complexes,
    get_challenges_by_status,
    add_workout,
    get_user_workouts,
    get_top_workouts,
    get_user_pvp_stats,
    get_pvp_challenge
)

logger = logging.getLogger(__name__)

# Создаем FastAPI приложение
app = FastAPI(
    title="Fitness Bot API",
    description="REST API for Fitness Bot VK Mini App",
    version="0.1.0"
)

# ==================== STATIC FILES ====================

# Монтируем статические файлы (для vk-bridge.min.js и других)
app.mount("/static", StaticFiles(directory="."), name="static")

# ==================== CORS MIDDLEWARE ====================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене ограничить конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== VK MINI APP HEADERS ====================

class VKMiniAppMiddleware(BaseHTTPMiddleware):
    """Middleware для добавления заголовков VK Mini App"""

    async def dispatch(self, request, call_next):
        response = await call_next(request)

        # УБИРАЕМ restrictive CSP для VK Mini Apps
        response.headers["X-Frame-Options"] = "ALLOWALL"
        # НЕ добавляем CSP - даём VK загружать скрипты

        return response

app.add_middleware(VKMiniAppMiddleware)

# ==================== PYDANTIC MODELS ====================

class WorkoutRequest(BaseModel):
    """Модель для создания тренировки"""
    user_id: int
    exercise_id: Optional[int] = None
    complex_id: Optional[int] = None
    result_value: str
    video_link: Optional[str] = ""
    user_level: Optional[str] = "beginner"
    comment: Optional[str] = None
    metric: Optional[str] = None

# ==================== HEALTH CHECK ====================

@app.get("/", response_class=HTMLResponse)
async def root():
    """VK Mini App главная страница"""
    file_path = os.path.join(os.path.dirname(__file__), "index.html")
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            logger.info(f"Serving index.html, size: {len(content)} bytes")
            return content
    else:
        logger.error("index.html not found!")
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Fitness Bot</title>
        </head>
        <body style="background: #000; color: #fff; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; font-family: Arial, sans-serif;">
            <div>Загрузка...</div>
        </body>
        </html>
        """

@app.get("/health")
async def health():
    """Detailed health check для Render monitoring"""
    return {
        "status": "healthy",
        "service": "fitness-bot-api",
        "version": "0.1.0",
        "timestamp": __import__("time").time()
    }

@app.get("/ping")
async def ping():
    """Простой ping для health checks"""
    return {"pong": True}

@app.get("/test")
async def test_page():
    """Тестовая страница для диагностики VK Bridge"""
    file_path = os.path.join(os.path.dirname(__file__), "test.html")
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    else:
        return "<h1>❌ test.html не найден</h1>"

@app.get("/xd_receiver.html")
async def get_xd_receiver():
    """VK XD Receiver для кросс-доменной коммуникации"""
    file_path = os.path.join(os.path.dirname(__file__), "xd_receiver.html")
    if os.path.exists(file_path):
        return FileResponse(file_path)
    else:
        raise HTTPException(status_code=404, detail="xd_receiver.html not found")

# ==================== USERS ====================

@app.get("/api/users/{user_id}")
async def get_user_profile(user_id: int):
    """
    Получить профиль пользователя

    Использует существующие функции из database_postgres:
    - get_user_info()
    - get_user_scoreboard_total()
    - get_user_coin_balance()
    - get_fun_fuel_balance()
    """
    try:
        # Получаем базовую информацию
        user = get_user_info(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Получаем балансы
        score = get_user_scoreboard_total(user_id)
        coins = get_user_coin_balance(user_id)
        fun_fuel = get_fun_fuel_balance(user_id)

        return {
            "id": user[0],
            "first_name": user[1],
            "username": user[2],
            "level": user[3],
            "balances": {
                "score": score,
                "coins": coins,
                "fun_fuel": fun_fuel
            },
            "registered_date": str(user[4]) if len(user) > 4 else None
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/users/register")
async def register_user(vk_id: int, first_name: str, last_name: str = ""):
    """
    Зарегистрировать или обновить пользователя через VK Mini App

    Создаёт запись пользователя с vk_id или обновляет существующего
    """
    try:
        from database_postgres import register_user as db_register_user

        # Регистрируем пользователя с vk_id
        success = db_register_user(
            telegram_id=None,  # Нет Telegram ID
            first_name=first_name,
            username=None,
            last_name=last_name,
            vk_id=vk_id
        )

        if success:
            return {
                "success": True,
                "message": "User registered successfully",
                "vk_id": vk_id
            }
        else:
            raise HTTPException(status_code=500, detail="Registration failed")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error registering user {vk_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== EXERCISES ====================

@app.get("/api/exercises")
async def list_exercises(active_only: bool = True):
    """
    Получить список упражнений

    Query parameters:
    - active_only: только активные упражнения (default: true)
    """
    try:
        exercises = get_exercises(active_only=active_only)

        result = []
        for ex in exercises:
            result.append({
                "id": ex[0],
                "name": ex[1],
                "metric": ex[2],          # reps, time, weight, distance
                "points": ex[3],
                "week": ex[4],
                "difficulty": ex[5]       # beginner, pro
            })

        return {
            "count": len(result),
            "exercises": result
        }

    except Exception as e:
        logger.error(f"Error getting exercises: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/exercises/{exercise_id}")
async def get_exercise_detail(exercise_id: int):
    """Получить детальную информацию об упражнении"""
    try:
        exercise = get_exercise_by_id(exercise_id)
        if not exercise:
            raise HTTPException(status_code=404, detail="Exercise not found")

        return {
            "id": exercise[0],
            "name": exercise[1],
            "description": exercise[2],
            "metric": exercise[3],
            "points": exercise[4],
            "week": exercise[5],
            "difficulty": exercise[6],
            "active": exercise[7]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting exercise {exercise_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== COMPLEXES ====================

@app.get("/api/complexes")
async def list_complexes():
    """Получить список комплексов упражнений"""
    try:
        complexes = get_all_complexes()

        result = []
        for comp in complexes:
            # Безопасно извлекаем данные с проверкой длины (всего 6 элементов)
            result.append({
                "id": comp[0] if len(comp) > 0 else None,
                "name": comp[1] if len(comp) > 1 else "",
                "description": comp[2] if len(comp) > 2 else "",
                "metric_type": comp[3] if len(comp) > 3 else "count",    # time, count
                "points": comp[4] if len(comp) > 4 else 0,
                "difficulty": comp[5] if len(comp) > 5 else "beginner"
            })

        return {
            "count": len(result),
            "complexes": result
        }

    except Exception as e:
        logger.error(f"Error getting complexes: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== CHALLENGES ====================

@app.get("/api/challenges")
async def list_challenges(status: str = "active"):
    """
    Получить список челленджей

    Query parameters:
    - status: active, completed, all (default: active)
    """
    try:
        # Конвертируем статус в формат для базы
        db_status = None if status == "all" else status

        challenges = get_challenges_by_status(db_status)

        result = []
        for ch in challenges:
            # Безопасно извлекаем данные с проверкой длины
            result.append({
                "id": ch[0] if len(ch) > 0 else None,
                "name": ch[1] if len(ch) > 1 else "",
                "description": ch[2] if len(ch) > 2 else "",
                "metric": ch[3] if len(ch) > 3 else "reps",
                "target_value": ch[4] if len(ch) > 4 else 0,
                "start_date": str(ch[5]) if len(ch) > 5 else None,
                "end_date": str(ch[6]) if len(ch) > 6 else None,
                "bonus_points": ch[7] if len(ch) > 7 else 0,
                "status": ch[8] if len(ch) > 8 else "active"
            })

        return {
            "count": len(result),
            "challenges": result
        }

    except Exception as e:
        logger.error(f"Error getting challenges: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== WORKOUTS ====================

@app.post("/api/workouts")
async def create_workout(workout: WorkoutRequest):
    """
    Записать тренировку

    Требует:
    - user_id: ID пользователя
    - exercise_id или complex_id: ID упражнения или комплекса
    - result_value: результат тренировки
    - video_link: опционально, ссылка на видео
    """
    try:
        # Проверяем что указано либо упражнение либо комплекс
        if not workout.exercise_id and not workout.complex_id:
            raise HTTPException(
                status_code=400,
                detail="Either exercise_id or complex_id must be provided"
            )

        # Добавляем тренировку
        workout_id = add_workout(
            user_id=workout.user_id,
            exercise_id=workout.exercise_id,
            complex_id=workout.complex_id,
            result_value=workout.result_value,
            video_link=workout.video_link,
            user_level=workout.user_level,
            comment=workout.comment,
            metric=workout.metric
        )

        return {
            "success": True,
            "workout_id": workout_id,
            "message": "Тренировка успешно записана"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating workout: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/workouts/{user_id}")
async def get_user_workouts_list(user_id: int, limit: int = 20):
    """
    Получить тренировки пользователя

    Query parameters:
    - limit: количество тренировок (default: 20)
    """
    try:
        workouts = get_user_workouts(user_id, limit=limit)

        result = []
        for wo in workouts:
            result.append({
                "id": wo[0] if len(wo) > 0 else None,
                "user_id": wo[1] if len(wo) > 1 else user_id,
                "exercise_id": wo[2] if len(wo) > 2 else None,
                "complex_id": wo[3] if len(wo) > 3 else None,
                "result_value": wo[4] if len(wo) > 4 else "",
                "video_link": wo[5] if len(wo) > 5 else "",
                "created_at": str(wo[6]) if len(wo) > 6 else None
            })

        return {
            "user_id": user_id,
            "count": len(result),
            "workouts": result
        }

    except Exception as e:
        logger.error(f"Error getting workouts for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/leaderboard")
async def get_leaderboard(limit: int = 10):
    """
    Получить топ пользователей по тренировкам

    Query parameters:
    - limit: количество пользователей (default: 10)
    """
    try:
        top_workouts = get_top_workouts(limit=limit)

        result = []
        for entry in top_workouts:
            result.append({
                "user_id": entry[0] if len(entry) > 0 else None,
                "first_name": entry[1] if len(entry) > 1 else "",
                "username": entry[2] if len(entry) > 2 else "",
                "total_workouts": entry[3] if len(entry) > 3 else 0,
                "total_score": entry[4] if len(entry) > 4 else 0
            })

        return {
            "limit": limit,
            "count": len(result),
            "leaderboard": result
        }

    except Exception as e:
        logger.error(f"Error getting leaderboard: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== PVP ====================

@app.get("/api/pvp/stats/{user_id}")
async def get_pvp_stats(user_id: int):
    """Получить PvP статистику пользователя"""
    try:
        stats = get_user_pvp_stats(user_id)

        return {
            "user_id": user_id,
            "stats": {
                "total": stats.get('total', 0),
                "wins": stats.get('wins', 0),
                "losses": stats.get('losses', 0),
                "draws": stats.get('draws', 0),
                "coins_won": stats.get('coins_won', 0),
                "coins_lost": stats.get('coins_lost', 0)
            },
            "win_rate": round(stats.get('wins', 0) / max(stats.get('total', 1), 1) * 100, 2)
        }

    except Exception as e:
        logger.error(f"Error getting PvP stats for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/pvp/challenge/{challenge_id}")
async def get_pvp_challenge_detail(challenge_id: int):
    """Получить детальную информацию о PvP баттле"""
    try:
        challenge = get_pvp_challenge(challenge_id)
        if not challenge:
            raise HTTPException(status_code=404, detail="PvP challenge not found")

        return {
            "id": challenge[0] if len(challenge) > 0 else None,
            "challenger_id": challenge[1] if len(challenge) > 1 else None,
            "opponent_id": challenge[2] if len(challenge) > 2 else None,
            "status": challenge[3] if len(challenge) > 3 else "unknown",
            "bet": challenge[4] if len(challenge) > 4 else 0,
            "exercise_id": challenge[5] if len(challenge) > 5 else None,
            "created_at": str(challenge[6]) if len(challenge) > 6 else None
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting PvP challenge {challenge_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== MAIN ====================

if __name__ == "__main__":
    import uvicorn
    import os

    # Render (и другие cloud платформы) используют переменную PORT
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")

    logger.info(f"🚀 Starting Fitness Bot API on {host}:{port}")
    logger.info(f"📚 Documentation: http://{host}:{port}/docs")

    # Конфигурация для Render - предотвращение падений
    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="info",
        access_log=True,
        # Увеличиваем лимиты для стабильности
        limit_concurrency=100,
        limit_max_requests=1000,
        timeout_keep_alive=30
    )

    server = uvicorn.Server(config)

    try:
        server.run()
    except KeyboardInterrupt:
        logger.info("👋 Server stopped by user")
    except Exception as e:
        logger.error(f"❌ Server error: {e}")
        raise

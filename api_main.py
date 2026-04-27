#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Minimal REST API for VK Mini App prototype
Uses existing database functions without modifying current code
"""

from fastapi import FastAPI, HTTPException
from typing import Optional
import logging

# Импортируем СУЩЕСТВУЮЩИЕ функции из database_postgres
from database_postgres import (
    get_user_info,
    get_user_scoreboard_total,
    get_user_coin_balance,
    get_fun_fuel_balance,
    get_exercises,
    get_exercise_by_id,
    get_all_complexes,
    get_challenges_by_status
)

logger = logging.getLogger(__name__)

# Создаем FastAPI приложение
app = FastAPI(
    title="Fitness Bot API",
    description="REST API for Fitness Bot VK Mini App",
    version="0.1.0"
)

# ==================== HEALTH CHECK ====================

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "message": "Fitness Bot API",
        "version": "0.1.0",
        "status": "running",
        "endpoints": {
            "users": "/api/users/{user_id}",
            "exercises": "/api/exercises",
            "health": "/health"
        }
    }

@app.get("/health")
async def health():
    """Detailed health check"""
    return {
        "status": "healthy",
        "service": "fitness-bot-api",
        "version": "0.1.0"
    }

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
            result.append({
                "id": comp[0],
                "name": comp[1],
                "description": comp[2],
                "metric_type": comp[3],    # time, count
                "points": comp[4],
                "difficulty": comp[5],
                "active": comp[6]
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
            result.append({
                "id": ch[0],
                "name": ch[1],
                "description": ch[2],
                "metric": ch[3],
                "target_value": ch[4],
                "start_date": str(ch[5]),
                "end_date": str(ch[6]),
                "bonus_points": ch[7],
                "status": ch[8]
            })

        return {
            "count": len(result),
            "challenges": result
        }

    except Exception as e:
        logger.error(f"Error getting challenges: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ==================== MAIN ====================

if __name__ == "__main__":
    import uvicorn

    logger.info("🚀 Starting Fitness Bot API on http://127.0.0.1:8000")
    logger.info("📚 Documentation: http://127.0.0.1:8000/docs")

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
        log_level="info"
    )

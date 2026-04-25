# Добавить в database_postgres.py в конец файла

def get_pvp_setting(key):
    """Получает процент конвертации для типа активности"""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT percent FROM pvp_settings WHERE key = %s", (key,))
    result = cur.fetchone()
    conn.close()
    return result[0] if result else 0

def set_pvp_setting(key, percent):
    """Устанавливает процент конвертации для типа активности"""
    if not (0 <= percent <= 100):
        raise ValueError("Процент должен быть от 0 до 100")

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO pvp_settings (key, percent)
        VALUES (%s, %s)
        ON CONFLICT (key) DO UPDATE SET percent = EXCLUDED.percent
    """, (key, percent))
    conn.commit()
    conn.close()
    return True

def get_all_pvp_settings():
    """Получает все настройки PvP конвертации"""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT key, percent FROM pvp_settings")
    settings = dict(cur.fetchall())
    conn.close()
    return settings

def add_pvp_points_from_workout(user_id, base_points, workout_type='exercise'):
    """
    Начисляет PvP Рейтинг на основе настроек конвертации
    workout_type: 'exercise', 'complex', 'challenge'
    """
    # Определяем какой процент использовать
    key_mapping = {
        'exercise': 'exercise_pvp_percent',
        'complex': 'complex_pvp_percent',
        'challenge': 'challenge_pvp_percent'
    }

    key = key_mapping.get(workout_type, 'exercise_pvp_percent')
    percent = get_pvp_setting(key)

    if percent <= 0:
        return 0  # Конвертация отключена

    # Конвертируем очки
    pvp_points = int(base_points * percent / 100)

    if pvp_points > 0:
        # Добавляем в scoreboard
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO scoreboard (user_id, exercise_id, period_start, period_end, rank, points)
            VALUES (%s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1, %s)
        """, (user_id, -workout_type[:10], pvp_points))  # exercise_id как идентификатор типа
        conn.commit()
        conn.close()

    return pvp_points

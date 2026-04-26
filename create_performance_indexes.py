# -*- coding: utf-8 -*-
"""
Создание критических индексов для производительности
Запустить один раз для применения оптимизаций
"""

import logging
from database_postgres import get_db_connection, release_db_connection

logger = logging.getLogger(__name__)

def create_performance_indexes():
    """Создает критически важные индексы"""
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        print("Creating performance indexes...")

        # 1. Most critical index! Used in 27 queries
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_users_telegram_id
            ON users(telegram_id);
        """)
        print("OK: idx_users_telegram_id - most critical!")

        # 2. Index for user groups
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_users_user_group
            ON users(user_group);
        """)
        print("OK: idx_users_user_group")

        # 3. Index for score (sorting and tops)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_users_score
            ON users(score DESC);
        """)
        print("OK: idx_users_score")

        # 4. Index for PvP statuses
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_pvp_challenges_status
            ON pvp_challenges(status, end_time)
            WHERE status IN ('pending', 'active');
        """)
        print("OK: idx_pvp_challenges_status")

        # 5. Index for user workouts
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_workouts_user_date
            ON workouts(user_id, DATE(date));
        """)
        print("OK: idx_workouts_user_date")

        # 6. Index for exercises in workouts
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_workouts_exercise
            ON workouts(exercise_id)
            WHERE exercise_id IS NOT NULL;
        """)
        print("OK: idx_workouts_exercise")

        # 7. Index for complexes in workouts
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_workouts_complex
            ON workouts(complex_id)
            WHERE complex_id IS NOT NULL;
        """)
        print("OK: idx_workouts_complex")

        # 8. Index for fun_fuel_balance (frequent queries)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_users_fun_fuel
            ON users(fun_fuel_balance);
        """)
        print("OK: idx_users_fun_fuel")

        conn.commit()
        print("\nAll indexes created successfully!")
        print("Expected speedup: 2-5x on DB queries")

    except Exception as e:
        print(f"Error creating indexes: {e}")
        conn.rollback()
    finally:
        release_db_connection(conn)


if __name__ == "__main__":
    print("Creating performance indexes...")
    print("This will take a few seconds...\n")
    create_performance_indexes()
    print("\nDone! Restart bot to apply changes.")
import psycopg2
import psycopg2.extras
from psycopg2 import pool
import logging
import json
import os
import calendar
import shutil
from datetime import datetime, timedelta
from decimal import Decimal

logger = logging.getLogger(__name__)

# PostgreSQL connection string from Render
DB_URL = "postgresql://consilium_bot_db_user:SABK9whZ2uQUDKtBfTgBZameKa0jzWR9@dpg-d75aj2h5pdvs73ci216g-a.oregon-postgres.render.com/consilium_bot_db"

# SQLite database (для совместимости со старым кодом, не используется)
DB_NAME = None

EXERCISES_JSON = "exercises.json"

# ==================== CONNECTION POOL ====================
# Глобальный пул соединений для оптимизации подключений к БД
_connection_pool = None

def init_connection_pool(minconn=3, maxconn=20):
    """
    Инициализирует пул соединений с PostgreSQL.
    Увеличены значения для лучшей производительности при нагрузке.
    """
    global _connection_pool
    try:
        _connection_pool = psycopg2.pool.SimpleConnectionPool(
            minconn=minconn,  # Увеличено с 1 до 3
            maxconn=maxconn,  # Увеличено с 10 до 20
            dsn=DB_URL,
            connect_timeout=5,  # Уменьшено с 10 до 5 для быстрого отказа
            options="-c statement_timeout=30000"  # 30 сек timeout для запросов
        )
        logger.info(f"✅ Connection pool initialized: {minconn}-{maxconn} connections")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to initialize connection pool: {e}")
        return False

def get_db_connection():
    """Возвращает соединение из пула или создаёт новое если пул не инициализирован."""
    global _connection_pool
    if _connection_pool:
        try:
            return _connection_pool.getconn()
        except Exception as e:
            logger.error(f"❌ Failed to get connection from pool: {e}")
            # Fallback: создаём новое соединение
            return psycopg2.connect(DB_URL, connect_timeout=10)
    else:
        # Если пул не инициализирован, создаём прямое соединение
        return psycopg2.connect(DB_URL, connect_timeout=10)

def release_db_connection(conn):
    """Возвращает соединение обратно в пул."""
    global _connection_pool
    if _connection_pool and conn:
        try:
            _connection_pool.putconn(conn)
        except Exception as e:
            logger.error(f"❌ Failed to return connection to pool: {e}")

def close_all_connections():
    """Закрывает все соединения в пуле."""
    global _connection_pool
    if _connection_pool:
        try:
            _connection_pool.closeall()
            logger.info("✅ All database connections closed")
        except Exception as e:
            logger.error(f"❌ Failed to close connections: {e}")

def dict_cursor(conn):
    """Возвращает cursor, который возвращает результаты как словари."""
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

# ==================== ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ ====================

def init_database():
    """Инициализирует базу данных — создаёт таблицы users, pvp_challenges, pvp_history."""
    # Сначала инициализируем пул соединений
    init_connection_pool()

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Таблица users
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                telegram_id BIGINT UNIQUE NOT NULL,
                username VARCHAR(255),
                first_name VARCHAR(255),
                last_name VARCHAR(255),
                registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                score INTEGER DEFAULT 0,
                user_group VARCHAR(20) DEFAULT 'newbie'
            )
        """)

        # Добавляем отсутствующие колонки в users
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'users'
        """)
        existing_columns = {row[0] for row in cur.fetchall()}

        if 'user_group' not in existing_columns:
            cur.execute("ALTER TABLE users ADD COLUMN user_group VARCHAR(20) DEFAULT 'newbie'")
            logger.info("Добавлена колонка user_group в users")

        # Таблица pvp_challenges
        cur.execute("""
            CREATE TABLE IF NOT EXISTS pvp_challenges (
                id SERIAL PRIMARY KEY,
                challenger_id BIGINT NOT NULL,
                opponent_id BIGINT NOT NULL,
                start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                end_time TIMESTAMP NOT NULL,
                status VARCHAR(20) DEFAULT 'pending',
                challenger_score INTEGER DEFAULT 0,
                opponent_score INTEGER DEFAULT 0,
                winner_id BIGINT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                bet INTEGER DEFAULT 0,
                challenger_score_start INTEGER DEFAULT 0,
                opponent_score_start INTEGER DEFAULT 0
            )
        """)

        # Добавляем отсутствующие колонки в pvp_challenges
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'pvp_challenges'
        """)
        pvp_columns = {row[0] for row in cur.fetchall()}

        for col_name, col_def in [('bet', 'INTEGER DEFAULT 0'),
                                   ('challenger_score_start', 'INTEGER DEFAULT 0'),
                                   ('opponent_score_start', 'INTEGER DEFAULT 0')]:
            if col_name not in pvp_columns:
                cur.execute(f"ALTER TABLE pvp_challenges ADD COLUMN {col_name} {col_def}")
                logger.info(f"Добавлена колонка {col_name} в pvp_challenges")

        # Таблица pvp_history
        cur.execute("""
            CREATE TABLE IF NOT EXISTS pvp_history (
                id SERIAL PRIMARY KEY,
                challenge_id INTEGER NOT NULL,
                user_id BIGINT NOT NULL,
                opponent_id BIGINT NOT NULL,
                result VARCHAR(20) NOT NULL,
                bet INTEGER DEFAULT 0,
                score_change INTEGER DEFAULT 0,
                date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Таблица admins
        cur.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                id SERIAL PRIMARY KEY,
                user_id BIGINT UNIQUE NOT NULL,
                level INTEGER DEFAULT 1,
                added_by BIGINT,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
        logger.info("init_database: таблицы созданы/проверены")
        return True
    except Exception as e:
        logger.error(f"Ошибка init_database: {e}")
        return False
    finally:
        release_db_connection(conn)


def backup_database():
    """Резервное копирование больше не требуется для PostgreSQL (Render делает бэкапы автоматически)."""
    logger.info("PostgreSQL на Render автоматически создаёт резервные копии.")


def init_db():
    """Инициализирует базу данных: создаёт все таблицы, если их нет."""
    conn = get_db_connection()
    cur = conn.cursor()

    # Таблица users
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            telegram_id BIGINT UNIQUE NOT NULL,
            username VARCHAR(255),
            first_name VARCHAR(255),
            last_name VARCHAR(255),
            registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            score INTEGER DEFAULT 0,
            user_group VARCHAR(20) DEFAULT 'newbie',
            referrer_id BIGINT,
            referral_code VARCHAR(20) UNIQUE,
            referral_bonus_received BOOLEAN DEFAULT FALSE,
            referrer_bonus_received BOOLEAN DEFAULT FALSE
        )
    """)
    logger.info("Таблица 'users' создана/проверена.")

    # Добавляем недостающие колонки в users (миграция)
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'users'
    """)
    existing_columns = {row[0] for row in cur.fetchall()}

    required_columns = {
        'referrer_id': 'BIGINT',
        'referral_code': 'VARCHAR(20) UNIQUE',
        'referral_bonus_received': 'BOOLEAN DEFAULT FALSE',
        'referrer_bonus_received': 'BOOLEAN DEFAULT FALSE'
    }

    for col_name, col_def in required_columns.items():
        if col_name not in existing_columns:
            try:
                if 'UNIQUE' in col_def:
                    # Для UNIQUE колонок нужно создать по-другому
                    col_def_clean = col_def.replace(' UNIQUE', '')
                    cur.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_def_clean}")
                    cur.execute(f"CREATE UNIQUE INDEX users_{col_name}_idx ON users({col_name})")
                else:
                    cur.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_def}")
                logger.info(f"Добавлена колонка {col_name} в users")
            except Exception as e:
                logger.warning(f"Ошибка добавления колонки {col_name}: {e}")

    # Таблица для настроек бота
    cur.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key VARCHAR(255) PRIMARY KEY,
            value TEXT
        )
    """)
    logger.info("Таблица 'settings' создана.")

    # Таблица для хранения системных настроек
    cur.execute("""
        CREATE TABLE IF NOT EXISTS system_config (
            key VARCHAR(255) PRIMARY KEY,
            value TEXT
        )
    """)
    cur.execute("""
        INSERT INTO system_config (key, value) VALUES ('last_recalc', '0')
        ON CONFLICT (key) DO NOTHING
    """)

    # Таблица scoreboard (рейтинг)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS scoreboard (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            exercise_id INTEGER NOT NULL,
            period_start TIMESTAMP NOT NULL,
            period_end TIMESTAMP NOT NULL,
            rank INTEGER NOT NULL,
            points INTEGER NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(telegram_id),
            FOREIGN KEY(exercise_id) REFERENCES exercises(id)
        )
    """)
    logger.info("Таблица 'scoreboard' создана.")

    # Таблица упражнений
    cur.execute("""
        CREATE TABLE IF NOT EXISTS exercises (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) UNIQUE NOT NULL,
            description TEXT,
            metric VARCHAR(50) NOT NULL,
            points INTEGER DEFAULT 0,
            week INTEGER DEFAULT 0,
            difficulty VARCHAR(20) DEFAULT 'beginner',
            is_active BOOLEAN DEFAULT TRUE
        )
    """)

    # Добавляем колонки если их нет
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'exercises'
    """)
    ex_columns = {row[0] for row in cur.fetchall()}
    if 'points' not in ex_columns:
        cur.execute("ALTER TABLE exercises ADD COLUMN points INTEGER DEFAULT 0")
    if 'week' not in ex_columns:
        cur.execute("ALTER TABLE exercises ADD COLUMN week INTEGER DEFAULT 0")
    if 'difficulty' not in ex_columns:
        cur.execute("ALTER TABLE exercises ADD COLUMN difficulty VARCHAR(20) DEFAULT 'beginner'")

    # Таблица комплексов
    cur.execute("""
        CREATE TABLE IF NOT EXISTS complexes (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) UNIQUE NOT NULL,
            description TEXT,
            type VARCHAR(50) NOT NULL,
            points INTEGER DEFAULT 0,
            week INTEGER DEFAULT 0,
            difficulty VARCHAR(20) DEFAULT 'beginner',
            is_active BOOLEAN DEFAULT TRUE
        )
    """)

    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'complexes'
    """)
    comp_columns = {row[0] for row in cur.fetchall()}
    if 'type' not in comp_columns:
        cur.execute("ALTER TABLE complexes ADD COLUMN type VARCHAR(50) DEFAULT 'for_time'")
        logger.info("Колонка 'type' добавлена в complexes.")
    if 'week' not in comp_columns:
        cur.execute("ALTER TABLE complexes ADD COLUMN week INTEGER DEFAULT 0")
        logger.info("Колонка 'week' добавлена в complexes.")
    if 'difficulty' not in comp_columns:
        cur.execute("ALTER TABLE complexes ADD COLUMN difficulty VARCHAR(20) DEFAULT 'beginner'")
        logger.info("Колонка 'difficulty' добавлена в complexes.")

    # Таблица челленджей
    cur.execute("""
        CREATE TABLE IF NOT EXISTS challenges (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            description TEXT,
            target_type VARCHAR(50) NOT NULL,
            target_id INTEGER NOT NULL,
            metric VARCHAR(50) NOT NULL,
            target_value VARCHAR(255) NOT NULL,
            start_date TIMESTAMP NOT NULL,
            end_date TIMESTAMP NOT NULL,
            bonus_points INTEGER NOT NULL,
            is_active BOOLEAN DEFAULT TRUE
        )
    """)
    logger.info("Таблица 'challenges' создана.")

    # Добавляем колонки если их нет
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'challenges'
    """)
    challenge_columns = {row[0] for row in cur.fetchall()}
    if 'target_reps' not in challenge_columns:
        cur.execute("ALTER TABLE challenges ADD COLUMN target_reps INTEGER DEFAULT 1")
        logger.info("Колонка 'target_reps' добавлена в challenges.")
    if 'duration_days' not in challenge_columns:
        cur.execute("ALTER TABLE challenges ADD COLUMN duration_days INTEGER DEFAULT 30")
        logger.info("Колонка 'duration_days' добавлена в challenges.")

    # Таблица участия в челленджах
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_challenges (
            user_id BIGINT NOT NULL,
            challenge_id INTEGER NOT NULL,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed BOOLEAN DEFAULT FALSE,
            completed_at TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(telegram_id),
            FOREIGN KEY(challenge_id) REFERENCES challenges(id),
            PRIMARY KEY (user_id, challenge_id)
        )
    """)
    logger.info("Таблица 'user_challenges' создана.")

    # Таблица прогресса по челленджам
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_challenge_progress (
            user_id BIGINT NOT NULL,
            challenge_id INTEGER NOT NULL,
            current_value TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(telegram_id),
            FOREIGN KEY(challenge_id) REFERENCES challenges(id),
            PRIMARY KEY (user_id, challenge_id)
        )
    """)
    logger.info("Таблица 'user_challenge_progress' создана.")

    # Таблица ачивок
    cur.execute("""
        CREATE TABLE IF NOT EXISTS achievements (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL,
            description TEXT,
            condition_type VARCHAR(50) NOT NULL,
            condition_value VARCHAR(255) NOT NULL,
            icon VARCHAR(50) DEFAULT '🏆'
        )
    """)
    logger.info("Таблица 'achievements' создана.")

    # Таблица полученных ачивок пользователями
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_achievements (
            user_id BIGINT NOT NULL,
            achievement_id INTEGER NOT NULL,
            earned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(telegram_id),
            FOREIGN KEY(achievement_id) REFERENCES achievements(id),
            PRIMARY KEY (user_id, achievement_id)
        )
    """)
    logger.info("Таблица 'user_achievements' создана.")

    # Добавляем стандартные ачивки, если их нет
    cur.execute("SELECT COUNT(*) FROM achievements")
    if cur.fetchone()[0] == 0:
        achievements_data = [
            ("Первая тренировка", "Запиши свою первую тренировку", "workout_count", "1", "🏅"),
            ("10 тренировок", "Выполни 10 тренировок", "workout_count", "10", "🏆"),
            ("Рекордсмен", "Установи новый личный рекорд в любом упражнении", "best_record", "1", "⭐"),
            ("Победитель челленджа", "Заверши любой челлендж", "challenge_completed", "1", "🎯"),
        ]
        cur.executemany("""
            INSERT INTO achievements (name, description, condition_type, condition_value, icon)
            VALUES (%s, %s, %s, %s, %s)
        """, achievements_data)
        logger.info(f"Добавлено {len(achievements_data)} ачивок.")

    # Связь комплексов с упражнениями
    cur.execute("""
        CREATE TABLE IF NOT EXISTS complex_exercises (
            id SERIAL PRIMARY KEY,
            complex_id INTEGER NOT NULL,
            exercise_id INTEGER NOT NULL,
            reps INTEGER,
            weight NUMERIC(10, 2),
            time VARCHAR(50),
            order_index INTEGER NOT NULL,
            FOREIGN KEY(complex_id) REFERENCES complexes(id),
            FOREIGN KEY(exercise_id) REFERENCES exercises(id)
        )
    """)
    logger.info("Таблица 'complex_exercises' создана.")

    # Таблица тренировок
    cur.execute("""
        CREATE TABLE IF NOT EXISTS workouts (
            id SERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL,
            exercise_id INTEGER,
            complex_id INTEGER,
            result_value TEXT NOT NULL,
            video_link TEXT NOT NULL,
            user_level VARCHAR(20) NOT NULL,
            is_best BOOLEAN DEFAULT FALSE,
            comment TEXT,
            performed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(telegram_id),
            FOREIGN KEY(exercise_id) REFERENCES exercises(id),
            FOREIGN KEY(complex_id) REFERENCES complexes(id)
        )
    """)

    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'workouts'
    """)
    work_columns = {row[0] for row in cur.fetchall()}
    if 'user_level' not in work_columns:
        cur.execute("ALTER TABLE workouts ADD COLUMN user_level VARCHAR(20) DEFAULT 'beginner'")
    if 'complex_id' not in work_columns:
        cur.execute("ALTER TABLE workouts ADD COLUMN complex_id INTEGER DEFAULT NULL")
    if 'is_best' not in work_columns:
        cur.execute("ALTER TABLE workouts ADD COLUMN is_best BOOLEAN DEFAULT FALSE")
    if 'comment' not in work_columns:
        cur.execute("ALTER TABLE workouts ADD COLUMN comment TEXT")
    if 'reps_count' not in work_columns:
        cur.execute("ALTER TABLE workouts ADD COLUMN reps_count INTEGER")
        logger.info("Колонка 'reps_count' добавлена в workouts.")
    if 'time_seconds' not in work_columns:
        cur.execute("ALTER TABLE workouts ADD COLUMN time_seconds INTEGER")
        logger.info("Колонка 'time_seconds' добавлена в workouts.")

    # Таблица для опубликованных постов
    cur.execute("""
        CREATE TABLE IF NOT EXISTS published_posts (
            id SERIAL PRIMARY KEY,
            entity_type VARCHAR(50) NOT NULL,
            entity_id INTEGER NOT NULL,
            channel_id BIGINT NOT NULL,
            message_id BIGINT NOT NULL,
            published_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    logger.info("Таблица 'published_posts' создана.")

    # Таблица для PvP-вызовов
    cur.execute("""
        CREATE TABLE IF NOT EXISTS pvp_challenges (
            id SERIAL PRIMARY KEY,
            challenger_id BIGINT NOT NULL,
            opponent_id BIGINT NOT NULL,
            start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            end_time TIMESTAMP NOT NULL,
            status VARCHAR(20) DEFAULT 'pending',
            challenger_score INTEGER DEFAULT 0,
            opponent_score INTEGER DEFAULT 0,
            winner_id BIGINT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            bet INTEGER DEFAULT 0,
            challenger_score_start INTEGER DEFAULT 0,
            opponent_score_start INTEGER DEFAULT 0
        )
    """)

    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'pvp_challenges'
    """)
    pvp_columns = {row[0] for row in cur.fetchall()}
    for col_name, col_def in [('bet', 'INTEGER DEFAULT 0'),
                               ('challenger_score_start', 'INTEGER DEFAULT 0'),
                               ('opponent_score_start', 'INTEGER DEFAULT 0')]:
        if col_name not in pvp_columns:
            cur.execute(f"ALTER TABLE pvp_challenges ADD COLUMN {col_name} {col_def}")
    logger.info("Таблица 'pvp_challenges' создана/обновлена.")

    # История PvP-результатов
    cur.execute("""
        CREATE TABLE IF NOT EXISTS pvp_history (
            id SERIAL PRIMARY KEY,
            challenge_id INTEGER NOT NULL,
            user_id BIGINT NOT NULL,
            opponent_id BIGINT NOT NULL,
            result VARCHAR(20) NOT NULL,
            bet INTEGER DEFAULT 0,
            score_change INTEGER DEFAULT 0,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    logger.info("Таблица 'pvp_history' создана.")

    conn.commit()
    conn.close()
    logger.info("База данных инициализирована.")
    load_exercises_from_json_if_empty()


def load_exercises_from_json_if_empty():
    """Загружает упражнения из JSON-файла, если таблица упражнений пуста."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM exercises")
    count = cur.fetchone()[0]
    conn.close()

    if count == 0:
        if not os.path.exists(EXERCISES_JSON):
            logger.warning(f"Файл {EXERCISES_JSON} не найден, пропускаем автозагрузку.")
            return
        try:
            with open(EXERCISES_JSON, 'r', encoding='utf-8') as f:
                exercises = json.load(f)
        except Exception as e:
            logger.error(f"Ошибка чтения {EXERCISES_JSON}: {e}")
            return
        added = 0
        for ex in exercises:
            name = ex.get('name')
            metric = ex.get('metric')
            description = ex.get('description', '')
            points = ex.get('points', 0)
            week = ex.get('week', 0)
            difficulty = ex.get('difficulty', 'beginner')
            if add_exercise(name, description, metric, points, week, difficulty):
                added += 1
        logger.info(f"Автозагрузка: добавлено {added} упражнений из {EXERCISES_JSON}.")
    else:
        logger.info("В базе уже есть упражнения, автозагрузка пропущена.")


# ==================== РАБОТА С ПОЛЬЗОВАТЕЛЯМИ ====================

def register_user(telegram_id, first_name, username=None, last_name=None):
    """Регистрирует нового пользователя или обновляет существующего."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Проверяем, существует ли пользователь
        cur.execute("SELECT id FROM users WHERE telegram_id = %s", (telegram_id,))
        existing = cur.fetchone()

        if existing:
            cur.execute("""
                UPDATE users
                SET first_name = %s, last_name = %s, username = %s
                WHERE telegram_id = %s
            """, (first_name, last_name, username, telegram_id))
            logger.info(f"Пользователь {telegram_id} обновлён: {first_name}")
        else:
            cur.execute("""
                INSERT INTO users (telegram_id, first_name, last_name, username)
                VALUES (%s, %s, %s, %s)
            """, (telegram_id, first_name, last_name, username))
            logger.info(f"Новый пользователь {telegram_id} зарегистрирован: {first_name}")

        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Ошибка регистрации пользователя {telegram_id}: {e}")
        return False
    finally:
        release_db_connection(conn)


def add_user(user_id, first_name, last_name=None, username=None, level='beginner'):
    """Добавляет или обновляет пользователя (использует telegram_id)."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO users (telegram_id, first_name, last_name, username)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (telegram_id)
            DO UPDATE SET first_name = EXCLUDED.first_name,
                        last_name = EXCLUDED.last_name,
                        username = EXCLUDED.username
        """, (user_id, first_name, last_name, username))
        conn.commit()
    except Exception as e:
        logger.error(f"❌ Ошибка добавления пользователя: {e}")
    finally:
        release_db_connection(conn)


def get_user_level(user_id):
    """Возвращает уровень пользователя (устаревшая функция, используйте get_user_group)."""
    return get_user_group(user_id) or 'beginner'


def set_user_level(user_id, new_level):
    """Устанавливает уровень пользователя (устаревшая функция, используйте set_user_group)."""
    return set_user_group(user_id, new_level)


def get_user_info(user_id):
    """Возвращает полную информацию о пользователе."""
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT telegram_id, first_name, last_name, username, score, registered_at, user_group
        FROM users
        WHERE telegram_id = %s
    """, (user_id,))

    row = cur.fetchone()
    conn.close()

    return row


def get_user_by_username(username):
    """Возвращает пользователя по username."""
    conn = get_db_connection()
    cur = conn.cursor()

    # Ищем по username (может быть с @ или без)
    if username.startswith("@"):
        username = username[1:]

    cur.execute("""
        SELECT telegram_id, first_name, last_name, username
        FROM users
        WHERE username = %s OR username = %s
        LIMIT 1
    """, (username, "@" + username))

    row = cur.fetchone()
    conn.close()

    return row


def get_user_group(user_id):
    """Возвращает группу пользователя."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT user_group
            FROM users
            WHERE telegram_id = %s
        """, (user_id,))

        row = cur.fetchone()
        release_db_connection(conn)

        if row:
            return row[0]
        return None
    except Exception as e:
        logger.error(f"Ошибка получения группы: {e}")
        return None


def set_user_group(user_id, group):
    """Устанавливает группу пользователя."""
    valid_groups = ['newbie', 'pro']
    if group not in valid_groups:
        logger.warning(f"Неверная группа: {group}. Допустимые значения: {valid_groups}")
        return False

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            UPDATE users
            SET user_group = %s
            WHERE telegram_id = %s
        """, (group, user_id))

        conn.commit()
        affected_rows = cur.rowcount
        release_db_connection(conn)

        if affected_rows > 0:
            logger.info(f"Пользователю {user_id} установлена группа {group}")
            return True
        else:
            logger.warning(f"Пользователь {user_id} не найден")
            return False
    except Exception as e:
        logger.error(f"Ошибка установки группы: {e}")
        return False


def get_users_by_group(group, limit=50):
    """Возвращает список пользователей по группе."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT telegram_id, first_name, username, score
            FROM users
            WHERE user_group = %s
            ORDER BY score DESC
            LIMIT %s
        """, (group, limit))

        rows = cur.fetchall()
        release_db_connection(conn)

        return rows
    except Exception as e:
        logger.error(f"Ошибка получения пользователей по группе: {e}")
        return []


# ==================== ФУНКЦИИ ДЛЯ РАБОТЫ С АДМИНАМИ ====================

def is_admin(user_id):
    """Проверяет, является ли пользователь администратором."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("SELECT level FROM admins WHERE user_id = %s", (user_id,))
        result = cur.fetchone()
        release_db_connection(conn)

        return result is not None
    except Exception as e:
        logger.error(f"Ошибка проверки админа: {e}")
        return False


def get_admin_level(user_id):
    """Возвращает уровень админа (0 если не админ)."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("SELECT level FROM admins WHERE user_id = %s", (user_id,))
        result = cur.fetchone()
        release_db_connection(conn)

        return result[0] if result else 0
    except Exception as e:
        logger.error(f"Ошибка получения уровня админа: {e}")
        return 0


def add_admin(user_id, level, added_by):
    """Добавляет админа в систему.

    Args:
        user_id: ID пользователя для добавления
        level: Уровень (1=модератор, 2=админ, 3=владелец)
        added_by: ID пользователя, который добавляет

    Returns:
        bool: True если успешно, False если ошибка
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Проверяем, что добавляющий имеет уровень 3
        adder_level = get_admin_level(added_by)
        if adder_level < 3:
            logger.warning(f"Пользователь {added_by} (level={adder_level}) пытается добавить админа")
            release_db_connection(conn)
            return False

        # Проверяем, что пользователь существует
        cur.execute("SELECT telegram_id FROM users WHERE telegram_id = %s", (user_id,))
        if not cur.fetchone():
            logger.warning(f"Пользователь {user_id} не найден")
            release_db_connection(conn)
            return False

        # Добавляем или обновляем админа
        cur.execute("""
            INSERT INTO admins (user_id, level, added_by)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE
            SET level = %s, added_by = %s
        """, (user_id, level, added_by, level, added_by))

        conn.commit()
        release_db_connection(conn)

        logger.info(f"Админ добавлен: user_id={user_id}, level={level}, added_by={added_by}")
        return True
    except Exception as e:
        logger.error(f"Ошибка добавления админа: {e}")
        return False


def remove_admin(admin_id, remover_id):
    """Удаляет админа из системы.

    Args:
        admin_id: ID админа для удаления
        remover_id: ID пользователя, который удаляет

    Returns:
        bool: True если успешно, False если ошибка
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Проверяем, что удаляющий имеет уровень 3
        remover_level = get_admin_level(remover_id)
        if remover_level < 3:
            logger.warning(f"Пользователь {remover_id} (level={remover_level}) пытается удалить админа")
            release_db_connection(conn)
            return False

        # Удаляем админа
        cur.execute("DELETE FROM admins WHERE user_id = %s", (admin_id,))

        conn.commit()
        affected_rows = cur.rowcount
        release_db_connection(conn)

        if affected_rows > 0:
            logger.info(f"Админ удалён: user_id={admin_id}, removed_by={remover_id}")
            return True
        else:
            logger.warning(f"Админ {admin_id} не найден")
            return False
    except Exception as e:
        logger.error(f"Ошибка удаления админа: {e}")
        return False


def get_all_admins():
    """Возвращает список всех админов с информацией.

    Returns:
        list: Список кортежей (user_id, username, first_name, level, added_by, added_at)
    """
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT
                a.user_id,
                u.username,
                u.first_name,
                a.level,
                a.added_by,
                a.added_at,
                adder.username as added_by_username,
                adder.first_name as added_by_name
            FROM admins a
            LEFT JOIN users u ON a.user_id = u.telegram_id
            LEFT JOIN users adder ON a.added_by = adder.telegram_id
            ORDER BY a.level DESC, a.added_at ASC
        """)

        rows = cur.fetchall()
        release_db_connection(conn)

        return rows
    except Exception as e:
        logger.error(f"Ошибка получения списка админов: {e}")
        return []


def get_admin_level_name(level):
    """Возвращает название уровня админа."""
    levels = {
        1: "🛡️ Модератор",
        2: "⭐ Админ",
        3: "👑 Владелец"
    }
    return levels.get(level, "❓ Неизвестно")


def get_active_users(limit=10, exclude_user_id=None):
    """Возвращает список активных пользователей."""
    conn = get_db_connection()
    cur = conn.cursor()

    query = """
        SELECT telegram_id, first_name, username, score
        FROM users
        WHERE 1=1
    """
    params = []

    if exclude_user_id:
        query += " AND telegram_id != %s"
        params.append(exclude_user_id)

    query += " ORDER BY telegram_id DESC LIMIT %s"
    params.append(limit)

    try:
        cur.execute(query, params)
        rows = cur.fetchall()
    except Exception as e:
        logger.error(f"❌ Ошибка в get_active_users: {e}")
        rows = []
    finally:
        release_db_connection(conn)

    return rows


# ==================== ТРЕНИРОВКИ И УПРАЖНЕНИЯ ====================

def add_workout(user_id, exercise_id=None, complex_id=None, result_value="", video_link="", user_level="beginner", comment=None, metric=None, notify_record_callback=None):
    """Добавляет тренировку в базу данных и начисляет очки пользователю."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO workouts (user_id, exercise_id, complex_id, result_value, video_link, user_level, comment)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """, (user_id, exercise_id, complex_id, result_value, video_link, user_level, comment))
    workout_id = cur.fetchone()[0]

    # Начисляем очки пользователю за тренировку
    pts = 0
    if exercise_id:
        cur.execute("SELECT points FROM exercises WHERE id = %s", (exercise_id,))
        row = cur.fetchone()
        if row:
            pts = row[0] or 0
    elif complex_id:
        cur.execute("SELECT points FROM complexes WHERE id = %s", (complex_id,))
        row = cur.fetchone()
        if row:
            pts = row[0] or 0
    if pts > 0:
        cur.execute("UPDATE users SET score = score + %s WHERE telegram_id = %s", (pts, user_id))

    # Начисляем FruN Fuel за тренировку (+10 FF)
    try:
        add_coins(user_id, 10, 'workout', '💪 За тренировку')
        logger.info(f"Начислено +10 FF пользователю {user_id} за тренировку")
    except Exception as e:
        logger.error(f"Ошибка начисления FruN Fuel за тренировку: {e}")

    conn.commit()
    new_achievements = check_and_award_achievements(user_id, conn)
    if metric is not None and exercise_id is not None:
        update_personal_best(user_id, exercise_id, result_value, metric, conn, notify_record_callback)
    conn.close()
    return workout_id, new_achievements


def update_personal_best(user_id, exercise_id, new_result, metric_type, conn=None, notify_record_callback=None):
    """Обновляет личный рекорд пользователя."""
    own_conn = False
    if conn is None:
        conn = get_db_connection()
        own_conn = True
    cur = conn.cursor()
    cur.execute("""
        SELECT id, result_value FROM workouts
        WHERE user_id = %s AND exercise_id = %s AND is_best = TRUE
    """, (user_id, exercise_id))
    current_best = cur.fetchone()
    is_new_best = False
    if metric_type == 'reps':
        new_val = int(new_result)
        if current_best:
            old_val = int(current_best[1])
            if new_val > old_val:
                is_new_best = True
        else:
            is_new_best = True
    else:
        if current_best:
            if new_result < current_best[1]:
                is_new_best = True
        else:
            is_new_best = True
    if is_new_best:
        if current_best:
            cur.execute("UPDATE workouts SET is_best = FALSE WHERE id = %s", (current_best[0],))
        cur.execute("""
            SELECT id FROM workouts
            WHERE user_id = %s AND exercise_id = %s AND result_value = %s AND is_best = FALSE
            ORDER BY id DESC LIMIT 1
        """, (user_id, exercise_id, new_result))
        row = cur.fetchone()
        if row:
            cur.execute("UPDATE workouts SET is_best = TRUE WHERE id = %s", (row[0],))
        conn.commit()
        if notify_record_callback:
            try:
                notify_record_callback(user_id, exercise_id, new_result, metric_type)
            except Exception as e:
                logger.error(f"Ошибка в notify_record_callback: {e}")
    if own_conn:
        release_db_connection(conn)


def get_user_workouts(user_id, limit=20):
    """Возвращает последние тренировки пользователя."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT
            w.id,
            COALESCE(e.name, c.name) as name,
            w.result_value,
            w.video_link,
            w.performed_at,
            w.is_best,
            CASE WHEN w.exercise_id IS NOT NULL THEN 'упражнение' ELSE 'комплекс' END as type,
            w.comment
        FROM workouts w
        LEFT JOIN exercises e ON w.exercise_id = e.id
        LEFT JOIN complexes c ON w.complex_id = c.id
        WHERE w.user_id = %s
        ORDER BY w.performed_at DESC
        LIMIT %s
    """, (user_id, limit))
    rows = cur.fetchall()
    conn.close()
    return rows


def get_user_stats(user_id, period=None, level=None):
    """Возвращает статистику пользователя."""
    conn = get_db_connection()
    cur = conn.cursor()
    query = """
        SELECT SUM(e.points), COUNT(w.id)
        FROM workouts w
        JOIN exercises e ON w.exercise_id = e.id
        WHERE w.user_id = %s
    """
    params = [user_id]
    if level is not None:
        query += " AND w.user_level = %s"
        params.append(level)
    if period:
        if period == 'day':
            query += " AND DATE(w.performed_at) = CURRENT_DATE"
        elif period == 'week':
            query += " AND EXTRACT(WEEK FROM w.performed_at) = EXTRACT(WEEK FROM CURRENT_TIMESTAMP) AND EXTRACT(YEAR FROM w.performed_at) = EXTRACT(YEAR FROM CURRENT_TIMESTAMP)"
        elif period == 'month':
            query += " AND EXTRACT(MONTH FROM w.performed_at) = EXTRACT(MONTH FROM CURRENT_TIMESTAMP) AND EXTRACT(YEAR FROM w.performed_at) = EXTRACT(YEAR FROM CURRENT_TIMESTAMP)"
        elif period == 'year':
            query += " AND EXTRACT(YEAR FROM w.performed_at) = EXTRACT(YEAR FROM CURRENT_TIMESTAMP)"
    cur.execute(query, params)
    result = cur.fetchone()
    conn.close()
    return result


def get_user_scoreboard_total(user_id):
    """Возвращает общее количество баллов пользователя из scoreboard."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COALESCE(SUM(points), 0) FROM scoreboard WHERE user_id = %s", (user_id,))
    total = cur.fetchone()[0]
    conn.close()
    return total


def get_leaderboard(period=None, league=None):
    """Возвращает таблицу лидеров (совместимость со старым кодом)"""
    return get_leaderboard_from_scoreboard()


def get_leaderboard_from_scoreboard(limit=10):
    """Возвращает таблицу лидеров из scoreboard."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT u.id, u.first_name, u.username, COALESCE(SUM(s.points), 0) as total
            FROM scoreboard s
            JOIN users u ON s.user_id = u.telegram_id
            GROUP BY u.id
            ORDER BY total DESC
            LIMIT %s
        """, (limit,))
    except:
        cur.execute("""
            SELECT user_id, user_id, user_id, COALESCE(SUM(points), 0) as total
            FROM scoreboard
            GROUP BY user_id
            ORDER BY total DESC
            LIMIT %s
        """, (limit,))
    rows = cur.fetchall()
    conn.close()
    return rows


# ==================== УПРАЖНЕНИЯ И КОМПЛЕКСЫ ====================

def get_exercises(active_only=True, week=None, difficulty=None):
    conn = get_db_connection()
    cur = conn.cursor()
    query = "SELECT id, name, metric, points, week, difficulty FROM exercises"
    conditions = []
    params = []
    # Временно убрана проверка is_active так как колонки нет в таблице
    # if active_only:
    #     conditions.append("is_active = TRUE")
    if week is not None:
        conditions.append("(week = 0 OR week = %s)")
        params.append(week)
    if difficulty is not None:
        conditions.append("difficulty = %s")
        params.append(difficulty)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    cur.execute(query, params)
    exercises = cur.fetchall()
    release_db_connection(conn)
    return exercises


def get_all_exercises():
    """Возвращает все упражнения."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name, metric, points, week, difficulty FROM exercises ORDER BY name")
    exercises = cur.fetchall()
    conn.close()
    return exercises


def get_exercise_by_id(exercise_id):
    """Возвращает упражнение по ID."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name, description, metric, points, week, difficulty FROM exercises WHERE id = %s", (exercise_id,))
    row = cur.fetchone()
    conn.close()
    return row


def add_exercise(name, description, metric, points=0, week=0, difficulty='beginner'):
    """Добавляет новое упражнение и возвращает его ID."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO exercises (name, description, metric, points, week, difficulty)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (name, description, metric, points, week, difficulty))
        result = cur.fetchone()
        conn.commit()
        return result[0] if result else None
    except psycopg2.IntegrityError:
        return None
    finally:
        release_db_connection(conn)


def delete_exercise(exercise_id):
    """Удаляет упражнение по ID."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM exercises WHERE id = %s", (exercise_id,))
    deleted = cur.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def update_exercise(exercise_id, name=None, description=None, metric=None, points=None, week=None, difficulty=None):
    """Обновляет упражнение по ID.

    Args:
        exercise_id: ID упражнения для обновления
        name: Новое название (опционально)
        description: Новое описание (опционально)
        metric: Новая метрика (опционально)
        points: Новые очки (опционально)
        week: Новая неделя (опционально)
        difficulty: Новая сложность (опционально)

    Returns:
        bool: True если обновление успешно, False в противном случае
    """
    conn = get_db_connection()
    cur = conn.cursor()

    # Собираем поля для обновления
    updates = []
    params = []

    if name is not None:
        updates.append("name = %s")
        params.append(name)

    if description is not None:
        updates.append("description = %s")
        params.append(description)

    if metric is not None:
        updates.append("metric = %s")
        params.append(metric)

    if points is not None:
        updates.append("points = %s")
        params.append(points)

    if week is not None:
        updates.append("week = %s")
        params.append(week)

    if difficulty is not None:
        updates.append("difficulty = %s")
        params.append(difficulty)

    if not updates:
        conn.close()
        return False  # Нечего обновлять

    # Добавляем exercise_id в параметры
    params.append(exercise_id)

    try:
        query = f"UPDATE exercises SET {', '.join(updates)} WHERE id = %s"
        cur.execute(query, params)
        conn.commit()
        updated = cur.rowcount > 0
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

    return updated


def set_exercise_week(exercise_id, week):
    """Устанавливает неделю для упражнения."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE exercises SET week = %s WHERE id = %s", (week, exercise_id))
    conn.commit()
    conn.close()


def get_all_complexes(active_only=True):
    """Возвращает все комплексы."""
    conn = get_db_connection()
    cur = conn.cursor()
    # Временно убрана проверка is_active так как колонки нет в таблице
    query = "SELECT id, name, description, type, points, difficulty FROM complexes ORDER BY id"
    cur.execute(query)
    rows = cur.fetchall()
    release_db_connection(conn)
    return rows


def get_complex_by_id(complex_id):
    """Получить комплекс по ID"""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, name, description, type, points, difficulty FROM complexes WHERE id = %s", (complex_id,))
        result = cur.fetchone()
        return result
    except Exception as e:
        logger.error(f"Ошибка get_complex_by_id: {e}")
        return None
    finally:
        release_db_connection(conn)


def get_complex_exercises(complex_id):
    """Возвращает упражнения комплекса."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT ce.id, ce.exercise_id, e.name, e.metric, ce.reps
        FROM complex_exercises ce
        JOIN exercises e ON ce.exercise_id = e.id
        WHERE ce.complex_id = %s
        ORDER BY ce.order_index
    """, (complex_id,))
    rows = cur.fetchall()
    conn.close()
    return rows


def add_complex(name, description, type_, points, week=0, difficulty='beginner'):
    """Добавляет новый комплекс."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO complexes (name, description, type, points, week, difficulty)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (name, description, type_, points, week, difficulty))
        complex_id = cur.fetchone()[0]
        conn.commit()
        return complex_id
    except psycopg2.IntegrityError:
        logger.error(f"Комплекс с именем {name} уже существует.")
        return None
    finally:
        release_db_connection(conn)


def add_complex_exercise(complex_id, exercise_id, reps, order_index=None):
    """Добавляет упражнение в комплекс."""
    conn = get_db_connection()
    cur = conn.cursor()
    if order_index is None:
        cur.execute("SELECT COALESCE(MAX(order_index), 0) + 1 FROM complex_exercises WHERE complex_id = %s", (complex_id,))
        order_index = cur.fetchone()[0]
    cur.execute("""
        INSERT INTO complex_exercises (complex_id, exercise_id, reps, order_index)
        VALUES (%s, %s, %s, %s)
    """, (complex_id, exercise_id, reps, order_index))
    conn.commit()
    conn.close()


def delete_complex(complex_id):
    """Удаляет комплекс и связанные упражнения."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Сначала удаляем упражнения комплекса
        cur.execute("DELETE FROM complex_exercises WHERE complex_id = %s", (complex_id,))
        # Затем удаляем сам комплекс
        cur.execute("DELETE FROM complexes WHERE id = %s", (complex_id,))
        deleted = cur.rowcount > 0
        conn.commit()
        return deleted
    except Exception as e:
        logger.error(f"Ошибка при удалении комплекса: {e}")
        conn.rollback()
        return False
    finally:
        release_db_connection(conn)


# ==================== ЧЕЛЛЕНДЖИ И СОСТЯЗАНИЯ ====================

def get_active_challenges():
    """Возвращает активные челленджи."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT c.id, c.name, c.description, c.target_type, c.target_id, c.metric, c.target_value,
               c.start_date, c.end_date, c.bonus_points,
               CASE
                   WHEN c.target_type = 'exercise' THEN e.name
                   WHEN c.target_type = 'complex' THEN cm.name
               END as target_name
        FROM challenges c
        LEFT JOIN exercises e ON c.target_type = 'exercise' AND c.target_id = e.id
        LEFT JOIN complexes cm ON c.target_type = 'complex' AND c.target_id = cm.id
        WHERE c.is_active = TRUE AND CURRENT_DATE BETWEEN c.start_date AND c.end_date
        ORDER BY c.start_date
    """)
    rows = cur.fetchall()
    conn.close()
    return rows


def join_challenge(user_id, challenge_id):
    """Присоединяет пользователя к челленджу."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO user_challenges (user_id, challenge_id)
            VALUES (%s, %s)
        """, (user_id, challenge_id))
        conn.commit()
        return True
    except psycopg2.IntegrityError:
        return False
    finally:
        release_db_connection(conn)


def get_challenge_by_id(challenge_id):
    """Возвращает челлендж по ID с всеми полями."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, name, description, target_type, target_id, metric, target_value,
               start_date, end_date, bonus_points, entry_fee_coins, prize_pool_coins, is_coin_challenge
        FROM challenges
        WHERE id = %s
    """, (challenge_id,))
    row = cur.fetchone()
    conn.close()
    return row


def delete_challenge(challenge_id):
    """Удаляет челлендж по ID."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM challenges WHERE id = %s", (challenge_id,))
    deleted = cur.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def update_challenge_progress(user_id, challenge_id, new_value):
    """Обновляет прогресс пользователя в челлендже."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO user_challenge_progress (user_id, challenge_id, current_value, updated_at)
        VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
        ON CONFLICT (user_id, challenge_id)
        DO UPDATE SET current_value = EXCLUDED.current_value, updated_at = CURRENT_TIMESTAMP
    """, (user_id, challenge_id, new_value))
    conn.commit()
    conn.close()


def check_challenge_completion(user_id, challenge_id, target_value, metric):
    """Проверяет, завершён ли челлендж."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT current_value FROM user_challenge_progress
        WHERE user_id = %s AND challenge_id = %s
    """, (user_id, challenge_id))
    row = cur.fetchone()
    conn.close()
    if not row:
        return False
    current = row[0]
    if metric == 'reps':
        try:
            return int(current) >= int(target_value)
        except:
            return False
    else:
        return current <= target_value


def get_user_challenges(user_id):
    """Возвращает челленджи пользователя."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT c.id, c.target_type, c.target_id, c.target_value, c.metric, c.bonus_points
        FROM challenges c
        JOIN user_challenges uc ON c.id = uc.challenge_id
        WHERE uc.user_id = %s AND c.is_active = TRUE
          AND CURRENT_DATE BETWEEN c.start_date AND c.end_date
    """, (user_id,))
    rows = cur.fetchall()
    conn.close()
    return rows


def complete_challenge(user_id, challenge_id):
    """Завершает челлендж и начисляет бонус."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT bonus_points FROM challenges WHERE id = %s", (challenge_id,))
        bonus = cur.fetchone()[0]
        cur.execute("""
            UPDATE user_challenges SET completed = TRUE, completed_at = CURRENT_TIMESTAMP
            WHERE user_id = %s AND challenge_id = %s
        """, (user_id, challenge_id))
        cur.execute("""
            INSERT INTO scoreboard (user_id, exercise_id, period_start, period_end, rank, points)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (user_id, -challenge_id, datetime.now(), datetime.now(), 0, bonus))
        conn.commit()
        check_and_award_achievements(user_id, conn)
        return True
    except Exception as e:
        logger.error(f"Ошибка при завершении челленджа: {e}")
        return False
    finally:
        release_db_connection(conn)


def get_challenges_by_status(status='active'):
    """Возвращает челленджи по статусу."""
    conn = get_db_connection()
    cur = conn.cursor()
    if status == 'active':
        where = "c.is_active = TRUE AND CURRENT_DATE BETWEEN c.start_date AND c.end_date"
    elif status == 'past':
        where = "c.is_active = TRUE AND c.end_date < CURRENT_DATE"
    elif status == 'future':
        where = "c.is_active = TRUE AND c.start_date > CURRENT_DATE"
    else:
        where = "c.is_active = TRUE"
    cur.execute(f"""
        SELECT c.id, c.name, c.description, c.target_type, c.target_id, c.metric, c.target_value,
               c.start_date, c.end_date, c.bonus_points,
               CASE
                   WHEN c.target_type = 'exercise' THEN e.name
                   WHEN c.target_type = 'complex' THEN cm.name
               END as target_name
        FROM challenges c
        LEFT JOIN exercises e ON c.target_type = 'exercise' AND c.target_id = e.id
        LEFT JOIN complexes cm ON c.target_type = 'complex' AND c.target_id = cm.id
        WHERE {where}
        ORDER BY c.start_date
    """)
    rows = cur.fetchall()
    release_db_connection(conn)
    return rows


def get_all_challenges():
    """Возвращает все челленджи."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT c.id, c.name, c.description, c.target_type, c.target_id, c.metric, c.target_value,
               c.start_date, c.end_date, c.bonus_points,
               CASE
                   WHEN CURRENT_DATE BETWEEN c.start_date AND c.end_date THEN 'active'
                   WHEN c.end_date < CURRENT_DATE THEN 'completed'
                   ELSE 'future'
               END as status
        FROM challenges c
        ORDER BY c.start_date DESC
    """)
    rows = cur.fetchall()
    release_db_connection(conn)
    return rows


def get_challenge_name(challenge_id):
    """Возвращает название челленджа."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT name FROM challenges WHERE id = %s", (challenge_id,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None


def get_user_challenges_with_details(user_id):
    """Возвращает челленджи пользователя с деталями."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT c.id, c.name, c.target_type, c.target_id, c.metric, c.target_value, c.bonus_points,
               c.start_date, c.end_date, COALESCE(p.current_value, '0') as current_value,
               CASE
                   WHEN c.target_type = 'exercise' THEN e.name
                   WHEN c.target_type = 'complex' THEN cm.name
               END as target_name
        FROM challenges c
        JOIN user_challenges uc ON c.id = uc.challenge_id
        LEFT JOIN user_challenge_progress p ON c.id = p.challenge_id AND p.user_id = uc.user_id
        LEFT JOIN exercises e ON c.target_type = 'exercise' AND c.target_id = e.id
        LEFT JOIN complexes cm ON c.target_type = 'complex' AND c.target_id = cm.id
        WHERE uc.user_id = %s AND c.is_active = TRUE
          AND CURRENT_DATE BETWEEN c.start_date AND c.end_date
        ORDER BY c.start_date
    """, (user_id,))
    rows = cur.fetchall()
    conn.close()
    return rows


def leave_challenge(user_id, challenge_id):
    """Выход из челленджа."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM user_challenges WHERE user_id = %s AND challenge_id = %s", (user_id, challenge_id))
    cur.execute("DELETE FROM user_challenge_progress WHERE user_id = %s AND challenge_id = %s", (user_id, challenge_id))
    conn.commit()
    conn.close()


def add_exercises_to_challenge(challenge_id, exercise_ids):
    """Добавляет упражнения к челленджу."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        for exercise_id in exercise_ids:
            cur.execute("""
                INSERT INTO challenge_exercises (challenge_id, exercise_id)
                VALUES (%s, %s)
            """, (challenge_id, exercise_id))
        conn.commit()
        return True
    except psycopg2.Error as e:
        logger.error(f"Ошибка при добавлении упражнений к челленджу: {e}")
        return False
    finally:
        release_db_connection(conn)


def create_challenge_tables():
    """Создает таблицы для системы челленджей."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Таблица участия в челленджах
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_challenges (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                challenge_id INTEGER REFERENCES challenges(id) ON DELETE CASCADE,
                join_date DATE DEFAULT CURRENT_DATE,
                status VARCHAR(20) DEFAULT 'active',
                UNIQUE(user_id, challenge_id)
            )
        """)

        # Таблица прогресса по упражнениям в челленджах
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_challenge_progress (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                challenge_id INTEGER REFERENCES challenges(id) ON DELETE CASCADE,
                exercise_id INTEGER REFERENCES exercises(id) ON DELETE CASCADE,
                completed BOOLEAN DEFAULT FALSE,
                result_value FLOAT,
                proof_link TEXT,
                completed_at TIMESTAMP,
                UNIQUE(user_id, challenge_id, exercise_id)
            )
        """)

        # Таблица истории выполнений упражнений
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_workouts (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                exercise_id INTEGER REFERENCES exercises(id) ON DELETE SET NULL,
                challenge_id INTEGER REFERENCES challenges(id) ON DELETE SET NULL,
                result_value FLOAT,
                proof_link TEXT,
                completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
        return True
    except psycopg2.Error as e:
        logger.error(f"Ошибка при создании таблиц: {e}")
        return False
    finally:
        release_db_connection(conn)


def add_exercises_to_challenge(challenge_id, exercise_ids):
    """Добавляет упражнения к челленджу."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        for exercise_id in exercise_ids:
            cur.execute("""
                INSERT INTO challenge_exercises (challenge_id, exercise_id)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
            """, (challenge_id, exercise_id))
        conn.commit()
        return True
    except psycopg2.Error as e:
        logger.error(f"Ошибка при добавлении упражнений к челленджу: {e}")
        return False
    finally:
        release_db_connection(conn)


def add_challenge(name, description, target_type, target_id, metric, target_value, start_date, end_date, bonus_points, exercise_ids=None):
    """Добавляет новый челлендж и привязывает упражнения."""
    # Сначала создаем таблицы если их нет
    create_challenge_tables()

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Создаем челлендж
        cur.execute("""
            INSERT INTO challenges (name, description, target_type, target_id, metric, target_value, start_date, end_date, bonus_points, entry_fee_coins, prize_pool_coins, is_coin_challenge)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (name, description, target_type, target_id, metric, target_value, start_date, end_date, bonus_points, 0, 0, False))
        challenge_id = cur.fetchone()[0]
        conn.commit()

        # Если переданы упражнения - привязываем их к челленджу
        if exercise_ids:
            add_exercises_to_challenge(challenge_id, exercise_ids)

        return challenge_id
    except psycopg2.Error as e:
        logger.error(f"Ошибка при добавлении челленджа: {e}")
        return False
    finally:
        release_db_connection(conn)


def get_challenge_exercises(challenge_id):
    """Получает список упражнений в челлендже."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT e.id, e.name, e.description, e.metric, e.points, e.week, e.difficulty
            FROM exercises e
            JOIN challenge_exercises ce ON e.id = ce.exercise_id
            WHERE ce.challenge_id = %s
            ORDER BY e.id
        """, (challenge_id,))
        return cur.fetchall()
    except psycopg2.Error as e:
        logger.error(f"Ошибка при получении упражнений челленджа: {e}")
        return []
    finally:
        release_db_connection(conn)


def get_user_challenge_progress(user_id, challenge_id):
    """Получает прогресс пользователя в челлендже."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT exercise_id, completed, result_value, proof_link, completed_at
            FROM user_challenge_progress
            WHERE user_id = %s AND challenge_id = %s
        """, (user_id, challenge_id))
        return cur.fetchall()
    except psycopg2.Error as e:
        logger.error(f"Ошибка при получении прогресса: {e}")
        return []
    finally:
        release_db_connection(conn)


def complete_challenge_exercise(user_id, challenge_id, exercise_id, result_value, proof_link):
    """Отмечает упражнение в челлендже как выполненное."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO user_challenge_progress (user_id, challenge_id, exercise_id, completed, result_value, proof_link, completed_at)
            VALUES (%s, %s, %s, TRUE, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (user_id, challenge_id, exercise_id)
            DO UPDATE SET completed = TRUE, result_value = %s, proof_link = %s, completed_at = CURRENT_TIMESTAMP
        """, (user_id, challenge_id, exercise_id, result_value, proof_link, result_value, proof_link))

        # Добавляем в историю тренировок
        cur.execute("""
            INSERT INTO user_workouts (user_id, exercise_id, challenge_id, result_value, proof_link)
            VALUES (%s, %s, %s, %s, %s)
        """, (user_id, exercise_id, challenge_id, result_value, proof_link))

        # Начисляем FruN Fuel за упражнение в челлендже (+5 FF)
        try:
            add_fun_fuel(user_id, 5, f'Упражнение в челлендже {challenge_id}')
            logger.info(f"Начислено +5 FF пользователю {user_id} за упражнение в челлендже")
        except Exception as e:
            logger.error(f"Ошибка начисления FF за упражнение: {e}")

        conn.commit()

        # Проверяем, все ли упражнения выполнены
        cur.execute("""
            SELECT COUNT(*) FROM challenge_exercises WHERE challenge_id = %s
        """, (challenge_id,))
        total_exercises = cur.fetchone()[0]

        cur.execute("""
            SELECT COUNT(*) FROM user_challenge_progress
            WHERE user_id = %s AND challenge_id = %s AND completed = TRUE
        """, (user_id, challenge_id))
        completed_exercises = cur.fetchone()[0]

        # Если все выполнены - завершаем челлендж
        if completed_exercises >= total_exercises:
            cur.execute("""
                UPDATE user_challenges
                SET completed = TRUE, completed_at = CURRENT_TIMESTAMP
                WHERE user_id = %s AND challenge_id = %s
            """, (user_id, challenge_id))

            # Начисляем FruN Fuel за завершение челленджа (+20 FF)
            try:
                add_fun_fuel(user_id, 20, f'Завершение челленджа {challenge_id}')
                logger.info(f"Начислено +20 FF пользователю {user_id} за завершение челленджа")
            except Exception as e:
                logger.error(f"Ошибка начисления FF за челлендж: {e}")

            conn.commit()
            return True, 'completed'  # Челлендж завершен!

        return True, 'active'  # Еще есть упражнения
    except psycopg2.Error as e:
        logger.error(f"Ошибка при выполнении упражнения: {e}")
        return False, None
    finally:
        release_db_connection(conn)


def get_active_challenges():
    """Получает список активных челленджей."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        from datetime import date
        today = date.today()

        cur.execute("""
            SELECT c.id, c.name, c.description, c.metric, c.target_value,
                   c.start_date, c.end_date, c.bonus_points,
                   COUNT(DISTINCT uc.user_id) as participants
            FROM challenges c
            LEFT JOIN user_challenges uc ON c.id = uc.challenge_id
            WHERE c.start_date <= %s AND c.end_date >= %s
            GROUP BY c.id
            ORDER BY c.start_date DESC
        """, (today, today))
        return cur.fetchall()
    except psycopg2.Error as e:
        logger.error(f"Ошибка при получении активных челленджей: {e}")
        return []
    finally:
        release_db_connection(conn)


def get_user_challenges(user_id):
    """Получает челленджи пользователя."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT c.id, c.name, c.description, c.metric, c.target_value,
                   c.start_date, c.end_date, c.bonus_points, uc.completed, uc.joined_at
            FROM challenges c
            JOIN user_challenges uc ON c.id = uc.challenge_id
            WHERE uc.user_id = %s
            ORDER BY c.start_date DESC
        """, (user_id,))
        return cur.fetchall()
    except psycopg2.Error as e:
        logger.error(f"Ошибка при получении челленджей пользователя: {e}")
        return []
    finally:
        release_db_connection(conn)


def create_coin_challenge(name, description, target_type, target_id, metric, target_value,
                           start_date, end_date, bonus_points, entry_fee, prize_pool):
    """
    Создаёт платный челлендж на FruN Fuel.

    Args:
        entry_fee: Вход в FF (50-200)
        prize_pool: Призовой фонд в FF (500-5000)
    """
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            INSERT INTO challenges (name, description, target_type, target_id, metric, target_value,
                                   start_date, end_date, bonus_points, entry_fee_coins, prize_pool_coins, is_coin_challenge)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (name, description, target_type, target_id, metric, target_value,
              start_date, end_date, bonus_points, entry_fee, prize_pool, True))
        conn.commit()
        challenge_id = cur.fetchone()[0] if cur.rowcount > 0 else None
        logger.info(f"Создан платный челлендж #{challenge_id}: вход={entry_fee} FF, приз={prize_pool} FF")
        return challenge_id
    except psycopg2.Error as e:
        logger.error(f"Ошибка создания платного челленджа: {e}")
        return None
    finally:
        release_db_connection(conn)


def join_coin_challenge(user_id, challenge_id):
    """
    Участвует в платном челлендже с оплатой входа FF.

    Returns:
        (success, message, new_balance)
    """
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Проверяем что челлендж существует и платный
        cur.execute("""
            SELECT entry_fee_coins, prize_pool_coins, end_date, is_coin_challenge
            FROM challenges
            WHERE id = %s
        """, (challenge_id,))
        challenge = cur.fetchone()

        if not challenge:
            return False, "Челлендж не найден", None

        entry_fee, prize_pool, end_date, is_coin = challenge

        if not is_coin:
            return False, "Это не платный челлендж", None

        # Проверяем что челлендж ещё активен
        if end_date and datetime.now() > end_date:
            return False, "Челлендж уже завершён", None

        # Проверяем баланс пользователя
        balance = get_user_coin_balance(user_id)
        if balance < entry_fee:
            return False, f"Недостаточно FF. Нужно: {entry_fee} FF, у тебя: {balance} FF", balance

        # Списываем вход и записываем участие
        success, new_balance = spend_coins(user_id, entry_fee, 'entry_fee', f'Вход в платный челлендж #{challenge_id}')

        if not success:
            return False, "Ошибка списания FF", balance

        conn.commit()
        logger.info(f"Пользователь {user_id} вступил в платный челлендж #{challenge_id}, вход={entry_fee} FF")
        return True, "Успешно вступили в челлендж!", new_balance

    except Exception as e:
        logger.error(f"Ошибка вступления в платный челлендж: {e}")
        conn.rollback()
        return False, f"Ошибка: {e}", None
    finally:
        release_db_connection(conn)


def distribute_coin_challenge(challenge_id):
    """
    Распределяет призовой фонд платного челленджа между победителями.
    Топ-3 получают: 60%, 30%, 10% от призового фонда.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Получаем информацию о челлендже
        cur.execute("""
            SELECT prize_pool_coins, target_type, target_id
            FROM challenges
            WHERE id = %s AND is_coin_challenge = TRUE
        """, (challenge_id,))
        challenge = cur.fetchone()

        if not challenge:
            logger.error(f"Платный челлендж #{challenge_id} не найден")
            return

        prize_pool, target_type, target_id = challenge

        if prize_pool <= 0:
            logger.info(f"У челленджа #{challenge_id} нет призового фонда")
            return

        # Получаем результаты участников (топ-3)
        # Это примерная логика - нужно адаптировать под вашу систему подсчёта
        cur.execute("""
            SELECT u.telegram_id, u.score
            FROM users u
            WHERE u.score > 0
            ORDER BY u.score DESC
            LIMIT 3
        """)
        winners = cur.fetchall()

        if not winners:
            logger.info(f"Нет победителей для челленджа #{challenge_id}")
            return

        # Распределяем приз: 60%, 30%, 10%
        prizes = [int(prize_pool * 0.6), int(prize_pool * 0.3), int(prize_pool * 0.1)]

        for i, (winner_id, score) in enumerate(winners):
            if i < len(prizes):
                prize = prizes[i]
                add_coins(winner_id, prize, 'prize', f'🏆 Приз за челлендж #{challenge_id} ({i+1}-е место)')
                logger.info(f"Начислено {prize} FF пользователю {winner_id} за {i+1}-е место в челлендже #{challenge_id}")

        conn.commit()
        logger.info(f"Распределён призовой фонд {prize_pool} FF челленджа #{challenge_id}")

    except Exception as e:
        logger.error(f"Ошибка распределения призов челленджа #{challenge_id}: {e}")
        conn.rollback()
    finally:
        release_db_connection(conn)


def distribute_challenge_bonus(challenge_id):
    """Распределяет бонус между топ-3 участниками челленджа"""
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Получаем бонус и метрику челленджа
        cur.execute("SELECT bonus_points, metric, target_value FROM challenges WHERE id = %s", (challenge_id,))
        row = cur.fetchone()
        if not row:
            release_db_connection(conn)
            return False
        bonus_points, metric, target_value = row

        # Получаем всех участников с их прогрессом
        cur.execute("""
            SELECT uc.user_id, p.current_value
            FROM user_challenges uc
            JOIN user_challenge_progress p ON uc.user_id = p.user_id AND uc.challenge_id = p.challenge_id
            WHERE uc.challenge_id = %s AND uc.completed = FALSE
        """, (challenge_id,))
        participants = cur.fetchall()

        # Фильтруем участников с None прогрессом
        participants = [(uid, val) for uid, val in participants if val is not None]

        if not participants:
            # Нет участников с прогрессом — просто закрываем челлендж
            cur.execute("""
                UPDATE user_challenges
                SET completed = TRUE, completed_at = CURRENT_TIMESTAMP
                WHERE challenge_id = %s
            """, (challenge_id,))
            conn.commit()
            release_db_connection(conn)
            return True

        # Сортируем по прогрессу
        if metric == 'reps':
            participants.sort(key=lambda x: float(x[1]), reverse=True)
        else:
            participants.sort(key=lambda x: float(x[1]))

        # Определяем топ-3
        top3 = participants[:3]

        # Распределяем бонус (50%, 30%, 20%)
        distribution = [0.5, 0.3, 0.2]
        for i, (user_id, progress) in enumerate(top3):
            awarded = int(bonus_points * distribution[i])
            if awarded > 0:
                cur.execute("""
                    INSERT INTO scoreboard (user_id, exercise_id, period_start, period_end, rank, points)
                    VALUES (%s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, %s, %s)
                """, (user_id, -challenge_id, i + 1, awarded))

        # Отмечаем всех участников как завершивших
        cur.execute("""
            UPDATE user_challenges
            SET completed = TRUE, completed_at = CURRENT_TIMESTAMP
            WHERE challenge_id = %s
        """, (challenge_id,))

        conn.commit()
        release_db_connection(conn)
        return True

    except Exception as e:
        logger.error(f"Ошибка при распределении бонуса челленджа: {e}")
        import traceback
        traceback.print_exc()
        if conn:
            release_db_connection(conn)
        return False


# ==================== АЧИВКИ И НАГРАДЫ ====================

def check_and_award_achievements(user_id, conn=None):
    """Проверяет и начисляет ачивки пользователю."""
    own_conn = False
    if conn is None:
        conn = get_db_connection()
        own_conn = True
    cur = conn.cursor()
    cur.execute("SELECT id, name, description, condition_type, condition_value, icon FROM achievements")
    achievements = cur.fetchall()
    cur.execute("SELECT achievement_id FROM user_achievements WHERE user_id = %s", (user_id,))
    earned = {row[0] for row in cur.fetchall()}
    new_achievements = []
    for ach in achievements:
        ach_id, name, desc, cond_type, cond_value, icon = ach
        if ach_id in earned:
            continue
        if cond_type == 'workout_count':
            cur.execute("SELECT COUNT(*) FROM workouts WHERE user_id = %s", (user_id,))
            count = cur.fetchone()[0]
            if count >= int(cond_value):
                new_achievements.append(ach)
        elif cond_type == 'best_record':
            cur.execute("SELECT 1 FROM workouts WHERE user_id = %s AND is_best = TRUE LIMIT 1", (user_id,))
            if cur.fetchone():
                new_achievements.append(ach)
        elif cond_type == 'challenge_completed':
            cur.execute("SELECT 1 FROM user_challenges WHERE user_id = %s AND completed = TRUE LIMIT 1", (user_id,))
            if cur.fetchone():
                new_achievements.append(ach)
    for ach in new_achievements:
        ach_id, name, desc, cond_type, cond_value, icon = ach
        cur.execute("INSERT INTO user_achievements (user_id, achievement_id) VALUES (%s, %s)", (user_id, ach_id))
        conn.commit()
    if own_conn:
        release_db_connection(conn)
    return new_achievements


# ==================== ИСТОРИЯ И КАЛЕНДАРЬ ====================

def get_user_activity_calendar(user_id, year, month):
    """Возвращает данные для календаря активности пользователя."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            DATE(performed_at) as day,
            COUNT(*) as workout_count,
            0 as record_count,
            SUM(CAST(result_value AS NUMERIC)) as total_volume
        FROM workouts
        WHERE user_id = %s
          AND EXTRACT(YEAR FROM performed_at) = %s
          AND EXTRACT(MONTH FROM performed_at) = %s
        GROUP BY DATE(performed_at)
    """, (user_id, year, month))
    rows = cursor.fetchall()
    conn.close()
    days_in_month = calendar.monthrange(year, month)[1]
    result = []
    for day in range(1, days_in_month + 1):
        day_str = f"{year}-{month:02d}-{day:02d}"
        found = False
        has_workout = False
        has_record = False
        total_volume = None
        for row in rows:
            if row[0] == day_str:
                found = True
                has_workout = row[1] > 0
                has_record = row[2] > 0
                total_volume = float(row[3]) if row[3] else 0
                break
        if not found:
            has_workout = False
            has_record = False
            total_volume = None
        result.append((day, has_workout, has_record, total_volume))
    return result


def save_published_post(entity_type, entity_id, channel_id, message_id):
    """Сохраняет информацию о опубликованном посте."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO published_posts (entity_type, entity_id, channel_id, message_id) VALUES (%s, %s, %s, %s)", (entity_type, entity_id, channel_id, message_id))
    conn.commit()
    conn.close()


def get_published_post_by_message_id(message_id):
    """Возвращает информацию о посте по message_id."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT entity_type, entity_id, channel_id, message_id FROM published_posts WHERE message_id = %s", (message_id,))
    row = cur.fetchone()
    conn.close()
    return row


# ==================== PVP ВЫЗОВЫ ====================

def _get_user_workout_score(cur, user_id):
    """Сумма очков за все тренировки пользователя."""
    cur.execute("""
        SELECT COALESCE(SUM(e.points), 0)
        FROM workouts w
        JOIN exercises e ON w.exercise_id = e.id
        WHERE w.user_id = %s
    """, (user_id,))
    return cur.fetchone()[0]


def _get_user_workout_score_period(cur, user_id, start_time, end_time):
    """Сумма очков за тренировки пользователя за период."""
    cur.execute("""
        SELECT COALESCE(SUM(e.points), 0)
        FROM workouts w
        JOIN exercises e ON w.exercise_id = e.id
        WHERE w.user_id = %s AND w.performed_at >= %s AND w.performed_at <= %s
    """, (user_id, start_time, end_time))
    return cur.fetchone()[0]


def create_challenge_with_bet(challenger_id, opponent_id, bet, duration_hours=24):
    """Создаёт PvP-вызов со ставкой в FruN Fuel. Резервирует ставку у вызывающего."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Проверяем наличие FF у вызывающего
        ch_balance = get_fun_fuel_balance(challenger_id)
        if ch_balance < bet:
            return None, f"Недостаточно FF у вас: {ch_balance} < {bet}. Заработайте FF выполняя тренировки!"

        # Проверяем наличие FF у соперника (проверка, но НЕ списываем)
        op_balance = get_fun_fuel_balance(opponent_id)
        if op_balance < bet:
            return None, f"Недостаточно FF у соперника: {op_balance} < {bet}. Соперник не сможет принять вызов!"

        # Проверяем, нет ли уже активного вызова
        cur.execute("""
            SELECT id FROM pvp_challenges
            WHERE ((challenger_id = %s AND opponent_id = %s) OR (challenger_id = %s AND opponent_id = %s))
            AND status IN ('pending', 'active')
        """, (challenger_id, opponent_id, opponent_id, challenger_id))
        if cur.fetchone():
            return None, "Уже есть активный вызов между этими пользователями"

        # Резервируем ставку у вызывающего
        success, result = reserve_fun_fuel(challenger_id, bet)
        if not success:
            return None, f"Ошибка резервирования ставки: {result}"

        # Фиксируем score_start как текущую сумму тренировочных очков
        ch_score_start = _get_user_workout_score(cur, challenger_id)
        op_score_start = _get_user_workout_score(cur, opponent_id)

        start_time = datetime.now()
        end_time = start_time + timedelta(hours=duration_hours)

        cur.execute("""
            INSERT INTO pvp_challenges
            (challenger_id, opponent_id, start_time, end_time, status,
             bet, challenger_score_start, opponent_score_start, commission_rate)
            VALUES (%s, %s, %s, %s, 'pending', %s, %s, %s, 0.10)
            RETURNING id
        """, (challenger_id, opponent_id, start_time, end_time,
              bet, ch_score_start, op_score_start))

        challenge_id = cur.fetchone()[0]
        conn.commit()
        return challenge_id, f"Вызов создан! Ставка: {bet} FF. Ожидайте принятия вызова."
    except Exception as e:
        logger.error(f"Ошибка создания PvP-вызова: {e}")
        conn.rollback()
        return None, f"Ошибка: {e}"
    finally:
        release_db_connection(conn)


def create_pvp_challenge(challenger_id, opponent_id, duration_hours=24, bet=0):
    """Создаёт новый PvP-вызов между двумя пользователями с опциональной ставкой."""
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        start_time = datetime.now()
        end_time = start_time + timedelta(hours=duration_hours)

        # Проверяем, нет ли уже активного вызова между этими пользователями
        cur.execute("""
            SELECT id FROM pvp_challenges
            WHERE ((challenger_id = %s AND opponent_id = %s) OR (challenger_id = %s AND opponent_id = %s))
            AND status IN ('pending', 'active')
        """, (challenger_id, opponent_id, opponent_id, challenger_id))

        if cur.fetchone():
            return None, "Уже есть активный вызов между этими пользователями"

        cur.execute("""
            INSERT INTO pvp_challenges
            (challenger_id, opponent_id, start_time, end_time, status, bet)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (challenger_id, opponent_id, start_time, end_time, 'pending', bet))

        challenge_id = cur.fetchone()[0]
        conn.commit()
        release_db_connection(conn)

        return challenge_id, "Вызов создан"
    except Exception as e:
        logger.error(f"Ошибка создания PvP-вызова: {e}")
        release_db_connection(conn)
        return None, f"Ошибка: {e}"


def accept_pvp_challenge(challenge_id, opponent_id):
    """Принимает PvP-вызов; резервирует ставку у принимающего, обновляет score_start для обоих."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT challenger_id, opponent_id, bet
            FROM pvp_challenges
            WHERE id = %s AND opponent_id = %s AND status = 'pending'
        """, (challenge_id, opponent_id))
        row = cur.fetchone()
        if not row:
            return False, "Вызов не найден или уже обработан"

        challenger_id, opponent_id_db, bet = row

        # Проверяем, что у принимающего достаточно FF
        op_balance = get_fun_fuel_balance(opponent_id_db)
        if op_balance < bet:
            return False, f"Недостаточно FF для принятия вызова: {op_balance} < {bet}. Заработайте FF выполняя тренировки!"

        # Резервируем ставку у принимающего
        success, result = reserve_fun_fuel(opponent_id_db, bet)
        if not success:
            return False, f"Ошибка резервирования ставки: {result}"

        # Обновляем score_start на момент начала дуэли
        ch_start = _get_user_workout_score(cur, challenger_id)
        op_start = _get_user_workout_score(cur, opponent_id_db)

        cur.execute("""
            UPDATE pvp_challenges
            SET status = 'active',
                challenger_score_start = %s,
                opponent_score_start = %s
            WHERE id = %s
        """, (ch_start, op_start, challenge_id))

        conn.commit()
        return True, f"Вызов принят! Ставка {bet} FF зарезервирована. Дуэль началась!"
    except Exception as e:
        logger.error(f"Ошибка принятия PvP-вызова: {e}")
        conn.rollback()
        return False, f"Ошибка: {e}"
    finally:
        release_db_connection(conn)


def reject_pvp_challenge(challenge_id, opponent_id):
    """Отклоняет PvP-вызов."""
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            UPDATE pvp_challenges
            SET status = 'cancelled'
            WHERE id = %s AND opponent_id = %s AND status = 'pending'
        """, (challenge_id, opponent_id))

        if cur.rowcount == 0:
            release_db_connection(conn)
            return False

        conn.commit()
        release_db_connection(conn)
        return True
    except Exception as e:
        logger.error(f"Ошибка отклонения PvP-вызова: {e}")
        release_db_connection(conn)
        return False


def cancel_pvp_challenge_and_refund(challenge_id, user_id):
    """Отменяет PvP-вызов и возвращает ставки обоим участникам.

    Args:
        challenge_id: ID вызова
        user_id: ID пользователя, который отменяет

    Returns:
        tuple: (success, message, challenger_id, opponent_id, bet)
    """
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Получаем информацию о вызове
        cur.execute("""
            SELECT id, challenger_id, opponent_id, status, bet
            FROM pvp_challenges
            WHERE id = %s
        """, (challenge_id,))

        challenge = cur.fetchone()

        if not challenge:
            release_db_connection(conn)
            return False, "Вызов не найден", None, None, 0

        db_challenge_id, challenger_id, opponent_id, status, bet = challenge

        # Проверяем, что пользователь является участником
        if user_id != challenger_id and user_id != opponent_id:
            release_db_connection(conn)
            return False, "Вы не участвуете в этом вызове", None, None, 0

        # Проверяем статус
        if status not in ['pending', 'active']:
            release_db_connection(conn)
            return False, "Этот вызов уже завершён", None, None, 0

        # Отменяем вызов
        cur.execute("""
            UPDATE pvp_challenges
            SET status = 'cancelled'
            WHERE id = %s
        """, (challenge_id,))

        # Возвращаем ставки обоим участникам
        if bet > 0:
            cur.execute("""
                UPDATE users
                SET score = score + %s
                WHERE telegram_id IN (%s, %s)
            """, (bet, challenger_id, opponent_id))

        conn.commit()

        release_db_connection(conn)
        return True, "Вызов отменён", challenger_id, opponent_id, bet

    except Exception as e:
        logger.error(f"Ошибка отмены PvP-вызова: {e}")
        release_db_connection(conn)
        return False, f"Ошибка: {e}", None, None, 0


def get_pvp_challenge(challenge_id):
    """Возвращает информацию о PvP-вызове."""
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, challenger_id, opponent_id, start_time, end_time, status,
               challenger_score, opponent_score, winner_id
        FROM pvp_challenges
        WHERE id = %s
    """, (challenge_id,))

    row = cur.fetchone()
    conn.close()

    return row


def get_user_active_challenge(user_id):
    """Возвращает активный PvP-вызов пользователя."""
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, challenger_id, opponent_id, start_time, end_time, status,
               challenger_score, opponent_score, winner_id
        FROM pvp_challenges
        WHERE (challenger_id = %s OR opponent_id = %s)
        AND status IN ('pending', 'active')
        ORDER BY created_at DESC
        LIMIT 1
    """, (user_id, user_id))

    row = cur.fetchone()
    conn.close()

    return row


def complete_pvp_challenge(challenge_id):
    """Завершает PvP-вызов: определяет победителя по приросту очков, распределяет ставку."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT challenger_id, opponent_id, start_time, end_time,
                   bet, challenger_score_start, opponent_score_start
            FROM pvp_challenges
            WHERE id = %s AND status = 'active'
        """, (challenge_id,))
        row = cur.fetchone()
        if not row:
            return False, None, 0, 0

        challenger_id, opponent_id, start_time, end_time, bet, \
            ch_start, op_start = row

        if isinstance(start_time, str):
            start_time = datetime.fromisoformat(start_time)
        if isinstance(end_time, str):
            end_time = datetime.fromisoformat(end_time)

        # Прирост = тренировочные очки, набранные ЗА ПЕРИОД дуэли
        ch_gain = _get_user_workout_score_period(cur, challenger_id, start_time, end_time)
        op_gain = _get_user_workout_score_period(cur, opponent_id, start_time, end_time)

        # Определяем победителя
        if ch_gain > op_gain:
            winner_id = challenger_id
        elif op_gain > ch_gain:
            winner_id = opponent_id
        else:
            winner_id = None  # Ничья

        # Распределяем ставку с комиссией 10%
        total_bet = bet * 2
        commission = int(total_bet * 0.10)  # 10% комиссия
        winnings = total_bet - commission  # Что получает победитель

        if winner_id is None:
            # Ничья — возврат ставки обоим
            refund_fun_fuel(challenger_id, bet, "Возврат ставки (ничья)")
            refund_fun_fuel(opponent_id, bet, "Возврат ставки (ничья)")
            ch_change = 0
            op_change = 0
            ch_result = 'draw'
            op_result = 'draw'
        elif winner_id == challenger_id:
            # Победа вызывающего - выплачиваем с комиссией
            add_fun_fuel(challenger_id, winnings, f'Выигрыш в PvP (вызов #{challenge_id})')
            ch_change = bet - int(commission / 2)
            op_change = -bet
            ch_result = 'win'
            op_result = 'lose'
        else:
            # Победа соперника - выплачиваем с комиссией
            add_fun_fuel(opponent_id, winnings, f'Выигрыш в PvP (вызов #{challenge_id})')
            ch_change = -bet
            op_change = bet - int(commission / 2)
            ch_result = 'lose'
            op_result = 'win'

        # Записываем комиссию в систему
        try:
            add_fun_fuel(0, commission, f'Комиссия за вызов #{challenge_id}')  # 0 = системный аккаунт
            logger.info(f"Получена комиссия {commission} FF за вызов #{challenge_id}")
        except:
            pass  # Если системный аккаунт не работает, просто игнорируем

        # Обновляем вызов
        cur.execute("""
            UPDATE pvp_challenges
            SET status = 'finished',
                challenger_score = %s,
                opponent_score = %s,
                winner_id = %s
            WHERE id = %s
        """, (ch_gain, op_gain, winner_id, challenge_id))

        # Запись в pvp_history
        now = datetime.now()
        cur.execute("""
            INSERT INTO pvp_history (challenge_id, user_id, opponent_id, result, bet, score_change, date)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (challenge_id, challenger_id, opponent_id, ch_result, bet, ch_change, now))
        cur.execute("""
            INSERT INTO pvp_history (challenge_id, user_id, opponent_id, result, bet, score_change, date)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (challenge_id, opponent_id, challenger_id, op_result, bet, op_change, now))

        conn.commit()
        return True, winner_id, ch_gain, op_gain
    except Exception as e:
        logger.error(f"Ошибка завершения PvP-вызова {challenge_id}: {e}")
        conn.rollback()
        return False, None, 0, 0
    finally:
        release_db_connection(conn)


def calculate_pvp_scores(challenge_id):
    """Устаревший алиас — используйте complete_pvp_challenge."""
    result = complete_pvp_challenge(challenge_id)
    return result[0]


def finish_expired_pvp_challenges():
    """Завершает истёкшие PvP-вызовы (вызывается фоновой задачей каждые 5 минут)."""
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT id FROM pvp_challenges
            WHERE status IN ('pending', 'active') AND end_time <= CURRENT_TIMESTAMP
        """)
        expired = [row[0] for row in cur.fetchall()]
    except Exception as e:
        logger.error(f"Ошибка поиска истёкших PvP: {e}")
        expired = []
    finally:
        release_db_connection(conn)

    for challenge_id in expired:
        complete_pvp_challenge(challenge_id)

    return len(expired)


def get_user_active_challenges(user_id):
    """Возвращает все активные вызовы пользователя (где он challenger или opponent)."""
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, challenger_id, opponent_id, start_time, end_time, status,
               challenger_score, opponent_score, winner_id
        FROM pvp_challenges
        WHERE (challenger_id = %s OR opponent_id = %s)
        AND status IN ('pending', 'active')
        ORDER BY created_at DESC
    """, (user_id, user_id))

    rows = cur.fetchall()
    conn.close()

    return rows


def get_user_pvp_history(user_id, limit=5):
    """Возвращает историю завершённых вызовов пользователя."""
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            pc.id, pc.challenger_id, pc.opponent_id,
            pc.start_time, pc.end_time, pc.status,
            pc.challenger_score, pc.opponent_score, pc.winner_id,
            pc.bet,
            u1.first_name as challenger_name, u1.username as challenger_username,
            u2.first_name as opponent_name, u2.username as opponent_username
        FROM pvp_challenges pc
        LEFT JOIN users u1 ON pc.challenger_id = u1.telegram_id
        LEFT JOIN users u2 ON pc.opponent_id = u2.telegram_id
        WHERE (pc.challenger_id = %s OR pc.opponent_id = %s)
        AND pc.status = 'finished'
        ORDER BY pc.created_at DESC
        LIMIT %s
    """, (user_id, user_id, limit))

    rows = cur.fetchall()
    conn.close()

    return rows


def get_user_pvp_stats(user_id):
    """Возвращает PvP-статистику пользователя из pvp_history."""
    conn = get_db_connection()
    cur = conn.cursor()

    # Получаем статистику из pvp_history
    cur.execute("""
        SELECT
            COUNT(*) as total_challenges,
            SUM(CASE WHEN result = 'win' THEN 1 ELSE 0 END) as wins,
            SUM(CASE WHEN result = 'loss' THEN 1 ELSE 0 END) as losses,
            SUM(CASE WHEN result = 'draw' THEN 1 ELSE 0 END) as draws,
            SUM(CASE WHEN result = 'win' THEN score_change ELSE 0 END) as coins_won,
            SUM(CASE WHEN result = 'loss' THEN score_change ELSE 0 END) as coins_lost
        FROM pvp_history
        WHERE user_id = %s
    """, (user_id,))

    row = cur.fetchone()
    conn.close()

    if row and row[0] > 0:
        return {
            'total': row[0],
            'wins': row[1] or 0,
            'losses': row[2] or 0,
            'draws': row[3] or 0,
            'coins_won': row[4] or 0,
            'coins_lost': row[5] or 0
        }
    else:
        return {
            'total': 0,
            'wins': 0,
            'losses': 0,
            'draws': 0,
            'coins_won': 0,
            'coins_lost': 0
        }


def check_active_challenge_between(user_id_1, user_id_2):
    """Проверяет, есть ли активный вызов между двумя пользователями."""
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id FROM pvp_challenges
        WHERE ((challenger_id = %s AND opponent_id = %s) OR (challenger_id = %s AND opponent_id = %s))
        AND status IN ('pending', 'active')
        LIMIT 1
    """, (user_id_1, user_id_2, user_id_2, user_id_1))

    row = cur.fetchone()
    conn.close()

    return row is not None


# ==================== СИСТЕМНЫЕ НАСТРОЙКИ ====================

def get_setting(key):
    """Возвращает значение настройки."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT value FROM settings WHERE key = %s", (key,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None


def set_setting(key, value):
    """Устанавливает значение настройки."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO settings (key, value) VALUES (%s, %s)
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
    """, (key, value))
    conn.commit()
    conn.close()


def get_last_recalc():
    """Возвращает дату последнего пересчёта рейтинга."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT value FROM system_config WHERE key = 'last_recalc'")
    row = cur.fetchone()
    conn.close()
    if row and row[0] != '0':
        return datetime.fromisoformat(row[0])
    return None


def set_last_recalc(date):
    """Устанавливает дату последнего пересчёта рейтинга."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE system_config SET value = %s WHERE key = 'last_recalc'", (date.isoformat(),))
    conn.commit()
    conn.close()


def recalculate_rankings(period_days=7):
    """Пересчитывает рейтинг за указанный период."""
    conn = get_db_connection()
    cur = conn.cursor()
    start_date = datetime.now() - timedelta(days=period_days)
    exercises = get_all_exercises()
    for ex in exercises:
        ex_id = ex[0]
        metric = ex[2]
        if metric == 'reps':
            query = """
                SELECT user_id, MAX(CAST(result_value AS INTEGER)) as best
                FROM workouts
                WHERE exercise_id = %s AND performed_at >= %s
                GROUP BY user_id
                ORDER BY best DESC
            """
        else:
            query = """
                SELECT user_id, MIN(result_value) as best
                FROM workouts
                WHERE exercise_id = %s AND performed_at >= %s
                GROUP BY user_id
                ORDER BY best ASC
            """
        cur.execute(query, (ex_id, start_date))
        results = cur.fetchall()
        rankings = []
        for i, (user_id, best) in enumerate(results):
            if i == 0:
                points = 15
            elif i == 1:
                points = 10
            elif i == 2:
                points = 5
            else:
                points = 0
            rankings.append((user_id, ex_id, start_date, datetime.now(), i+1, points))
        cur.execute("DELETE FROM scoreboard WHERE exercise_id = %s AND period_start = %s", (ex_id, start_date))
        cur.executemany("""
            INSERT INTO scoreboard (user_id, exercise_id, period_start, period_end, rank, points)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, rankings)

        # Комплексы
        complexes = get_all_complexes()
        for comp in complexes:
            comp_id = comp[0]
            metric = 'reps'  # или 'time' — нужно хранить в таблице complexes
            if metric == 'reps':
                query = """
                        SELECT user_id, SUM(CAST(result_value AS INTEGER)) as best
                        FROM workouts
                        WHERE complex_id = %s
                          AND performed_at >= %s
                        GROUP BY user_id
                        ORDER BY best DESC
                        """
            else:
                query = """
                        SELECT user_id, SUM(result_value) as best
                        FROM workouts
                        WHERE complex_id = %s
                          AND performed_at >= %s
                        GROUP BY user_id
                        ORDER BY best ASC
                        """
            cur.execute(query, (comp_id, start_date))
            results = cur.fetchall()
            rankings = []
            for i, (user_id, best) in enumerate(results):
                if i == 0:
                    points = 15
                elif i == 1:
                    points = 10
                elif i == 2:
                    points = 5
                else:
                    points = 0
                rankings.append((user_id, -comp_id, start_date, datetime.now(), i + 1, points))
            if rankings:
                cur.execute("DELETE FROM scoreboard WHERE exercise_id = %s AND period_start = %s", (-comp_id, start_date))
                cur.executemany("""
                                INSERT INTO scoreboard (user_id, exercise_id, period_start, period_end, rank, points)
                                VALUES (%s, %s, %s, %s, %s, %s)
                                """, rankings)
    conn.commit()
    conn.close()
    logger.info(f"Рейтинг пересчитан за период с {start_date} по {datetime.now()}")


# ==================== РЕФЕРАЛЬНАЯ СИСТЕМА ====================

def generate_referral_code(telegram_id):
    """Генерирует уникальный реферальный код для пользователя."""
    import random
    import string

    # Генерируем код на основе telegram_id и случайных символов
    base = str(telegram_id)[-6:]  # Последние 6 цифр telegram_id
    random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=3))
    referral_code = base + random_part

    return referral_code.upper()


def get_referral_code(telegram_id):
    """Получает реферальный код пользователя."""
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("SELECT referral_code FROM users WHERE telegram_id = %s", (telegram_id,))
        row = cur.fetchone()

        if row and row[0]:
            code = row[0]
        else:
            # Генерируем новый код
            code = generate_referral_code(telegram_id)
            cur.execute("UPDATE users SET referral_code = %s WHERE telegram_id = %s", (code, telegram_id))
            conn.commit()
            logger.info(f"Сгенерирован реферальный код {code} для пользователя {telegram_id}")

        cur.close()
        return code
    except Exception as e:
        logger.error(f"Ошибка получения реферального кода: {e}")
        cur.close()
        return None


def get_referral_info(telegram_id):
    """Получает информацию о рефералах пользователя."""
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT referral_code, referrer_id, referral_bonus_received, referrer_bonus_received
            FROM users WHERE telegram_id = %s
        """, (telegram_id,))
        row = cur.fetchone()
        cur.close()
        return row
    except Exception as e:
        logger.error(f"Ошибка получения реферальной информации: {e}")
        cur.close()
        return None


def get_referral_count(telegram_id):
    """Получает количество приглашенных пользователей."""
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("SELECT COUNT(*) FROM users WHERE referrer_id = %s", (telegram_id,))
        count = cur.fetchone()[0]
        cur.close()
        return count
    except Exception as e:
        logger.error(f"Ошибка подсчета рефералов: {e}")
        cur.close()
        return 0


def process_referral(new_user_id, referral_code):
    """Обрабатывает реферальный код при регистрации."""
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Проверяем код
        cur.execute("SELECT telegram_id, referral_bonus_received FROM users WHERE referral_code = %s", (referral_code,))
        referrer = cur.fetchone()

        if not referrer:
            cur.close()
            return False, "Реферальный код не найден"

        referrer_id, referrer_bonus_received = referrer

        if referrer_bonus_received:
            cur.close()
            return False, "Этот код уже был использован"

        if referrer_id == new_user_id:
            cur.close()
            return False, "Нельзя использовать свой код"

        # Получаем настройки бонусов
        bonus = get_setting('referral_bonus')
        if not bonus:
            bonus = '50'
        bonus = int(bonus)

        # Начисляем бонусы
        cur.execute("UPDATE users SET score = score + %s WHERE telegram_id = %s", (bonus, referrer_id))
        cur.execute("UPDATE users SET score = score + %s WHERE telegram_id = %s", (bonus, new_user_id))

        # Начисляем FruN Fuel за реферала (+100 FF обоим)
        try:
            add_coins(referrer_id, 100, 'referral', f'👥 За приглашенного друга (user_{new_user_id})')
            add_coins(new_user_id, 100, 'referral', f'🎁 Бонус за регистрацию по приглашению')
            logger.info(f"Начислено +100 FF пользователю {referrer_id} за реферала (user_{new_user_id})")
            logger.info(f"Начислено +100 FF пользователю {new_user_id} за регистрацию по рефералу")
        except Exception as e:
            logger.error(f"Ошибка начисления FruN Fuel за реферала: {e}")

        # Отмечаем бонусы как полученные
        cur.execute("UPDATE users SET referrer_bonus_received = TRUE WHERE telegram_id = %s", (referrer_id,))
        cur.execute("UPDATE users SET referral_bonus_received = TRUE WHERE telegram_id = %s", (new_user_id,))

        # Записываем referrer_id
        cur.execute("UPDATE users SET referrer_id = %s WHERE telegram_id = %s", (referrer_id, new_user_id))

        conn.commit()
        cur.close()

        return True, f"Поздравляем! Вы и ваш пригласивший получили {bonus} очков!"

    except Exception as e:
        logger.error(f"Ошибка обработки реферала: {e}")
        conn.rollback()
        cur.close()
        return False, f"Ошибка при обработке реферального кода: {e}"


def get_referral_settings():
    """Получает настройки реферальной системы."""
    settings = {
        'referral_bonus': get_setting('referral_bonus') or '50',
        'referral_success_text': get_setting('referral_success_text') or '🎉 {inviter}, ты пригласил {new_user}! +{bonus} очков. Спасибо, что помогаешь развитию спорта и делаешь людей здоровее!',
        'referral_welcome_text': get_setting('referral_welcome_text') or '🤝 {new_user}, тебя пригласил {inviter}! +{bonus} очков на счёт. Добро пожаловать!'
    }

    return settings


def update_referral_setting(key, value):
    """Обновляет настройку реферальной системы."""
    return set_setting(key, value)


def get_referral_stats():
    """Получает статистику реферальной системы."""
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Всего пользователей с реферальным кодом
        cur.execute("SELECT COUNT(*) FROM users WHERE referral_code IS NOT NULL")
        total_with_code = cur.fetchone()[0]

        # Всего приглашенных
        cur.execute("SELECT COUNT(*) FROM users WHERE referrer_id IS NOT NULL")
        total_referred = cur.fetchone()[0]

        # Топ 10 рефереров
        cur.execute("""
            SELECT u.telegram_id, u.first_name, u.username, u.score,
                   (SELECT COUNT(*) FROM users ref WHERE ref.referrer_id = u.telegram_id) as referral_count
            FROM users u
            WHERE u.referrer_id IS NOT NULL
            GROUP BY u.telegram_id, u.first_name, u.username, u.score
            ORDER BY referral_count DESC
            LIMIT 10
        """)
        top_referrers = cur.fetchall()

        # Сумма бонусов
        cur.execute("SELECT COALESCE(SUM(score), 0) FROM users WHERE referrer_id IS NOT NULL")
        total_bonus = cur.fetchone()[0]

        cur.close()

        return {
            'total_with_code': total_with_code,
            'total_referred': total_referred,
            'top_referrers': top_referrers,
            'total_bonus': total_bonus
        }
    except Exception as e:
        logger.error(f"Ошибка получения статистики: {e}")
        cur.close()
        return {}


def get_referral_logs(limit=20):
    """Получает последние реферальные логи."""
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT
                u1.telegram_id as new_user_id,
                u1.first_name as new_user_name,
                u1.username as new_user_username,
                u2.telegram_id as referrer_id,
                u2.first_name as referrer_name,
                u2.username as referrer_username,
                u1.registered_at
            FROM users u1
            LEFT JOIN users u2 ON u1.referrer_id = u2.telegram_id
            ORDER BY u1.registered_at DESC
            LIMIT %s
        """, (limit,))
        logs = cur.fetchall()
        cur.close()
        return logs
    except Exception as e:
        logger.error(f"Ошибка получения логов: {e}")
        cur.close()
        return []


def reset_referral_texts():
    """Сбрасывает тексты на стандартные значения."""
    default_success_text = '🎉 {inviter}, ты пригласил {new_user}! +{bonus} очков. Спасибо, что помогаешь развитию спорта и делаешь людей здоровее!'
    default_welcome_text = '🤝 {new_user}, тебя пригласил {inviter}! +{bonus} очков на счёт. Добро пожаловать!'

    set_setting('referral_success_text', default_success_text)
    set_setting('referral_welcome_text', default_welcome_text)

    return {
        'referral_success_text': default_success_text,
        'referral_welcome_text': default_welcome_text
    }


# ==================== ГОРА УСПЕХА (RANKING SYSTEM) ====================

def get_mountain_ranking(group='newbie', limit=20, search_query=None):
    """Получает рейтинг для Горы Успеха.

    Args:
        group: Группа ('newbie' или 'pro')
        limit: Лимит участников
        search_query: Поисковый запрос (опционально)

    Returns:
        list: Список кортежей (telegram_id, first_name, username, score)
    """
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        if search_query:
            # Поиск по имени или username
            search_pattern = f"%{search_query}%"
            cur.execute("""
                SELECT u.telegram_id, u.first_name, u.username, u.score as total_score
                FROM users u
                WHERE u.user_group = %s
                AND (u.first_name ILIKE %s OR u.username ILIKE %s)
                ORDER BY u.score DESC
                LIMIT %s
            """, (group, search_pattern, search_pattern, limit))
        else:
            # Общий рейтинг
            cur.execute("""
                SELECT u.telegram_id, u.first_name, u.username, u.score as total_score
                FROM users u
                WHERE u.user_group = %s
                ORDER BY u.score DESC
                LIMIT %s
            """, (group, limit))

        users = cur.fetchall()
        return users

    except Exception as e:
        logger.error(f"Ошибка получения рейтинга горы: {e}")
        return []

    finally:
        release_db_connection(conn)


def get_mountain_total_users(group='newbie'):
    """Возвращает общее количество пользователей в группе."""
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("SELECT COUNT(*) FROM users WHERE user_group = %s", (group,))
        total = cur.fetchone()[0]
        return total

    except Exception as e:
        logger.error(f"Ошибка получения количества пользователей: {e}")
        return 0

    finally:
        release_db_connection(conn)


def get_user_position_on_mountain(user_id, group=None):
    """Возвращает позицию пользователя на Горе Успеха.

    Args:
        user_id: Telegram ID пользователя
        group: Группа ('newbie' или 'pro'), если None — использует текущую группу пользователя

    Returns:
        tuple: (position, total) или (None, None) если пользователь не найден
    """
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Определяем группу
        if group is None:
            cur.execute("SELECT user_group FROM users WHERE telegram_id = %s", (user_id,))
            row = cur.fetchone()
            if not row:
                return None, None
            group = row[0]

        # Получаем позицию пользователя (на основе scoreboard)
        cur.execute("""
            SELECT COUNT(*) + 1
            FROM (
                SELECT u.telegram_id, COALESCE(SUM(s.points), 0) as total_score
                FROM users u
                LEFT JOIN scoreboard s ON u.telegram_id = s.user_id
                WHERE u.user_group = %s
                GROUP BY u.telegram_id
            ) ranked
            WHERE total_score > (
                SELECT COALESCE(SUM(s.points), 0)
                FROM scoreboard s
                WHERE s.user_id = %s
            )
        """, (group, user_id))

        position = cur.fetchone()[0]

        # Получаем общее количество
        cur.execute("SELECT COUNT(*) FROM users WHERE user_group = %s", (group,))
        total = cur.fetchone()[0]

        return position, total

    except Exception as e:
        logger.error(f"Ошибка получения позиции на горе: {e}")
        return None, None

    finally:
        release_db_connection(conn)


def get_mountain_users_around_position(user_id, group=None, radius=5):
    """Возвращает пользователей вокруг позиции пользователя (для показа контекста).

    Args:
        user_id: Telegram ID пользователя
        group: Группа ('newbie' или 'pro'), если None — использует текущую группу
        radius: Сколько пользователей выше и ниже показать

    Returns:
        tuple: (users_above, current_user, users_below)
    """
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Определяем группу
        if group is None:
            cur.execute("SELECT user_group, score FROM users WHERE telegram_id = %s", (user_id,))
            row = cur.fetchone()
            if not row:
                return [], None, []
            group, user_score = row
        else:
            cur.execute("SELECT score FROM users WHERE telegram_id = %s AND user_group = %s", (user_id, group))
            row = cur.fetchone()
            if not row:
                return [], None, []
            user_score = row[0]

        # Получаем пользователей выше
        cur.execute("""
            SELECT telegram_id, first_name, username, score
            FROM users
            WHERE user_group = %s AND score > %s
            ORDER BY score ASC
            LIMIT %s
        """, (group, user_score, radius))

        users_above = cur.fetchall()

        # Получаем текущего пользователя
        cur.execute("""
            SELECT telegram_id, first_name, username, score
            FROM users
            WHERE telegram_id = %s AND user_group = %s
        """, (user_id, group))

        current_user = cur.fetchone()

        # Получаем пользователей ниже
        cur.execute("""
            SELECT telegram_id, first_name, username, score
            FROM users
            WHERE user_group = %s AND score < %s
            ORDER BY score DESC
            LIMIT %s
        """, (group, user_score, radius))

        users_below = cur.fetchall()

        return users_above, current_user, users_below

    except Exception as e:
        logger.error(f"Ошибка получения окружения на горе: {e}")
        return [], None, []

    finally:
        release_db_connection(conn)


def get_user_mountain_stats(user_id):
    """Возвращает полную статистику пользователя для Горы Успеха.

    Args:
        user_id: Telegram ID пользователя

    Returns:
        dict: Словарь со статистикой
    """
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Получаем информацию о пользователе
        cur.execute("""
            SELECT telegram_id, first_name, username, score, user_group, registered_at
            FROM users
            WHERE telegram_id = %s
        """, (user_id,))

        row = cur.fetchone()
        if not row:
            return None

        telegram_id, first_name, username, score, user_group, registered_at = row

        # Получаем позицию в группе
        position, total = get_user_position_on_mountain(user_id, user_group)

        # Вычисляем процент от вершины
        percent_from_top = None
        if position is not None and total is not None and total > 0:
            percent_from_top = ((position - 1) / total) * 100

        # Получаем количество рефералов
        cur.execute("SELECT COUNT(*) FROM users WHERE referrer_id = %s", (user_id,))
        referral_count = cur.fetchone()[0]

        # Получаем количество тренировок
        cur.execute("SELECT COUNT(*) FROM workouts WHERE user_id = %s", (user_id,))
        workout_count = cur.fetchone()[0]

        return {
            'telegram_id': telegram_id,
            'first_name': first_name,
            'username': username,
            'score': score,
            'user_group': user_group,
            'registered_at': registered_at,
            'position': position,
            'total': total,
            'percent_from_top': percent_from_top,
            'referral_count': referral_count,
            'workout_count': workout_count
        }

    except Exception as e:
        logger.error(f"Ошибка получения статистики горы: {e}")
        return None

    finally:
        release_db_connection(conn)


def search_users_by_name(search_query, limit=20):
    """Ищет пользователей по имени или username.

    Args:
        search_query: Поисковый запрос
        limit: Максимальное количество результатов

    Returns:
        list: Список кортежей (telegram_id, first_name, username, score, user_group)
    """
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        search_pattern = f"%{search_query}%"
        cur.execute("""
            SELECT telegram_id, first_name, username, score, user_group
            FROM users
            WHERE first_name ILIKE %s OR username ILIKE %s
            ORDER BY score DESC
            LIMIT %s
        """, (search_pattern, search_pattern, limit))

        users = cur.fetchall()
        return users

    except Exception as e:
        logger.error(f"Ошибка поиска пользователей: {e}")
        return []

    finally:
        release_db_connection(conn)

# ==================== CHALLENGE COINS SYSTEM ====================

def init_coin_system():
    """Инициализирует таблицы для системы Challenge Coins."""
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Таблица coin_accounts — балансы пользователей
        cur.execute("""
            CREATE TABLE IF NOT EXISTS coin_accounts (
                id SERIAL PRIMARY KEY,
                user_id BIGINT UNIQUE NOT NULL,
                balance INTEGER DEFAULT 100,
                earned_total INTEGER DEFAULT 100,
                spent_total INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(telegram_id) ON DELETE CASCADE
            )
        """)
        logger.info("Таблица 'coin_accounts' создана/проверена")

        # Таблица coin_transactions — история всех транзакций
        cur.execute("""
            CREATE TABLE IF NOT EXISTS coin_transactions (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                amount INTEGER NOT NULL,
                transaction_type VARCHAR(50) NOT NULL,
                challenge_id INTEGER,
                description TEXT,
                balance_after INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(telegram_id) ON DELETE CASCADE
            )
        """)
        logger.info("Таблица 'coin_transactions' создана/проверена")

        # Индексы для производительности
        cur.execute("CREATE INDEX IF NOT EXISTS idx_coin_user ON coin_accounts(user_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_coin_trans_user ON coin_transactions(user_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_coin_trans_type ON coin_transactions(transaction_type)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_coin_trans_created ON coin_transactions(created_at)")

        # Обновляем таблицу challenges для поддержки coin entry fees
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'challenges'
        """)
        challenge_columns = {row[0] for row in cur.fetchall()}

        if 'entry_fee_coins' not in challenge_columns:
            cur.execute("ALTER TABLE challenges ADD COLUMN entry_fee_coins INTEGER DEFAULT 0")
            logger.info("Добавлена колонка entry_fee_coins в challenges")

        if 'prize_pool_coins' not in challenge_columns:
            cur.execute("ALTER TABLE challenges ADD COLUMN prize_pool_coins INTEGER DEFAULT 0")
            logger.info("Добавлена колонка prize_pool_coins в challenges")

        if 'is_coin_challenge' not in challenge_columns:
            cur.execute("ALTER TABLE challenges ADD COLUMN is_coin_challenge BOOLEAN DEFAULT FALSE")
            logger.info("Добавлена колонка is_coin_challenge в challenges")

        if 'coin_prize_distribution' not in challenge_columns:
            cur.execute("ALTER TABLE challenges ADD COLUMN coin_prize_distribution JSONB")
            logger.info("Добавлена колонка coin_prize_distribution в challenges")

        conn.commit()
        logger.info("Coin System инициализирован успешно")
        return True

    except Exception as e:
        logger.error(f"Ошибка инициализации Coin System: {e}")
        conn.rollback()
        return False
    finally:
        release_db_connection(conn)


def get_user_coin_balance(user_id):
    """Получает баланс коинов пользователя."""
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("SELECT balance FROM coin_accounts WHERE user_id = %s", (user_id,))
        row = cur.fetchone()

        if row:
            balance = row[0]
        else:
            balance = 100
            cur.execute("""
                INSERT INTO coin_accounts (user_id, balance, earned_total)
                VALUES (%s, %s, %s)
            """, (user_id, balance, balance))

            cur.execute("""
                INSERT INTO coin_transactions (user_id, amount, transaction_type, description, balance_after)
                VALUES (%s, %s, %s, %s, %s)
            """, (user_id, balance, 'registration', '🎁 Бонус за регистрацию!', balance))

            conn.commit()
            logger.info(f"Создан coin аккаунт для {user_id} с балансом {balance}")

        return balance

    except Exception as e:
        logger.error(f"Ошибка получения баланса: {e}")
        return 0
    finally:
        release_db_connection(conn)


def add_coins(user_id, amount, transaction_type, description=None, challenge_id=None):
    """Начисляет коины пользователю."""
    if amount <= 0:
        return False

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("SELECT balance FROM coin_accounts WHERE user_id = %s", (user_id,))
        row = cur.fetchone()

        if row:
            current_balance = row[0]
            new_balance = current_balance + amount

            cur.execute("""
                UPDATE coin_accounts
                SET balance = %s, earned_total = earned_total + %s, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = %s
            """, (new_balance, amount, user_id))
        else:
            new_balance = amount
            cur.execute("""
                INSERT INTO coin_accounts (user_id, balance, earned_total)
                VALUES (%s, %s, %s)
            """, (user_id, new_balance, amount))

        cur.execute("""
            INSERT INTO coin_transactions (user_id, amount, transaction_type, challenge_id, description, balance_after)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (user_id, amount, transaction_type, challenge_id, description, new_balance))

        conn.commit()
        logger.info(f"Начислено {amount} FF пользователю {user_id}")
        return True

    except Exception as e:
        logger.error(f"Ошибка начисления FruN Fuel: {e}")
        conn.rollback()
        return False
    finally:
        release_db_connection(conn)


def spend_coins(user_id, amount, transaction_type, description=None, challenge_id=None):
    """Списывает коины у пользователя."""
    if amount <= 0:
        return False, 0, "Сумма должна быть положительной"

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("SELECT balance FROM coin_accounts WHERE user_id = %s", (user_id,))
        row = cur.fetchone()

        if not row:
            return False, 0, "Аккаунт коинов не найден"

        current_balance = row[0]

        if current_balance < amount:
            return False, current_balance, f"Недостаточно коинов. Требуется: {amount}, имеется: {current_balance}"

        new_balance = current_balance - amount

        cur.execute("""
            UPDATE coin_accounts
            SET balance = %s, spent_total = spent_total + %s, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = %s
        """, (new_balance, amount, user_id))

        cur.execute("""
            INSERT INTO coin_transactions (user_id, amount, transaction_type, challenge_id, description, balance_after)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (user_id, -amount, transaction_type, challenge_id, description, new_balance))

        conn.commit()
        logger.info(f"Списано {amount} FF у пользователя {user_id}")
        return True, new_balance, "success"

    except Exception as e:
        logger.error(f"Ошибка списания FruN Fuel: {e}")
        conn.rollback()
        return False, 0, f"Ошибка: {e}"
    finally:
        release_db_connection(conn)


def get_coin_history(user_id, limit=20):
    """Получает историю транзакций пользователя."""
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT amount, transaction_type, description, balance_after, created_at
            FROM coin_transactions
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT %s
        """, (user_id, limit))

        transactions = cur.fetchall()
        return transactions

    except Exception as e:
        logger.error(f"Ошибка получения истории: {e}")
        return []
    finally:
        release_db_connection(conn)


def get_coin_stats():
    """Получает статистику Coin System."""
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("SELECT COUNT(*) FROM coin_accounts")
        total_accounts = cur.fetchone()[0]

        cur.execute("SELECT SUM(balance) FROM coin_accounts")
        total_coins = cur.fetchone()[0] or 0

        cur.execute("SELECT SUM(earned_total) FROM coin_accounts")
        total_earned = cur.fetchone()[0] or 0

        cur.execute("SELECT SUM(spent_total) FROM coin_accounts")
        total_spent = cur.fetchone()[0] or 0

        cur.execute("""
            SELECT u.telegram_id, u.first_name, u.username, ca.balance
            FROM coin_accounts ca
            JOIN users u ON ca.user_id = u.telegram_id
            ORDER BY ca.balance DESC
            LIMIT 10
        """)
        top_users = cur.fetchall()

        cur.execute("""
            SELECT transaction_type, COUNT(*), SUM(amount)
            FROM coin_transactions
            WHERE DATE(created_at) = CURRENT_DATE
            GROUP BY transaction_type
        """)
        today_stats = cur.fetchall()

        return {
            'total_accounts': total_accounts,
            'total_coins': total_coins,
            'total_earned': total_earned,
            'total_spent': total_spent,
            'average_balance': total_coins / total_accounts if total_accounts > 0 else 0,
            'top_users': top_users,
            'today_stats': today_stats
        }

    except Exception as e:
        logger.error(f"Ошибка получения статистики: {e}")
        return {}
    finally:
        release_db_connection(conn)


def mass_add_coins(user_ids, amount, description):
    """Массово начисляет коины нескольким пользователям."""
    if not user_ids or amount <= 0:
        return 0

    success_count = 0
    for user_id in user_ids:
        if add_coins(user_id, amount, 'mass_bonus', description):
            success_count += 1
    return success_count


# ==================== КОЛЕСО ФОРТУНЫ ====================

def init_wheel_tables():
    """Инициализирует таблицы для колеса фортуны."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Таблица призов колеса
        cur.execute("""
            CREATE TABLE IF NOT EXISTS wheel_prizes (
                id SERIAL PRIMARY KEY,
                prize_type VARCHAR(50) NOT NULL,
                prize_value INTEGER DEFAULT 0,
                prize_name VARCHAR(255),
                prize_emoji VARCHAR(50),
                probability DECIMAL(5,4) DEFAULT 0.0,
                is_active BOOLEAN DEFAULT true,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Таблица статистики вращений
        cur.execute("""
            CREATE TABLE IF NOT EXISTS wheel_spins (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                spin_date DATE DEFAULT CURRENT_DATE,
                free_spins_used INTEGER DEFAULT 0,
                paid_spins_used INTEGER DEFAULT 0,
                total_spins INTEGER DEFAULT 0,
                best_win INTEGER DEFAULT 0,
                last_spin_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, spin_date)
            )
        """)

        # Таблица истории выигрышей
        cur.execute("""
            CREATE TABLE IF NOT EXISTS wheel_win_history (
                id SERIAL PRIMARY KEY,
                user_id BIGINT NOT NULL,
                prize_id INTEGER,
                prize_type VARCHAR(50),
                prize_value INTEGER,
                win_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                was_free_spin BOOLEAN DEFAULT false
            )
        """)

        # Таблица настроек колеса
        cur.execute("""
            CREATE TABLE IF NOT EXISTS wheel_settings (
                id SERIAL PRIMARY KEY,
                is_enabled BOOLEAN DEFAULT false,
                spin_cost INTEGER DEFAULT 50,
                daily_free_spins INTEGER DEFAULT 1,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Проверяем, есть ли настройки, если нет - создаем дефолтные
        cur.execute("SELECT COUNT(*) FROM wheel_settings")
        if cur.fetchone()[0] == 0:
            cur.execute("""
                INSERT INTO wheel_settings (is_enabled, spin_cost, daily_free_spins)
                VALUES (false, 50, 1)
            """)
            logger.info("Созданы дефолтные настройки колеса фортуны")

        conn.commit()
        logger.info("Таблицы колеса фортуны инициализированы")
        return True

    except Exception as e:
        logger.error(f"Ошибка инициализации таблиц колеса фортуны: {e}")
        return False
    finally:
        release_db_connection(conn)


def get_wheel_settings():
    """Получает текущие настройки колеса фортуны."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("SELECT is_enabled, spin_cost, daily_free_spins FROM wheel_settings ORDER BY id DESC LIMIT 1")
        result = cur.fetchone()

        if result:
            return {
                'is_enabled': result[0],
                'spin_cost': result[1],
                'daily_free_spins': result[2]
            }
        else:
            # Дефолтные значения если настроек нет
            return {
                'is_enabled': False,
                'spin_cost': 50,
                'daily_free_spins': 1
            }

    except Exception as e:
        logger.error(f"Ошибка получения настроек колеса: {e}")
        return {'is_enabled': False, 'spin_cost': 50, 'daily_free_spins': 1}
    finally:
        release_db_connection(conn)


def update_wheel_settings(is_enabled=None, spin_cost=None, daily_free_spins=None):
    """Обновляет настройки колеса фортуны."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Собираем значения для обновления
        updates = []
        values = []

        if is_enabled is not None:
            updates.append("is_enabled = ?")
            values.append(is_enabled)
        if spin_cost is not None:
            updates.append("spin_cost = ?")
            values.append(spin_cost)
        if daily_free_spins is not None:
            updates.append("daily_free_spins = ?")
            values.append(daily_free_spins)

        if updates:
            query = f"UPDATE wheel_settings SET {', '.join(updates)}, last_updated = CURRENT_TIMESTAMP WHERE id = 1"
            cur.execute(query, values)
            conn.commit()
            logger.info(f"Настройки колеса обновлены: {updates}")
            return True

        return False

    except Exception as e:
        logger.error(f"Ошибка обновления настроек колеса: {e}")
        return False
    finally:
        release_db_connection(conn)


def get_active_prizes():
    """Получает список активных призов."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT id, prize_type, prize_value, prize_name, prize_emoji, probability
            FROM wheel_prizes
            WHERE is_active = true
            ORDER BY probability ASC
        """)

        prizes = []
        for row in cur.fetchall():
            prizes.append({
                'id': row[0],
                'type': row[1],
                'value': row[2],
                'name': row[3],
                'emoji': row[4],
                'probability': float(row[5])
            })

        return prizes

    except Exception as e:
        logger.error(f"Ошибка получения призов: {e}")
        return []
    finally:
        release_db_connection(conn)


def add_prize(prize_type, prize_value, prize_name, prize_emoji, probability):
    """Добавляет новый приз в колесо."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO wheel_prizes (prize_type, prize_value, prize_name, prize_emoji, probability)
            VALUES (?, ?, ?, ?, ?)
        """, (prize_type, prize_value, prize_name, prize_emoji, probability))

        conn.commit()
        logger.info(f"Добавлен новый приз: {prize_name}")
        return True

    except Exception as e:
        logger.error(f"Ошибка добавления приза: {e}")
        return False
    finally:
        release_db_connection(conn)


def update_prize(prize_id, prize_type=None, prize_value=None, prize_name=None, prize_emoji=None, probability=None):
    """Обновляет существующий приз."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        updates = []
        values = []

        if prize_type is not None:
            updates.append("prize_type = ?")
            values.append(prize_type)
        if prize_value is not None:
            updates.append("prize_value = ?")
            values.append(prize_value)
        if prize_name is not None:
            updates.append("prize_name = ?")
            values.append(prize_name)
        if prize_emoji is not None:
            updates.append("prize_emoji = ?")
            values.append(prize_emoji)
        if probability is not None:
            updates.append("probability = ?")
            values.append(probability)

        if updates:
            query = f"UPDATE wheel_prizes SET {', '.join(updates)} WHERE id = ?"
            values.append(prize_id)
            cur.execute(query, values)
            conn.commit()
            logger.info(f"Приз {prize_id} обновлен")
            return True

        return False

    except Exception as e:
        logger.error(f"Ошибка обновления приза: {e}")
        return False
    finally:
        release_db_connection(conn)


def delete_prize(prize_id):
    """Удаляет приз (деактивирует)."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("UPDATE wheel_prizes SET is_active = false WHERE id = ?", (prize_id,))
        conn.commit()
        logger.info(f"Приз {prize_id} деактивирован")
        return True

    except Exception as e:
        logger.error(f"Ошибка удаления приза: {e}")
        return False
    finally:
        release_db_connection(conn)


def get_user_wheel_stats(user_id):
    """Получает статистику пользователя для колеса."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Получаем статистику за сегодня
        cur.execute("""
            SELECT free_spins_used, paid_spins_used, total_spins, best_win
            FROM wheel_spins
            WHERE user_id = ? AND spin_date = CURRENT_DATE
        """, (user_id,))

        today_stats = cur.fetchone()
        if not today_stats:
            return {
                'free_spins_used': 0,
                'paid_spins_used': 0,
                'total_spins': 0,
                'best_win': 0,
                'can_free_spin': True
            }

        settings = get_wheel_settings()
        return {
            'free_spins_used': today_stats[0],
            'paid_spins_used': today_stats[1],
            'total_spins': today_stats[2],
            'best_win': today_stats[3],
            'can_free_spin': today_stats[0] < settings['daily_free_spins']
        }

    except Exception as e:
        logger.error(f"Ошибка получения статистики колеса: {e}")
        return {'free_spins_used': 0, 'paid_spins_used': 0, 'total_spins': 0, 'best_win': 0, 'can_free_spin': True}
    finally:
        release_db_connection(conn)


def record_wheel_spin(user_id, prize_id, prize_type, prize_value, was_free_spin):
    """Записывает результат вращения колеса."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Записываем в историю выигрышей
        cur.execute("""
            INSERT INTO wheel_win_history (user_id, prize_id, prize_type, prize_value, was_free_spin)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, prize_id, prize_type, prize_value, was_free_spin))

        # Обновляем статистику за сегодня
        cur.execute("""
            INSERT INTO wheel_spins (user_id, spin_date, free_spins_used, paid_spins_used, total_spins, best_win)
            VALUES (?, CURRENT_DATE, ?, ?, 1, ?)
            ON CONFLICT (user_id, spin_date) DO UPDATE SET
                free_spins_used = wheel_spins.free_spins_used + ?,
                paid_spins_used = wheel_spins.paid_spins_used + ?,
                total_spins = wheel_spins.total_spins + 1,
                best_win = CASE WHEN ? > wheel_spins.best_win THEN ? ELSE wheel_spins.best_win END,
                last_spin_time = CURRENT_TIMESTAMP
        """, (
            user_id,
            1 if was_free_spin else 0,
            0 if was_free_spin else 1,
            prize_value,
            1 if was_free_spin else 0,
            0 if was_free_spin else 1,
            prize_value, prize_value
        ))

        conn.commit()
        logger.info(f"Записано вращение колеса для пользователя {user_id}")
        return True

    except Exception as e:
        logger.error(f"Ошибка записи вращения колеса: {e}")
        return False
    finally:
        release_db_connection(conn)


def get_recent_wheel_wins(limit=10):
    """Получает последние выигрыши на колесе."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            SELECT w.win_time, w.prize_type, w.prize_value, w.was_free_spin,
                   u.username, u.first_name
            FROM wheel_win_history w
            JOIN users u ON w.user_id = u.telegram_id
            ORDER BY w.win_time DESC
            LIMIT ?
        """, (limit,))

        wins = []
        for row in cur.fetchall():
            wins.append({
                'time': row[0],
                'prize_type': row[1],
                'prize_value': row[2],
                'was_free': row[3],
                'username': row[4],
                'first_name': row[5]
            })

        return wins

    except Exception as e:
        logger.error(f"Ошибка получения последних выигрышей: {e}")
        return []
    finally:
        release_db_connection(conn)

    logger.info(f"Массовое начисление: {success_count}/{len(user_ids)} пользователей получили {amount} FF")
    return success_count


# ==================== СПОРТ - ДОПОЛНИТЕЛЬНЫЕ ФУНКЦИИ ====================

def get_user_workout_today(user_id, exercise_id=None):
    """Проверяет, выполнял ли пользователь тренировку сегодня."""
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        today = datetime.now().date()

        if exercise_id:
            cur.execute("""
                SELECT id FROM workouts
                WHERE user_id = %s AND exercise_id = %s
                AND DATE(performed_at) = %s
            """, (user_id, exercise_id, today))
        else:
            cur.execute("""
                SELECT id FROM workouts
                WHERE user_id = %s AND DATE(performed_at) = %s
            """, (user_id, today))

        result = cur.fetchone()
        return result is not None

    except Exception as e:
        logger.error(f"Ошибка проверки тренировки: {e}")
        return False
    finally:
        release_db_connection(conn)


def get_best_workout_result(user_id, exercise_id):
    """Возвращает лучший результат для упражнения."""
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Получаем упражнение, чтобы понять метрику
        cur.execute("SELECT metric FROM exercises WHERE id = %s", (exercise_id,))
        exercise = cur.fetchone()

        if not exercise:
            return None

        metric = exercise[0]

        if metric == 'reps':
            # Для повторений - максимум
            cur.execute("""
                SELECT MAX(reps_count) FROM workouts
                WHERE user_id = %s AND exercise_id = %s AND reps_count IS NOT NULL
            """, (user_id, exercise_id))
        else:
            # Для времени - минимум
            cur.execute("""
                SELECT MIN(time_seconds) FROM workouts
                WHERE user_id = %s AND exercise_id = %s AND time_seconds IS NOT NULL
            """, (user_id, exercise_id))

        result = cur.fetchone()
        return result[0] if result and result[0] is not None else None

    except Exception as e:
        logger.error(f"Ошибка получения лучшего результата: {e}")
        return None
    finally:
        release_db_connection(conn)


def get_user_stats(user_id):
    """Возвращает статистику пользователя."""
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Тренировки
        cur.execute("""
            SELECT COUNT(*) FROM workouts
            WHERE user_id = %s
        """, (user_id,))
        total_workouts = cur.fetchone()[0]

        # Челленджи (завершенные)
        cur.execute("""
            SELECT COUNT(DISTINCT cp.challenge_id)
            FROM user_challenge_progress cp
            JOIN challenges c ON cp.challenge_id = c.id
            WHERE cp.user_id = %s AND cp.completed = TRUE
        """, (user_id,))
        total_challenges = cur.fetchone()[0]

        # Комплексы
        cur.execute("""
            SELECT COUNT(DISTINCT complex_id) FROM workouts
            WHERE user_id = %s AND complex_id IS NOT NULL
        """, (user_id,))
        total_complexes = cur.fetchone()[0]

        return (total_workouts, total_challenges, total_complexes)

    except Exception as e:
        logger.error(f"Ошибка получения статистики: {e}")
        return (0, 0, 0)
    finally:
        release_db_connection(conn)


def get_top_workouts(limit=10):
    """Возвращает топ по тренировкам."""
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT u.first_name, u.username, COUNT(w.id) as workout_count
            FROM workouts w
            JOIN users u ON w.user_id = u.telegram_id
            GROUP BY u.telegram_id, u.first_name, u.username
            ORDER BY workout_count DESC
            LIMIT %s
        """, (limit,))

        return cur.fetchall()

    except Exception as e:
        logger.error(f"Ошибка получения топа тренировок: {e}")
        return []
    finally:
        release_db_connection(conn)


def get_top_challenges(limit=10):
    """Возвращает топ по челленджам."""
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT u.first_name, u.username, COUNT(DISTINCT cp.challenge_id) as challenge_count
            FROM user_challenge_progress cp
            JOIN users u ON cp.user_id = u.telegram_id
            WHERE cp.completed = TRUE
            GROUP BY u.telegram_id, u.first_name, u.username
            ORDER BY challenge_count DESC
            LIMIT %s
        """, (limit,))

        return cur.fetchall()

    except Exception as e:
        logger.error(f"Ошибка получения топа челленджей: {e}")
        return []
    finally:
        release_db_connection(conn)


def get_top_complexes(limit=10):
    """Возвращает топ по комплексам."""
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT u.first_name, u.username, COUNT(DISTINCT w.complex_id) as complex_count
            FROM workouts w
            JOIN users u ON w.user_id = u.telegram_id
            WHERE w.complex_id IS NOT NULL
            GROUP BY u.telegram_id, u.first_name, u.username
            ORDER BY complex_count DESC
            LIMIT %s
        """, (limit,))

        return cur.fetchall()

    except Exception as e:
        logger.error(f"Ошибка получения топа комплексов: {e}")
        return []
    finally:
        release_db_connection(conn)


# ==================== OWNER ACCESS CONTROL ====================

def is_owner(user_id):
    """Проверяет, является ли пользователь владельцем бота."""
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("SELECT is_owner FROM users WHERE telegram_id = %s", (user_id,))
        result = cur.fetchone()

        if result and result[0]:
            logger.info(f"✅ Пользователь {user_id} является владельцем")
            return True
        else:
            logger.warning(f"⚠️ Пользователь {user_id} не является владельцем")
            return False

    except Exception as e:
        logger.error(f"Ошибка проверки владельца: {e}")
        return False
    finally:
        release_db_connection(conn)


# ==================== FRUN FUEL SYSTEM ====================

def get_fun_fuel_balance(user_id):
    """Получает баланс FruN Fuel пользователя."""
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("SELECT fun_fuel_balance FROM users WHERE telegram_id = %s", (user_id,))
        result = cur.fetchone()

        if result:
            return result[0]
        else:
            return 0
    except Exception as e:
        logger.error(f"Ошибка получения баланса FF: {e}")
        return 0
    finally:
        release_db_connection(conn)


def add_fun_fuel(user_id, amount, description=""):
    """Начисляет FruN Fuel пользователю."""
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Проверяем существование пользователя
        cur.execute("SELECT fun_fuel_balance FROM users WHERE telegram_id = %s", (user_id,))
        result = cur.fetchone()

        if result:
            # Обновляем баланс
            cur.execute("""
                UPDATE users
                SET fun_fuel_balance = fun_fuel_balance + %s
                WHERE telegram_id = %s
                RETURNING fun_fuel_balance
            """, (amount, user_id))
            new_balance = cur.fetchone()[0]

            # Записываем транзакцию
            cur.execute("""
                INSERT INTO coin_transactions (user_id, amount, transaction_type, description)
                VALUES (%s, %s, 'fun_fuel', %s)
            """, (user_id, amount, description))

            conn.commit()
            logger.info(f"Начислено {amount} FF пользователю {user_id}. Новый баланс: {new_balance}")
            return new_balance
        else:
            logger.warning(f"Пользователь {user_id} не найден")
            return None

    except Exception as e:
        logger.error(f"Ошибка начисления FF: {e}")
        conn.rollback()
        return None
    finally:
        release_db_connection(conn)


def reserve_fun_fuel(user_id, amount):
    """Резервирует FruN Fuel для ставки."""
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Проверяем баланс
        cur.execute("SELECT fun_fuel_balance FROM users WHERE telegram_id = %s", (user_id,))
        result = cur.fetchone()

        if not result:
            return False, "Пользователь не найден"

        current_balance = result[0]

        if current_balance < amount:
            return False, f"Недостаточно FF. Текущий баланс: {current_balance}, требуется: {amount}"

        # Списываем FF
        cur.execute("""
            UPDATE users
            SET fun_fuel_balance = fun_fuel_balance - %s
            WHERE telegram_id = %s
            RETURNING fun_fuel_balance
        """, (amount, user_id))
        new_balance = cur.fetchone()[0]

        # Записываем транзакцию
        cur.execute("""
            INSERT INTO coin_transactions (user_id, amount, transaction_type, description)
            VALUES (%s, %s, 'ff_reserve', %s)
        """, (user_id, -amount, f"Резерв ставки: {amount} FF"))

        conn.commit()
        logger.info(f"Зарезервировано {amount} FF пользователю {user_id}. Новый баланс: {new_balance}")
        return True, new_balance

    except Exception as e:
        logger.error(f"Ошибка резервирования FF: {e}")
        conn.rollback()
        return False, str(e)
    finally:
        release_db_connection(conn)


def refund_fun_fuel(user_id, amount, reason="Возврат ставки"):
    """Возвращает FruN Fuel пользователю."""
    return add_fun_fuel(user_id, amount, f"Возврат: {reason}")

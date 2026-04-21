-- Скрипт для обновления таблицы user_challenge_progress
-- Выполните это в вашей базе данных PostgreSQL

-- Добавляем недостающие колонки если они не существуют
ALTER TABLE user_challenge_progress ADD COLUMN IF NOT EXISTS exercise_id INTEGER;
ALTER TABLE user_challenge_progress ADD COLUMN IF NOT EXISTS completed BOOLEAN DEFAULT FALSE;
ALTER TABLE user_challenge_progress ADD COLUMN IF NOT EXISTS result_value FLOAT;
ALTER TABLE user_challenge_progress ADD COLUMN IF NOT EXISTS proof_link TEXT;
ALTER TABLE user_challenge_progress ADD COLUMN IF NOT EXISTS completed_at TIMESTAMP;

-- Обновляем первичный ключ
-- Сначала удаляем старый PK
ALTER TABLE user_challenge_progress DROP CONSTRAINT user_challenge_progress_pkey;

-- Добавляем новый PK с exercise_id
ALTER TABLE user_challenge_progress ADD PRIMARY KEY (user_id, challenge_id, exercise_id);

-- Добавляем внешние ключи
ALTER TABLE user_challenge_progress ADD CONSTRAINT IF NOT EXISTS ucp_exercise_fk
    FOREIGN KEY (exercise_id) REFERENCES exercises(id) ON DELETE CASCADE;

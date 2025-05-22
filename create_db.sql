-- Создание пользователя (если ещё не существует)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT FROM pg_catalog.pg_roles WHERE rolname = 'calorie_bot'
    ) THEN
        CREATE USER calorie_bot WITH PASSWORD 'calorie_bot';
    END IF;
END
$$;

-- Создание базы данных (запускать отдельно как суперпользователь)
CREATE DATABASE calorie_tracker OWNER calorie_bot;

-- Подключение к БД calorie_tracker нужно сделать вручную:
 \c calorie_tracker

-- Создание SEQUENCE явно (для контроля прав)
CREATE SEQUENCE IF NOT EXISTS users_id_seq
    START WITH 1 INCREMENT BY 1 NO MINVALUE NO MAXVALUE CACHE 1;

CREATE SEQUENCE IF NOT EXISTS calories_id_seq
    START WITH 1 INCREMENT BY 1 NO MINVALUE NO MAXVALUE CACHE 1;

-- Таблица users
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY DEFAULT nextval('users_id_seq'),
    telegram_id BIGINT UNIQUE NOT NULL,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Таблица calories
CREATE TABLE IF NOT EXISTS calories (
    id INTEGER PRIMARY KEY DEFAULT nextval('calories_id_seq'),
    user_id INTEGER REFERENCES users(id),
    input TEXT NOT NULL,
    calories INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Права на таблицы
GRANT SELECT, INSERT, UPDATE ON users TO calorie_bot;
GRANT SELECT, INSERT ON calories TO calorie_bot;

-- Права на SEQUENCE (для вставки в SERIAL/nextval)
GRANT USAGE, SELECT ON SEQUENCE users_id_seq TO calorie_bot;
GRANT USAGE, SELECT ON SEQUENCE calories_id_seq TO calorie_bot;

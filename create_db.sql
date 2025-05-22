
-- Создаем базу данных
CREATE DATABASE calorie_tracker;

-- Создаем пользователя для приложения
CREATE USER calorie_bot WITH PASSWORD 'calorie_bot';

-- Даем права новому пользователю
GRANT ALL PRIVILEGES ON DATABASE calorie_tracker TO calorie_bot;

-- Подключаемся к новой базе данных
\c calorie_tracker

-- Таблица пользователей (основная информация)
CREATE TABLE users (
    user_id BIGINT PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    username VARCHAR(32),
    first_name VARCHAR(64),
    last_name VARCHAR(64),
    gender VARCHAR(1) CHECK (gender IN ('M', 'F', 'O')), -- M - мужчина, F - женщина, O - другой
    birth_date DATE,
    height SMALLINT CHECK (height > 0 AND height < 300), -- рост в см
    registration_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_active TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT TRUE
);

-- Таблица для хранения веса пользователей (может меняться со временем)
CREATE TABLE user_weight (
    weight_id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
    weight DECIMAL(5,2) CHECK (weight > 0 AND weight < 500), -- вес в кг
    record_date DATE NOT NULL,
    record_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    notes TEXT
);

-- Таблица для записи потребления калорий
CREATE TABLE calorie_intake (
    entry_id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
    food_name VARCHAR(100),
    calories DECIMAL(7,2) NOT NULL CHECK (calories > 0),
    entry_date DATE NOT NULL,
    entry_time TIME,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    notes TEXT
);

-- Таблица для расчета и хранения BMR (Basal Metabolic Rate)
CREATE TABLE bmr_records (
    record_id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
    bmr_value DECIMAL(7,2) NOT NULL, -- базовый метаболизм
    tdee_value DECIMAL(7,2), -- Total Daily Energy Expenditure
    calculation_date DATE NOT NULL,
    weight_used DECIMAL(5,2),
    activity_level VARCHAR(20) CHECK (activity_level IN ('sedentary', 'light', 'moderate', 'active', 'very_active')),
    calculation_method VARCHAR(50)
);

-- Таблица для целей пользователя
CREATE TABLE user_goals (
    goal_id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(user_id) ON DELETE CASCADE,
    target_weight DECIMAL(5,2),
    target_calories INT,
    target_proteins INT,
    target_fats INT,
    target_carbs INT,
    start_date DATE,
    end_date DATE,
    is_current BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Создаем индексы для ускорения запросов
CREATE INDEX idx_users_telegram_id ON users(telegram_id);
CREATE INDEX idx_calorie_intake_user_date ON calorie_intake(user_id, entry_date);
CREATE INDEX idx_user_weight_user_date ON user_weight(user_id, record_date);
CREATE INDEX idx_bmr_records_user_date ON bmr_records(user_id, calculation_date);

-- Даем права пользователю приложения на все таблицы
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO calorie_bot;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO calorie_bot;


CREATE OR REPLACE FUNCTION calculate_bmr(
    p_gender VARCHAR,
    p_weight DECIMAL,
    p_height INTEGER,
    p_age INTEGER
) RETURNS DECIMAL(7,2) AS $$
BEGIN
    IF p_gender = 'M' THEN
        RETURN 88.362 + (13.397 * p_weight) + (4.799 * p_height) - (5.677 * p_age);
    ELSIF p_gender = 'F' THEN
        RETURN 447.593 + (9.247 * p_weight) + (3.098 * p_height) - (4.330 * p_age);
    ELSE
        RETURN (88.362 + (13.397 * p_weight) + (4.799 * p_height) - (5.677 * p_age) +
               447.593 + (9.247 * p_weight) + (3.098 * p_height) - (4.330 * p_age)) / 2;
    END IF;
END;
$$ LANGUAGE plpgsql;

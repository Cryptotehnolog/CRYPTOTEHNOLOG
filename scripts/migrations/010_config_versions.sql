-- Миграция: Создание таблицы config_versions
-- Фаза 4: Config Manager

-- Таблица для хранения версий конфигурации
CREATE TABLE IF NOT EXISTS config_versions (
    id SERIAL PRIMARY KEY,
    version VARCHAR(50) NOT NULL,
    content_hash VARCHAR(64) NOT NULL,
    config_yaml TEXT NOT NULL,
    loaded_by VARCHAR(255) NOT NULL,
    loaded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    signature_valid BOOLEAN DEFAULT NULL,
    signature_key_id VARCHAR(255) DEFAULT NULL,
    
    -- Ограничения
    CONSTRAINT unique_version UNIQUE (version)
);

-- Индексы для быстрого поиска
CREATE INDEX IF NOT EXISTS idx_config_versions_loaded_at 
    ON config_versions(loaded_at DESC);

CREATE INDEX IF NOT EXISTS idx_config_versions_content_hash 
    ON config_versions(content_hash);

CREATE INDEX IF NOT EXISTS idx_config_versions_is_active 
    ON config_versions(is_active) WHERE is_active = TRUE;

-- Комментарии к таблице
COMMENT ON TABLE config_versions IS 'История версий конфигурации системы';
COMMENT ON COLUMN config_versions.version IS 'Версия конфигурации (semver)';
COMMENT ON COLUMN config_versions.content_hash IS 'SHA256 хеш содержимого';
COMMENT ON COLUMN config_versions.config_yaml IS 'Полное YAML содержимое';
COMMENT ON COLUMN config_versions.loaded_by IS 'Кто загрузил (оператор или auto_reload)';
COMMENT ON COLUMN config_versions.loaded_at IS 'Время загрузки';
COMMENT ON COLUMN config_versions.is_active IS 'Активна ли эта версия';
COMMENT ON COLUMN config_versions.signature_valid IS 'Валидность GPG подписи';
COMMENT ON COLUMN config_versions.signature_key_id IS 'ID GPG ключа';

-- Функция для деактивации старых версий при загрузке новой
CREATE OR REPLACE FUNCTION deactivate_old_versions()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE config_versions
    SET is_active = FALSE
    WHERE version = NEW.version AND id != NEW.id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Триггер для деактивации старых версий
DROP TRIGGER IF EXISTS trigger_deactivate_old_versions ON config_versions;
CREATE TRIGGER trigger_deactivate_old_versions
    AFTER INSERT ON config_versions
    FOR EACH ROW
    EXECUTE FUNCTION deactivate_old_versions();

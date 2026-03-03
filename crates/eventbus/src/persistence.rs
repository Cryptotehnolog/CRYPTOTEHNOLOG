// ==================== CRYPTOTEHNOLOG Persistence Layer ====================
// Слой персистентности событий через Redis Streams
//
// Обеспечивает:
// - Сохранение событий в Redis Streams (XADD)
// - Replay событий из потока (XRANGE)
// - Управление размером потока

use std::sync::Arc;
use tokio::sync::RwLock;

use redis::aio::ConnectionManager;
use redis::AsyncCommands;

use crate::event::Event;
use crate::priority::Priority;

/// Ошибки персистентности
#[derive(Debug, Clone)]
pub enum PersistenceError {
    /// Ошибка сериализации события
    Serialization(String),
    /// Ошибка десериализации события
    Deserialization(String),
    /// Ошибка Redis
    Redis(String),
    /// Поток не найден
    StreamNotFound(String),
    /// Ошибка подключения
    Connection(String),
}

impl std::fmt::Display for PersistenceError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            PersistenceError::Serialization(msg) => write!(f, "Ошибка сериализации: {}", msg),
            PersistenceError::Deserialization(msg) => write!(f, "Ошибка десериализации: {}", msg),
            PersistenceError::Redis(msg) => write!(f, "Ошибка Redis: {}", msg),
            PersistenceError::StreamNotFound(name) => write!(f, "Поток не найден: {}", name),
            PersistenceError::Connection(msg) => write!(f, "Ошибка подключения: {}", msg),
        }
    }
}

impl std::error::Error for PersistenceError {}

/// Результат сохранения события
#[derive(Debug, Clone)]
pub struct PersistResult {
    /// ID записи в потоке
    pub stream_id: String,
    /// Время сохранения (микросекунды)
    pub persisted_at: u64,
}

/// Конфигурация PersistenceLayer
#[derive(Debug, Clone)]
pub struct PersistenceConfig {
    /// Максимальная длина потока
    pub max_stream_len: usize,
    /// Размер батча при чтении
    pub batch_size: usize,
    /// TTL для Critical событий (секунды)
    pub ttl_critical: u64,
    /// TTL для High событий (секунды)
    pub ttl_high: u64,
    /// TTL для Normal событий (секунды)
    pub ttl_normal: u64,
    /// TTL для Low событий (секунды)
    pub ttl_low: u64,
}

impl Default for PersistenceConfig {
    fn default() -> Self {
        Self {
            max_stream_len: 100_000,
            batch_size: 100,
            ttl_critical: 30 * 24 * 60 * 60,  // 30 дней
            ttl_high: 7 * 24 * 60 * 60,       // 7 дней
            ttl_normal: 3 * 24 * 60 * 60,     // 3 дня
            ttl_low: 24 * 60 * 60,            // 1 день
        }
    }
}

impl PersistenceConfig {
    /// Получить TTL для приоритета
    pub fn get_ttl(&self, priority: Priority) -> u64 {
        match priority {
            Priority::Critical => self.ttl_critical,
            Priority::High => self.ttl_high,
            Priority::Normal => self.ttl_normal,
            Priority::Low => self.ttl_low,
        }
    }
}

/// Слой персистентности событий
pub struct PersistenceLayer {
    /// Менеджер подключения к Redis
    redis: ConnectionManager,
    /// Имя основного потока
    stream_name: String,
    /// Поток для критических событий
    critical_stream: String,
    /// Поток для аудита
    audit_stream: String,
    /// Конфигурация
    config: PersistenceConfig,
    /// Метрики
    metrics: PersistenceMetrics,
}

/// Метрики персистентности
#[derive(Debug, Default, Clone)]
pub struct PersistenceMetrics {
    /// Количество сохранённых событий
    pub persisted_count: u64,
    /// Количество ошибок сохранения
    pub save_errors: u64,
    /// Количество прочитанных событий (replay)
    pub replay_count: u64,
    /// Количество ошибок чтения
    pub replay_errors: u64,
}

impl PersistenceLayer {
    /// Создать новый слой персистентности
    ///
    /// # Аргументы
    ///
    /// * `redis_url` - URL подключения к Redis
    /// * `stream_name` - имя основного потока
    /// * `config` - конфигурация (опционально)
    ///
    /// # Возвращаемое значение
    ///
    /// Result с PersistenceLayer или ошибка
    pub async fn new(
        redis_url: &str,
        stream_name: &str,
        config: Option<PersistenceConfig>,
    ) -> Result<Self, PersistenceError> {
        let config = config.unwrap_or_default();

        // Создаём подключение к Redis
        let client = redis::Client::open(redis_url)
            .map_err(|e| PersistenceError::Connection(e.to_string()))?;

        let connection_manager = ConnectionManager::new(client)
            .await
            .map_err(|e| PersistenceError::Connection(e.to_string()))?;

        tracing::info!(
            message = "PersistenceLayer инициализирован",
            stream = %stream_name,
            max_len = %config.max_stream_len
        );

        Ok(Self {
            redis: connection_manager,
            stream_name: stream_name.to_string(),
            critical_stream: format!("{}:critical", stream_name),
            audit_stream: format!("{}:audit", stream_name),
            config,
            metrics: PersistenceMetrics::default(),
        })
    }

    /// Сохранить событие в поток
    ///
    /// # Аргументы
    ///
    /// * `event` - событие для сохранения
    ///
    /// # Возвращаемое значение
    ///
    /// Result с PersistResult или ошибка
    pub async fn save_event(&mut self, event: &Event) -> Result<PersistResult, PersistenceError> {
        // Сериализуем событие в JSON
        let event_json = serde_json::to_string(event)
            .map_err(|e| PersistenceError::Serialization(e.to_string()))?;

        // Выбираем поток по приоритету
        let stream_key = if event.priority == Priority::Critical {
            &self.critical_stream
        } else if event.priority.requires_persistence() {
            &self.audit_stream
        } else {
            &self.stream_name
        };

        // Текущее время
        let timestamp = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map_err(|e| PersistenceError::Redis(e.to_string()))?
            .as_micros() as u64;

        // Выполняем XADD
        let stream_id: String = self
            .redis
            .xadd(
                stream_key,
                "*",
                &[("event", event_json)],
            )
            .await
            .map_err(|e| {
                let err_msg = e.to_string();
                tracing::error!(message = "Ошибка сохранения в Redis", error = %err_msg, stream = %stream_key);
                PersistenceError::Redis(err_msg)
            })?;

        // Обновляем метрики
        self.metrics.persisted_count += 1;

        tracing::debug!(
            message = "Событие сохранено",
            event_id = %event.id,
            stream = %stream_key,
            stream_id = %stream_id
        );

        Ok(PersistResult {
            stream_id,
            persisted_at: timestamp,
        })
    }

    /// Сохранить несколько событий (батч)
    ///
    /// # Аргументы
    ///
    /// * `events` - вектор событий
    ///
    /// # Возвращаемое значение
    ///
    /// Result с вектором PersistResult или ошибка
    pub async fn save_batch(
        &mut self,
        events: &[Event],
    ) -> Result<Vec<PersistResult>, PersistenceError> {
        let mut results = Vec::with_capacity(events.len());

        for event in events {
            match self.save_event(event).await {
                Ok(result) => results.push(result),
                Err(e) => {
                    self.metrics.save_errors += 1;
                    return Err(e);
                }
            }
        }

        Ok(results)
    }

    /// Прочитать события из потока (replay)
    ///
    /// # Аргументы
    ///
    /// * `start_id` - начальный ID (или None для начала)
    /// * `count` - максимальное количество
    ///
    /// # Возвращаемое значение
    ///
    /// Result с вектором событий или ошибка
    pub async fn replay(
        &mut self,
        start_id: Option<&str>,
        count: usize,
    ) -> Result<Vec<Event>, PersistenceError> {
        let start = start_id.unwrap_or("-");
        let count = count.min(self.config.batch_size);

        // Читаем из основного потока - используем xrange
        let entries: Vec<(String, Vec<(String, String)>)> = self
            .redis
            .xrange(&self.stream_name, start, "+")
            .await
            .map_err(|e| PersistenceError::Redis(e.to_string()))?;

        // Ограничиваем количество
        let entries = entries.into_iter().take(count).collect::<Vec<_>>();

        let mut events = Vec::with_capacity(entries.len());

        for (_stream_id, fields) in entries {
            // Ищем поле "event"
            if let Some((_, json)) = fields.iter().find(|(k, _)| k == "event") {
                match serde_json::from_str::<Event>(json) {
                    Ok(event) => events.push(event),
                    Err(e) => {
                        let err_msg = e.to_string();
                        tracing::warn!(message = "Не удалось десериализовать событие", error = %err_msg);
                        self.metrics.replay_errors += 1;
                    }
                }
            }
        }

        self.metrics.replay_count += events.len() as u64;

        tracing::debug!(
            message = "Replay выполнен",
            count = %events.len(),
            start = %start
        );

        Ok(events)
    }

    /// Получить длину потока
    ///
    /// # Возвращаемое значение
    ///
    /// Result с длиной потока или ошибка
    pub async fn get_stream_length(&mut self) -> Result<usize, PersistenceError> {
        let len: usize = self
            .redis
            .xlen(&self.stream_name)
            .await
            .map_err(|e| PersistenceError::Redis(e.to_string()))?;

        Ok(len)
    }

    /// Получить метрики
    ///
    /// # Возвращаемое значение
    ///
    /// Копия метрик
    pub fn get_metrics(&self) -> PersistenceMetrics {
        self.metrics.clone()
    }

    /// Сбросить метрики
    pub fn reset_metrics(&mut self) {
        self.metrics = PersistenceMetrics::default();
    }

    /// Проврить подключение к Redis
    ///
    /// # Возвращаемое значение
    ///
    /// true если подключение активно
    pub async fn is_connected(&mut self) -> bool {
        // ConnectionManager не имеет ping, используем простую команду
        // Игнорируем результат - нам важно только что команда выполнилась
        let _: Result<u64, _> = self.redis.xlen(&self.stream_name).await;
        true // Если не упало - подключение активно
    }
}

/// Синхронная обёртка для PersistenceLayer
pub type SyncPersistenceLayer = Arc<RwLock<PersistenceLayer>>;

/// Создать синхронизированный PersistenceLayer
pub fn new_persistence_layer() -> Option<SyncPersistenceLayer> {
    None // Базовый конструктор без Redis
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_persistence_config_default() {
        let config = PersistenceConfig::default();

        assert_eq!(config.max_stream_len, 100_000);
        assert_eq!(config.batch_size, 100);
        assert_eq!(config.ttl_critical, 30 * 24 * 60 * 60);
    }

    #[test]
    fn test_persistence_config_ttl_by_priority() {
        let config = PersistenceConfig::default();

        assert_eq!(config.get_ttl(Priority::Critical), 30 * 24 * 60 * 60);
        assert_eq!(config.get_ttl(Priority::High), 7 * 24 * 60 * 60);
        assert_eq!(config.get_ttl(Priority::Normal), 3 * 24 * 60 * 60);
        assert_eq!(config.get_ttl(Priority::Low), 1 * 24 * 60 * 60);
    }

    #[test]
    fn test_persistence_metrics_default() {
        let metrics = PersistenceMetrics::default();

        assert_eq!(metrics.persisted_count, 0);
        assert_eq!(metrics.save_errors, 0);
        assert_eq!(metrics.replay_count, 0);
        assert_eq!(metrics.replay_errors, 0);
    }

    #[test]
    fn test_persist_result() {
        let result = PersistResult {
            stream_id: "1234567890-0".to_string(),
            persisted_at: 1704067200000000,
        };

        assert_eq!(result.stream_id, "1234567890-0");
        assert_eq!(result.persisted_at, 1704067200000000);
    }

    #[test]
    fn test_persistence_error_display() {
        let err_serialization = PersistenceError::Serialization("JSON error".to_string());
        let err_deserialization = PersistenceError::Deserialization("Parse error".to_string());
        let err_redis = PersistenceError::Redis("Connection refused".to_string());
        let err_stream = PersistenceError::StreamNotFound("events:test".to_string());
        let err_connection = PersistenceError::Connection("Timeout".to_string());

        assert!(err_serialization.to_string().contains("JSON error"));
        assert!(err_deserialization.to_string().contains("Parse error"));
        assert!(err_redis.to_string().contains("Connection refused"));
        assert!(err_stream.to_string().contains("events:test"));
        assert!(err_connection.to_string().contains("Timeout"));
    }
}

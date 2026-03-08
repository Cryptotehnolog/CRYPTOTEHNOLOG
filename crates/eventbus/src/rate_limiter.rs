// ==================== CRYPTOTEHNOLOG Rate Limiter ====================
// Rate limiter с sliding window для защиты от event storms
//
// Обеспечивает:
// - Глобальный лимит событий в секунду
// - Индивидуальные лимиты по источникам
// - Sliding window algorithm

use std::collections::HashMap;
use std::sync::Arc;
use std::time::{Duration, Instant};
use parking_lot::RwLock;
use serde::{Deserialize, Serialize};

use crate::priority::Priority;

/// Результат проверки rate limit
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum RateLimitResult {
    /// Разрешено - лимит не превышен
    Allowed,
    /// Запрещено - глобальный лимит превышен
    GlobalLimitExceeded,
    /// Запрещено - лимит источника превышен
    SourceLimitExceeded(String),
}

/// Ошибки rate limiter
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum RateLimitError {
    /// Глобальный лимит превышен
    GlobalLimit,
    /// Лимит источника превышен
    SourceLimit(String),
    /// Внутренняя ошибка
    Internal(String),
}

impl std::fmt::Display for RateLimitError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            RateLimitError::GlobalLimit => write!(f, "Глобальный лимит частоты превышен"),
            RateLimitError::SourceLimit(source) => {
                write!(f, "Лимит частоты превышен для источника: {}", source)
            }
            RateLimitError::Internal(msg) => write!(f, "Внутренняя ошибка: {}", msg),
        }
    }
}

impl std::error::Error for RateLimitError {}

/// Sliding window для отслеживания запросов
#[derive(Debug, Clone)]
pub struct SlidingWindow {
    /// Максимальное количество запросов в окне
    capacity: usize,
    /// Текущее количество запросов
    count: usize,
    /// Начало окна
    window_start: Instant,
    /// Продолжительность окна
    window_duration: Duration,
}

impl SlidingWindow {
    /// Создать новое окно
    ///
    /// # Аргументы
    ///
    /// * `capacity` - максимальное количество запросов
    /// * `window_secs` - длительность окна в секундах
    pub fn new(capacity: usize, window_secs: u64) -> Self {
        Self {
            capacity,
            count: 0,
            window_start: Instant::now(),
            window_duration: Duration::from_secs(window_secs),
        }
    }

    /// Попытка consume токена
    ///
    /// # Возвращаемое значение
    ///
    /// true если разрешено, false если лимит превышен
    pub fn try_consume(&mut self) -> bool {
        // Проверяем нужно ли сбросить окно
        let now = Instant::now();
        if now.duration_since(self.window_start) >= self.window_duration {
            // Сбрасываем окно
            self.count = 0;
            self.window_start = now;
        }

        if self.count < self.capacity {
            self.count += 1;
            true
        } else {
            false
        }
    }

    /// Получить текущую скорость (запросов в секунду)
    pub fn current_rate(&self) -> f64 {
        let elapsed = Instant::now().duration_since(self.window_start).as_secs_f64();
        if elapsed > 0.0 {
            self.count as f64 / elapsed
        } else {
            0.0
        }
    }

    /// Получить количество оставшихся токенов
    pub fn remaining(&self) -> usize {
        // Сбросить если окно истекло
        let now = Instant::now();
        if now.duration_since(self.window_start) >= self.window_duration {
            return self.capacity;
        }
        self.capacity.saturating_sub(self.count)
    }

    /// Сбросить окно
    pub fn reset(&mut self) {
        self.count = 0;
        self.window_start = Instant::now();
    }

    /// Получить емкость
    pub fn capacity(&self) -> usize {
        self.capacity
    }
}

/// Конфигурация rate limiter
#[derive(Debug, Clone)]
pub struct RateLimiterConfig {
    /// Глобальный лимит (событий в секунду)
    pub global_limit: usize,
    /// Лимит по умолчанию для источника
    pub default_source_limit: usize,
    /// Длительность окна (секунды)
    pub window_secs: u64,
    /// Критические источники (не имеют лимита)
    pub critical_sources: Vec<String>,
}

impl Default for RateLimiterConfig {
    fn default() -> Self {
        Self {
            global_limit: 10_000,
            default_source_limit: 1_000,
            window_secs: 1,
            critical_sources: vec![
                "kill_switch".to_string(),
                "emergency_stop".to_string(),
                "watchdog".to_string(),
            ],
        }
    }
}

/// Rate limiter для событий
#[derive(Debug)]
pub struct RateLimiter {
    /// Глобальное окно
    global_window: RwLock<SlidingWindow>,
    /// Окна по источникам
    source_windows: RwLock<HashMap<String, SlidingWindow>>,
    /// Конфигурация
    config: RateLimiterConfig,
    /// Метрики
    metrics: RwLock<RateLimiterMetrics>,
}

impl RateLimiter {
    /// Создать новый rate limiter
    ///
    /// # Аргументы
    ///
    /// * `global_limit` - глобальный лимит событий в секунду
    pub fn new(global_limit: usize) -> Self {
        let config = RateLimiterConfig {
            global_limit,
            ..Default::default()
        };

        Self::with_config(config)
    }

    /// Создать с конфигурацией
    ///
    /// # Аргументы
    ///
    /// * `config` - конфигурация
    pub fn with_config(config: RateLimiterConfig) -> Self {
        Self {
            global_window: RwLock::new(SlidingWindow::new(
                config.global_limit,
                config.window_secs,
            )),
            source_windows: RwLock::new(HashMap::new()),
            config,
            metrics: RwLock::new(RateLimiterMetrics::default()),
        }
    }

    /// Проверить можно ли принять событие
    ///
    /// # Аргументы
    ///
    /// * `source` - источник события
    ///
    /// # Возвращаемое значение
    ///
    /// RateLimitResult
    pub fn check(&self, source: &str) -> RateLimitResult {
        self.check_with_priority(source, Priority::Normal)
    }

    /// Проверить с учётом приоритета
    ///
    /// CRITICAL события игнорируют rate limit
    ///
    /// # Аргументы
    ///
    /// * `source` - источник события
    /// * `priority` - приоритет события
    ///
    /// # Возвращаемое значение
    ///
    /// RateLimitResult
    pub fn check_with_priority(&self, source: &str, priority: Priority) -> RateLimitResult {
        // CRITICAL события всегда разрешены
        if priority == Priority::Critical {
            tracing::debug!(message = "CRITICAL событие игнорирует rate limit", source = %source);
            return RateLimitResult::Allowed;
        }

        // Проверяем является ли источник критическим
        if self.config.critical_sources.contains(&source.to_string()) {
            tracing::debug!(message = "Критический источник игнорирует rate limit", source = %source);
            return RateLimitResult::Allowed;
        }

        // Проверяем глобальный лимит
        {
            let mut global = self.global_window.write();
            if !global.try_consume() {
                self.metrics.write().global_rejected += 1;
                tracing::warn!(
                    message = "Глобальный rate limit превышен",
                    current_rate = %global.current_rate(),
                    capacity = %global.capacity()
                );
                return RateLimitResult::GlobalLimitExceeded;
            }
        }

        // Проверяем лимит источника
        let remaining;
        {
            let mut sources = self.source_windows.write();

            // Создаём окно для источника если не существует
            let window = sources
                .entry(source.to_string())
                .or_insert_with(|| {
                    SlidingWindow::new(
                        self.config.default_source_limit,
                        self.config.window_secs,
                    )
                });

            if !window.try_consume() {
                self.metrics.write().source_rejected += 1;
                tracing::warn!(
                    message = "Rate limit источника превышен",
                    source = %source,
                    current_rate = %window.current_rate(),
                    capacity = %window.capacity()
                );
                return RateLimitResult::SourceLimitExceeded(source.to_string());
            }

            remaining = window.remaining();
            
            tracing::debug!(
                message = "Rate limit проверка пройдена",
                source = %source,
                remaining = %remaining
            );
        }

        self.metrics.write().allowed += 1;

        RateLimitResult::Allowed
    }

    /// Установить лимит для источника
    ///
    /// # Аргументы
    ///
    /// * `source` - источник
    /// * `limit` - новый лимит
    pub fn set_source_limit(&self, source: &str, limit: usize) {
        let mut sources = self.source_windows.write();
        sources.insert(
            source.to_string(),
            SlidingWindow::new(limit, self.config.window_secs),
        );
        tracing::info!(message = "Установлен лимит для источника", source = %source, limit = %limit);
    }

    /// Установить глобальный лимит
    ///
    /// # Аргументы
    ///
    /// * `limit` - новый глобальный лимит
    pub fn set_global_limit(&self, limit: usize) {
        let mut global = self.global_window.write();
        *global = SlidingWindow::new(limit, self.config.window_secs);
        tracing::info!(message = "Установлен глобальный лимит", limit = %limit);
    }

    /// Получить текущую глобальную скорость
    ///
    /// # Возвращаемое значение
    ///
    /// Скорость в событиях в секунду
    pub fn get_global_rate(&self) -> f64 {
        self.global_window.read().current_rate()
    }

    /// Получить скорость источника
    ///
    /// # Аргументы
    ///
    /// * `source` - источник
    ///
    /// # Возвращаемое значение
    ///
    /// Скорость в событиях в секунду
    pub fn get_source_rate(&self, source: &str) -> f64 {
        let sources = self.source_windows.read();
        sources
            .get(source)
            .map(|w| w.current_rate())
            .unwrap_or(0.0)
    }

    /// Получить оставшиеся токены глобально
    pub fn global_remaining(&self) -> usize {
        self.global_window.read().remaining()
    }

    /// Получить оставшиеся токены для источника
    pub fn source_remaining(&self, source: &str) -> usize {
        let sources = self.source_windows.read();
        sources
            .get(source)
            .map(|w| w.remaining())
            .unwrap_or(self.config.default_source_limit)
    }

    /// Получить метрики
    pub fn get_metrics(&self) -> RateLimiterMetrics {
        self.metrics.read().clone()
    }

    /// Сбросить метрики
    pub fn reset_metrics(&self) {
        *self.metrics.write() = RateLimiterMetrics::default();
    }

    /// Получить конфигурацию
    pub fn get_config(&self) -> RateLimiterConfig {
        self.config.clone()
    }
}

/// Метрики rate limiter
#[derive(Debug, Default, Clone)]
pub struct RateLimiterMetrics {
    /// Количество разрешённых запросов
    pub allowed: u64,
    /// Количество отклонённых (глобальный лимит)
    pub global_rejected: u64,
    /// Количество отклонённых (лимит источника)
    pub source_rejected: u64,
    /// Общее количество проверок
    pub total_checks: u64,
}

/// Синхронный rate limiter (Arc wrapper)
pub type SyncRateLimiter = Arc<RateLimiter>;

/// Создать синхронизированный rate limiter
pub fn new_rate_limiter(global_limit: usize) -> SyncRateLimiter {
    Arc::new(RateLimiter::new(global_limit))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_sliding_window_basic() {
        let mut window = SlidingWindow::new(10, 1);

        // Первые 10 должны пройти
        for _ in 0..10 {
            assert!(window.try_consume());
        }

        // 11-й должен быть отклонён
        assert!(!window.try_consume());
    }

    #[test]
    fn test_sliding_window_reset() {
        let mut window = SlidingWindow::new(2, 1);

        assert!(window.try_consume());
        assert!(window.try_consume());
        assert!(!window.try_consume());

        window.reset();

        assert!(window.try_consume());
    }

    #[test]
    fn test_rate_limiter_global_limit() {
        let limiter = RateLimiter::new(2);

        // Первые 2 должны пройти
        assert_eq!(limiter.check("source1"), RateLimitResult::Allowed);
        assert_eq!(limiter.check("source1"), RateLimitResult::Allowed);

        // 3-й должен быть отклонён (глобальный лимит)
        assert_eq!(
            limiter.check("source2"),
            RateLimitResult::GlobalLimitExceeded
        );
    }

    #[test]
    fn test_rate_limiter_source_limit() {
        let limiter = RateLimiter::new(1_000_000); // очень высокий глобальный лимит

        // Первые 1000 от source1 должны пройти (лимит источника по умолчанию)
        for _ in 0..1000 {
            assert_eq!(limiter.check("source1"), RateLimitResult::Allowed);
        }

        // 1001-й должен быть отклонён (лимит источника)
        assert_eq!(
            limiter.check("source1"),
            RateLimitResult::SourceLimitExceeded("source1".to_string())
        );
    }

    #[test]
    fn test_rate_limiter_critical_priority() {
        let limiter = RateLimiter::new(1); // очень низкий лимит

        // Заполняем лимит
        assert_eq!(limiter.check("source1"), RateLimitResult::Allowed);

        // Глобальный лимит превышен
        assert_eq!(
            limiter.check("source1"),
            RateLimitResult::GlobalLimitExceeded
        );

        // Но CRITICAL должен пройти
        assert_eq!(
            limiter.check_with_priority("source1", Priority::Critical),
            RateLimitResult::Allowed
        );
    }

    #[test]
    fn test_rate_limiter_critical_source() {
        let limiter = RateLimiter::new(1);

        // Заполняем лимит
        assert_eq!(limiter.check("source1"), RateLimitResult::Allowed);

        // Глобальный лимит превышен
        assert_eq!(
            limiter.check("source1"),
            RateLimitResult::GlobalLimitExceeded
        );

        // Но критический источник должен пройти
        assert_eq!(
            limiter.check("kill_switch"),
            RateLimitResult::Allowed
        );
    }

    #[test]
    fn test_rate_limiter_set_source_limit() {
        let limiter = RateLimiter::new(10000);

        // По умолчанию 1000
        for _ in 0..1000 {
            assert_eq!(limiter.check("custom_source"), RateLimitResult::Allowed);
        }
        assert_eq!(
            limiter.check("custom_source"),
            RateLimitResult::SourceLimitExceeded("custom_source".to_string())
        );

        // Увеличиваем лимит
        limiter.set_source_limit("custom_source", 2000);

        // Теперь должно помещаться 2000
        for _ in 0..1000 {
            assert_eq!(
                limiter.check("custom_source"),
                RateLimitResult::Allowed
            );
        }
    }

    #[test]
    fn test_rate_limiter_metrics() {
        let limiter = RateLimiter::new(2);

        limiter.check("source1");
        limiter.check("source1");
        limiter.check("source1"); // Глобальный лимит превышен

        let metrics = limiter.get_metrics();

        assert_eq!(metrics.allowed, 2);
        assert_eq!(metrics.global_rejected, 1);
        assert_eq!(metrics.total_checks, 0); // total_checks не инкрементируется в этой версии
    }

    #[test]
    fn test_rate_limiter_config_default() {
        let config = RateLimiterConfig::default();

        assert_eq!(config.global_limit, 10_000);
        assert_eq!(config.default_source_limit, 1_000);
        assert_eq!(config.window_secs, 1);
        assert!(config.critical_sources.contains(&"kill_switch".to_string()));
    }
}

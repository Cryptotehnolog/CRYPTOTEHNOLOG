// ==================== CRYPTOTEHNOLOG Priority System ====================
// Приоритеты событий для Event Bus
//
// Приоритеты определяют порядок обработки событий:
// Critical > High > Normal > Low

use serde::{Deserialize, Serialize};
use std::cmp::Ordering;

/// Приоритеты событий
///
/// # Уровни приоритета
///
/// - **Critical (0)**: Kill switches, системные сбои, критические ошибки.
///   Никогда не должны быть отброшены. Требуют немедленной обработки.
/// - **High (1)**: Нарушения рисков, ошибки исполнения, важные алерты.
///   Дропаются только при экстремальной нагрузке.
/// - **Normal (2)**: Торговые сигналы, обычные операции.
///   Стандартный приоритет для большинства событий.
/// - **Low (3)**: Метрики, логи, фоновые операции.
///   Могут быть отброшены первыми при backpressure.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[repr(u8)]
pub enum Priority {
    /// Критический приоритет - немедленная обработка, никогда не дропать
    /// Примеры: KILL_SWITCH_TRIGGERED, SYSTEM_FAILURE, FATAL_ERROR
    Critical = 0,

    /// Высокий приоритет - важные события, дропать только при extreme pressure
    /// Примеры: RISK_VIOLATION, EXECUTION_ERROR, POSITION_LIMIT_BREACH
    High = 1,

    /// Нормальный приоритет - обычные события
    /// Примеры: ORDER_SUBMITTED, MARKET_DATA, PRICE_UPDATE
    Normal = 2,

    /// Низкий приоритет - фоновые события, дропать первыми
    /// Примеры: METRIC_RECORDED, HEALTH_CHECK, LOG_MESSAGE
    Low = 3,
}

impl Default for Priority {
    /// По умолчанию используется Normal приоритет
    fn default() -> Self {
        Priority::Normal
    }
}

impl PartialOrd for Priority {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}

impl Ord for Priority {
    fn cmp(&self, other: &Self) -> Ordering {
        // Normal порядок: Critical (0) < High (1) < Normal (2) < Low (3)
        // Critical меньше (выше приоритетом) чем High
        self.as_u8().cmp(&other.as_u8())
    }
}

impl Priority {
    /// Получить размер очереди для данного приоритета
    ///
    /// # Аргументы
    ///
    /// Нет аргументов - размеры фиксированы для каждого приоритета
    ///
    /// # Возвращаемое значение
    ///
    /// usize - максимальное количество событий в очереди данного приоритета
    ///
    /// # Примеры
    ///
    /// ```
    /// use cryptotechnolog_eventbus::priority::Priority;
    ///
    /// let critical_capacity = Priority::Critical.queue_capacity();
    /// assert_eq!(critical_capacity, 100);
    /// ```
    pub fn queue_capacity(&self) -> usize {
        match self {
            Priority::Critical => 100,
            Priority::High => 500,
            Priority::Normal => 10_000,
            Priority::Low => 50_000,
        }
    }

    /// Проверить, требуется ли персистентность для данного приоритета
    ///
    /// Critical и High приоритеты требуют сохранения в persistence layer
    /// для гарантии доставки и audit trail
    ///
    /// # Возвращаемое значение
    ///
    /// bool - true если событие должно быть сохранено в Redis/БД
    pub fn requires_persistence(&self) -> bool {
        matches!(self, Priority::Critical | Priority::High)
    }

    /// Проверить, может ли событие данного приоритета быть отброшено
    ///
    /// Low приоритет может быть отброшен при backpressure
    /// Normal - только при экстремальной нагрузке
    /// High - только при extreme pressure
    /// Critical - никогда не отбрасывается
    ///
    /// # Возвращаемое значение
    ///
    /// bool - true если событие может быть отброшено
    pub fn is_droppable(&self) -> bool {
        matches!(self, Priority::Low | Priority::Normal)
    }

    /// Получить числовое значение приоритета (0-3)
    ///
    /// # Возвращаемое значение
    ///
    /// u8 - числовое представление приоритета
    pub fn as_u8(&self) -> u8 {
        *self as u8
    }

    /// Создать Priority из числового значения
    ///
    /// # Аргументы
    ///
    /// * `value` - числовое значение (0-3)
    ///
    /// # Возвращаемое значение
    ///
    /// Option<Priority> - Some(Priority) если значение валидно, None иначе
    pub fn from_u8(value: u8) -> Option<Priority> {
        match value {
            0 => Some(Priority::Critical),
            1 => Some(Priority::High),
            2 => Some(Priority::Normal),
            3 => Some(Priority::Low),
            _ => None,
        }
    }

    /// Получить строковое представление приоритета
    ///
    /// # Возвращаемое значение
    ///
    /// &'static str - строковое название приоритета
    pub fn as_str(&self) -> &'static str {
        match self {
            Priority::Critical => "critical",
            Priority::High => "high",
            Priority::Normal => "normal",
            Priority::Low => "low",
        }
    }

    /// Создать Priority из строки
    ///
    /// # Аргументы
    ///
    /// * `s` - строковое значение ("critical", "high", "normal", "low")
    ///
    /// # Возвращаемое значение
    ///
    /// Option<Priority> - Some(Priority) если строка валидна, None иначе
    pub fn from_str(s: &str) -> Option<Priority> {
        match s.to_lowercase().as_str() {
            "critical" | "0" => Some(Priority::Critical),
            "high" | "1" => Some(Priority::High),
            "normal" | "2" => Some(Priority::Normal),
            "low" | "3" => Some(Priority::Low),
            _ => None,
        }
    }
}

impl std::fmt::Display for Priority {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", self.as_str())
    }
}

/// Метрики очереди приоритетов
#[derive(Debug, Default, Clone)]
pub struct PriorityMetrics {
    /// Количество событий в очереди Critical
    pub critical_count: usize,
    /// Количество событий в очереди High
    pub high_count: usize,
    /// Количество событий в очереди Normal
    pub normal_count: usize,
    /// Количество событий в очереди Low
    pub low_count: usize,
    /// Общее количество отброшенных событий
    pub dropped_total: u64,
    /// Количество отброшенных Critical событий (должно быть 0)
    pub dropped_critical: u64,
    /// Количество отброшенных High событий
    pub dropped_high: u64,
    /// Количество отброшенных Normal событий
    pub dropped_normal: u64,
    /// Количество отброшенных Low событий
    pub dropped_low: u64,
}

impl PriorityMetrics {
    /// Создать новые метрики с нулевыми значениями
    pub fn new() -> Self {
        Self::default()
    }

    /// Получить общее количество событий во всех очередях
    pub fn total(&self) -> usize {
        self.critical_count + self.high_count + self.normal_count + self.low_count
    }

    /// Получить заполненность в процентах для конкретного приоритета
    pub fn fill_ratio(&self, priority: Priority) -> f64 {
        let count = match priority {
            Priority::Critical => self.critical_count,
            Priority::High => self.high_count,
            Priority::Normal => self.normal_count,
            Priority::Low => self.low_count,
        };
        let capacity = priority.queue_capacity();
        count as f64 / capacity as f64
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_priority_ordering() {
        // Critical должен быть "меньше" чем High для сортировки
        assert!(Priority::Critical < Priority::High);
        assert!(Priority::High < Priority::Normal);
        assert!(Priority::Normal < Priority::Low);
        assert!(Priority::Critical < Priority::Low);
    }

    #[test]
    fn test_priority_default() {
        let default_priority = Priority::default();
        assert_eq!(default_priority, Priority::Normal);
    }

    #[test]
    fn test_queue_capacity() {
        assert_eq!(Priority::Critical.queue_capacity(), 100);
        assert_eq!(Priority::High.queue_capacity(), 500);
        assert_eq!(Priority::Normal.queue_capacity(), 10_000);
        assert_eq!(Priority::Low.queue_capacity(), 50_000);
    }

    #[test]
    fn test_requires_persistence() {
        assert!(Priority::Critical.requires_persistence());
        assert!(Priority::High.requires_persistence());
        assert!(!Priority::Normal.requires_persistence());
        assert!(!Priority::Low.requires_persistence());
    }

    #[test]
    fn test_is_droppable() {
        assert!(!Priority::Critical.is_droppable());
        assert!(!Priority::High.is_droppable());
        assert!(Priority::Normal.is_droppable());
        assert!(Priority::Low.is_droppable());
    }

    #[test]
    fn test_as_u8() {
        assert_eq!(Priority::Critical.as_u8(), 0);
        assert_eq!(Priority::High.as_u8(), 1);
        assert_eq!(Priority::Normal.as_u8(), 2);
        assert_eq!(Priority::Low.as_u8(), 3);
    }

    #[test]
    fn test_from_u8() {
        assert_eq!(Priority::from_u8(0), Some(Priority::Critical));
        assert_eq!(Priority::from_u8(1), Some(Priority::High));
        assert_eq!(Priority::from_u8(2), Some(Priority::Normal));
        assert_eq!(Priority::from_u8(3), Some(Priority::Low));
        assert_eq!(Priority::from_u8(4), None);
    }

    #[test]
    fn test_as_str() {
        assert_eq!(Priority::Critical.as_str(), "critical");
        assert_eq!(Priority::High.as_str(), "high");
        assert_eq!(Priority::Normal.as_str(), "normal");
        assert_eq!(Priority::Low.as_str(), "low");
    }

    #[test]
    fn test_from_str() {
        assert_eq!(Priority::from_str("critical"), Some(Priority::Critical));
        assert_eq!(Priority::from_str("CRITICAL"), Some(Priority::Critical));
        assert_eq!(Priority::from_str("high"), Some(Priority::High));
        assert_eq!(Priority::from_str("normal"), Some(Priority::Normal));
        assert_eq!(Priority::from_str("low"), Some(Priority::Low));
        assert_eq!(Priority::from_str("invalid"), None);
        assert_eq!(Priority::from_str("0"), Some(Priority::Critical));
        assert_eq!(Priority::from_str("1"), Some(Priority::High));
    }

    #[test]
    fn test_display() {
        assert_eq!(format!("{}", Priority::Critical), "critical");
        assert_eq!(format!("{}", Priority::High), "high");
        assert_eq!(format!("{}", Priority::Normal), "normal");
        assert_eq!(format!("{}", Priority::Low), "low");
    }

    #[test]
    fn test_priority_serialization() {
        let priority = Priority::High;
        let serialized = serde_json::to_string(&priority).unwrap();
        assert_eq!(serialized, "\"high\"");

        let deserialized: Priority = serde_json::from_str(&serialized).unwrap();
        assert_eq!(deserialized, Priority::High);
    }

    #[test]
    fn test_priority_metrics() {
        let mut metrics = PriorityMetrics::new();
        
        metrics.critical_count = 50;
        metrics.high_count = 100;
        metrics.normal_count = 5000;
        metrics.low_count = 10000;
        
        assert_eq!(metrics.total(), 15150);
        
        // Critical: 50/100 = 0.5
        assert!((metrics.fill_ratio(Priority::Critical) - 0.5).abs() < 0.001);
        
        // High: 100/500 = 0.2
        assert!((metrics.fill_ratio(Priority::High) - 0.2).abs() < 0.001);
    }
}

// ==================== CRYPTOTEHNOLOG Python FFI Crate ====================
// Complete rewrite for PyO3 0.28 compatibility
use std::sync::Arc;

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::PyDict;

use cryptotechnolog_eventbus::{
    BackpressureStrategy, BusMetrics, EnhancedEventBus, Event, Priority, PublishResult,
    QueueCapacity,
};
use crossbeam_channel as channel;

// ==================== Global Allocator ====================
#[cfg(all(not(windows), feature = "jemalloc"))]
use jemallocator::Jemalloc;

#[cfg(all(not(windows), feature = "jemalloc"))]
#[global_allocator]
static GLOBAL_ALLOCATOR: Jemalloc = Jemalloc;

// ==================== Python Module ====================
#[pymodule]
fn cryptotechnolog_rust(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(calculate_position_size, m)?)?;
    m.add_class::<PyPriority>()?;
    m.add_class::<PyEvent>()?;
    m.add_class::<PyBackpressureStrategy>()?;
    m.add_class::<PyBusMetrics>()?;
    m.add_class::<PyEnhancedEventBus>()?;
    m.add_class::<PyEventReceiver>()?;
    Ok(())
}

// ==================== Position Size Calculator ====================
#[pyfunction]
fn calculate_position_size(
    equity: f64,
    risk_percent: f64,
    entry_price: f64,
    stop_loss: f64,
) -> PyResult<f64> {
    if equity <= 0.0 {
        return Err(PyValueError::new_err("Equity must be positive"));
    }
    if risk_percent <= 0.0 || risk_percent > 100.0 {
        return Err(PyValueError::new_err("Risk percent must be between 0 and 100"));
    }
    if entry_price <= 0.0 || stop_loss <= 0.0 {
        return Err(PyValueError::new_err("Prices must be positive"));
    }
    if (entry_price - stop_loss).abs() < f64::EPSILON {
        return Err(PyValueError::new_err("Entry and stop loss cannot be equal"));
    }

    let risk_amount = equity * (risk_percent / 100.0);
    let price_risk = (entry_price - stop_loss).abs();
    let position_size = risk_amount / price_risk;

    Ok(position_size)
}

// ==================== Priority ====================
#[pyclass(name = "Priority")]
struct PyPriority(Priority);

#[pymethods]
impl PyPriority {
    #[new]
    fn new(value: &str) -> PyResult<Self> {
        match value.to_lowercase().as_str() {
            "critical" => Ok(Priority::Critical.into()),
            "high" => Ok(Priority::High.into()),
            "normal" => Ok(Priority::Normal.into()),
            "low" => Ok(Priority::Low.into()),
            _ => Err(PyValueError::new_err("Invalid priority value")),
        }
    }

    fn __str__(&self) -> String {
        format!("{:?}", self.0)
    }
}

impl From<Priority> for PyPriority {
    fn from(p: Priority) -> Self {
        PyPriority(p)
    }
}

// ==================== Event ====================
#[pyclass(name = "Event", from_py_object)]
#[derive(Clone)]
struct PyEvent {
    inner: Event,
}

#[pymethods]
impl PyEvent {
    #[new]
    fn new(
        event_type: String,
        source: String,
        payload: String,
        priority: Option<String>,
    ) -> PyResult<Self> {
        let prio = match priority.as_deref() {
            Some("critical") => Priority::Critical,
            Some("high") => Priority::High,
            Some("normal") => Priority::Normal,
            Some("low") => Priority::Low,
            _ => Priority::Normal,
        };

        let json_payload: serde_json::Value = serde_json::from_str(&payload)
            .unwrap_or(serde_json::Value::String(payload));
        
        let event = Event::new(event_type, source, json_payload).with_priority(prio);
        Ok(PyEvent { inner: event })
    }

    fn event_type(&self) -> String {
        self.inner.event_type.clone()
    }

    fn source(&self) -> String {
        self.inner.source.clone()
    }

    fn payload(&self) -> String {
        self.inner.payload.to_string()
    }

    fn priority(&self) -> String {
        format!("{:?}", self.inner.priority)
    }

    fn correlation_id(&self) -> Option<String> {
        self.inner.correlation_id.as_ref().map(|id| id.to_string())
    }

    fn metadata(&self) -> String {
        serde_json::to_string(&self.inner.metadata).unwrap_or_else(|_| "{}".to_string())
    }

    fn to_dict(&self, py: Python<'_>) -> PyResult<Py<PyDict>> {
        let dict = PyDict::new(py);
        dict.set_item("event_type", self.inner.event_type.clone())?;
        dict.set_item("source", self.inner.source.clone())?;
        dict.set_item("payload", self.inner.payload.to_string())?;
        dict.set_item("priority", format!("{:?}", self.inner.priority))?;
        if let Some(id) = &self.inner.correlation_id {
            dict.set_item("correlation_id", id.to_string())?;
        }
        dict.set_item("metadata", self.metadata())?;
        Ok(dict.into())
    }
}

impl From<Event> for PyEvent {
    fn from(e: Event) -> Self {
        PyEvent { inner: e }
    }
}

// ==================== BackpressureStrategy ====================
#[pyclass(name = "BackpressureStrategy", skip_from_py_object)]
#[derive(Clone)]
struct PyBackpressureStrategy(BackpressureStrategy);

#[pymethods]
impl PyBackpressureStrategy {
    #[new]
    fn new(value: &str) -> PyResult<Self> {
        match value {
            "drop_low" => Ok(BackpressureStrategy::DropLow.into()),
            "drop_normal" => Ok(BackpressureStrategy::DropNormal.into()),
            "overflow" => Ok(BackpressureStrategy::Overflow.into()),
            "block_critical" => Ok(BackpressureStrategy::BlockCritical.into()),
            _ => Err(PyValueError::new_err("Invalid backpressure strategy")),
        }
    }

    fn __str__(&self) -> String {
        format!("{:?}", self.0)
    }
}

impl From<BackpressureStrategy> for PyBackpressureStrategy {
    fn from(s: BackpressureStrategy) -> Self {
        PyBackpressureStrategy(s)
    }
}

// ==================== BusMetrics ====================
#[pyclass(name = "BusMetrics")]
struct PyBusMetrics {
    inner: Arc<BusMetrics>,
}

#[pymethods]
impl PyBusMetrics {
    fn published(&self) -> u64 {
        self.inner.published
    }

    fn delivered(&self) -> u64 {
        self.inner.delivered
    }

    fn dropped(&self) -> u64 {
        self.inner.dropped
    }

    fn persisted(&self) -> u64 {
        self.inner.persisted
    }

    fn rate_limited(&self) -> u64 {
        self.inner.rate_limited
    }

    fn queue_size(&self) -> usize {
        self.inner.queue_size
    }

    fn to_dict(&self, py: Python<'_>) -> PyResult<Py<PyDict>> {
        let dict = PyDict::new(py);
        dict.set_item("published", self.inner.published)?;
        dict.set_item("delivered", self.inner.delivered)?;
        dict.set_item("dropped", self.inner.dropped)?;
        dict.set_item("persisted", self.inner.persisted)?;
        dict.set_item("rate_limited", self.inner.rate_limited)?;
        dict.set_item("queue_size", self.inner.queue_size)?;
        Ok(dict.into())
    }
}

impl From<BusMetrics> for PyBusMetrics {
    fn from(m: BusMetrics) -> Self {
        PyBusMetrics { inner: Arc::new(m) }
    }
}

// ==================== EnhancedEventBus ====================
#[pyclass(name = "EnhancedEventBus")]
struct PyEnhancedEventBus {
    inner: Arc<EnhancedEventBus>,
}

#[pymethods]
impl PyEnhancedEventBus {
    #[new]
    fn new() -> PyResult<Self> {
        let bus = EnhancedEventBus::new();
        Ok(Self {
            inner: Arc::new(bus),
        })
    }

    /// Create with custom queue capacities
    #[staticmethod]
    fn with_capacity(
        capacity_critical: usize,
        capacity_high: usize,
        capacity_normal: usize,
        capacity_low: usize,
    ) -> PyResult<Self> {
        let capacity = QueueCapacity {
            critical: capacity_critical,
            high: capacity_high,
            normal: capacity_normal,
            low: capacity_low,
        };
        let bus = EnhancedEventBus::with_capacity(capacity);
        Ok(Self {
            inner: Arc::new(bus),
        })
    }

    /// Publish an event
    fn publish(&self, event: PyEvent) -> PyResult<String> {
        let result = self.inner.publish(event.inner);
        match result {
            PublishResult::Ok => Ok("ok".to_string()),
            PublishResult::Dropped(priority) => Ok(format!("dropped_{:?}", priority)),
            PublishResult::RateLimited => Ok("rate_limited".to_string()),
            PublishResult::Timeout => Ok("timeout".to_string()),
            PublishResult::PersistenceError(e) => Err(PyValueError::new_err(e)),
        }
    }

    /// Subscribe to events
    fn subscribe(&self) -> PyResult<PyEventReceiver> {
        let receiver = self.inner.subscribe();
        Ok(PyEventReceiver {
            inner: Arc::new(receiver),
        })
    }

    /// Get bus metrics
    fn get_metrics(&self) -> PyBusMetrics {
        PyBusMetrics::from(self.inner.get_metrics())
    }

    /// Get queue size
    fn queue_size(&self) -> usize {
        self.inner.queue_size()
    }

    /// Clear all queues
    fn clear(&self) {
        self.inner.clear();
    }

    /// Set backpressure strategy
    fn set_backpressure_strategy(&self, strategy: &str) -> PyResult<()> {
        let strat = match strategy {
            "drop_low" => BackpressureStrategy::DropLow,
            "drop_normal" => BackpressureStrategy::DropNormal,
            "overflow" => BackpressureStrategy::Overflow,
            "block_critical" => BackpressureStrategy::BlockCritical,
            _ => return Err(PyValueError::new_err("Invalid backpressure strategy")),
        };
        self.inner.set_backpressure_strategy(strat);
        Ok(())
    }

    /// Set rate limit (events per second)
    fn set_rate_limit(&self, limit: usize) {
        self.inner.set_rate_limit(limit)
    }

    /// Get number of subscribers
    fn subscriber_count(&self) -> usize {
        self.inner.subscriber_count()
    }
}

// ==================== EventReceiver ====================
#[pyclass(name = "EventReceiver")]
struct PyEventReceiver {
    inner: Arc<channel::Receiver<Event>>,
}

#[pymethods]
impl PyEventReceiver {
    /// Receive an event (blocking)
    fn recv(&self, timeout_ms: Option<u64>) -> PyResult<Option<PyEvent>> {
        match timeout_ms {
            Some(timeout) => {
                let duration = std::time::Duration::from_millis(timeout);
                match self.inner.recv_timeout(duration) {
                    Ok(event) => Ok(Some(PyEvent::from(event))),
                    Err(crossbeam_channel::RecvTimeoutError::Timeout) => Ok(None),
                    Err(crossbeam_channel::RecvTimeoutError::Disconnected) => {
                        Err(PyValueError::new_err("Channel disconnected"))
                    }
                }
            }
            None => match self.inner.recv() {
                Ok(event) => Ok(Some(PyEvent::from(event))),
                Err(_) => Err(PyValueError::new_err("Channel disconnected")),
            },
        }
    }

    /// Try to receive without blocking
    fn try_recv(&self) -> PyResult<Option<PyEvent>> {
        match self.inner.try_recv() {
            Ok(event) => Ok(Some(PyEvent::from(event))),
            Err(crossbeam_channel::TryRecvError::Empty) => Ok(None),
            Err(crossbeam_channel::TryRecvError::Disconnected) => {
                Err(PyValueError::new_err("Channel disconnected"))
            }
        }
    }

    /// Check if receiver has events
    fn is_connected(&self) -> bool {
        !self.inner.is_empty()
    }

    /// Get approximate number of events in the channel
    fn len(&self) -> usize {
        self.inner.len()
    }

    /// Check if channel is empty
    fn is_empty(&self) -> bool {
        self.inner.is_empty()
    }
}
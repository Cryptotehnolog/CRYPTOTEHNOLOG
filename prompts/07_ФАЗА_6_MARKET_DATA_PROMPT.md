# AI ПРОМТ: ФАЗА 6 - MARKET DATA LAYER + UNIVERSE ENGINE (v2.0 — ПОЛНАЯ РЕДАКЦИЯ)

## КОНТЕКСТ

Вы — Senior Data Engineer, специализирующийся на real-time market data processing,
WebSocket handling, time-series databases и dynamic universe management.

**Фазы 0-5 завершены.** Доступны:
- Event Bus (Rust + Python) — работает с persistence
- Control Plane (State Machine, Watchdog) — работает
- Config Manager — hot reload, GPG signatures, Vault
- Risk Engine v4.4 — R-unit, TrailingPolicy, RiskLedger, FundingManager, Velocity KillSwitch
- Database Layer, Logging, Metrics — готовы

**Текущая задача:** Реализовать production-ready Market Data Layer v4.4, включающий:
1. **MarketDataManager** — WebSocket connections, tick processing, OHLCV bars, orderbook
2. **UniverseEngine** — трёхуровневая система управления вселенной торгуемых активов:
   - `universe_raw` — всё что есть на биржах
   - `universe_admissible` — прошло фильтры ликвидности
   - `universe_ranked` — отранжировано по opportunity score
3. **SymbolMetricsCollector** — сбор ликвидностных метрик (spread, depth, funding, latency)
4. **UniverseConfidenceMonitor** — оценка качества вселенной, интеграция со State Machine

---

## ⚠️ КРИТИЧЕСКИ ВАЖНО: РУССКИЙ ЯЗЫК

**ВСЕ** комментарии, docstrings, логи и сообщения об ошибках должны быть **НА РУССКОМ ЯЗЫКЕ**.

### Python docstrings — ТОЛЬКО русский:

```python
class UniverseEngine:
    """
    Трёхуровневая система управления вселенной торгуемых активов.

    Гарантирует, что система торгует только валидными, ликвидными,
    проверенными инструментами.

    Три уровня вселенной:
    - universe_raw:        Все символы с бирж (futures + funding)
    - universe_admissible: Прошли фильтры ликвидности и инфраструктуры
    - universe_ranked:     Отранжированы по opportunity score (OpportunityEngine)

    Обновляется каждые UNIVERSE_UPDATE_INTERVAL секунд (default: 60).
    Версионирование позволяет стратегиям работать со стабильным срезом.

    Confidence = min(mean_score, q25_score):
        Чувствителен к нижней четверти — защита от «хвостов токсичности».
        Если 80% символов отличные, но 20% токсичные — confidence падает.
    """

class MarketDataManager:
    """
    Менеджер рыночных данных с WebSocket подключениями.

    Особенности:
    - Multi-exchange WebSocket (Bybit, OKX, Binance)
    - Real-time tick aggregation с валидацией качества
    - OHLCV bar construction (1m, 5m, 15m, 1h, 4h, 1d)
    - Orderbook L2 (top 20 levels, binary search обновления)
    - Auto-reconnection с exponential backoff
    - UniverseEngine — динамическая подписка по текущей вселенной
    """
```

### Логи — ТОЛЬКО русский:

```python
logger.info("Вселенная активов обновлена", version=5,
            raw=312, admissible=47, confidence=0.84)
logger.warning("Confidence вселенной ниже порога",
               confidence=0.52, threshold=0.60, version=6)
logger.info("Символ добавлен в допустимую вселенную",
            symbol="SOL/USDT", spread_bps=12.3, depth_usd=450000)
logger.warning("Символ удалён из допустимой вселенной",
               symbol="XYZ/USDT", reason="spread_too_wide",
               spread_bps=87.5, max_allowed=50.0)
logger.error("Ошибка сбора метрик символа",
             symbol="ABC/USDT", exchange="bybit", error="timeout")
logger.info("WebSocket подключён", exchange="bybit", symbols_count=47)
logger.warning("Обнаружен пропуск данных", symbol="BTC/USDT", gap_ms=8500)
```

---

## 🔗 КОМПОНЕНТНЫЕ ИНТЕГРАЦИИ

### Роль компонента в системе:

Market Data Layer v4.4 — единственный источник рыночных данных И управляющий компонент
торговой вселенной. Он не только доставляет тики/свечи, но и определяет:
**какие символы вообще могут торговаться в системе** — через UniverseEngine.

### Входящие зависимости:

#### 1. State Machine (Фаза 2) → переходы по состоянию вселенной
- `LOW_UNIVERSE_QUALITY` → TRADING → DEGRADED (если confidence < 0.6)
- `UNIVERSE_EMPTY` → любое состояние → HALT (нет символов = нет торговли)
- `UNIVERSE_READY` → BOOT → TRADING (вселенная инициализирована)

#### 2. Strategy Manager (Фаза 14) → запрашивает текущую вселенную
- `get_universe(min_confidence=0.6)` → `(symbols, version, confidence, timestamp)`
- `is_admissible(symbol)` → bool (быстрая проверка без блокировки)
- Критичность: HIGH — Strategy Manager торгует только admissible символами

#### 3. OpportunityEngine (Фаза 8) → запрашивает ranked universe
- `get_universe()` → set символов для скоринга
- `get_symbol(name)` → Symbol с метриками (spread, depth, funding)
- Результат скоринга записывается обратно как `universe_ranked`

#### 4. Risk Engine (Фаза 5) → проверяет FundingManager
- `get_symbol_metrics(symbol)` → SymbolMetrics (funding_8h для арбитража)
- Критичность: MEDIUM

#### 5. Config Manager (Фаза 4) → CONFIG_UPDATED
- Hot reload параметров фильтрации (max_spread_bps, min_depth, и т.д.)
- При изменении параметров → немедленный пересчёт admissible universe

#### 6. Watchdog (Фаза 2) → health check
- `check_health()` → `{websockets, universe_confidence, admissible_count}`

### Исходящие события:

#### 1. → Event Bus → TICK_RECEIVED (priority: NORMAL)
```json
{"symbol": "BTC/USDT", "price": "50000.00", "quantity": "0.5",
 "side": "buy", "timestamp": 1704067200000000, "exchange": "bybit"}
```

#### 2. → Event Bus → BAR_COMPLETED (priority: HIGH)
```json
{"symbol": "BTC/USDT", "timeframe": "5m",
 "open": 50000, "high": 50100, "low": 49900, "close": 50050,
 "volume": 1234.5, "bid_volume": 600.0, "ask_volume": 634.5,
 "trades_count": 450, "close_time": "2025-01-01T00:05:00Z"}
```
*Примечание: `bid_volume` и `ask_volume` — новые поля v4.4 для Delta Divergence (Фаза 7)*

#### 3. → Event Bus → ORDERBOOK_UPDATED (priority: NORMAL)
```json
{"symbol": "BTC/USDT", "exchange": "bybit",
 "bids": [[50000, 1.5], [49999, 2.0]],
 "asks": [[50001, 1.2], [50002, 3.0]],
 "spread_bps": 2.0, "timestamp": 1704067200000000}
```

#### 4. → Event Bus → UNIVERSE_UPDATED (priority: HIGH) ★ НОВОЕ
```json
{"version": 7, "raw_count": 312, "admissible_count": 47,
 "confidence": 0.84, "added": ["SOL/USDT"], "removed": ["XYZ/USDT"],
 "timestamp": "2025-01-01T00:01:00Z"}
```

#### 5. → Event Bus → UNIVERSE_CONFIDENCE_LOW (priority: CRITICAL) ★ НОВОЕ
```json
{"confidence": 0.52, "threshold": 0.60, "version": 6,
 "admissible_count": 31, "worst_symbols": ["ABC/USDT", "DEF/USDT"]}
```

#### 6. → Event Bus → SYMBOL_REMOVED_FROM_UNIVERSE (priority: HIGH) ★ НОВОЕ
```json
{"symbol": "XYZ/USDT", "reason": "spread_too_wide",
 "spread_bps": 87.5, "max_allowed": 50.0, "version": 7}
```

#### 7. → Event Bus → DATA_GAP_DETECTED (priority: CRITICAL)
```json
{"symbol": "BTC/USDT", "gap_start": 1704067200000000,
 "gap_duration_ms": 32000}
```

#### 8. → TimescaleDB → ohlcv_bars, universe_history, symbol_metrics_history

#### 9. → Redis → last_price:{symbol}, universe:current, symbol_metrics:{symbol}

---

## 📐 АРХИТЕКТУРА ФАЙЛОВ

```
CRYPTOTEHNOLOG/
├── src/
│   └── market_data/
│       ├── __init__.py
│       ├── manager.py                    # Main MarketDataManager
│       ├── websocket.py                  # WebSocket connections (multi-exchange)
│       ├── tick_handler.py               # Tick processing + bid/ask volume split
│       ├── bar_builder.py                # OHLCV aggregation + bid/ask volumes
│       ├── orderbook_manager.py          # L2 orderbook (binary search)
│       ├── data_quality.py               # Validation, gap detection, outliers
│       ├── timescale_writer.py           # Batch TimescaleDB persistence
│       ├── universe_engine.py            # ★ UniverseEngine — НОВЫЙ
│       ├── symbol_metrics.py             # ★ SymbolMetricsCollector — НОВЫЙ
│       └── models.py                     # Tick, OHLCVBar, Orderbook, Symbol, SymbolMetrics
│
└── tests/
    ├── unit/
    │   ├── test_tick_handler.py
    │   ├── test_bar_builder.py
    │   ├── test_orderbook_manager.py
    │   ├── test_data_quality.py
    │   ├── test_universe_engine.py       # ★ НОВЫЙ
    │   └── test_symbol_metrics.py        # ★ НОВЫЙ
    ├── integration/
    │   ├── test_websocket_connection.py
    │   ├── test_timescale_persistence.py
    │   ├── test_market_data_full_flow.py
    │   └── test_universe_full_cycle.py   # ★ НОВЫЙ
    └── benchmarks/
        └── bench_market_data.py
```

---

## 📋 КОНТРАКТЫ ДАННЫХ

### Tick (расширенный — добавлен агрессор):

```python
@dataclass
class Tick:
    """Единичная сделка на бирже."""

    symbol: str          # "BTC/USDT"
    price: Decimal       # 50000.00
    quantity: Decimal    # 0.5 BTC
    side: str            # "buy" / "sell"
    timestamp: int       # Unix микросекунды
    exchange: str        # "bybit"
    trade_id: str        # Уникальный ID от биржи
    is_buyer_maker: bool = False  # True = агрессор — продавец (tick идёт в bid_volume)
```

### OHLCVBar (расширенный — добавлены bid/ask volumes):

```python
@dataclass
class OHLCVBar:
    """Свеча (candlestick) для заданного таймфрейма."""

    symbol: str
    timeframe: str
    open_time: datetime
    close_time: datetime

    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal

    # ★ НОВЫЕ ПОЛЯ v4.4 — нужны для Delta Divergence (Фаза 7)
    bid_volume: Decimal = Decimal(0)  # Объём на стороне продавца (агрессивные продажи)
    ask_volume: Decimal = Decimal(0)  # Объём на стороне покупателя (агрессивные покупки)

    trades_count: int = 0
    is_closed: bool = False
```

### Symbol (НОВЫЙ):

```python
@dataclass
class Symbol:
    """
    Торговый инструмент с метриками ликвидности.

    Проходит через три уровня UniverseEngine:
    raw → admissible → ranked
    """

    name: str              # "BTC/USDT"
    base: str              # "BTC"
    quote: str             # "USDT"
    exchange: str          # Основная биржа листинга
    has_futures: bool      # Есть ли фьючерсный контракт
    has_funding: bool      # Есть ли funding rate (перп. фьючерс)
    listed_at: Optional[datetime]  # Дата листинга

    # Заполняется после admissibility check
    metrics: Optional["SymbolMetrics"] = None
    admissible_since: Optional[datetime] = None
    individual_score: float = 0.0  # Нормированный score 0.0–1.0
```

### SymbolMetrics (НОВЫЙ):

```python
@dataclass
class SymbolMetrics:
    """
    Ликвидностные метрики символа для admissibility фильтра.

    Агрегируются консервативно по всем биржам:
    - spread_bps: лучший (минимальный) спред
    - depth_1pct: суммарная глубина по всем биржам
    - latency_ms: наихудшая задержка
    - funding_8h: средний funding по биржам
    - exchange_count: количество бирж где доступен
    - exchange_health: GREEN / YELLOW / RED
    """

    spread_bps: float      # Спред в базисных пунктах (best bid/ask)
    depth_1pct: float      # Глубина стакана в $USD в пределах 1% от цены
    latency_ms: float      # Задержка WebSocket сообщений
    funding_8h: float      # 8-часовой funding rate
    exchange_count: int    # Количество бирж с этим символом
    exchange_health: str   # GREEN / YELLOW / RED
```

---

## 🔧 ТРЕБОВАНИЕ 1: UniverseEngine (src/market_data/universe_engine.py)

```python
"""
UniverseEngine — трёхуровневая система управления вселенной торгуемых активов.

Три уровня:
    universe_raw:        Все futures-символы с поддержкой funding с бирж
    universe_admissible: Прошли все 7 фильтров ликвидности
    universe_ranked:     Отранжированы по opportunity score (заполняет OpportunityEngine)

Фильтры admissibility (все должны пройти):
    1. spread_bps < max_spread_bps (50 по умолчанию)
    2. depth_1pct > min_depth_1pct_usd (100,000 USD)
    3. abs(funding_8h) < max_funding_8h (1%)
    4. latency_ms < max_latency_ms (500 мс)
    5. exchange_count >= min_exchange_coverage (2 биржи)
    6. listing_age <= max_listing_age_days (30 дней)
    7. exchange_health == GREEN

Confidence = min(mean_score, q25_score):
    Защита от «хвостов токсичности» — если 20% символов плохие,
    confidence падает даже при хороших средних значениях.
    Если confidence < min_confidence (0.6) → уведомление State Machine → DEGRADED.
"""

import asyncio
import threading
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from statistics import mean
from typing import Optional, List, Set, Tuple, Dict

from src.core.logger import get_logger
from src.market_data.models import Symbol, SymbolMetrics

logger = get_logger("UniverseEngine")


class UniverseEngine:
    """
    Трёхуровневая система управления вселенной торгуемых активов.

    Цикл обновления (каждые UNIVERSE_UPDATE_INTERVAL секунд):
    1. _discover_universe()    — сбор всех futures-символов с бирж
    2. _filter_admissible()    — 7-критериальная фильтрация ликвидности
    3. _calculate_confidence() — оценка качества вселенной (min/q25)
    4. Публикация UNIVERSE_UPDATED в Event Bus
    5. Уведомление State Machine при low confidence / empty universe
    """

    def __init__(self, market_data_manager, config_manager, event_bus, state_machine):
        """
        Аргументы:
            market_data_manager: Доступ к exchange connectors и orderbook
            config_manager: Параметры фильтрации и интервал обновления
            event_bus: Для публикации UNIVERSE_UPDATED, UNIVERSE_CONFIDENCE_LOW
            state_machine: Для перехода TRADING → DEGRADED при low confidence
        """
        self.market_data = market_data_manager
        self.config = config_manager
        self.event_bus = event_bus
        self.state_machine = state_machine

        # Три уровня вселенной
        self.universe_raw: Set[Symbol] = set()
        self.universe_admissible: Set[Symbol] = set()
        self.universe_ranked: List[Symbol] = []  # Заполняется OpportunityEngine

        # Версионирование — атомарное обновление
        self.version: int = 0
        self._update_lock = asyncio.Lock()

        # Confidence tracking
        self._confidence_history: deque = deque(maxlen=100)
        self.last_update: Optional[datetime] = None

        # Метрики изменений
        self._prev_admissible_names: Set[str] = set()

    async def start(self):
        """
        Запустить фоновый цикл обновления вселенной.

        Вызывается при старте MarketDataManager.
        Первое обновление выполняется сразу (не ждёт интервала).
        """
        logger.info("UniverseEngine запускается")

        # Первое обновление немедленно
        await self._perform_update()

        # Фоновый цикл
        asyncio.create_task(self._update_loop())

    async def _update_loop(self):
        """
        Фоновый цикл периодического обновления вселенной.

        Интервал: universe.update_interval_seconds (default: 60).
        """
        while True:
            interval = int(self.config.get(
                "universe.update_interval_seconds", default=60
            ))
            await asyncio.sleep(interval)
            try:
                await self._perform_update()
            except Exception as e:
                logger.error("Ошибка обновления вселенной", error=str(e))

    async def _perform_update(self):
        """
        Полный цикл обновления вселенной (атомарный под локом).

        Этапы:
        1. Discovery — сбор символов с бирж
        2. Admissibility — 7-критериальная фильтрация
        3. Confidence — оценка качества вселенной
        4. Публикация событий об изменениях
        """
        async with self._update_lock:
            # Этап 1: Discovery
            new_raw = await self._discover_universe()

            # Этап 2: Admissibility
            new_admissible = await self._filter_admissible(new_raw)

            # Этап 3: Confidence
            confidence = self._calculate_confidence(new_admissible)

            # Вычислить добавленные / удалённые символы
            new_names = {s.name for s in new_admissible}
            old_names = self._prev_admissible_names
            added   = list(new_names - old_names)
            removed = list(old_names - new_names)

            # Атомарно обновить версию
            self.universe_raw       = new_raw
            self.universe_admissible = new_admissible
            self.version            += 1
            self.last_update        = datetime.utcnow()
            self._prev_admissible_names = new_names

            self._confidence_history.append({
                "timestamp":  self.last_update,
                "confidence": confidence,
                "count":      len(new_admissible),
            })

            # Логирование добавленных символов
            for sym in added:
                logger.info("Символ добавлен в допустимую вселенную",
                            symbol=sym, version=self.version)

            # Логирование удалённых символов
            for sym in removed:
                # Найдём причину (был в old, нет в new)
                logger.warning("Символ удалён из допустимой вселенной",
                               symbol=sym, version=self.version)
                await self.event_bus.publish({
                    "type": "SYMBOL_REMOVED_FROM_UNIVERSE",
                    "priority": "HIGH",
                    "payload": {
                        "symbol": sym,
                        "version": self.version,
                        "reason": "не прошёл фильтры ликвидности",
                    }
                })

            # Публикация UNIVERSE_UPDATED
            await self.event_bus.publish({
                "type": "UNIVERSE_UPDATED",
                "priority": "HIGH",
                "payload": {
                    "version":         self.version,
                    "raw_count":       len(new_raw),
                    "admissible_count": len(new_admissible),
                    "confidence":      round(confidence, 4),
                    "added":           added,
                    "removed":         removed,
                    "timestamp":       self.last_update.isoformat(),
                }
            })

            logger.info(
                "Вселенная активов обновлена",
                version=self.version,
                raw=len(new_raw),
                admissible=len(new_admissible),
                confidence=round(confidence, 4),
                added=len(added),
                removed=len(removed),
            )

            # Проверка confidence порога
            min_confidence = float(self.config.get(
                "universe.min_confidence", default=0.6
            ))
            if confidence < min_confidence:
                await self._handle_low_confidence(confidence, min_confidence, new_admissible)

            # Пустая вселенная — критическая ситуация
            if not new_admissible:
                logger.critical(
                    "Вселенная активов пуста — торговля невозможна",
                    version=self.version,
                )
                await self.state_machine.transition("UNIVERSE_EMPTY", {
                    "version": self.version,
                })

    async def _discover_universe(self) -> Set[Symbol]:
        """
        Этап 1: Сбор всех потенциально торгуемых инструментов с бирж.

        Критерии для попадания в raw:
        - has_futures = True (только фьючерсные контракты)
        - has_funding = True (только перпетуальные с funding rate)

        При ошибке на бирже — продолжает с другими биржами.
        """
        discovered: Set[Symbol] = set()

        for exchange_id, exchange in self.market_data.exchanges.items():
            try:
                symbols_data = await exchange.list_symbols()

                for sd in symbols_data:
                    if sd.get("has_futures") and sd.get("has_funding"):
                        symbol = Symbol(
                            name=sd["name"],
                            base=sd["base"],
                            quote=sd["quote"],
                            exchange=exchange_id,
                            has_futures=True,
                            has_funding=True,
                            listed_at=sd.get("listed_at"),
                        )
                        discovered.add(symbol)

            except Exception as e:
                logger.error(
                    "Ошибка при discovery символов с биржи",
                    exchange=exchange_id,
                    error=str(e),
                )
                # Продолжаем с другими биржами

        logger.debug(
            "Discovery завершён",
            total_found=len(discovered),
        )
        return discovered

    async def _filter_admissible(self, universe_raw: Set[Symbol]) -> Set[Symbol]:
        """
        Этап 2: Жёсткая фильтрация по ликвидности и инфраструктуре.

        7 критериев (все должны пройти):
        1. spread_bps < max_spread_bps           — не слишком широкий спред
        2. depth_1pct > min_depth_1pct_usd       — достаточная глубина стакана
        3. abs(funding_8h) < max_funding_8h      — умеренный funding rate
        4. latency_ms < max_latency_ms           — приемлемая задержка WebSocket
        5. exchange_count >= min_exchange_coverage — присутствует на ≥2 биржах
        6. listing_age <= max_listing_age_days   — не слишком новый (30 дней)
        7. exchange_health == GREEN              — все биржи в норме
        """
        max_spread_bps        = float(self.config.get("universe.max_spread_bps", 50))
        min_depth_usd         = float(self.config.get("universe.min_depth_1pct_usd", 100_000))
        max_funding           = float(self.config.get("universe.max_funding_8h", 0.01))
        max_latency           = float(self.config.get("universe.max_latency_ms", 500))
        min_coverage          = int(self.config.get("universe.min_exchange_coverage", 2))
        max_listing_age_days  = int(self.config.get("universe.max_listing_age_days", 30))
        watch_list            = self.config.get("universe.watch_list", default=[])

        admissible: Set[Symbol] = set()

        for symbol in universe_raw:
            try:
                metrics = await self._gather_symbol_metrics(symbol)

                # Возраст листинга
                listing_age = self._listing_age_days(symbol)

                checks = {
                    "spread":        metrics.spread_bps < max_spread_bps,
                    "depth":         metrics.depth_1pct > min_depth_usd,
                    "funding":       abs(metrics.funding_8h) < max_funding,
                    "latency":       metrics.latency_ms < max_latency,
                    "coverage":      metrics.exchange_count >= min_coverage,
                    "listing_age":   listing_age <= max_listing_age_days if max_listing_age_days else True,
                    "exchange_health": metrics.exchange_health == "GREEN",
                }

                if all(checks.values()):
                    symbol.metrics = metrics
                    symbol.admissible_since = datetime.utcnow()
                    admissible.add(symbol)
                else:
                    # Подробный лог только для watch_list символов
                    if symbol.name in watch_list:
                        failed = [k for k, v in checks.items() if not v]
                        logger.warning(
                            "Символ не прошёл admissibility (watch_list)",
                            symbol=symbol.name,
                            failed_checks=failed,
                            spread_bps=metrics.spread_bps,
                            depth_usd=metrics.depth_1pct,
                            funding_8h=metrics.funding_8h,
                        )

            except Exception as e:
                logger.error(
                    "Ошибка при проверке символа",
                    symbol=symbol.name,
                    error=str(e),
                )
                # Символ не проходит при ошибке — безопасная сторона

        logger.debug(
            "Фильтрация admissibility завершена",
            raw=len(universe_raw),
            admissible=len(admissible),
            filtered_out=len(universe_raw) - len(admissible),
        )
        return admissible

    def _calculate_confidence(self, universe: Set[Symbol]) -> float:
        """
        Этап 3: Оценка качества вселенной как целого.

        Формула: confidence = min(mean_score, q25_score)

        Использует МИНИМУМ из среднего и 25-го перцентиля.
        Это защищает от «хвостов токсичности»:
        если 20% символов плохие → q25 падает → confidence падает.

        Компоненты individual_score каждого символа:
        - depth_score:    depth_1pct / target_depth (насыщение к target)
        - spread_score:   1 - spread_bps / max_spread_bps (обратная зависимость)
        - exchange_score: exchange_count / max_exchanges (покрытие)
        - latency_score:  1 - latency_ms / max_latency_ms (обратная зависимость)

        Возвращает float 0.0–1.0.
        """
        if not universe:
            return 0.0

        target_depth  = float(self.config.get("universe.target_depth", 500_000))
        max_spread    = float(self.config.get("universe.max_spread_bps", 50))
        max_exchanges = int(self.config.get("universe.max_exchanges", 5))
        max_latency   = float(self.config.get("universe.max_latency_ms", 500))

        individual_scores = []

        for symbol in universe:
            if not symbol.metrics:
                individual_scores.append(0.0)
                continue

            m = symbol.metrics

            depth_score    = min(1.0, m.depth_1pct / target_depth)
            spread_score   = max(0.0, 1.0 - m.spread_bps / max_spread)
            exchange_score = min(1.0, m.exchange_count / max_exchanges)
            latency_score  = max(0.0, 1.0 - m.latency_ms / max_latency)

            symbol.individual_score = mean([
                depth_score, spread_score, exchange_score, latency_score
            ])
            individual_scores.append(symbol.individual_score)

        if not individual_scores:
            return 0.0

        mean_score = mean(individual_scores)

        # q25 — 25-й перцентиль
        sorted_scores = sorted(individual_scores)
        q25_idx = max(0, int(len(sorted_scores) * 0.25) - 1)
        q25_score = sorted_scores[q25_idx]

        confidence = min(mean_score, q25_score)

        # Логирование worst символов
        worst = sorted(universe, key=lambda s: s.individual_score)[:5]
        logger.debug(
            "Confidence вселенной рассчитан",
            version=self.version,
            mean=round(mean_score, 4),
            q25=round(q25_score, 4),
            confidence=round(confidence, 4),
            count=len(universe),
            worst_symbols=[{"name": s.name, "score": round(s.individual_score, 3)}
                           for s in worst],
        )

        return confidence

    async def _gather_symbol_metrics(self, symbol: Symbol) -> SymbolMetrics:
        """
        Сбор ликвидностных метрик символа по всем биржам.

        Агрегация консервативная:
        - spread_bps:  МИНИМАЛЬНЫЙ (лучший спред среди бирж)
        - depth_1pct:  СУММА (общая ликвидность)
        - latency_ms:  МАКСИМАЛЬНАЯ (наихудшая задержка)
        - funding_8h:  СРЕДНЕЕ
        - exchange_count: количество бирж где доступен
        - exchange_health: GREEN если все GREEN, YELLOW если хоть одна GREEN, иначе RED
        """
        exchange_data = []

        for exchange_id, exchange in self.market_data.exchanges.items():
            if not await exchange.has_symbol(symbol.name):
                continue
            try:
                data = await exchange.get_symbol_metrics(symbol.name)
                exchange_data.append({
                    "spread_bps": data["spread_bps"],
                    "depth_1pct": data["depth_1pct"],
                    "latency_ms": data["latency_ms"],
                    "funding_8h": data.get("funding_8h", 0.0),
                    "health":     exchange.health_state,
                })
            except Exception as e:
                logger.error(
                    "Ошибка сбора метрик символа",
                    symbol=symbol.name,
                    exchange=exchange_id,
                    error=str(e),
                )

        if not exchange_data:
            return SymbolMetrics(
                spread_bps=float("inf"),
                depth_1pct=0.0,
                latency_ms=float("inf"),
                funding_8h=0.0,
                exchange_count=0,
                exchange_health="RED",
            )

        all_green  = all(d["health"] == "GREEN" for d in exchange_data)
        any_green  = any(d["health"] == "GREEN" for d in exchange_data)
        health     = "GREEN" if all_green else ("YELLOW" if any_green else "RED")

        return SymbolMetrics(
            spread_bps    = min(d["spread_bps"] for d in exchange_data),
            depth_1pct    = sum(d["depth_1pct"] for d in exchange_data),
            latency_ms    = max(d["latency_ms"] for d in exchange_data),
            funding_8h    = mean(d["funding_8h"] for d in exchange_data),
            exchange_count = len(exchange_data),
            exchange_health = health,
        )

    async def _handle_low_confidence(
        self,
        confidence: float,
        threshold: float,
        universe: Set[Symbol],
    ) -> None:
        """
        Обработать ситуацию низкого confidence вселенной.

        Действия:
        1. WARNING лог с деталями
        2. Публикация UNIVERSE_CONFIDENCE_LOW в Event Bus
        3. Уведомление State Machine → DEGRADED (если в TRADING)
        """
        worst = sorted(universe, key=lambda s: s.individual_score)[:5]

        logger.warning(
            "Confidence вселенной ниже порога",
            confidence=round(confidence, 4),
            threshold=threshold,
            version=self.version,
            admissible_count=len(universe),
        )

        await self.event_bus.publish({
            "type": "UNIVERSE_CONFIDENCE_LOW",
            "priority": "CRITICAL",
            "payload": {
                "confidence":      round(confidence, 4),
                "threshold":       threshold,
                "version":         self.version,
                "admissible_count": len(universe),
                "worst_symbols":   [s.name for s in worst],
            }
        })

        # Уведомить State Machine
        await self.state_machine.transition("LOW_UNIVERSE_QUALITY", {
            "confidence": confidence,
            "version":    self.version,
        })

    # ── Публичный API ──────────────────────────────────────────

    def get_universe(
        self,
        min_confidence: Optional[float] = None,
    ) -> Tuple[Set[Symbol], int, float, Optional[datetime]]:
        """
        Получить текущую валидную вселенную.

        Аргументы:
            min_confidence: Минимальный confidence (если ниже — вернуть пустое)

        Возвращает:
            (symbols, version, confidence, last_update)

        Latency: <1μs — только чтение из памяти, без блокировки.
        Вызывается Strategy Manager на каждом цикле торговли.
        """
        confidence = (self._confidence_history[-1]["confidence"]
                      if self._confidence_history else 0.0)

        if min_confidence and confidence < min_confidence:
            return (set(), self.version, confidence, self.last_update)

        return (
            self.universe_admissible.copy(),
            self.version,
            confidence,
            self.last_update,
        )

    def is_admissible(self, symbol_name: str) -> bool:
        """
        Быстрая проверка — допустим ли символ для торговли.

        Latency: O(N) но N ≤ 100 → практически мгновенно.
        Вызывается RiskEngine и Strategy Manager перед каждым ордером.
        """
        return any(s.name == symbol_name for s in self.universe_admissible)

    def get_symbol(self, symbol_name: str) -> Optional[Symbol]:
        """
        Получить данные символа с метриками.

        Используется FundingManager для arbitrage решений.
        """
        for s in self.universe_admissible:
            if s.name == symbol_name:
                return s
        return None

    def set_ranked_universe(self, ranked: List[Symbol]) -> None:
        """
        Установить отранжированную вселенную.

        Вызывается OpportunityEngine (Фаза 8) после скоринга.
        """
        self.universe_ranked = ranked

    def get_ranked_universe(self) -> List[Symbol]:
        """
        Получить отранжированную вселенную (топ символы по opportunity score).

        Заполняется OpportunityEngine. Если пусто — вернуть admissible.
        """
        return self.universe_ranked if self.universe_ranked else list(self.universe_admissible)

    def get_current_confidence(self) -> float:
        """Текущий confidence вселенной. Latency: <1μs."""
        if not self._confidence_history:
            return 0.0
        return self._confidence_history[-1]["confidence"]

    @staticmethod
    def _listing_age_days(symbol: Symbol) -> int:
        """Возраст листинга в днях (0 если неизвестно = считаем старым)."""
        if not symbol.listed_at:
            return 0
        return (datetime.utcnow() - symbol.listed_at).days
```

---

## 🔧 ТРЕБОВАНИЕ 2: BarBuilder с bid/ask volumes (src/market_data/bar_builder.py)

```python
"""
BarBuilder — инкрементальное построение OHLCV баров.

v4.4: Добавлен раздельный учёт bid_volume / ask_volume
для Delta Divergence (Фаза 7, ImpulseAnalyzer).

Логика разделения по is_buyer_maker:
    is_buyer_maker = True  → агрессор продавец → bid_volume += quantity
    is_buyer_maker = False → агрессор покупатель → ask_volume += quantity
"""

class BarBuilder:
    """
    Инкрементальный построитель OHLCV bars.

    НЕ хранит все ticks — только текущее состояние бара (O(1) memory).
    Поддерживает 6 таймфреймов: 1m, 5m, 15m, 1h, 4h, 1d.
    """

    def __init__(self, symbol: str, timeframe: str):
        """
        Аргументы:
            symbol: Торговый символ
            timeframe: Таймфрейм бара (1m, 5m, 15m, 1h, 4h, 1d)
        """
        self.symbol            = symbol
        self.timeframe         = timeframe
        self.timeframe_seconds = self._parse_timeframe(timeframe)
        self.current_bar: Optional[OHLCVBar] = None
        self.current_bar_start: Optional[datetime] = None

    async def add_tick(self, tick: "Tick") -> Optional[OHLCVBar]:
        """
        Добавить tick к текущему бару.

        Аргументы:
            tick: Tick с полем is_buyer_maker для bid/ask разделения

        Возвращает:
            Завершённый OHLCVBar если бар закрылся, None иначе
        """
        tick_time = datetime.fromtimestamp(
            tick.timestamp / 1_000_000, tz=timezone.utc
        )
        bar_start = self._get_bar_start(tick_time)

        completed_bar = None

        if self.current_bar_start != bar_start:
            # Завершить предыдущий бар
            if self.current_bar:
                self.current_bar.is_closed = True
                completed_bar = self.current_bar
                await self._complete_bar(self.current_bar)

            # Создать новый бар
            self.current_bar = OHLCVBar(
                symbol=self.symbol,
                timeframe=self.timeframe,
                open_time=bar_start,
                close_time=bar_start + timedelta(seconds=self.timeframe_seconds),
                open=tick.price,
                high=tick.price,
                low=tick.price,
                close=tick.price,
                volume=tick.quantity,
                bid_volume=tick.quantity if tick.is_buyer_maker else Decimal(0),
                ask_volume=Decimal(0) if tick.is_buyer_maker else tick.quantity,
                trades_count=1,
                is_closed=False,
            )
            self.current_bar_start = bar_start
        else:
            # Инкрементальное обновление текущего бара
            bar = self.current_bar
            bar.high        = max(bar.high, tick.price)
            bar.low         = min(bar.low, tick.price)
            bar.close       = tick.price
            bar.volume     += tick.quantity
            bar.trades_count += 1

            # ★ Разделение по агрессору
            if tick.is_buyer_maker:
                bar.bid_volume += tick.quantity
            else:
                bar.ask_volume += tick.quantity

        return completed_bar

    def _get_bar_start(self, tick_time: datetime) -> datetime:
        """Округлить время до начала бара (UTC)."""
        ts = int(tick_time.timestamp())
        bar_ts = (ts // self.timeframe_seconds) * self.timeframe_seconds
        return datetime.fromtimestamp(bar_ts, tz=timezone.utc)

    @staticmethod
    def _parse_timeframe(tf: str) -> int:
        """Преобразовать строку таймфрейма в секунды."""
        units = {"m": 60, "h": 3600, "d": 86400}
        return int(tf[:-1]) * units[tf[-1]]

    async def _complete_bar(self, bar: OHLCVBar) -> None:
        """Опубликовать BAR_COMPLETED (вызывается MarketDataManager)."""
        # Делегируется MarketDataManager через callback
        pass
```

---

## 📊 DATABASE SCHEMA (PostgreSQL + TimescaleDB)

```sql
-- OHLCV бары (с bid/ask volumes для Delta Divergence)
CREATE TABLE ohlcv_bars (
    time         TIMESTAMPTZ NOT NULL,
    symbol       VARCHAR(20) NOT NULL,
    timeframe    VARCHAR(5) NOT NULL,
    open         NUMERIC(20, 8) NOT NULL,
    high         NUMERIC(20, 8) NOT NULL,
    low          NUMERIC(20, 8) NOT NULL,
    close        NUMERIC(20, 8) NOT NULL,
    volume       NUMERIC(20, 8) NOT NULL,
    bid_volume   NUMERIC(20, 8) NOT NULL DEFAULT 0,  -- ★ НОВОЕ v4.4
    ask_volume   NUMERIC(20, 8) NOT NULL DEFAULT 0,  -- ★ НОВОЕ v4.4
    trades_count INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (time, symbol, timeframe)
);
SELECT create_hypertable('ohlcv_bars', 'time');
CREATE INDEX idx_ohlcv_symbol_tf ON ohlcv_bars(symbol, timeframe, time DESC);

-- Критичные тики (только для аудита)
CREATE TABLE critical_ticks (
    time       TIMESTAMPTZ NOT NULL,
    symbol     VARCHAR(20) NOT NULL,
    price      NUMERIC(20, 8) NOT NULL,
    quantity   NUMERIC(20, 8) NOT NULL,
    side       VARCHAR(4) NOT NULL,
    exchange   VARCHAR(20) NOT NULL,
    PRIMARY KEY (time, symbol, exchange)
);
SELECT create_hypertable('critical_ticks', 'time');

-- История состояний вселенной (для анализа)
CREATE TABLE universe_history (
    id               SERIAL PRIMARY KEY,
    version          INTEGER NOT NULL,
    raw_count        INTEGER NOT NULL,
    admissible_count INTEGER NOT NULL,
    confidence       NUMERIC(6, 4) NOT NULL,
    added_symbols    TEXT[],
    removed_symbols  TEXT[],
    recorded_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_universe_hist ON universe_history(recorded_at DESC);

-- Текущие метрики символов (последнее известное состояние)
CREATE TABLE symbol_metrics (
    symbol           VARCHAR(20) PRIMARY KEY,
    spread_bps       NUMERIC(8, 2),
    depth_1pct_usd   NUMERIC(20, 2),
    latency_ms       NUMERIC(8, 2),
    funding_8h       NUMERIC(10, 6),
    exchange_count   INTEGER,
    exchange_health  VARCHAR(10),
    individual_score NUMERIC(6, 4),
    is_admissible    BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- История метрик символов (для анализа тенденций)
CREATE TABLE symbol_metrics_history (
    id             SERIAL PRIMARY KEY,
    symbol         VARCHAR(20) NOT NULL,
    spread_bps     NUMERIC(8, 2),
    depth_1pct_usd NUMERIC(20, 2),
    latency_ms     NUMERIC(8, 2),
    funding_8h     NUMERIC(10, 6),
    is_admissible  BOOLEAN,
    recorded_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
SELECT create_hypertable('symbol_metrics_history', 'recorded_at');
CREATE INDEX idx_sym_metrics_symbol ON symbol_metrics_history(symbol, recorded_at DESC);
```

---

## 🚀 ПРОИЗВОДИТЕЛЬНОСТЬ

```
Операция                                 Target       Частота
──────────────────────────────────────────────────────────────────
process_tick()                           <5ms         10–100/сек
add_tick() в BarBuilder                  <1ms         каждый tick
update_orderbook()                       <3ms         100–500/сек
UniverseEngine._perform_update()         <30s         каждые 60 сек
UniverseEngine.get_universe()            <1μs         sync read
UniverseEngine.is_admissible()           <10μs        на каждый ордер
_calculate_confidence() (100 символов)  <100ms        раз в минуту
persist_bar() (batch COPY, 100 баров)   <50ms         batch flush
WebSocket message parsing (ujson)        <1ms          500+/сек
──────────────────────────────────────────────────────────────────
```

---

## ⚠️ КРИТИЧЕСКИЕ ОГРАНИЧЕНИЯ ФАЗЫ 6

### ✅ Что реализовано:
- Multi-exchange WebSocket (Bybit, OKX, Binance), auto-reconnect, exponential backoff
- Tick processing с bid/ask volume разделением (is_buyer_maker)
- OHLCV bar construction (6 timeframes) с bid_volume / ask_volume для Delta Divergence
- Orderbook L2 top 20 (binary search, O(log N) updates)
- Data quality validation (gaps, outliers, future timestamps)
- TimescaleDB batch persistence (asyncpg COPY, 100x быстрее)
- **UniverseEngine** — трёхуровневая вселенная (raw → admissible → ranked)
- **SymbolMetricsCollector** — 7-критериальная admissibility фильтрация
- **Confidence monitoring** — min(mean, q25), уведомление State Machine
- Events: UNIVERSE_UPDATED, UNIVERSE_CONFIDENCE_LOW, SYMBOL_REMOVED_FROM_UNIVERSE

### ❌ Что НЕ реализовано (future phases):
- L3 full depth orderbook
- Historical data backfill (→ Фаза 19)
- Cross-exchange aggregated orderbook
- Trade flow / order flow analysis (→ Фаза 7: Delta Divergence)
- Rust WebSocket для ultra-high-frequency (1000+ ticks/сек)

---

## ACCEPTANCE CRITERIA

### WebSocket Management
- [ ] Multi-exchange connections (Bybit, OKX, Binance)
- [ ] Auto-reconnection с exponential backoff (1s, 2s, 4s, ... 60s max)
- [ ] Subscribe / unsubscribe по символам
- [ ] Ping/pong keep-alive
- [ ] Graceful shutdown

### Tick Processing
- [ ] Validate quality (outliers >10%, gaps >5s, future timestamps)
- [ ] Publish TICK_RECEIVED events
- [ ] Update Redis last_price cache
- [ ] **bid_volume / ask_volume разделение** по is_buyer_maker

### Bar Construction
- [ ] 6 timeframes (1m, 5m, 15m, 1h, 4h, 1d), O(1) memory
- [ ] **bid_volume и ask_volume** в каждом OHLCVBar
- [ ] Mark incomplete bars при gaps
- [ ] Publish BAR_COMPLETED events
- [ ] Persist в TimescaleDB (batch COPY)

### UniverseEngine ★ НОВОЕ
- [ ] Три уровня: raw → admissible → ranked
- [ ] 7 фильтров admissibility (spread, depth, funding, latency, coverage, age, health)
- [ ] Confidence = min(mean, q25) — защита от «хвостов токсичности»
- [ ] Confidence < 0.6 → State Machine → DEGRADED
- [ ] Пустая вселенная → State Machine → HALT
- [ ] UNIVERSE_UPDATED event при каждом обновлении
- [ ] SYMBOL_REMOVED event при выбывании символа
- [ ] get_universe() < 1μs (sync read)
- [ ] is_admissible() < 10μs
- [ ] Версионирование — атомарное обновление под asyncio.Lock

### Data Quality
- [ ] Gap detection (>5s warning, >30s critical)
- [ ] Outlier filtering (price spike >10%)
- [ ] Timestamp и quantity validation

### Performance
- [ ] Tick processing <5ms
- [ ] Orderbook update <3ms
- [ ] WebSocket throughput >500 msg/sec
- [ ] Universe update cycle <30s (для 100+ символов)

---

**Version:** CRYPTOTEHNOLOG v4.4 (Фаза 6 — полная редакция)
**Dependencies:** Phases 0-5
**Next:** Phase 7 - Indicators + Intelligence Layer
       (использует bid_volume/ask_volume из BarBuilder для Delta Divergence,
        читает admissible universe из UniverseEngine)

# AI ПРОМТ: ФАЗА 5 - RISK ENGINE (v2.0 — ПОЛНАЯ РЕДАКЦИЯ)

## КОНТЕКСТ

Вы — Senior Quantitative Risk Engineer, специализирующийся на position sizing,
risk management systems, trailing stop systems, и financial mathematics.

**Фазы 0-4 завершены.** Доступны:
- Event Bus (Rust + Python) — работает с persistence
- Control Plane (State Machine, Watchdog) — работает
- Config Manager — hot reload, GPG signatures, Vault
- Database Layer, Logging, Metrics — готовы
- Stubs для Risk Engine — будут заменены реальной реализацией

**Текущая задача:** Реализовать production-ready Risk Engine v4.4, включающий:
1. R-unit position sizing (Van Tharp)
2. Correlation analysis + Drawdown monitoring
3. **TrailingPolicy** — институциональный модуль управления трейлинг-стопом
4. **RiskLedger** — единый реестр рисков позиций (обязательна синхронизация)
5. **FundingManager** — Funding Rate Arbitrage между биржами
6. **Velocity-based KillSwitch** — автостоп при потере 2R за 10 сделок

---

## ⚠️ КРИТИЧЕСКИ ВАЖНО: РУССКИЙ ЯЗЫК

**ВСЕ** комментарии, docstrings, логи и сообщения об ошибках должны быть **НА РУССКОМ ЯЗЫКЕ**.

### Python docstrings — ТОЛЬКО русский:

```python
class RiskEngine:
    """
    Движок управления рисками с R-unit системой v4.4.

    Особенности:
    - R-unit position sizing (Van Tharp)
    - Корреляционный анализ портфеля (Correlation Groups: Majors/L1/DeFi/Memes)
    - Мониторинг просадки в реальном времени (Soft/Hard/Velocity)
    - TrailingPolicy — институциональный трейлинг-стоп (T1-T4 tiers)
    - RiskLedger — единый реестр рисков (ОБЯЗАТЕЛЬНАЯ синхронизация)
    - FundingManager — Funding Rate Arbitrage
    - Velocity-based KillSwitch (2R за 10 сделок)
    - Интеграция с State Machine для автоматической деградации
    """

    async def check_trade(self, order: Order) -> RiskCheckResult:
        """
        Проверить допустимость сделки перед исполнением.

        Аргументы:
            order: Ордер для проверки

        Возвращает:
            RiskCheckResult с решением (allowed/rejected) и причиной

        Проверки (в порядке выполнения):
        1. State Machine разрешает торговлю (TRADING или DEGRADED)
        2. R-unit не превышает max_r_per_trade
        3. Velocity KillSwitch — не сработал (< 2R за 10 сделок)
        4. Корреляция с существующими позициями < correlation_limit
        5. Correlation Group лимит не превышен
        6. Общая экспозиция < max_total_exposure
        7. Текущая просадка < max_drawdown_hard
        8. Funding rate приемлем (если есть альтернативная биржа)
        """
        pass
```

### Логи — ТОЛЬКО русский:

```python
logger.info("Сделка одобрена", symbol=order.symbol, risk_r=risk_r, reason="within_limits")
logger.warning("Сделка отклонена", reason="correlation_too_high", correlation=0.85)
logger.error("Превышен жёсткий лимит просадки", current_dd=0.25, limit=0.20)
logger.critical("🛑 Velocity KillSwitch сработал", losses_r=2.1, window_trades=10)
logger.info("Трейлинг передвинут", position_id="SOL-123", old_stop=102.5, new_stop=104.8,
            pnl_r=3.6, tier="T2", risk_before=0.42, risk_after=0.31)
```

### Примеры замены:

| ❌ Неправильно | ✅ Правильно |
|----------------|--------------|
| "Trade approved" | "Сделка одобрена" |
| "Risk limit exceeded" | "Превышен лимит риска" |
| "Trailing stop moved" | "Трейлинг-стоп передвинут" |
| "Velocity limit hit" | "Velocity лимит достигнут" |
| "Funding rate arbitrage found" | "Обнаружена возможность funding арбитража" |

---

## 🔗 КОМПОНЕНТНЫЕ ИНТЕГРАЦИИ

### Роль компонента в системе:
Risk Engine v4.4 — главный гейткипер торговой системы. Ни одна сделка не выполняется
без его одобрения. Включает TrailingPolicy (управление открытым риском),
RiskLedger (единый источник истины по рискам всех позиций),
FundingManager (оптимизация финансирования), Velocity KillSwitch (защита от серии убытков).

### Входящие зависимости:

#### 1. Strategy Manager (Фаза 14) → check_trade()
- Запрос: `async def check_trade(order: Order) -> RiskCheckResult`
- Timeout: 100ms
- Блокирующий: Да

#### 2. Portfolio Governor (Фаза 9) → calculate_position_size()
- Запрос: `async def calculate_position_size(symbol, entry_price, stop_loss) -> PositionSize`
- Timeout: 50ms

#### 3. Execution Layer (Фаза 10) → ORDER_FILLED event
- Payload: `{order_id, symbol, filled_qty, avg_price}`
- Действие: Обновить RiskLedger, запустить TrailingPolicy

#### 4. Market Data (Фаза 6) → BAR_COMPLETED event
- Payload: `{symbol, high, low, close, atr, volume, adx}`
- Действие: Вызвать TrailingPolicy.evaluate() для всех открытых позиций

#### 5. State Machine (Фаза 2) → STATE_TRANSITION event
- Действие: SURVIVAL/RISK_REDUCTION → переключить TrailingPolicy в EMERGENCY mode

#### 6. Config Manager (Фаза 4) → CONFIG_UPDATED event
- Действие: Hot reload всех параметров риска без рестарта

### Исходящие зависимости:

#### 1. → Event Bus → RISK_VIOLATION (priority: HIGH)
```json
{
  "violation_type": "max_r_exceeded",
  "symbol": "BTC/USDT",
  "requested_r": 0.08,
  "max_allowed_r": 0.05,
  "action_taken": "reject_trade"
}
```

#### 2. → Event Bus → TRAILING_STOP_MOVED (priority: NORMAL)
```json
{
  "event": "TRAILING_STOP_MOVED",
  "position_id": "SOL-123",
  "old_stop": 102.5,
  "new_stop": 104.8,
  "pnl_r": 3.6,
  "tier": "T2",
  "mode": "NORMAL",
  "state": "TRADING",
  "risk_before": 0.42,
  "risk_after": 0.31
}
```

#### 3. → Event Bus → DRAWDOWN_ALERT (priority: CRITICAL)
```json
{
  "current_drawdown_percent": 0.18,
  "soft_limit": 0.15,
  "hard_limit": 0.20,
  "action_taken": "reduce_position_sizes"
}
```

#### 4. → Event Bus → VELOCITY_KILLSWITCH (priority: CRITICAL)
```json
{
  "event": "VELOCITY_KILLSWITCH_TRIGGERED",
  "losses_r": 2.1,
  "window_trades": 10,
  "window_minutes": 60,
  "action": "halt_new_trades"
}
```

#### 5. → Event Bus → FUNDING_ARBITRAGE_FOUND (priority: NORMAL)
```json
{
  "symbol": "ETH/USDT",
  "long_exchange": "bybit",
  "short_exchange": "okx",
  "spread": 0.0025,
  "annualized_profit": 10.95
}
```

#### 6. → Database → таблицы risk_checks, trailing_stops, risk_ledger, funding_rates

---

## 📐 АРХИТЕКТУРА ФАЙЛОВ

```
CRYPTOTEHNOLOG/
├── src/
│   └── risk/
│       ├── __init__.py
│       ├── engine.py                    # Главный RiskEngine класс
│       ├── models.py                    # Order, RiskCheckResult, Position, StopUpdate
│       ├── position_sizing.py           # R-unit calculations (Van Tharp)
│       ├── correlation.py               # CorrelationCalculator + CorrelationGroups
│       ├── drawdown_monitor.py          # DrawdownMonitor (Soft/Hard/Velocity)
│       ├── trailing_policy.py           # ★ TrailingPolicy — НОВЫЙ МОДУЛЬ
│       ├── risk_ledger.py               # ★ RiskLedger — НОВЫЙ МОДУЛЬ
│       ├── funding_manager.py           # ★ FundingManager — НОВЫЙ МОДУЛЬ
│       └── portfolio_state.py           # PortfolioState tracker
│
└── tests/
    ├── unit/
    │   ├── test_position_sizing.py
    │   ├── test_correlation.py
    │   ├── test_drawdown_monitor.py
    │   ├── test_trailing_policy.py       # ★ НОВЫЙ
    │   ├── test_risk_ledger.py           # ★ НОВЫЙ
    │   ├── test_funding_manager.py       # ★ НОВЫЙ
    │   └── test_risk_engine.py
    ├── integration/
    │   ├── test_risk_engine_integration.py
    │   └── test_trailing_policy_integration.py  # ★ НОВЫЙ
    └── benchmarks/
        └── bench_risk_engine.py
```

---

## 📋 КОНТРАКТЫ ДАННЫХ

### Order (входящий):

```python
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

@dataclass
class Order:
    """Ордер для проверки риска."""

    order_id: str
    symbol: str            # "BTC/USDT"
    side: str              # "buy" или "sell"
    entry_price: Decimal   # Планируемая цена входа
    stop_loss: Decimal     # Стоп-лосс (ОБЯЗАТЕЛЕН)
    take_profit: Optional[Decimal] = None

    # Опционально (если None — Risk Engine рассчитает)
    quantity: Optional[Decimal] = None
    risk_usd: Optional[Decimal] = None

    # Контекст
    strategy_id: Optional[str] = None
    exchange_id: str = "bybit"           # На какой бирже исполнять
```

### RiskCheckResult (исходящий):

```python
@dataclass
class RiskCheckResult:
    """Результат проверки риска."""

    allowed: bool
    reason: str

    # Sizing
    risk_r: Decimal = Decimal(0)
    position_size_usd: Decimal = Decimal(0)
    position_size_base: Decimal = Decimal(0)

    # Лимиты
    current_total_r: Decimal = Decimal(0)
    max_total_r: Decimal = Decimal(0)
    correlation_with_portfolio: Optional[Decimal] = None

    # Рекомендации
    recommended_exchange: Optional[str] = None   # Если лучше другая биржа
    max_size: Optional[Decimal] = None           # Уменьшенный размер (DEGRADED mode)

    check_duration_ms: int = 0
```

### StopUpdate (для TrailingPolicy):

```python
@dataclass
class StopUpdate:
    """
    Результат оценки трейлинг-стопа.

    Возвращается TrailingPolicy.evaluate() и force_emergency().
    """

    position_id: str
    old_stop: Decimal          # Предыдущий стоп
    new_stop: Decimal          # Новый стоп (ОБЯЗАТЕЛЬНО >= old_stop для LONG)
    pnl_r: Decimal             # Текущий P&L в R-единицах
    tier: str                  # T1 / T2 / T3 / T4
    mode: str                  # NORMAL / STRUCTURAL / EMERGENCY
    state: str                 # Текущее состояние StateMachine
    risk_before: Decimal       # R-risk ДО передвижения стопа
    risk_after: Decimal        # R-risk ПОСЛЕ (всегда < risk_before)
    should_execute: bool       # Нужно ли отправить ордер на биржу
    reason: str                # Объяснение для аудита
```

### PositionRiskRecord (для RiskLedger):

```python
@dataclass
class PositionRiskRecord:
    """Запись о риске позиции в RiskLedger."""

    position_id: str
    symbol: str
    side: str                   # "long" / "short"
    entry_price: Decimal
    current_stop: Decimal       # Актуальный стоп (обновляется TrailingPolicy)
    quantity: Decimal
    current_risk_usd: Decimal   # |entry - current_stop| × qty
    current_risk_r: Decimal     # В R-единицах от капитала
    trailing_state: str         # INACTIVE / ARMED / ACTIVE / EMERGENCY / TERMINATED
    opened_at: datetime
    updated_at: datetime
```

---

## 🔧 ТРЕБОВАНИЕ 1: Risk Engine Core (src/risk/engine.py)

```python
from decimal import Decimal
from typing import Dict, Optional, List
import asyncio
import time
from datetime import datetime, timedelta
from collections import deque

from src.core.logger import get_logger
from src.core.config_manager import ConfigManager
from src.risk.models import Order, RiskCheckResult, Position
from src.risk.position_sizing import PositionSizer
from src.risk.correlation import CorrelationCalculator
from src.risk.drawdown_monitor import DrawdownMonitor
from src.risk.trailing_policy import TrailingPolicy
from src.risk.risk_ledger import RiskLedger
from src.risk.funding_manager import FundingManager

logger = get_logger("RiskEngine")


class RiskEngine:
    """
    Движок управления рисками v4.4.

    Состав:
    - PositionSizer: R-unit расчёт (Van Tharp)
    - CorrelationCalculator: корреляция по группам (Majors/L1/DeFi/Memes)
    - DrawdownMonitor: Soft/Hard/Velocity drawdown tracking
    - TrailingPolicy: институциональный трейлинг T1-T4
    - RiskLedger: реестр рисков позиций (single source of truth)
    - FundingManager: funding rate arbitrage между биржами

    Инварианты:
    - Ни одна сделка не проходит без одобрения этого класса
    - TrailingPolicy НИКОГДА не двигает стоп без обновления RiskLedger
    - При ошибке любого компонента → отклонить сделку (fail-safe)
    """

    def __init__(
        self,
        config_manager: ConfigManager,
        event_bus,           # PyEventBus
        db,                  # PostgreSQLManager
        state_machine,       # StateMachine из Control Plane
    ):
        """
        Инициализировать Risk Engine.

        Аргументы:
            config_manager: Менеджер конфигурации
            event_bus: Шина событий
            db: База данных для аудита и RiskLedger
            state_machine: State Machine из Control Plane
        """
        self.config = config_manager
        self.event_bus = event_bus
        self.db = db
        self.state_machine = state_machine

        # ─── Основные компоненты ───────────────────────────
        self.position_sizer = PositionSizer(config_manager)
        self.correlation_calc = CorrelationCalculator(window_size=100)
        self.drawdown_monitor = DrawdownMonitor(db, event_bus)

        # ─── НОВЫЕ компоненты v4.4 ─────────────────────────
        self.risk_ledger = RiskLedger(db)
        self.trailing_policy = TrailingPolicy(
            config_manager=config_manager,
            risk_ledger=self.risk_ledger,
            event_bus=event_bus,
            state_machine=state_machine,
        )
        self.funding_manager = FundingManager(config_manager, event_bus)

        # ─── Velocity KillSwitch state ────────────────────
        # Последние N сделок (для расчёта velocity)
        self._recent_trades: deque = deque(maxlen=10)
        self._velocity_triggered: bool = False
        self._velocity_triggered_at: Optional[datetime] = None

        # ─── Portfolio state (lock-free reads) ────────────
        self._portfolio_lock = asyncio.Lock()
        self._open_positions: Dict[str, Position] = {}
        self._quick_check_cache = {
            "total_risk_r": Decimal(0),
            "position_count": 0,
        }

        logger.info("Risk Engine v4.4 инициализирован")

    # ══════════════════════════════════════════════════════
    # ПУБЛИЧНЫЙ API
    # ══════════════════════════════════════════════════════

    async def check_trade(self, order: Order) -> RiskCheckResult:
        """
        Проверить допустимость сделки.

        ОБЯЗАТЕЛЬНО реализовать все проверки в порядке:
        1. State Machine разрешает торговлю
        2. Velocity KillSwitch не сработал
        3. R-unit размер не превышает max_r_per_trade
        4. Общий риск RiskLedger не превышает max_total_r
        5. Корреляция < correlation_limit
        6. Correlation Group лимит не превышен
        7. Текущая просадка < max_drawdown_hard
        8. Funding rate check (рекомендация биржи)
        """
        start_time = time.time()

        try:
            limits = self._get_risk_limits()

            # ── 1. State Machine check ──────────────────────
            sm_state = self.state_machine.state
            if sm_state not in ("TRADING", "DEGRADED"):
                return self._reject(
                    "state_machine_not_trading",
                    start_time,
                    detail=f"Текущее состояние: {sm_state}"
                )

            # ── 2. Velocity KillSwitch ──────────────────────
            if self._velocity_triggered:
                # Проверить не истёк ли cooldown (24 часа)
                if self._velocity_triggered_at and \
                   (datetime.utcnow() - self._velocity_triggered_at) < timedelta(hours=24):
                    return self._reject(
                        "velocity_killswitch_active",
                        start_time,
                        detail="Velocity KillSwitch активен — новые сделки запрещены"
                    )
                else:
                    # Cooldown истёк → сбросить
                    self._velocity_triggered = False
                    logger.info("Velocity KillSwitch сброшен после cooldown")

            # ── 3. R-unit check ─────────────────────────────
            risk_r = self._calculate_risk_r(order, limits)

            if risk_r > limits.max_r_per_trade:
                await self._publish_risk_violation("max_r_exceeded", order, risk_r)
                return self._reject("max_r_exceeded", start_time, risk_r=risk_r)

            # В DEGRADED mode — дополнительное ограничение (50% от обычного)
            if sm_state == "DEGRADED":
                degraded_max_r = limits.max_r_per_trade * Decimal("0.5")
                if risk_r > degraded_max_r:
                    return self._reject(
                        "max_r_exceeded_degraded_mode",
                        start_time,
                        risk_r=risk_r,
                        max_size=self.position_sizer.calculate(
                            order, degraded_max_r,
                            await self._get_account_balance()
                        ).position_size_usd,
                    )

            # ── 4. Total R из RiskLedger ─────────────────────
            total_r_ledger = await self.risk_ledger.get_total_risk_r()
            if total_r_ledger + risk_r > limits.max_total_r:
                return self._reject(
                    "max_total_r_exceeded",
                    start_time,
                    risk_r=risk_r,
                    current_total_r=total_r_ledger,
                )

            # ── 5. Correlation check ─────────────────────────
            if self._open_positions:
                correlation = await self._check_correlation(order)
                if correlation > limits.correlation_limit:
                    return self._reject(
                        "correlation_too_high",
                        start_time,
                        correlation_with_portfolio=correlation,
                    )

            # ── 6. Correlation Group лимит ───────────────────
            group = self.correlation_calc.get_group(order.symbol)
            group_r = await self.risk_ledger.get_group_risk_r(group)
            if group_r + risk_r > limits.max_group_r.get(group, limits.max_total_r):
                return self._reject(
                    "correlation_group_limit_exceeded",
                    start_time,
                    detail=f"Группа {group}: {group_r:.2f}R уже занято"
                )

            # ── 7. Drawdown check ────────────────────────────
            current_dd = self.drawdown_monitor.get_current_drawdown()
            if current_dd >= limits.max_drawdown_hard:
                await self._publish_drawdown_alert("hard_limit", current_dd)
                return self._reject("drawdown_hard_limit_exceeded", start_time)

            # ── 8. Funding Rate рекомендация ──────────────────
            recommended_exchange = await self.funding_manager.get_best_exchange(
                order.symbol, order.side, order.exchange_id
            )

            # ── Все проверки пройдены ────────────────────────
            account_balance = await self._get_account_balance()
            position_size = self.position_sizer.calculate(order, risk_r, account_balance)

            duration_ms = int((time.time() - start_time) * 1000)
            self.metrics.record_histogram("risk_check_duration_ms", duration_ms)

            logger.info(
                "Сделка одобрена",
                symbol=order.symbol,
                risk_r=float(risk_r),
                position_size_usd=float(position_size.position_size_usd),
                recommended_exchange=recommended_exchange,
                duration_ms=duration_ms,
            )

            return RiskCheckResult(
                allowed=True,
                reason="within_limits",
                risk_r=risk_r,
                position_size_usd=position_size.position_size_usd,
                position_size_base=position_size.quantity,
                current_total_r=total_r_ledger + risk_r,
                max_total_r=limits.max_total_r,
                recommended_exchange=recommended_exchange,
                check_duration_ms=duration_ms,
            )

        except Exception as e:
            logger.error(
                "Ошибка проверки риска — отклонение для безопасности",
                order_id=order.order_id,
                error=str(e),
            )
            return self._reject("internal_error", start_time)

    async def on_bar_completed(self, event) -> None:
        """
        Обработать завершение бара (вызывается от Market Data).

        Для каждой открытой позиции вызывает TrailingPolicy.evaluate().
        Это ГЛАВНЫЙ цикл трейлинга — вызывается на каждом новом баре.

        Аргументы:
            event: BAR_COMPLETED с полями {symbol, high, low, close, atr, adx, volume}
        """
        symbol = event.payload["symbol"]
        market_data = event.payload  # {high, low, close, atr, adx, ...}

        # Найти позиции по этому символу
        positions_for_symbol = [
            pos for pos in self._open_positions.values()
            if pos.symbol == symbol
        ]

        for position in positions_for_symbol:
            try:
                # Переключить TrailingPolicy в EMERGENCY если система деградировала
                sm_state = self.state_machine.state
                if sm_state in ("SURVIVAL", "RISK_REDUCTION"):
                    stop_update = await self.trailing_policy.force_emergency(position)
                else:
                    stop_update = await self.trailing_policy.evaluate(position, market_data)

                if stop_update and stop_update.should_execute:
                    # Отправить обновление стопа на биржу через Event Bus
                    await self.event_bus.publish({
                        "type": "UPDATE_STOP_LOSS",
                        "priority": "HIGH",
                        "payload": {
                            "position_id": position.position_id,
                            "new_stop": float(stop_update.new_stop),
                            "exchange_id": position.exchange_id,
                        }
                    })

                    # Опубликовать событие для мониторинга
                    await self.event_bus.publish({
                        "type": "TRAILING_STOP_MOVED",
                        "priority": "NORMAL",
                        "payload": {
                            "position_id": stop_update.position_id,
                            "old_stop": float(stop_update.old_stop),
                            "new_stop": float(stop_update.new_stop),
                            "pnl_r": float(stop_update.pnl_r),
                            "tier": stop_update.tier,
                            "mode": stop_update.mode,
                            "state": stop_update.state,
                            "risk_before": float(stop_update.risk_before),
                            "risk_after": float(stop_update.risk_after),
                        }
                    })

            except Exception as e:
                logger.error(
                    "Ошибка TrailingPolicy — оставляем текущий стоп",
                    position_id=position.position_id,
                    symbol=symbol,
                    error=str(e),
                )

    async def on_order_filled(self, event) -> None:
        """
        Обработать исполнение ордера.

        Обновляет:
        - Internal portfolio state
        - RiskLedger (ОБЯЗАТЕЛЬНО)
        - Velocity KillSwitch (учёт сделки)
        - TrailingPolicy (инициализация для новой позиции)
        """
        payload = event.payload
        symbol = payload["symbol"]
        side = payload["side"]
        qty = Decimal(str(payload["filled_qty"]))
        price = Decimal(str(payload["avg_price"]))
        stop_loss = Decimal(str(payload.get("stop_loss", 0)))

        async with self._portfolio_lock:
            # Обновить portfolio state
            await self._update_position(symbol, side, qty, price, stop_loss)

            # Обновить RiskLedger
            position = self._open_positions.get(symbol)
            if position:
                await self.risk_ledger.register_position(position)

            # Обновить quick check cache
            self._quick_check_cache["position_count"] = len(self._open_positions)
            self._quick_check_cache["total_risk_r"] = await self.risk_ledger.get_total_risk_r()

        # Учесть для Velocity KillSwitch
        await self._record_trade_for_velocity(payload)

    async def on_position_closed(self, event) -> None:
        """
        Обработать закрытие позиции.

        Завершает TrailingPolicy для позиции, освобождает RiskLedger.
        """
        position_id = event.payload["position_id"]
        realized_pnl_r = Decimal(str(event.payload.get("realized_pnl_r", 0)))

        # Завершить TrailingPolicy
        position = self._find_position_by_id(position_id)
        if position:
            await self.trailing_policy.terminate(position)

        # Освободить в RiskLedger
        await self.risk_ledger.close_position(position_id)

        # Учесть P&L для Velocity KillSwitch
        if realized_pnl_r < 0:
            await self._record_loss_for_velocity(realized_pnl_r)

        async with self._portfolio_lock:
            # Удалить из open positions
            symbol = event.payload.get("symbol")
            if symbol and symbol in self._open_positions:
                del self._open_positions[symbol]
            self._quick_check_cache["position_count"] = len(self._open_positions)
            self._quick_check_cache["total_risk_r"] = await self.risk_ledger.get_total_risk_r()

        logger.info(
            "Позиция закрыта, риск освобождён",
            position_id=position_id,
            realized_pnl_r=float(realized_pnl_r),
        )
```

---

## 🔧 ТРЕБОВАНИЕ 2: RiskLedger (src/risk/risk_ledger.py)

```python
"""
RiskLedger — единый реестр рисков всех открытых позиций.

❗ КРИТИЧЕСКИ ВАЖНО:
TrailingPolicy НЕ ИМЕЕТ ПРАВА менять стоп-лосс позиции
без синхронизации с RiskLedger через update_position_risk().

RiskLedger — единственный источник истины о текущем риске системы.
"""

from decimal import Decimal
from typing import Dict, Optional, List
from datetime import datetime
from dataclasses import dataclass, field

from src.core.logger import get_logger
from src.risk.models import PositionRiskRecord

logger = get_logger("RiskLedger")


class RiskLedger:
    """
    Реестр рисков открытых позиций.

    Отслеживает:
    - Текущий стоп-лосс каждой позиции (актуальный, с учётом трейлинга)
    - Риск каждой позиции в R-единицах и USD
    - Суммарный риск портфеля
    - Риск по correlation groups

    Инварианты:
    - Риск позиции ТОЛЬКО уменьшается (трейлинг двигает стоп в сторону прибыли)
    - Суммарный риск всегда корректен (обновляется атомарно)
    - Все изменения логируются для аудита
    """

    def __init__(self, db):
        """
        Аргументы:
            db: PostgreSQLManager для персистентности
        """
        self.db = db
        self._positions: Dict[str, PositionRiskRecord] = {}
        self._lock = asyncio.Lock()
        self._total_risk_r_cache: Decimal = Decimal(0)

    async def register_position(self, position) -> None:
        """
        Зарегистрировать новую позицию в реестре.

        Вызывается при открытии позиции (after ORDER_FILLED).

        Аргументы:
            position: Position объект с entry_price, stop_loss, quantity, side
        """
        risk_usd = abs(position.entry_price - position.stop_loss) * position.quantity
        account_balance = await self._get_account_balance()
        risk_r = risk_usd / (account_balance * Decimal("0.01"))  # Нормируем к 1R

        record = PositionRiskRecord(
            position_id=position.position_id,
            symbol=position.symbol,
            side=position.side,
            entry_price=position.entry_price,
            current_stop=position.stop_loss,
            quantity=position.quantity,
            current_risk_usd=risk_usd,
            current_risk_r=risk_r,
            trailing_state="INACTIVE",
            opened_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        async with self._lock:
            self._positions[position.position_id] = record
            self._recalculate_total_risk()

        # Персистировать
        await self._save_to_db(record)

        logger.info(
            "Позиция зарегистрирована в RiskLedger",
            position_id=position.position_id,
            risk_usd=float(risk_usd),
            risk_r=float(risk_r),
        )

    async def update_position_risk(
        self,
        position_id: str,
        old_risk_r: Decimal,
        new_risk_r: Decimal,
        new_stop: Decimal,
        trailing_state: str,
    ) -> bool:
        """
        Обновить риск позиции после передвижения стопа.

        ❗ ОБЯЗАТЕЛЬНО вызывать ДО отправки ордера на биржу.
        ❗ Гарантирует: new_risk_r <= old_risk_r (риск только уменьшается).

        Аргументы:
            position_id: ID позиции
            old_risk_r: Предыдущий риск в R
            new_risk_r: Новый риск в R (ДОЛЖЕН БЫТЬ <= old_risk_r)
            new_stop: Новый уровень стоп-лосса
            trailing_state: Новое состояние трейлинга

        Возвращает:
            True если обновление применено
            False если нарушен инвариант (риск увеличился)
        """
        # Инвариант: риск может только уменьшаться
        if new_risk_r > old_risk_r:
            logger.error(
                "❌ Нарушение инварианта RiskLedger: риск должен уменьшаться",
                position_id=position_id,
                old_risk_r=float(old_risk_r),
                new_risk_r=float(new_risk_r),
            )
            return False

        async with self._lock:
            if position_id not in self._positions:
                logger.warning("Позиция не найдена в RiskLedger", position_id=position_id)
                return False

            record = self._positions[position_id]
            record.current_risk_r = new_risk_r
            record.current_stop = new_stop
            record.trailing_state = trailing_state
            record.updated_at = datetime.utcnow()

            self._recalculate_total_risk()

        # Аудит в БД
        await self._log_risk_change(position_id, old_risk_r, new_risk_r, new_stop)

        logger.info(
            "Риск позиции обновлён в RiskLedger",
            position_id=position_id,
            old_risk_r=float(old_risk_r),
            new_risk_r=float(new_risk_r),
            reduction=float(old_risk_r - new_risk_r),
        )
        return True

    async def close_position(self, position_id: str) -> None:
        """
        Закрыть позицию — освободить риск в реестре.

        Аргументы:
            position_id: ID закрываемой позиции
        """
        async with self._lock:
            if position_id in self._positions:
                record = self._positions.pop(position_id)
                self._recalculate_total_risk()
                logger.info(
                    "Позиция удалена из RiskLedger",
                    position_id=position_id,
                    freed_risk_r=float(record.current_risk_r),
                )

    async def get_total_risk_r(self) -> Decimal:
        """
        Получить суммарный риск портфеля в R-единицах (lock-free).

        Используется в hot path check_trade().
        Latency: <1μs (чтение из кэша).
        """
        return self._total_risk_r_cache

    async def get_group_risk_r(self, group: str) -> Decimal:
        """
        Получить суммарный риск по correlation group.

        Аргументы:
            group: "Majors" / "L1" / "DeFi" / "Memes"
        """
        GROUP_SYMBOLS = {
            "Majors": {"BTC/USDT", "ETH/USDT"},
            "L1": {"SOL/USDT", "AVAX/USDT", "NEAR/USDT", "APT/USDT"},
            "DeFi": {"UNI/USDT", "AAVE/USDT", "SNX/USDT"},
            "Memes": {"DOGE/USDT", "SHIB/USDT", "PEPE/USDT"},
        }
        symbols_in_group = GROUP_SYMBOLS.get(group, set())
        return sum(
            r.current_risk_r
            for r in self._positions.values()
            if r.symbol in symbols_in_group
        )

    def _recalculate_total_risk(self) -> None:
        """Пересчитать суммарный риск (вызывается под lock)."""
        self._total_risk_r_cache = sum(
            r.current_risk_r for r in self._positions.values()
        )

    async def _save_to_db(self, record: PositionRiskRecord) -> None:
        """Сохранить запись в таблицу risk_ledger."""
        await self.db.execute("""
            INSERT INTO risk_ledger
                (position_id, symbol, side, entry_price, current_stop,
                 quantity, current_risk_usd, current_risk_r,
                 trailing_state, opened_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            ON CONFLICT (position_id) DO UPDATE SET
                current_stop = EXCLUDED.current_stop,
                current_risk_usd = EXCLUDED.current_risk_usd,
                current_risk_r = EXCLUDED.current_risk_r,
                trailing_state = EXCLUDED.trailing_state,
                updated_at = EXCLUDED.updated_at
        """, record.position_id, record.symbol, record.side,
            record.entry_price, record.current_stop, record.quantity,
            record.current_risk_usd, record.current_risk_r,
            record.trailing_state, record.opened_at, record.updated_at)

    async def _log_risk_change(
        self,
        position_id: str,
        old_risk_r: Decimal,
        new_risk_r: Decimal,
        new_stop: Decimal,
    ) -> None:
        """Залогировать изменение риска для аудита."""
        await self.db.execute("""
            INSERT INTO risk_ledger_audit
                (position_id, old_risk_r, new_risk_r, new_stop, changed_at)
            VALUES ($1, $2, $3, $4, NOW())
        """, position_id, old_risk_r, new_risk_r, new_stop)
```

---

## 🔧 ТРЕБОВАНИЕ 3: TRAILING POLICY  (ПОЛНАЯ РЕАЛИЗАЦИЯ)


**Назначение:** Подсистема управления уже принятым риском (НЕ стратегия, НЕ execution).

**Главная задача:**
- Монотонно снижать риск открытой позиции
- Без увеличения экспозиции
- С учётом состояния системы (State Machine), рынка (ADX), инфраструктуры

**Место в архитектуре:**
```
RiskEngine
├── RiskLedger
├── TrailingPolicy      ← ЭТОТ КОМПОНЕНТ
├── RiskInvariants
└── VelocityKillSwitch
```

❗ **КРИТИЧНО:** Trailing Stop НЕ принадлежит StrategyModule — это часть RiskEngine.

---

### Файл: src/risk/trailing_policy.py

```python
"""
TrailingPolicy v4.4 — институциональное управление трейлинг-стопом.

Спецификация: Trailing Stop.txt

Ключевые особенности:
- Tier-based логика (T1-T4 по R-multiples)
- Структурный трейлинг (Soft HL) при ADX > threshold
- Emergency mode при StateMachine = SURVIVAL/RISK_REDUCTION
- ОБЯЗАТЕЛЬНАЯ синхронизация с RiskLedger
- Инварианты: монотонность, снижение риска, наблюдаемость
"""

from enum import Enum
from typing import Optional, Dict
from decimal import Decimal
from datetime import datetime, timezone
from dataclasses import dataclass

from src.core.logger import get_logger
from src.risk.risk_ledger import RiskLedger

logger = get_logger("TrailingPolicy")


class TrailingState(str, Enum):
    """
    Состояния трейлинга согласно спецификации.
    """
    INACTIVE = "INACTIVE"       # Трейлинг не активен (PnL < R_START)
    ARMED = "ARMED"             # Условия выполнены, но стоп ещё не двигаем
    ACTIVE = "ACTIVE"           # Нормальный трейлинг
    EMERGENCY = "EMERGENCY"     # Аварийный режим
    TERMINATED = "TERMINATED"   # Позиция закрыта


class TrailingTier(str, Enum):
    """
    Tier-based уровни трейлинга по R-multiples.
    """
    T1 = "T1"  # 1–2R: очень мягкий (2.0 × ATR)
    T2 = "T2"  # 2–4R: стандарт (1.5 × ATR)
    T3 = "T3"  # 4–6R: агрессивный (1.1 × ATR)
    T4 = "T4"  # >6R: защитный (0.8 × ATR)


class TrailingMode(str, Enum):
    """Режимы трейлинга."""
    NORMAL = "NORMAL"       # Стандартный
    EMERGENCY = "EMERGENCY"  # Аварийный


@dataclass
class StopUpdate:
    """
    Обновление стоп-цены.
    
    Атрибуты:
        old_stop: Старая стоп-цена
        new_stop: Новая стоп-цена
        pnl_r: Текущий PnL в R-multiples
        tier: Tier трейлинга (T1-T4)
        mode: Режим (NORMAL/EMERGENCY)
        risk_before: Риск до обновления (R units)
        risk_after: Риск после обновления (R units)
        reason: Причина обновления
    """
    old_stop: Decimal
    new_stop: Decimal
    pnl_r: Decimal
    tier: TrailingTier
    mode: TrailingMode
    risk_before: Decimal
    risk_after: Decimal
    reason: str


@dataclass
class TrailingParams:
    """
    Параметры трейлинга из конфигурации.
    """
    # Активация
    r_start: Decimal = Decimal("1.0")  # Активация при +1R
    
    # Tier multipliers (× ATR)
    t1_multiplier: Decimal = Decimal("2.0")   # 1–2R
    t2_multiplier: Decimal = Decimal("1.5")   # 2–4R
    t3_multiplier: Decimal = Decimal("1.1")   # 4–6R
    t4_multiplier: Decimal = Decimal("0.8")   # >6R
    
    # Structural trailing (Soft HL)
    use_soft_hl: bool = True
    adx_threshold: Decimal = Decimal("25.0")  # Минимальный ADX для Soft HL
    confirmed_hh_count: int = 2               # Минимум подтверждённых HH
    
    # Emergency mode
    emergency_buffer_bps: Decimal = Decimal("50")  # 50 bps от best bid/ask


class TrailingPolicy:
    """
    Институциональное управление трейлинг-стопом.
    
    Инварианты (КРИТИЧНО):
    1. Trailing stop can only reduce risk
    2. Stop price is monotonic (never moves away)
    3. Trailing respects system state
    4. No soft trailing in EMERGENCY
    5. Every stop move updates RiskLedger
    6. Trailing action is fully logged
    """
    
    def __init__(
        self,
        risk_ledger: RiskLedger,
        state_machine,
        params: Optional[TrailingParams] = None,
    ):
        """
        Аргументы:
            risk_ledger: RiskLedger для синхронизации рисков
            state_machine: State Machine для проверки состояния системы
            params: Параметры трейлинга (по умолчанию из конфига)
        """
        self.risk_ledger = risk_ledger
        self.state_machine = state_machine
        self.params = params or TrailingParams()
        
        # Состояния трейлинга для каждой позиции
        self.trailing_states: Dict[str, TrailingState] = {}
        
        logger.info(
            "TrailingPolicy инициализирован",
            r_start=float(self.params.r_start),
            use_soft_hl=self.params.use_soft_hl,
        )
    
    def evaluate(
        self,
        position,
        market_data: dict,
    ) -> Optional[StopUpdate]:
        """
        Оценить необходимость обновления стопа для позиции.
        
        ГЛАВНЫЙ МЕТОД согласно спецификации.
        
        Аргументы:
            position: Позиция с полями:
                - position_id
                - pnl_r (текущий PnL в R)
                - stop_loss (текущий стоп)
                - direction (LONG/SHORT)
                - is_open
                - current_risk
            market_data: Рыночные данные:
                - current_price
                - atr
                - adx (опционально)
                - best_bid, best_ask (для EMERGENCY)
                - soft_high_low (опционально)
        
        Возвращает:
            StopUpdate если стоп нужно передвинуть
            None если обновление не требуется
        
        Workflow:
        1. Проверить условия активации трейлинга
        2. Определить tier (T1-T4) по pnl_r
        3. Определить mode (NORMAL/EMERGENCY) по State Machine
        4. Рассчитать new_stop
        5. Проверить инварианты
        6. Синхронизировать с RiskLedger
        7. Вернуть StopUpdate
        """
        # 1. Проверить базовые условия активации
        if not self._check_activation_conditions(position):
            return None
        
        # 2. Определить текущее состояние трейлинга
        current_state = self._get_or_init_state(position.position_id)
        
        # Если INACTIVE и PnL >= R_START → ARMED
        if current_state == TrailingState.INACTIVE:
            if position.pnl_r >= self.params.r_start:
                self.trailing_states[position.position_id] = TrailingState.ARMED
                logger.info(
                    "Трейлинг ARMED",
                    position_id=position.position_id,
                    pnl_r=float(position.pnl_r),
                )
                current_state = TrailingState.ARMED
            else:
                # Ещё не достиг R_START
                return None
        
        # 3. Определить tier по pnl_r
        tier = self._select_tier(position.pnl_r)
        
        # 4. Определить mode по State Machine
        mode = self._determine_mode()
        
        # 5. Рассчитать new_stop
        new_stop = self._calculate_new_stop(
            position=position,
            market_data=market_data,
            tier=tier,
            mode=mode,
        )
        
        # 6. Проверить инварианты
        if not self._check_invariants(position, new_stop):
            logger.warning(
                "Трейлинг отклонён — нарушение инварианта",
                position_id=position.position_id,
                old_stop=float(position.stop_loss),
                new_stop=float(new_stop),
            )
            return None
        
        # 7. Если стоп не изменился — skip
        if new_stop == position.stop_loss:
            return None
        
        # 8. Синхронизация с RiskLedger (КРИТИЧНО!)
        old_risk = position.current_risk
        new_risk = self._calculate_risk_after_stop_move(position, new_stop)
        
        # Обновить RiskLedger
        try:
            self.risk_ledger.update_position_risk(
                position_id=position.position_id,
                old_risk=old_risk,
                new_risk=new_risk,
            )
        except Exception as e:
            logger.error(
                "❌ БЛОКИРОВКА трейлинга — RiskLedger timeout",
                position_id=position.position_id,
                error=str(e),
            )
            # ИНВАРИАНТ: No stop move without RiskLedger sync
            return None
        
        # 9. Обновить состояние на ACTIVE
        if current_state == TrailingState.ARMED:
            self.trailing_states[position.position_id] = TrailingState.ACTIVE
        
        # 10. Создать StopUpdate
        stop_update = StopUpdate(
            old_stop=position.stop_loss,
            new_stop=new_stop,
            pnl_r=position.pnl_r,
            tier=tier,
            mode=mode,
            risk_before=old_risk,
            risk_after=new_risk,
            reason=f"tier_{tier.value}_mode_{mode.value}",
        )
        
        # 11. Логирование (ОБЯЗАТЕЛЬНО для observability)
        logger.info(
            "✅ Трейлинг-стоп передвинут",
            position_id=position.position_id,
            old_stop=float(stop_update.old_stop),
            new_stop=float(stop_update.new_stop),
            pnl_r=float(stop_update.pnl_r),
            tier=tier.value,
            mode=mode.value,
            risk_before=float(stop_update.risk_before),
            risk_after=float(stop_update.risk_after),
        )
        
        return stop_update
    
    def _check_activation_conditions(self, position) -> bool:
        """
        Проверить базовые условия активации трейлинга.
        
        Из спецификации:
        if (
            position.pnl_r >= R_START and
            position.is_open and
            StateMachine.state in ["TRADING", "DEGRADED"]
        ):
            return True
        
        Запреты:
        - StateMachine == HALT
        - KillSwitch.triggered == True
        - position.execution_uncertain == True
        """
        # Позиция должна быть открыта
        if not position.is_open:
            return False
        
        # State Machine в допустимом состоянии
        system_state = self.state_machine.get_current_state()
        if system_state not in ["TRADING", "DEGRADED", "RISK_REDUCTION"]:
            logger.debug(
                "Трейлинг заблокирован State Machine",
                state=system_state,
                position_id=position.position_id,
            )
            return False
        
        # Execution uncertain — запрет
        if getattr(position, 'execution_uncertain', False):
            logger.warning(
                "Трейлинг заблокирован — execution uncertain",
                position_id=position.position_id,
            )
            return False
        
        return True
    
    def _select_tier(self, pnl_r: Decimal) -> TrailingTier:
        """
        Выбрать tier по pnl_r согласно спецификации.
        
        Tier	PnL (R)	Trail Multiplier
        T1	1–2R	2.0 × ATR
        T2	2–4R	1.5 × ATR
        T3	4–6R	1.1 × ATR
        T4	>6R	    0.8 × ATR
        """
        if pnl_r < 2:
            return TrailingTier.T1
        elif pnl_r < 4:
            return TrailingTier.T2
        elif pnl_r < 6:
            return TrailingTier.T3
        else:
            return TrailingTier.T4
    
    def _determine_mode(self) -> TrailingMode:
        """
        Определить режим трейлинга по State Machine.
        
        Из спецификации:
        if StateMachine.state in ["SURVIVAL", "RISK_REDUCTION"]:
            trailing_mode = "EMERGENCY"
        """
        system_state = self.state_machine.get_current_state()
        
        if system_state in ["SURVIVAL", "RISK_REDUCTION"]:
            return TrailingMode.EMERGENCY
        
        return TrailingMode.NORMAL
    
    def _calculate_new_stop(
        self,
        position,
        market_data: dict,
        tier: TrailingTier,
        mode: TrailingMode,
    ) -> Decimal:
        """
        Рассчитать новую стоп-цену.
        
        NORMAL mode (базовая формула):
            new_stop = max(
                previous_stop,
                reference_price - trail_mult * ATR
            )
        
        EMERGENCY mode:
            new_stop = best_bid - emergency_buffer
            (запрещены: Soft HL, ATR smoothing, Confirmation)
        """
        current_price = market_data['current_price']
        atr = market_data['atr']
        
        # EMERGENCY MODE
        if mode == TrailingMode.EMERGENCY:
            return self._calculate_emergency_stop(position, market_data)
        
        # NORMAL MODE
        
        # Trail multiplier по tier
        trail_mult = self._get_trail_multiplier(tier)
        
        # Reference price
        # Structural (Soft HL) если условия выполнены
        if self._can_use_soft_hl(market_data):
            reference_price = market_data.get('soft_high_low', current_price)
            logger.debug(
                "Использован Soft HL",
                reference_price=float(reference_price),
                current_price=float(current_price),
            )
        else:
            reference_price = current_price
        
        # Рассчитать new_stop
        if position.direction == "LONG":
            new_stop = reference_price - trail_mult * atr
        else:  # SHORT
            new_stop = reference_price + trail_mult * atr
        
        # Монотонность (ИНВАРИАНТ)
        if position.direction == "LONG":
            new_stop = max(position.stop_loss, new_stop)
        else:
            new_stop = min(position.stop_loss, new_stop)
        
        return new_stop
    
    def _get_trail_multiplier(self, tier: TrailingTier) -> Decimal:
        """Получить trail multiplier для tier."""
        multipliers = {
            TrailingTier.T1: self.params.t1_multiplier,
            TrailingTier.T2: self.params.t2_multiplier,
            TrailingTier.T3: self.params.t3_multiplier,
            TrailingTier.T4: self.params.t4_multiplier,
        }
        return multipliers[tier]
    
    def _can_use_soft_hl(self, market_data: dict) -> bool:
        """
        Проверить можно ли использовать Structural (Soft HL) trailing.
        
        Условия из спецификации:
        - ADX > ADX_THRESHOLD
        - confirmed_HH_count >= 2
        - StateMachine.state == "TRADING"
        - params.use_soft_hl == True
        """
        if not self.params.use_soft_hl:
            return False
        
        # ADX check
        adx = market_data.get('adx')
        if adx is None or adx < self.params.adx_threshold:
            return False
        
        # Confirmed HH count
        confirmed_hh = market_data.get('confirmed_hh_count', 0)
        if confirmed_hh < self.params.confirmed_hh_count:
            return False
        
        # State Machine
        if self.state_machine.get_current_state() != "TRADING":
            return False
        
        return True
    
    def _calculate_emergency_stop(
        self,
        position,
        market_data: dict,
    ) -> Decimal:
        """
        Рассчитать стоп в EMERGENCY mode.
        
        Из спецификации:
        new_stop = best_bid - emergency_buffer
        
        Цель: немедленно снизить риск
        """
        best_bid = market_data['best_bid']
        best_ask = market_data['best_ask']
        
        buffer_bps = self.params.emergency_buffer_bps
        
        if position.direction == "LONG":
            # Стоп ниже best_bid на buffer
            new_stop = best_bid * (Decimal("1") - buffer_bps / Decimal("10000"))
        else:  # SHORT
            # Стоп выше best_ask на buffer
            new_stop = best_ask * (Decimal("1") + buffer_bps / Decimal("10000"))
        
        logger.warning(
            "EMERGENCY трейлинг",
            position_id=position.position_id,
            new_stop=float(new_stop),
            buffer_bps=float(buffer_bps),
        )
        
        return new_stop
    
    def _check_invariants(
        self,
        position,
        new_stop: Decimal,
    ) -> bool:
        """
        Проверить инварианты трейлинга.
        
        Из спецификации:
        1. Trailing stop can only reduce risk
        2. Stop price is monotonic (never moves away)
        3. Trailing respects system state
        """
        # 1. Монотонность
        if position.direction == "LONG":
            if new_stop < position.stop_loss:
                logger.error(
                    "ИНВАРИАНТ НАРУШЕН: Монотонность (LONG)",
                    old_stop=float(position.stop_loss),
                    new_stop=float(new_stop),
                )
                return False
        else:  # SHORT
            if new_stop > position.stop_loss:
                logger.error(
                    "ИНВАРИАНТ НАРУШЕН: Монотонность (SHORT)",
                    old_stop=float(position.stop_loss),
                    new_stop=float(new_stop),
                )
                return False
        
        # 2. Стоп не должен быть за текущей ценой
        current_price = position.current_price
        if position.direction == "LONG" and new_stop > current_price:
            logger.error(
                "ИНВАРИАНТ НАРУШЕН: Stop > market price",
                new_stop=float(new_stop),
                current_price=float(current_price),
            )
            return False
        if position.direction == "SHORT" and new_stop < current_price:
            logger.error(
                "ИНВАРИАНТ НАРУШЕН: Stop < market price",
                new_stop=float(new_stop),
                current_price=float(current_price),
            )
            return False
        
        # 3. Риск должен снижаться
        old_risk = position.current_risk
        new_risk = self._calculate_risk_after_stop_move(position, new_stop)
        
        if new_risk > old_risk:
            logger.error(
                "ИНВАРИАНТ НАРУШЕН: Риск увеличился",
                old_risk=float(old_risk),
                new_risk=float(new_risk),
            )
            return False
        
        return True
    
    def _calculate_risk_after_stop_move(
        self,
        position,
        new_stop: Decimal,
    ) -> Decimal:
        """
        Рассчитать риск после перемещения стопа.
        
        risk = |entry_price - new_stop| * quantity
        """
        risk_per_unit = abs(position.entry_price - new_stop)
        total_risk = risk_per_unit * position.quantity
        return total_risk
    
    def force_emergency(self, position) -> StopUpdate:
        """
        Принудительный перевод в EMERGENCY mode.
        
        Используется Kill Switch при критических событиях.
        """
        logger.critical(
            "🔴 ПРИНУДИТЕЛЬНЫЙ EMERGENCY трейлинг",
            position_id=position.position_id,
        )
        
        # Установить состояние
        self.trailing_states[position.position_id] = TrailingState.EMERGENCY
        
        # Вызвать evaluate в EMERGENCY mode
        # (State Machine уже должен быть в SURVIVAL/RISK_REDUCTION)
        
        return self.evaluate(
            position=position,
            market_data={
                'current_price': position.current_price,
                'atr': position.atr,
                'best_bid': position.best_bid,
                'best_ask': position.best_ask,
            }
        )
    
    def terminate(self, position_id: str) -> None:
        """
        Завершить трейлинг для позиции (позиция закрыта).
        
        Аргументы:
            position_id: ID закрытой позиции
        """
        if position_id in self.trailing_states:
            self.trailing_states[position_id] = TrailingState.TERMINATED
            logger.info(
                "Трейлинг завершён",
                position_id=position_id,
            )
    
    def _get_or_init_state(self, position_id: str) -> TrailingState:
        """Получить или инициализировать состояние трейлинга."""
        if position_id not in self.trailing_states:
            self.trailing_states[position_id] = TrailingState.INACTIVE
        return self.trailing_states[position_id]
```

### Events & Logging (для Monitoring)

```python
# Event при каждом перемещении стопа
{
  "event": "TRAILING_STOP_MOVED",
  "position_id": "SOL-123",
  "old_stop": 102.5,
  "new_stop": 104.8,
  "pnl_r": 3.6,
  "tier": "T2",
  "mode": "NORMAL",
  "state": "TRADING",
  "risk_before": 0.42,
  "risk_after": 0.31,
  "timestamp": "2026-02-20T01:15:00Z"
}
```

### Database Schema

```sql
-- Trailing stop movements (audit trail)
CREATE TABLE trailing_stop_movements (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    position_id VARCHAR(50) NOT NULL,
    old_stop NUMERIC(20, 8) NOT NULL,
    new_stop NUMERIC(20, 8) NOT NULL,
    
    pnl_r NUMERIC(10, 4) NOT NULL,
    tier VARCHAR(5) NOT NULL,
    mode VARCHAR(20) NOT NULL,
    
    risk_before NUMERIC(20, 8) NOT NULL,
    risk_after NUMERIC(20, 8) NOT NULL,
    
    system_state VARCHAR(20) NOT NULL,
    
    market_data JSONB
);

CREATE INDEX idx_trailing_position ON trailing_stop_movements(position_id, timestamp DESC);
CREATE INDEX idx_trailing_time ON trailing_stop_movements(timestamp DESC);
```

### Ошибки и защитные реакции

| Ошибка | Реакция |
|--------|---------|
| RiskLedger timeout | **БЛОКИРОВАТЬ** trailing |
| Market data stale | Switch to **EMERGENCY** |
| Stop > market price | **Immediate close** |
| Execution reject | Retry → **EMERGENCY** |

### Инварианты (КРИТИЧНО для тестирования)

```python
TRAILING_INVARIANTS = [
    "Trailing stop can only reduce risk",
    "Stop price is monotonic (never moves away)",
    "Trailing respects system state",
    "No soft trailing in EMERGENCY",
    "Every stop move updates RiskLedger",
    "Trailing action is fully logged"
]
```

---

## ACCEPTANCE CRITERIA — TrailingPolicy

### Функциональность ✅
- [ ] Tier selection (T1-T4) по pnl_r
- [ ] NORMAL mode с Soft HL (при ADX > 25, HH >= 2)
- [ ] EMERGENCY mode при SURVIVAL/RISK_REDUCTION
- [ ] Монотонность стоп-цены (никогда не отдаляется)
- [ ] Синхронизация с RiskLedger (ОБЯЗАТЕЛЬНО)

### Инварианты ✅
- [ ] Trailing stop can only reduce risk (проверка в _check_invariants)
- [ ] Stop price is monotonic (проверка в _check_invariants)
- [ ] No stop move without RiskLedger sync (try-catch в evaluate)

### Integration ✅
- [ ] State Machine check перед каждым evaluate
- [ ] RiskLedger.update_position_risk() при каждом движении стопа
- [ ] Event TRAILING_STOP_MOVED публикуется
- [ ] Database audit trail (trailing_stop_movements)

### Observability ✅
- [ ] Полное логирование каждого движения стопа
- [ ] Metrics: trailing_stops_moved_total, trailing_latency
- [ ] Replay support (детерминированность)

---

## 🔧 ТРЕБОВАНИЕ 4: Velocity KillSwitch (в составе engine.py)

```python
class RiskEngine:
    """Добавить в существующий класс RiskEngine."""

    async def _record_trade_for_velocity(self, trade_payload: dict) -> None:
        """
        Учесть сделку для Velocity KillSwitch.

        Velocity KillSwitch срабатывает при потере >= 2R
        в последних 10 сделках (скользящее окно).

        Аргументы:
            trade_payload: {realized_pnl_r, symbol, side, ...}
        """
        pnl_r = Decimal(str(trade_payload.get("realized_pnl_r", 0)))

        # Добавить в скользящее окно
        self._recent_trades.append({
            "pnl_r": pnl_r,
            "timestamp": datetime.utcnow(),
            "symbol": trade_payload.get("symbol"),
        })

        # Рассчитать суммарные потери в окне
        total_losses_r = sum(
            abs(t["pnl_r"])
            for t in self._recent_trades
            if t["pnl_r"] < 0  # Только убыточные сделки
        )

        velocity_limit = self.config.get(
            "risk.velocity_killswitch.max_loss_r",
            default=Decimal("2.0")
        )

        if total_losses_r >= velocity_limit and not self._velocity_triggered:
            self._velocity_triggered = True
            self._velocity_triggered_at = datetime.utcnow()

            logger.critical(
                "🛑 Velocity KillSwitch СРАБОТАЛ",
                total_losses_r=float(total_losses_r),
                window_trades=len(self._recent_trades),
                velocity_limit=float(velocity_limit),
            )

            # Опубликовать критическое событие
            await self.event_bus.publish({
                "type": "VELOCITY_KILLSWITCH_TRIGGERED",
                "priority": "CRITICAL",
                "payload": {
                    "losses_r": float(total_losses_r),
                    "window_trades": len(self._recent_trades),
                    "triggered_at": datetime.utcnow().isoformat(),
                    "action": "halt_new_trades_24h",
                }
            })

            # Уведомить State Machine — перейти в DEGRADED или SURVIVAL
            await self.state_machine.transition(
                "DEGRADED",
                trigger="velocity_killswitch",
                metadata={"losses_r": float(total_losses_r)},
            )
```

---

## 🔧 ТРЕБОВАНИЕ 5: FundingManager (src/risk/funding_manager.py)

```python
"""
FundingManager — мониторинг и арбитраж Funding Rate между биржами.

Назначение:
    1. Мониторить funding rates на всех биржах
    2. Рекомендовать оптимальную биржу для новых позиций
    3. Находить arbitrage opportunities (longs на одной бирже, short на другой)
    4. Логировать все funding rates для аналитики
"""

from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import asyncio

from src.core.logger import get_logger

logger = get_logger("FundingManager")


class FundingManager:
    """
    Менеджер Funding Rate Arbitrage.

    Биржи: Bybit, OKX, Binance.
    Funding period: каждые 8 часов (стандарт).

    Arbitrage условие:
        spread = |funding_rate_bybit - funding_rate_okx| > MIN_SPREAD (0.2%)
        annualized = spread × 3 (периодов/день) × 365 > MIN_ANNUAL (5%)
    """

    # Минимальный спред для арбитража (0.2% за период = ~21.9% годовых)
    MIN_ARBITRAGE_SPREAD: Decimal = Decimal("0.002")

    # Максимальный допустимый funding rate для открытия позиции
    MAX_ACCEPTABLE_FUNDING: Decimal = Decimal("0.003")  # 0.3% за 8ч = 32.8% годовых

    def __init__(self, config_manager, event_bus):
        """
        Аргументы:
            config_manager: Для чтения параметров арбитража
            event_bus: Для публикации FUNDING_ARBITRAGE_FOUND
        """
        self.config = config_manager
        self.event_bus = event_bus

        # Кэш funding rates: {symbol: {exchange: rate}}
        self._funding_rates: Dict[str, Dict[str, Decimal]] = {}
        self._rates_updated_at: Dict[str, datetime] = {}

        # Стоп-флаги для арбитражных позиций
        self._active_arb_positions: Dict[str, dict] = {}

    async def update_funding_rates(self, symbol: str, rates: Dict[str, Decimal]) -> None:
        """
        Обновить funding rates от Market Data Layer.

        Аргументы:
            symbol: Например, "BTC/USDT"
            rates: {"bybit": 0.0001, "okx": 0.0003, "binance": 0.0002}
        """
        self._funding_rates[symbol] = {
            exchange: Decimal(str(rate))
            for exchange, rate in rates.items()
        }
        self._rates_updated_at[symbol] = datetime.utcnow()

        # Проверить arbitrage opportunity
        await self._check_arbitrage_opportunity(symbol)

    async def get_best_exchange(
        self,
        symbol: str,
        side: str,
        current_exchange: str,
    ) -> str:
        """
        Рекомендовать оптимальную биржу для открытия позиции.

        Для LONG: предпочитаем биржу с наименьшим (или отрицательным) funding rate
        Для SHORT: предпочитаем биржу с наибольшим funding rate

        Аргументы:
            symbol: Торговый символ
            side: "long" или "short"
            current_exchange: Предложенная биржа

        Возвращает:
            Название оптимальной биржи
        """
        rates = self._funding_rates.get(symbol, {})
        if not rates:
            return current_exchange  # Нет данных → используем предложенную

        if side == "long":
            # Минимальный funding (платим как можно меньше)
            best = min(rates.items(), key=lambda x: x[1])
        else:
            # Максимальный funding (получаем как можно больше)
            best = max(rates.items(), key=lambda x: x[1])

        best_exchange, best_rate = best
        current_rate = rates.get(current_exchange, Decimal(0))

        # Рекомендовать смену только если разница значительна (>0.05% за период)
        MIN_IMPROVEMENT = Decimal("0.0005")
        if abs(best_rate - current_rate) > MIN_IMPROVEMENT:
            logger.info(
                "Рекомендована смена биржи по funding rate",
                symbol=symbol,
                side=side,
                current=f"{current_exchange}({float(current_rate):.4%})",
                recommended=f"{best_exchange}({float(best_rate):.4%})",
                saving_per_period=float(abs(best_rate - current_rate)),
            )
            return best_exchange

        return current_exchange

    async def _check_arbitrage_opportunity(self, symbol: str) -> None:
        """
        Проверить наличие funding rate arbitrage.

        Arbitrage = открыть LONG на бирже с низким funding,
                    одновременно SHORT на бирже с высоким funding.

        Публикует FUNDING_ARBITRAGE_FOUND если spread достаточен.
        """
        rates = self._funding_rates.get(symbol, {})
        if len(rates) < 2:
            return

        sorted_rates = sorted(rates.items(), key=lambda x: x[1])
        long_exchange, long_rate = sorted_rates[0]   # Минимальный funding (для LONG)
        short_exchange, short_rate = sorted_rates[-1]  # Максимальный (для SHORT)

        spread = short_rate - long_rate
        annualized_profit = spread * 3 * 365  # 3 периода в день × 365 дней

        if spread >= self.MIN_ARBITRAGE_SPREAD:
            logger.info(
                "Обнаружена возможность funding арбитража",
                symbol=symbol,
                long_exchange=long_exchange,
                short_exchange=short_exchange,
                spread=float(spread),
                annualized_percent=float(annualized_profit * 100),
            )

            await self.event_bus.publish({
                "type": "FUNDING_ARBITRAGE_FOUND",
                "priority": "NORMAL",
                "payload": {
                    "symbol": symbol,
                    "long_exchange": long_exchange,
                    "short_exchange": short_exchange,
                    "spread": float(spread),
                    "annualized_profit": float(annualized_profit),
                    "long_rate": float(long_rate),
                    "short_rate": float(short_rate),
                    "detected_at": datetime.utcnow().isoformat(),
                }
            })
```

---

## 📊 DATABASE SCHEMA (PostgreSQL)

```sql
-- Реестр рисков позиций
CREATE TABLE risk_ledger (
    position_id     VARCHAR(50) PRIMARY KEY,
    symbol          VARCHAR(20) NOT NULL,
    side            VARCHAR(10) NOT NULL,
    entry_price     NUMERIC(20, 8) NOT NULL,
    current_stop    NUMERIC(20, 8) NOT NULL,
    quantity        NUMERIC(20, 8) NOT NULL,
    current_risk_usd NUMERIC(20, 8) NOT NULL,
    current_risk_r  NUMERIC(10, 4) NOT NULL,
    trailing_state  VARCHAR(20) NOT NULL DEFAULT 'INACTIVE',
    opened_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Аудит изменений риска (каждое движение стопа)
CREATE TABLE risk_ledger_audit (
    audit_id        SERIAL PRIMARY KEY,
    position_id     VARCHAR(50) NOT NULL,
    old_risk_r      NUMERIC(10, 4) NOT NULL,
    new_risk_r      NUMERIC(10, 4) NOT NULL,
    new_stop        NUMERIC(20, 8) NOT NULL,
    risk_reduction  NUMERIC(10, 4) GENERATED ALWAYS AS (old_risk_r - new_risk_r) STORED,
    changed_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Трейлинг-стопы (детальный лог)
CREATE TABLE trailing_stops (
    id              SERIAL PRIMARY KEY,
    position_id     VARCHAR(50) NOT NULL,
    symbol          VARCHAR(20) NOT NULL,
    old_stop        NUMERIC(20, 8) NOT NULL,
    new_stop        NUMERIC(20, 8) NOT NULL,
    pnl_r           NUMERIC(10, 4) NOT NULL,
    tier            VARCHAR(20) NOT NULL,
    mode            VARCHAR(20) NOT NULL,     -- NORMAL, STRUCTURAL, EMERGENCY
    system_state    VARCHAR(20) NOT NULL,
    risk_before     NUMERIC(10, 4) NOT NULL,
    risk_after      NUMERIC(10, 4) NOT NULL,
    reason          TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_trailing_stops_position ON trailing_stops(position_id);
CREATE INDEX idx_trailing_stops_created ON trailing_stops(created_at DESC);

-- Funding rates (история для анализа)
CREATE TABLE funding_rates (
    id              SERIAL PRIMARY KEY,
    symbol          VARCHAR(20) NOT NULL,
    exchange        VARCHAR(20) NOT NULL,
    rate            NUMERIC(10, 6) NOT NULL,
    annualized      NUMERIC(10, 4),
    recorded_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_funding_rates_symbol ON funding_rates(symbol, exchange, recorded_at DESC);

-- Velocity KillSwitch (история срабатываний)
CREATE TABLE velocity_killswitch_events (
    id              SERIAL PRIMARY KEY,
    total_losses_r  NUMERIC(10, 4) NOT NULL,
    window_trades   INTEGER NOT NULL,
    triggered_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reset_at        TIMESTAMPTZ
);

-- Проверки риска (audit trail)
CREATE TABLE risk_checks (
    id              SERIAL PRIMARY KEY,
    order_id        VARCHAR(50),
    symbol          VARCHAR(20),
    risk_r          NUMERIC(10, 4),
    decision        VARCHAR(10) NOT NULL,   -- ALLOW / REJECT
    reason          VARCHAR(100),
    check_duration_ms INTEGER,
    exchange_recommended VARCHAR(20),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_risk_checks_created ON risk_checks(created_at DESC);
```

---

## ⚠️ CRITICAL ОГРАНИЧЕНИЯ ФАЗЫ 5

### ✅ Что реализовано:
- R-unit position sizing (Van Tharp методология)
- Correlation analysis + CorrelationGroups (Majors/L1/DeFi/Memes)
- Drawdown Monitoring (Soft 5% / Hard 10% / Recovery mode)
- **TrailingPolicy** — T1/T2/T3/T4 tier-based, Structural (Soft HL), Emergency mode
- **RiskLedger** — единый реестр рисков, синхронизирован с TrailingPolicy
- **FundingManager** — мониторинг + Arbitrage (Bybit/OKX/Binance)
- **Velocity KillSwitch** — 2R за 10 сделок → 24h cooldown
- Интеграция с State Machine (DEGRADED → ужесточение, SURVIVAL → Emergency trailing)

### ❌ Что НЕ реализовано (для future phases):
- ML-предсказание корреляций (→ Фаза 21)
- Options Greeks risk (delta, gamma, vega)
- VaR / CVaR (→ Фаза 15/SimulationEngine)
- Pyramiding (масштабирование в прибыльную позицию)
- HTF Liquidity Map (→ Фаза 7: Indicators)
- Stop Hunt Score (→ Фаза 7: Indicators)

---

## 🚀 ПРОИЗВОДИТЕЛЬНОСТЬ

```
Операция                              Target      Частота
─────────────────────────────────────────────────────────────
check_trade()                         <100ms      10-100/сек
calculate_position_size()             <50ms       10-100/сек
TrailingPolicy.evaluate()             <20ms       1/бар на позицию
RiskLedger.update_position_risk()     <10ms       при каждом движении стопа
RiskLedger.get_total_risk_r()         <1μs        lock-free read
FundingManager.get_best_exchange()    <5ms        при каждой сделке
CorrelationMatrix full recalc         <5s         каждые 5 минут
─────────────────────────────────────────────────────────────
```

---

## ACCEPTANCE CRITERIA

### Core Risk Engine
- [ ] check_trade() проверяет все 8 условий по порядку
- [ ] R-unit sizing рассчитывается корректно (Van Tharp)
- [ ] Velocity KillSwitch срабатывает при ≥2R потерь за 10 сделок
- [ ] В DEGRADED mode max_r_per_trade уменьшается до 50%

### TrailingPolicy
- [ ] TRAILING_STATES: INACTIVE → ARMED → ACTIVE → TERMINATED (happy path)
- [ ] EMERGENCY mode включается при SURVIVAL/RISK_REDUCTION
- [ ] Tier-based логика: T1=2.0×ATR, T2=1.5×ATR, T3=1.1×ATR, T4=0.8×ATR
- [ ] Монотонность: стоп НИКОГДА не движется дальше от цены
- [ ] Structural trailing требует ADX > 18 И ≥2 подтверждённых HH
- [ ] При HALT — TrailingPolicy не выполняется

### RiskLedger
- [ ] Каждое движение стопа синхронизировано с RiskLedger
- [ ] Инвариант нарушен (риск вырос) → StopUpdate отклонён
- [ ] get_total_risk_r() < 1μs (lock-free)
- [ ] Аудит всех изменений в risk_ledger_audit

### FundingManager
- [ ] Рекомендует биржу с наименьшим funding для LONG
- [ ] Публикует FUNDING_ARBITRAGE_FOUND при spread > 0.2%
- [ ] Логирует все rates в funding_rates таблицу

### Performance
- [ ] check_trade() median <50ms, p99 <100ms
- [ ] TrailingPolicy.evaluate() <20ms per position
- [ ] 100 concurrent check_trade <500ms total

---

**Version:** CRYPTOTEHNOLOG v4.4 (Фаза 5 — полная редакция)
**Dependencies:** Phases 0-4
**Next:** Phase 6 - Market Data Layer (UniverseEngine, ADX, HTF levels)

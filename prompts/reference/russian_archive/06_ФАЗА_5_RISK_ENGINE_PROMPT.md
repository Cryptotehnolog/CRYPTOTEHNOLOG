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

## 🔧 ТРЕБОВАНИЕ 3: TrailingPolicy (src/risk/trailing_policy.py)

```python
"""
TrailingPolicy — институциональный модуль управления трейлинг-стопом.

Назначение:
    Монотонно снижать риск открытой позиции — без увеличения экспозиции,
    с учётом состояния системы, рынка и инфраструктуры.

❗ TrailingPolicy НЕ принадлежит StrategyModule.
   TrailingPolicy — часть RiskEngine (Control Plane).

Архитектура:
    RiskEngine
    └── TrailingPolicy
        ├── evaluate()          # Нормальная оценка (каждый бар)
        ├── force_emergency()   # Аварийный режим (SURVIVAL/RISK_REDUCTION)
        └── terminate()         # Завершение (при закрытии позиции)

❗ ОБЯЗАТЕЛЬНЫЙ инвариант:
    Любое передвижение стопа ДОЛЖНО быть синхронизировано с RiskLedger
    через risk_ledger.update_position_risk() ДО отправки ордера на биржу.
"""

from decimal import Decimal
from typing import Optional, Dict
from datetime import datetime
import asyncio

from src.core.logger import get_logger
from src.risk.models import StopUpdate, PositionRiskRecord

logger = get_logger("TrailingPolicy")


# ─── Константы состояний ────────────────────────────────────────────────────
TRAILING_STATES = [
    "INACTIVE",    # Трейлинг не активен (PnL < R_START)
    "ARMED",       # Условия выполнены, стоп ещё не двигаем
    "ACTIVE",      # Нормальный трейлинг — стоп движется
    "EMERGENCY",   # Аварийный режим — немедленное снижение риска
    "TERMINATED",  # Позиция закрыта
]

# ─── Инварианты (нарушение → panic + log) ───────────────────────────────────
TRAILING_INVARIANTS = [
    "Trailing stop can only reduce risk",           # Стоп движется ТОЛЬКО в прибыль
    "Stop price is monotonic (never moves away)",   # Для LONG: stop только вверх
    "Trailing respects system state",               # При HALT — не двигаем
    "No soft trailing in EMERGENCY",               # В аварийном режиме — только raw
    "Every stop move updates RiskLedger",          # Обязательная синхронизация
    "Trailing action is fully logged",             # Каждое действие логируется
]


class TrailingPolicy:
    """
    Политика управления трейлинг-стопом (Tier-based, R-multiple driven).

    Жизненный цикл позиции:
        POSITION_OPENED
              ↓
        TRAILING_INACTIVE   (PnL < R_START)
              ↓
        TRAILING_ARMED      (PnL ≥ R_START, ждём подтверждения)
              ↓
        TRAILING_ACTIVE     (стоп движется по tier-логике)
              ↓
        STOP_MOVED (0..N)   (каждый бар, если условия выполнены)
              ↓
        POSITION_CLOSED

    Tier-based логика (по R-multiples):
        T1 (1–2R):   trail_mult = 2.0 × ATR   (очень мягкий)
        T2 (2–4R):   trail_mult = 1.5 × ATR   (стандартный)
        T3 (4–6R):   trail_mult = 1.1 × ATR   (агрессивный)
        T4 (>6R):    trail_mult = 0.8 × ATR   (защитный)
    """

    # Tier-based мультипликаторы ATR
    TIER_MULTIPLIERS = {
        "T1": Decimal("2.0"),   # 1–2R: мягкий
        "T2": Decimal("1.5"),   # 2–4R: стандарт
        "T3": Decimal("1.1"),   # 4–6R: агрессивный
        "T4": Decimal("0.8"),   # >6R: защитный (сохранение прибыли)
    }

    def __init__(
        self,
        config_manager,
        risk_ledger: "RiskLedger",
        event_bus,
        state_machine,
    ):
        """
        Аргументы:
            config_manager: Для чтения параметров (R_START, ADX_THRESHOLD)
            risk_ledger: ОБЯЗАТЕЛЬНО — для синхронизации при каждом движении стопа
            event_bus: Для публикации TRAILING_STOP_MOVED
            state_machine: Для проверки текущего состояния системы
        """
        self.config = config_manager
        self.risk_ledger = risk_ledger
        self.event_bus = event_bus
        self.state_machine = state_machine

        # Состояния трейлинга для каждой позиции
        self._states: Dict[str, str] = {}

        # Tracking для Structural (Soft HL) trailing
        # position_id → список подтверждённых HH (High-High)
        self._confirmed_hh: Dict[str, list] = {}
        self._last_swing_high: Dict[str, Decimal] = {}

    async def evaluate(
        self,
        position,
        market_data: dict,
    ) -> Optional[StopUpdate]:
        """
        Оценить и (если нужно) передвинуть трейлинг-стоп.

        MAIN ENTRY POINT — вызывается на каждом закрытом баре
        из RiskEngine.on_bar_completed().

        Аргументы:
            position: Открытая позиция с {position_id, symbol, side,
                       entry_price, current_stop, quantity, pnl_r}
            market_data: {high, low, close, atr, adx, volume, timestamp}

        Возвращает:
            StopUpdate если стоп нужно передвинуть
            None если стоп остаётся на месте
        """
        position_id = position.position_id
        sm_state = self.state_machine.state

        # ── Инвариант: не активен при HALT ──────────────────
        if sm_state == "HALT":
            logger.debug(
                "TrailingPolicy пропущен — система в HALT",
                position_id=position_id,
            )
            return None

        # ── Проверить, не завершена ли позиция ──────────────
        current_state = self._states.get(position_id, "INACTIVE")
        if current_state == "TERMINATED":
            return None

        # ── Рассчитать текущий P&L в R-единицах ─────────────
        pnl_r = self._calculate_pnl_r(position, market_data["close"])

        # ── Обновить состояние трейлинга ─────────────────────
        R_START = self.config.get("risk.trailing.r_start", default=Decimal("1.0"))

        if current_state == "INACTIVE":
            if pnl_r >= R_START and position.is_open:
                self._states[position_id] = "ARMED"
                logger.info(
                    "TrailingPolicy ARMED",
                    position_id=position_id,
                    pnl_r=float(pnl_r),
                    r_start=float(R_START),
                )
            return None  # ARMED — ещё не двигаем

        if current_state == "ARMED":
            # Одно подтверждение → переходим в ACTIVE
            self._states[position_id] = "ACTIVE"

        # ── Выбрать тир и режим ──────────────────────────────
        tier = self._select_tier(pnl_r)
        trail_mult = self.TIER_MULTIPLIERS[tier]
        atr = Decimal(str(market_data["atr"]))
        adx = float(market_data.get("adx", 0))

        # ── Определить режим трейлинга ───────────────────────
        use_structural = self._should_use_structural(
            position_id=position_id,
            market_data=market_data,
            adx=adx,
        )

        if use_structural:
            reference_price = self._get_soft_high_low(position, market_data)
            mode = "STRUCTURAL"
        else:
            # Обычный: reference = текущий close
            if position.side == "long":
                reference_price = Decimal(str(market_data["high"]))
            else:
                reference_price = Decimal(str(market_data["low"]))
            mode = "NORMAL"

        # ── Рассчитать новый стоп ────────────────────────────
        new_stop = self._calculate_new_stop(
            position=position,
            reference_price=reference_price,
            trail_mult=trail_mult,
            atr=atr,
        )

        # ── Проверить монотонность (инвариант) ───────────────
        if not self._is_monotonic(position, new_stop):
            # Стоп не улучшился — оставляем текущий
            return None

        # ── ОБЯЗАТЕЛЬНО: синхронизация с RiskLedger ──────────
        ledger_record = await self.risk_ledger._positions.get(position_id)
        if ledger_record is None:
            logger.error(
                "Позиция не найдена в RiskLedger — отмена движения стопа",
                position_id=position_id,
            )
            return None

        old_risk_r = ledger_record.current_risk_r
        new_risk_r = self._calculate_new_risk_r(position, new_stop)

        # Обновить RiskLedger
        success = await self.risk_ledger.update_position_risk(
            position_id=position_id,
            old_risk_r=old_risk_r,
            new_risk_r=new_risk_r,
            new_stop=new_stop,
            trailing_state="ACTIVE",
        )

        if not success:
            logger.error(
                "RiskLedger отклонил обновление — отмена движения стопа",
                position_id=position_id,
            )
            return None

        logger.info(
            "Трейлинг-стоп передвинут",
            position_id=position_id,
            old_stop=float(position.current_stop),
            new_stop=float(new_stop),
            pnl_r=float(pnl_r),
            tier=tier,
            mode=mode,
            risk_before=float(old_risk_r),
            risk_after=float(new_risk_r),
        )

        return StopUpdate(
            position_id=position_id,
            old_stop=position.current_stop,
            new_stop=new_stop,
            pnl_r=pnl_r,
            tier=tier,
            mode=mode,
            state=sm_state,
            risk_before=old_risk_r,
            risk_after=new_risk_r,
            should_execute=True,
            reason=f"Tier {tier}, ATR×{trail_mult}, режим {mode}",
        )

    async def force_emergency(self, position) -> StopUpdate:
        """
        Активировать аварийный режим трейлинга.

        Вызывается при StateMachine.state in ["SURVIVAL", "RISK_REDUCTION"].

        Поведение в EMERGENCY:
        - Soft HL (структурный трейлинг) — ЗАПРЕЩЁН
        - ATR smoothing — ОТКЛЮЧЁН
        - Confirmation — НЕ НУЖНО
        - Цель — немедленно снизить риск до минимума
        - Формула: new_stop = best_bid - emergency_buffer

        ❗ ОБЯЗАТЕЛЬНО синхронизировать с RiskLedger.

        Аргументы:
            position: Позиция для аварийного закрытия стопа

        Возвращает:
            StopUpdate с новым аварийным стопом
        """
        position_id = position.position_id
        sm_state = self.state_machine.state

        # Маркируем как EMERGENCY
        self._states[position_id] = "EMERGENCY"

        emergency_buffer = self.config.get(
            "risk.trailing.emergency_buffer_atr",
            default=Decimal("0.5")
        )

        # Аварийный стоп = best_bid - emergency_buffer × ATR
        # (для LONG: стоп ставим как можно ближе к текущей цене)
        atr = position.last_atr or Decimal("10")  # Fallback если нет ATR
        best_bid = position.current_price

        if position.side == "long":
            new_stop = best_bid - emergency_buffer * atr
            # Но не ниже текущего стопа (монотонность)
            new_stop = max(new_stop, position.current_stop)
        else:
            new_stop = best_bid + emergency_buffer * atr
            new_stop = min(new_stop, position.current_stop)

        # Синхронизация с RiskLedger (ОБЯЗАТЕЛЬНО)
        ledger_record = self.risk_ledger._positions.get(position_id)
        old_risk_r = ledger_record.current_risk_r if ledger_record else Decimal("0")
        new_risk_r = self._calculate_new_risk_r(position, new_stop)

        await self.risk_ledger.update_position_risk(
            position_id=position_id,
            old_risk_r=old_risk_r,
            new_risk_r=new_risk_r,
            new_stop=new_stop,
            trailing_state="EMERGENCY",
        )

        logger.warning(
            "⚠️  TrailingPolicy EMERGENCY активирован",
            position_id=position_id,
            old_stop=float(position.current_stop),
            new_stop=float(new_stop),
            sm_state=sm_state,
            risk_before=float(old_risk_r),
            risk_after=float(new_risk_r),
        )

        return StopUpdate(
            position_id=position_id,
            old_stop=position.current_stop,
            new_stop=new_stop,
            pnl_r=self._calculate_pnl_r(position, position.current_price),
            tier="EMERGENCY",
            mode="EMERGENCY",
            state=sm_state,
            risk_before=old_risk_r,
            risk_after=new_risk_r,
            should_execute=True,
            reason=f"EMERGENCY MODE: {sm_state}",
        )

    async def terminate(self, position) -> None:
        """
        Завершить трейлинг для позиции (при закрытии позиции).

        Аргументы:
            position: Закрытая позиция
        """
        position_id = position.position_id
        self._states[position_id] = "TERMINATED"
        self._confirmed_hh.pop(position_id, None)
        self._last_swing_high.pop(position_id, None)

        logger.info(
            "TrailingPolicy завершён для позиции",
            position_id=position_id,
        )

    # ══════════════════════════════════════════════════════
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ
    # ══════════════════════════════════════════════════════

    def _select_tier(self, pnl_r: Decimal) -> str:
        """
        Выбрать тир трейлинга по текущему P&L в R-единицах.

        Tier-таблица:
            T1 (1–2R):  trail_mult = 2.0 × ATR  — очень мягкий
            T2 (2–4R):  trail_mult = 1.5 × ATR  — стандартный
            T3 (4–6R):  trail_mult = 1.1 × ATR  — агрессивный
            T4 (>6R):   trail_mult = 0.8 × ATR  — защитный

        Аргументы:
            pnl_r: Текущий P&L позиции в R-единицах

        Возвращает:
            "T1", "T2", "T3" или "T4"
        """
        if pnl_r < Decimal("2"):
            return "T1"
        if pnl_r < Decimal("4"):
            return "T2"
        if pnl_r < Decimal("6"):
            return "T3"
        return "T4"

    def _should_use_structural(
        self,
        position_id: str,
        market_data: dict,
        adx: float,
    ) -> bool:
        """
        Определить использовать ли Structural (Soft HL) трейлинг.

        Structural trailing используется только если:
        1. ADX > ADX_THRESHOLD (сильный тренд)
        2. Подтверждено >= 2 последовательных Higher High
        3. StateMachine.state == "TRADING" (не DEGRADED и не EMERGENCY)

        В противном случае — базовый ATR-трейлинг.

        Аргументы:
            position_id: ID позиции (для tracking HH)
            market_data: {high, low, adx, ...}
            adx: Значение ADX

        Возвращает:
            True если использовать структурный трейлинг
        """
        ADX_THRESHOLD = float(
            self.config.get("risk.trailing.adx_threshold", default=18.0)
        )

        # Условие 1: Сильный тренд
        if adx <= ADX_THRESHOLD:
            return False

        # Условие 2: State Machine не DEGRADED
        if self.state_machine.state != "TRADING":
            return False

        # Условие 3: Проверить подтверждённые HH
        confirmed_hh = self._confirmed_hh.get(position_id, [])
        current_high = Decimal(str(market_data["high"]))

        # Обновить tracking HH
        last_high = self._last_swing_high.get(position_id, Decimal(0))
        if current_high > last_high:
            confirmed_hh.append(current_high)
            self._last_swing_high[position_id] = current_high
            self._confirmed_hh[position_id] = confirmed_hh[-5:]  # Храним последние 5

        return len(confirmed_hh) >= 2

    def _get_soft_high_low(self, position, market_data: dict) -> Decimal:
        """
        Получить soft High/Low для структурного трейлинга.

        Вместо тик-цен использует подтверждённые swing high/low.

        Аргументы:
            position: Открытая позиция
            market_data: {high, low}

        Возвращает:
            reference_price для расчёта нового стопа
        """
        position_id = position.position_id
        confirmed_hh = self._confirmed_hh.get(position_id, [])

        if position.side == "long" and confirmed_hh:
            # Для LONG: используем последний подтверждённый HH
            return confirmed_hh[-1]
        else:
            # Fallback: текущий high/low
            key = "high" if position.side == "long" else "low"
            return Decimal(str(market_data[key]))

    def _calculate_new_stop(
        self,
        position,
        reference_price: Decimal,
        trail_mult: Decimal,
        atr: Decimal,
    ) -> Decimal:
        """
        Рассчитать новый уровень стоп-лосса.

        Базовая формула (NORMAL/STRUCTURAL mode):
            new_stop = max(previous_stop, reference_price - trail_mult × ATR)  # LONG
            new_stop = min(previous_stop, reference_price + trail_mult × ATR)  # SHORT

        Аргументы:
            position: Позиция с current_stop и side
            reference_price: Опорная цена (close или soft HH/LL)
            trail_mult: Мультипликатор ATR из tier
            atr: Значение Average True Range

        Возвращает:
            Новый уровень стоп-лосса
        """
        if position.side == "long":
            proposed_stop = reference_price - trail_mult * atr
            return max(position.current_stop, proposed_stop)
        else:
            proposed_stop = reference_price + trail_mult * atr
            return min(position.current_stop, proposed_stop)

    def _is_monotonic(self, position, new_stop: Decimal) -> bool:
        """
        Проверить монотонность: стоп движется только в сторону прибыли.

        Для LONG: new_stop > current_stop (стоп движется вверх)
        Для SHORT: new_stop < current_stop (стоп движется вниз)

        Аргументы:
            position: Позиция с current_stop и side
            new_stop: Предлагаемый новый стоп

        Возвращает:
            True если новый стоп лучше текущего
        """
        if position.side == "long":
            return new_stop > position.current_stop
        else:
            return new_stop < position.current_stop

    def _calculate_pnl_r(self, position, current_price: Decimal) -> Decimal:
        """
        Рассчитать текущий P&L в R-единицах.

        Формула: PnL_R = (current_price - entry_price) / initial_risk_per_unit

        Аргументы:
            position: Позиция с entry_price, initial_stop, side
            current_price: Текущая цена

        Возвращает:
            P&L в R-единицах (>0 прибыль, <0 убыток)
        """
        initial_risk_per_unit = abs(position.entry_price - position.initial_stop)

        if initial_risk_per_unit == 0:
            return Decimal(0)

        if position.side == "long":
            pnl_per_unit = current_price - position.entry_price
        else:
            pnl_per_unit = position.entry_price - current_price

        return pnl_per_unit / initial_risk_per_unit

    def _calculate_new_risk_r(self, position, new_stop: Decimal) -> Decimal:
        """
        Рассчитать новый риск в R-единицах после передвижения стопа.

        Аргументы:
            position: Позиция
            new_stop: Новый стоп-лосс

        Возвращает:
            Новый риск в R-единицах
        """
        initial_risk_per_unit = abs(position.entry_price - position.initial_stop)

        if initial_risk_per_unit == 0:
            return Decimal(0)

        current_risk_per_unit = abs(position.current_price - new_stop)
        return (current_risk_per_unit / initial_risk_per_unit) * position.entry_risk_r


# ─── Обработка ошибок TrailingPolicy ────────────────────────────────────────
TRAILING_ERROR_HANDLERS = {
    "RiskLedger timeout": "BLOCK trailing — не двигаем стоп без подтверждения RiskLedger",
    "Market data stale":  "Switch to EMERGENCY — используем last known ATR",
    "Stop > market price": "Immediate close — стоп пробит, закрываем позицию",
    "Execution reject":    "Retry (3 попытки) → EMERGENCY mode",
}
```

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

# AI ПРОМТ: ФАЗА 8 - SIGNAL GENERATOR + OPPORTUNITY ENGINE (v2.0 — ПОЛНАЯ РЕДАКЦИЯ)

## КОНТЕКСТ

Вы — Senior Quantitative Trader, специализирующийся на algorithmic trading strategies,
signal generation, opportunity scoring, и conflict resolution.

**Фазы 0-7 завершены.** Доступны:
- Event Bus (Rust + Python) — работает с persistence
- Control Plane (State Machine, Watchdog, OperatorGate) — работает
- Config Manager — hot reload, GPG signatures, Vault
- Risk Engine v4.4 — R-unit, TrailingPolicy, RiskLedger, FundingManager, Velocity KillSwitch
- Market Data Layer — WebSocket, ticks, OHLCV bars, orderbook
- Indicators + Intelligence Layer — 20+ индикаторов, RegimeClusterEngine,
  ImpulseAnalyzer, LiquidityIntelligence (HTF Map + Stop Hunt), MAE/MFE Tracker
- Database Layer, Logging, Metrics — готовы

**Текущая задача:** Реализовать production-ready Signal Generator v4.4, включающий:
1. **SignalGenerator** — генерация сигналов, multi-condition logic, confidence scoring
2. **OpportunityEngine** — скоринг и ранжирование торговых возможностей по символам
3. **MetaClassifier** — разрешение конфликтов между стратегиями (одна стратегия сигнал BUY, другая SELL)
4. **Стратегии (4 штуки):**
   - `DonchianBreakoutStrategy` — Donchian + ADX (основная из v4.3.1)
   - `MomentumStrategy` — RSI + MACD + EMA
   - `MeanReversionStrategy` — Bollinger Bands + RSI
   - `RegimeAdaptiveStrategy` — адаптация к режиму рынка (RegimeClusterEngine)
5. **Pyramiding** — масштабирование позиции при подтверждении тренда (3 tiers, 50% decay)
6. **StopHuntFilter** — фильтрация ложных входов при stop hunt сигнале

---

## ⚠️ КРИТИЧЕСКИ ВАЖНО: РУССКИЙ ЯЗЫК

**ВСЕ** комментарии, docstrings, логи и сообщения об ошибках должны быть **НА РУССКОМ ЯЗЫКЕ**.

### Python docstrings — ТОЛЬКО русский:

```python
class OpportunityEngine:
    """
    Движок скоринга торговых возможностей.

    Ранжирует все символы из торговой вселенной по привлекательности
    на основе: confidence сигнала, режима рынка, Impulse Factor,
    liquidity score, risk/reward ratio.

    Возвращает топ-N символов для Strategy Manager (Фаза 14).
    """

class MetaClassifier:
    """
    Классификатор для разрешения конфликтов между стратегиями.

    Ситуация конфликта: DonchianBreakout генерирует BUY,
    MomentumStrategy генерирует SELL для одного символа.

    Алгоритм разрешения:
    1. Сравнить confidence каждого сигнала
    2. Проверить согласованность с режимом рынка (RegimeClusterEngine)
    3. Проверить согласованность с HTF Liquidity Map
    4. Если консенсус невозможен → ABSTAIN (не торговать)
    5. Логировать причину решения для аудита
    """
```

### Логи — ТОЛЬКО русский:

```python
logger.info("Сигнал сгенерирован", strategy="donchian_breakout",
            symbol="SOL/USDT", direction="BUY", confidence=82, rr=2.3)
logger.info("Возможность оценена", symbol="BTC/USDT", total_score=78.5,
            rank=1, regime="TRENDING_UP", impulse=1.35)
logger.warning("Конфликт стратегий разрешён", symbol="ETH/USDT",
               strategy_a="donchian_breakout", signal_a="BUY",
               strategy_b="momentum", signal_b="SELL",
               resolution="ABSTAIN", reason="противоречивые сигналы")
logger.info("Pyramiding добавлен", position_id="SOL-123",
            tier=2, additional_size_r=0.5, new_stop=104.8)
logger.warning("Сигнал отфильтрован stop hunt фильтром",
               symbol="BTC/USDT", stop_hunt_score=75, threshold=60)
```

---

## 🔗 КОМПОНЕНТНЫЕ ИНТЕГРАЦИИ

### Роль компонента в системе:

Signal Generator + OpportunityEngine + MetaClassifier — интеллектуальный слой системы.
Не просто генерирует сигналы, но и ранжирует возможности и разрешает конфликты,
чтобы Strategy Manager получал только лучшие, не противоречивые сигналы.

### Входящие зависимости:

#### 1. Market Data Layer (Фаза 6) → BAR_COMPLETED
- Trigger для всего цикла генерации сигналов
- Payload: `{symbol, timeframe, open, high, low, close, volume, bid_vol, ask_vol}`

#### 2. Indicators + Intelligence Layer (Фаза 7)
- `get_indicator(symbol, tf, name, params)` → IndicatorValue
- `get_regime(symbol)` → MarketRegime
- `get_impulse_factor(symbol, tf)` → ImpulseFactor
- `get_liquidity_map(symbol)` → LiquidityMap
- `detect_stop_hunt(symbol, bar, prev_bars, liq_map)` → Optional[StopHuntSignal]
- Event: `STOP_HUNT_DETECTED` → фильтровать сигналы по символу

#### 3. Risk Engine (Фаза 5)
- `check_trade(order)` → RiskCheckResult (перед финализацией сигнала)
- `get_adx(symbol, tf)` для DonchianBreakout условий

#### 4. Strategy Manager (Фаза 14) → запрашивает сигналы и возможности
- `get_signal(symbol, timeframe, strategy)` → Optional[TradingSignal]
- `get_top_opportunities(n=5)` → List[OpportunityScore]
- `get_resolved_signal(symbol)` → Optional[TradingSignal] (через MetaClassifier)

#### 5. Config Manager (Фаза 4) → CONFIG_UPDATED
- Hot reload всех параметров стратегий

### Исходящие зависимости:

#### 1. → Event Bus → TRADING_SIGNAL (priority: HIGH)
```json
{
  "signal_id": "uuid",
  "symbol": "SOL/USDT",
  "timeframe": "4h",
  "strategy": "donchian_breakout",
  "direction": "BUY",
  "entry_price": 105.0,
  "stop_loss": 101.5,
  "take_profit": 115.0,
  "confidence": 82,
  "regime": "TRENDING_UP",
  "impulse_factor": 1.35,
  "stop_hunt_score": 12,
  "metadata": {"adx": 32.5, "donchian_upper": 104.8, "atr": 3.5}
}
```

#### 2. → Event Bus → OPPORTUNITY_SCORED (priority: NORMAL)
```json
{
  "symbol": "SOL/USDT",
  "total_score": 78.5,
  "rank": 1,
  "confidence_component": 82,
  "regime_component": 90,
  "impulse_component": 75,
  "liquidity_component": 68,
  "rr_component": 85
}
```

#### 3. → Event Bus → CONFLICT_RESOLVED (priority: NORMAL)
```json
{
  "symbol": "ETH/USDT",
  "strategies": ["donchian_breakout", "momentum"],
  "signals": ["BUY", "SELL"],
  "resolution": "ABSTAIN",
  "reason": "противоречивые сигналы без консенсуса"
}
```

#### 4. → Event Bus → PYRAMID_SIGNAL (priority: HIGH)
```json
{
  "position_id": "SOL-123",
  "tier": 2,
  "additional_size_r": 0.5,
  "new_entry": 108.0,
  "tightened_stop": 104.8,
  "reason": "подтверждение тренда: 2-й Higher High"
}
```

#### 5. → Event Bus → SIGNAL_FILTERED (priority: NORMAL)
```json
{
  "symbol": "BTC/USDT",
  "strategy": "momentum",
  "filter": "stop_hunt",
  "stop_hunt_score": 75,
  "reason": "возможный stop hunt — вход отложен"
}
```

#### 6. → Database → таблицы trading_signals, opportunity_scores, conflict_log, pyramid_log

---

## 📐 АРХИТЕКТУРА ФАЙЛОВ

```
CRYPTOTEHNOLOG/
├── src/
│   └── signals/
│       ├── __init__.py
│       ├── generator.py                    # Главный SignalGenerator
│       ├── opportunity_engine.py           # ★ OpportunityEngine — НОВЫЙ
│       ├── meta_classifier.py              # ★ MetaClassifier — НОВЫЙ
│       ├── pyramiding.py                   # ★ PyramidingManager — НОВЫЙ
│       ├── strategies/
│       │   ├── __init__.py
│       │   ├── base.py                     # BaseStrategy abstract class
│       │   ├── donchian_breakout.py        # ★ DonchianBreakoutStrategy — НОВЫЙ
│       │   ├── momentum.py                 # MomentumStrategy (обновлён)
│       │   ├── mean_reversion.py           # MeanReversionStrategy
│       │   └── regime_adaptive.py          # ★ RegimeAdaptiveStrategy — НОВЫЙ
│       ├── filters.py                      # SignalFilters (добавлен StopHuntFilter)
│       ├── deduplicator.py                 # SignalDeduplicator (LRU + Redis)
│       ├── confidence.py                   # ConfidenceCalculator
│       ├── levels.py                       # StopLoss & TakeProfit calculator
│       └── models.py                       # TradingSignal, OpportunityScore, etc.
│
└── tests/
    ├── unit/
    │   ├── test_donchian_breakout.py        # ★ НОВЫЙ
    │   ├── test_regime_adaptive.py          # ★ НОВЫЙ
    │   ├── test_opportunity_engine.py       # ★ НОВЫЙ
    │   ├── test_meta_classifier.py          # ★ НОВЫЙ
    │   ├── test_pyramiding.py               # ★ НОВЫЙ
    │   ├── test_stop_hunt_filter.py         # ★ НОВЫЙ
    │   ├── test_momentum_strategy.py
    │   ├── test_filters.py
    │   ├── test_deduplicator.py
    │   └── test_confidence.py
    ├── integration/
    │   ├── test_signal_generator.py
    │   ├── test_opportunity_engine_integration.py  # ★ НОВЫЙ
    │   └── test_meta_classifier_integration.py     # ★ НОВЫЙ
    └── benchmarks/
        └── bench_signal_generator.py
```

---

## 📋 КОНТРАКТЫ ДАННЫХ

### TradingSignal (расширенный):

```python
from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum
import uuid


class SignalDirection(str, Enum):
    """Направление сигнала."""
    BUY  = "BUY"
    SELL = "SELL"


class SignalStatus(str, Enum):
    """Статус сигнала."""
    PENDING   = "PENDING"    # Сгенерирован, ждёт исполнения
    EXECUTED  = "EXECUTED"   # Отправлен на биржу
    FILTERED  = "FILTERED"   # Отфильтрован
    EXPIRED   = "EXPIRED"    # Истёк
    CANCELLED = "CANCELLED"  # Отменён вручную


@dataclass
class TradingSignal:
    """Торговый сигнал — полная спецификация входа."""

    signal_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.utcnow)

    # Рыночные параметры
    symbol: str = ""
    timeframe: str = ""
    strategy: str = ""          # "donchian_breakout" / "momentum" / etc.

    # Вход
    direction: SignalDirection = SignalDirection.BUY
    entry_price: Decimal = Decimal(0)
    stop_loss: Decimal = Decimal(0)
    take_profit: Decimal = Decimal(0)
    take_profit_2: Optional[Decimal] = None  # Второй TP (для частичного закрытия)

    # Качество
    confidence: int = 0          # 0–100

    # Контекст рынка (новые поля v4.4)
    regime: str = ""             # "TRENDING_UP" / "RANGING" / etc.
    impulse_factor: float = 1.0  # ATR5/ATR20 (из ImpulseAnalyzer)
    stop_hunt_score: int = 0     # 0–100 (из LiquidityIntelligence)
    adx_value: float = 0.0       # Значение ADX на момент сигнала
    atr_value: float = 0.0       # ATR на момент сигнала

    # Метаданные (все задействованные индикаторы)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Статус
    status: SignalStatus = SignalStatus.PENDING

    # Исполнение (заполняется позже)
    executed_at: Optional[datetime] = None
    execution_price: Optional[Decimal] = None

    # Итог (после закрытия)
    outcome: Optional[str] = None      # "WIN" / "LOSS" / "BREAKEVEN"
    pnl_r: Optional[Decimal] = None    # P&L в R-единицах

    def get_risk_reward_ratio(self) -> Decimal:
        """
        Рассчитать соотношение риск/прибыль.

        Для BUY: RR = (TP - entry) / (entry - SL)
        Для SELL: RR = (entry - TP) / (SL - entry)
        """
        if self.direction == SignalDirection.BUY:
            risk   = self.entry_price - self.stop_loss
            reward = self.take_profit - self.entry_price
        else:
            risk   = self.stop_loss - self.entry_price
            reward = self.entry_price - self.take_profit

        if risk <= 0:
            return Decimal(0)
        return reward / risk

    def is_valid(self) -> bool:
        """
        Проверить структурную валидность сигнала.

        Проверки:
        1. entry_price > 0
        2. Для BUY:  SL < entry < TP
        3. Для SELL: SL > entry > TP
        4. RR >= 1.5
        """
        if self.entry_price <= 0:
            return False
        if self.direction == SignalDirection.BUY:
            if not (self.stop_loss < self.entry_price < self.take_profit):
                return False
        else:
            if not (self.stop_loss > self.entry_price > self.take_profit):
                return False
        return self.get_risk_reward_ratio() >= Decimal("1.5")


@dataclass
class OpportunityScore:
    """
    Оценка торговой возможности для одного символа.

    Используется OpportunityEngine для ранжирования символов.
    Strategy Manager выбирает топ-N для торговли.
    """

    symbol: str
    total_score: float          # 0–100 (итоговый рейтинг)
    rank: int                   # Позиция в рейтинге (1 = лучшая)

    # Компоненты score (каждый 0–100)
    confidence_score: float     # Confidence лучшего сигнала
    regime_score: float         # Привлекательность режима (TRENDING > RANGING)
    impulse_score: float        # Impulse Factor нормированный
    liquidity_score: float      # Близость к ключевым уровням ликвидности
    rr_score: float             # Risk/Reward ratio нормированный

    # Лучший сигнал для этого символа
    best_signal: Optional[TradingSignal] = None
    regime: str = ""
    calculated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class PyramidTier:
    """
    Один уровень пирамидинга (масштабирования позиции).

    Tier 1: начальная позиция (100%)
    Tier 2: +50% при подтверждении (первый новый HH)
    Tier 3: +25% при подтверждении (второй новый HH, стоп перенесён)
    """

    tier_number: int            # 1, 2, 3
    position_id: str
    symbol: str
    additional_size_r: Decimal  # Дополнительный размер в R
    entry_price: Decimal        # Цена входа этого тира
    tightened_stop: Decimal     # Новый (более тесный) стоп после добавления
    trigger_reason: str         # "новый Higher High" / "подтверждение тренда"
    created_at: datetime = field(default_factory=datetime.utcnow)
```

---

## 🔧 ТРЕБОВАНИЕ 1: DonchianBreakoutStrategy (src/signals/strategies/donchian_breakout.py)

```python
"""
DonchianBreakoutStrategy — основная стратегия из v4.3.1.

Логика:
    BUY:  close > Donchian upper И ADX > 20 И +DI > -DI И volume > avg
    SELL: close < Donchian lower И ADX > 20 И -DI > +DI И volume > avg

Фильтры:
    - Режим должен быть TRENDING_UP (для BUY) или TRENDING_DOWN (для SELL)
    - Stop Hunt score < stop_hunt_threshold (не входить при возможном sweep)
    - Impulse Factor > 0.8 (не входить при консолидации)

Stop-loss: Donchian lower (для BUY) / Donchian upper (для SELL)
           Или ATR × 1.5 от входа — выбирается бо́льший (дальше от цены)

Take-profit: Donchian upper + ATR × 2 (для BUY) — проекция продолжения
             Минимальный RR: 2.0
"""

from decimal import Decimal
from typing import Optional, Dict
from datetime import datetime

from src.core.logger import get_logger
from src.signals.strategies.base import BaseStrategy
from src.signals.models import TradingSignal, SignalDirection
from src.intelligence.models import MarketRegime, RegimeType, ImpulseFactor, LiquidityMap

logger = get_logger("DonchianBreakoutStrategy")


class DonchianBreakoutStrategy(BaseStrategy):
    """
    Стратегия пробоя канала Дончиана с подтверждением ADX.

    Основана на методологии из v4.3.1 (чеклист Tier-1 Trailing):
    - Donchian Channels + ADX для определения пробоя
    - Impulse Factor для оценки силы движения
    - HTF Liquidity Map для размещения стопов
    - Stop Hunt фильтр для защиты от ложных пробоев

    Параметры (конфигурируемые):
        donchian_period: 20 баров (стандарт)
        adx_min: 20.0 (минимальный ADX для подтверждения тренда)
        volume_multiplier: 1.3 (объём должен быть 130% от среднего)
        min_confidence: 65
        min_rr: 2.0
        stop_hunt_threshold: 60 (не входить если stop hunt score > 60)
        impulse_min: 0.8 (не входить при консолидации)
    """

    STRATEGY_NAME = "donchian_breakout"

    def __init__(self, config_manager, indicator_engine, intelligence_layer):
        """
        Аргументы:
            config_manager: Параметры стратегии
            indicator_engine: Для получения Donchian, ADX, ATR
            intelligence_layer: Для RegimeClusterEngine, ImpulseAnalyzer, LiquidityIntelligence
        """
        self.config = config_manager
        self.indicators = indicator_engine
        self.intelligence = intelligence_layer

    async def generate(
        self,
        symbol: str,
        timeframe: str,
        bar: dict,
        prev_bars: list,
        context: dict,
    ) -> Optional[TradingSignal]:
        """
        Сгенерировать сигнал Donchian Breakout.

        Аргументы:
            symbol: Торговый символ
            timeframe: Таймфрейм (рекомендуется 4h или 1h)
            bar: Текущий бар {open, high, low, close, volume}
            prev_bars: Предыдущие бары для контекста
            context: {regime, impulse_factor, liquidity_map, stop_hunt_signal}

        Возвращает:
            TradingSignal или None
        """
        # ── Читать параметры ─────────────────────────────────
        donchian_period  = int(self.config.get("signals.donchian.period", 20))
        adx_min          = float(self.config.get("signals.donchian.adx_min", 20.0))
        vol_mult         = float(self.config.get("signals.donchian.volume_multiplier", 1.3))
        min_confidence   = int(self.config.get("signals.donchian.min_confidence", 65))
        min_rr           = Decimal(str(self.config.get("signals.donchian.min_rr", 2.0)))
        sh_threshold     = int(self.config.get("signals.donchian.stop_hunt_threshold", 60))
        impulse_min      = float(self.config.get("signals.donchian.impulse_min", 0.8))

        close   = Decimal(str(bar["close"]))
        volume  = float(bar["volume"])

        # ── Получить контекст рынка ───────────────────────────
        regime: MarketRegime        = context.get("regime")
        impulse: ImpulseFactor      = context.get("impulse_factor")
        liquidity_map: LiquidityMap = context.get("liquidity_map")
        stop_hunt_score: int        = context.get("stop_hunt_score", 0)

        # ── Получить индикаторы параллельно ──────────────────
        import asyncio
        donchian_task = self.indicators.get_donchian(symbol, timeframe, donchian_period)
        adx_task      = self.indicators.get_adx(symbol, timeframe)
        atr_task      = self.indicators.get_atr(symbol, timeframe, period=14)
        avg_vol_task  = self.indicators.get_avg_volume(symbol, timeframe, period=20)

        donchian, adx_result, atr, avg_vol = await asyncio.gather(
            donchian_task, adx_task, atr_task, avg_vol_task,
            return_exceptions=True,
        )

        # Проверить что все индикаторы готовы
        for name, val in [("donchian", donchian), ("adx", adx_result),
                          ("atr", atr), ("avg_vol", avg_vol)]:
            if isinstance(val, Exception) or val is None:
                logger.debug("Индикатор недоступен", indicator=name, symbol=symbol)
                return None

        donchian_upper = donchian["upper"]
        donchian_lower = donchian["lower"]
        adx_val        = adx_result["adx"]
        di_plus        = adx_result["di_plus"]
        di_minus       = adx_result["di_minus"]
        atr_val        = Decimal(str(atr))
        avg_volume     = float(avg_vol)

        # ── Базовые фильтры (общие для BUY и SELL) ───────────

        # Фильтр 1: Stop Hunt — не входить при высоком score
        if stop_hunt_score >= sh_threshold:
            logger.warning(
                "Сигнал отфильтрован stop hunt фильтром",
                symbol=symbol,
                stop_hunt_score=stop_hunt_score,
                threshold=sh_threshold,
            )
            return None

        # Фильтр 2: Impulse Factor — не входить при консолидации
        if impulse and float(impulse.ratio) < impulse_min:
            logger.debug(
                "Impulse Factor слишком низкий для входа",
                symbol=symbol,
                ratio=float(impulse.ratio),
                min_required=impulse_min,
            )
            return None

        # Фильтр 3: ADX минимум
        if adx_val < adx_min:
            logger.debug("ADX ниже минимума", symbol=symbol,
                         adx=adx_val, min_required=adx_min)
            return None

        # Фильтр 4: Объём подтверждение
        if volume < avg_volume * vol_mult:
            logger.debug("Объём недостаточен для подтверждения",
                         symbol=symbol, volume=volume,
                         required=avg_volume * vol_mult)
            return None

        # ── BUY условия ──────────────────────────────────────
        is_buy = (
            close > donchian_upper and
            di_plus > di_minus and
            (regime is None or regime.regime in (
                RegimeType.TRENDING_UP, RegimeType.VOLATILE
            ))
        )

        # ── SELL условия ─────────────────────────────────────
        is_sell = (
            close < donchian_lower and
            di_minus > di_plus and
            (regime is None or regime.regime in (
                RegimeType.TRENDING_DOWN, RegimeType.VOLATILE
            ))
        )

        if not is_buy and not is_sell:
            return None

        direction = SignalDirection.BUY if is_buy else SignalDirection.SELL

        # ── Рассчитать уровни ─────────────────────────────────
        entry_price, stop_loss, take_profit = self._calculate_levels(
            direction=direction,
            close=close,
            donchian_upper=donchian_upper,
            donchian_lower=donchian_lower,
            atr=atr_val,
            min_rr=min_rr,
            liquidity_map=liquidity_map,
        )

        if entry_price is None:
            return None

        # ── Рассчитать confidence score ───────────────────────
        confidence = self._calculate_confidence(
            direction=direction,
            adx_val=adx_val,
            di_plus=di_plus,
            di_minus=di_minus,
            volume=volume,
            avg_volume=avg_volume,
            impulse=impulse,
            regime=regime,
            stop_hunt_score=stop_hunt_score,
            rr_ratio=float((take_profit - entry_price) / (entry_price - stop_loss))
                     if direction == SignalDirection.BUY else
                     float((entry_price - take_profit) / (stop_loss - entry_price)),
        )

        if confidence < min_confidence:
            logger.debug("Confidence ниже минимума", symbol=symbol,
                         confidence=confidence, min_required=min_confidence)
            return None

        signal = TradingSignal(
            symbol=symbol,
            timeframe=timeframe,
            strategy=self.STRATEGY_NAME,
            direction=direction,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            confidence=confidence,
            regime=regime.regime.value if regime else "",
            impulse_factor=float(impulse.ratio) if impulse else 1.0,
            stop_hunt_score=stop_hunt_score,
            adx_value=adx_val,
            atr_value=float(atr_val),
            metadata={
                "donchian_upper": float(donchian_upper),
                "donchian_lower": float(donchian_lower),
                "di_plus": di_plus,
                "di_minus": di_minus,
                "volume_ratio": round(volume / avg_volume, 2),
            },
        )

        logger.info(
            "Donchian Breakout сигнал сгенерирован",
            symbol=symbol,
            direction=direction.value,
            confidence=confidence,
            rr=float(signal.get_risk_reward_ratio()),
            adx=adx_val,
        )

        return signal

    def _calculate_levels(
        self,
        direction: SignalDirection,
        close: Decimal,
        donchian_upper: Decimal,
        donchian_lower: Decimal,
        atr: Decimal,
        min_rr: Decimal,
        liquidity_map,
    ):
        """
        Рассчитать entry, stop-loss, take-profit.

        Stop-loss для BUY:
            max(donchian_lower, entry - 1.5 × ATR)
            → берём дальше от цены (больше пространства)

        Stop-loss для SELL:
            min(donchian_upper, entry + 1.5 × ATR)

        Take-profit:
            Проекция: entry ± ATR × 3 (минимум 2.0 RR)
            Корректируется если рядом HTF уровень ликвидности

        Возвращает:
            (entry_price, stop_loss, take_profit) или (None, None, None)
        """
        entry_price = close

        if direction == SignalDirection.BUY:
            # Стоп — максимально защитный (дальше от entry)
            sl_donchian = donchian_lower
            sl_atr      = entry_price - atr * Decimal("1.5")
            stop_loss   = min(sl_donchian, sl_atr)  # Берём дальше (меньше)

            # TP — проекция продолжения
            risk         = entry_price - stop_loss
            take_profit  = entry_price + risk * min_rr

            # Корректировка TP к ближайшему HTF уровню (если он ближе)
            if liquidity_map:
                for level in liquidity_map.levels:
                    lp = level.price
                    if lp > take_profit and lp < entry_price + risk * (min_rr + Decimal("1")):
                        take_profit = lp - atr * Decimal("0.2")  # Немного ниже уровня
                        break
        else:
            sl_donchian = donchian_upper
            sl_atr      = entry_price + atr * Decimal("1.5")
            stop_loss   = max(sl_donchian, sl_atr)

            risk         = stop_loss - entry_price
            take_profit  = entry_price - risk * min_rr

            if liquidity_map:
                for level in sorted(liquidity_map.levels, key=lambda x: -float(x.price)):
                    lp = level.price
                    if lp < take_profit and lp > entry_price - risk * (min_rr + Decimal("1")):
                        take_profit = lp + atr * Decimal("0.2")
                        break

        # Проверить RR
        risk = abs(entry_price - stop_loss)
        if risk <= 0:
            return None, None, None
        rr = abs(take_profit - entry_price) / risk
        if rr < min_rr:
            return None, None, None

        return entry_price, stop_loss, take_profit

    def _calculate_confidence(
        self,
        direction: SignalDirection,
        adx_val: float,
        di_plus: float,
        di_minus: float,
        volume: float,
        avg_volume: float,
        impulse,
        regime,
        stop_hunt_score: int,
        rr_ratio: float,
    ) -> int:
        """
        Рассчитать confidence score для Donchian Breakout.

        Компоненты (сумма весов = 1.0):
            1. ADX сила тренда (вес 0.25):
               ADX 20-30 → 60%, 30-40 → 80%, >40 → 100%
            2. DI разрыв (вес 0.20):
               (+DI - -DI) нормированный 0–100%
            3. Объём подтверждение (вес 0.20):
               volume / avg_volume → нормированный
            4. Impulse Factor (вес 0.15):
               ratio > 1.5 → 100%, 1.0-1.5 → 70%, <1.0 → 40%
            5. Режим рынка (вес 0.15):
               TRENDING → 100%, VOLATILE → 70%, RANGING → 20%
            6. RR ratio (вес 0.05):
               RR 2.0 → 60%, 2.5 → 80%, 3.0+ → 100%

        Штраф:
            stop_hunt_score / 100 × 15 баллов вычитается из итога
        """
        # Компонент 1: ADX
        if adx_val >= 40:
            adx_score = 100.0
        elif adx_val >= 30:
            adx_score = 60.0 + (adx_val - 30) * 2.0
        else:
            adx_score = max(0.0, (adx_val - 20) * 6.0)

        # Компонент 2: DI разрыв
        if direction == SignalDirection.BUY:
            di_gap = di_plus - di_minus
        else:
            di_gap = di_minus - di_plus
        di_score = min(100.0, max(0.0, di_gap * 4.0))

        # Компонент 3: Объём
        vol_ratio = volume / avg_volume if avg_volume > 0 else 1.0
        vol_score = min(100.0, (vol_ratio - 1.0) * 100.0)

        # Компонент 4: Impulse Factor
        if impulse:
            r = float(impulse.ratio)
            impulse_score = 100.0 if r >= 1.5 else (70.0 if r >= 1.0 else 40.0)
        else:
            impulse_score = 50.0

        # Компонент 5: Режим
        if regime:
            rt = regime.regime
            if direction == SignalDirection.BUY:
                regime_score = (100.0 if rt == RegimeType.TRENDING_UP
                                else 70.0 if rt == RegimeType.VOLATILE
                                else 20.0)
            else:
                regime_score = (100.0 if rt == RegimeType.TRENDING_DOWN
                                else 70.0 if rt == RegimeType.VOLATILE
                                else 20.0)
        else:
            regime_score = 50.0

        # Компонент 6: RR ratio
        rr_score = min(100.0, max(0.0, (rr_ratio - 1.5) * 40.0 + 40.0))

        # Взвешенная сумма
        raw = (
            adx_score    * 0.25 +
            di_score     * 0.20 +
            vol_score    * 0.20 +
            impulse_score * 0.15 +
            regime_score * 0.15 +
            rr_score     * 0.05
        )

        # Штраф за stop hunt
        penalty = (stop_hunt_score / 100.0) * 15.0
        final = max(0.0, raw - penalty)

        return int(round(final))
```

---

## 🔧 ТРЕБОВАНИЕ 2: OpportunityEngine (src/signals/opportunity_engine.py)

```python
"""
OpportunityEngine — ранжирование торговых возможностей.

Для каждого символа из торговой вселенной рассчитывает OpportunityScore
и возвращает топ-N символов для Strategy Manager.

Алгоритм (каждый компонент 0–100, веса указаны):
    confidence_score (вес 0.35) — confidence лучшего сигнала
    regime_score     (вес 0.25) — привлекательность режима рынка
    impulse_score    (вес 0.20) — Impulse Factor (ATR5/ATR20)
    liquidity_score  (вес 0.10) — расстояние до ближайшего HTF уровня
    rr_score         (вес 0.10) — RR ratio лучшего сигнала
"""

from decimal import Decimal
from typing import Dict, List, Optional
from datetime import datetime
import asyncio

from src.core.logger import get_logger
from src.signals.models import OpportunityScore, TradingSignal
from src.intelligence.models import RegimeType

logger = get_logger("OpportunityEngine")


class OpportunityEngine:
    """
    Движок скоринга и ранжирования торговых возможностей.

    Вызывается Strategy Manager после того, как все стратегии
    сгенерировали сигналы для всех символов.
    Возвращает ранжированный список — Strategy Manager торгует
    только топ-N символов (configurable, default 5).
    """

    def __init__(self, config_manager, intelligence_layer):
        """
        Аргументы:
            config_manager: Параметры (топ-N, веса компонентов)
            intelligence_layer: Для RegimeClusterEngine и ImpulseAnalyzer
        """
        self.config = config_manager
        self.intelligence = intelligence_layer

    async def score_all(
        self,
        signals_by_symbol: Dict[str, Optional[TradingSignal]],
    ) -> List[OpportunityScore]:
        """
        Оценить все символы и вернуть ранжированный список.

        Аргументы:
            signals_by_symbol: {symbol: TradingSignal или None}
                None означает — нет сигнала для этого символа

        Возвращает:
            List[OpportunityScore] отсортированный по total_score DESC
        """
        scores: List[OpportunityScore] = []

        for symbol, signal in signals_by_symbol.items():
            score = await self._score_symbol(symbol, signal)
            if score is not None:
                scores.append(score)

        # Сортировать по убыванию total_score
        scores.sort(key=lambda x: x.total_score, reverse=True)

        # Назначить ранги
        for i, score in enumerate(scores):
            score.rank = i + 1

        top_n = int(self.config.get("signals.opportunity.top_n", default=5))

        logger.info(
            "Возможности оценены и ранжированы",
            total_symbols=len(scores),
            top_n=top_n,
            top_symbol=scores[0].symbol if scores else "нет",
            top_score=scores[0].total_score if scores else 0,
        )

        return scores[:top_n]  # Только топ-N

    async def _score_symbol(
        self,
        symbol: str,
        signal: Optional[TradingSignal],
    ) -> Optional[OpportunityScore]:
        """
        Рассчитать score для одного символа.

        Символ без сигнала → confidence_score = 0,
        но может иметь ненулевые другие компоненты.
        Если итоговый score < 20 → исключить из рассмотрения.
        """
        # ── Confidence компонент ─────────────────────────────
        confidence_score = float(signal.confidence) if signal else 0.0

        # ── Regime компонент ─────────────────────────────────
        regime = self.intelligence.regime_engine.get_current_regime(symbol)
        if regime:
            regime_score_map = {
                RegimeType.TRENDING_UP:   90.0,
                RegimeType.TRENDING_DOWN: 90.0,
                RegimeType.VOLATILE:      60.0,
                RegimeType.RANGING:       30.0,
                RegimeType.QUIET:         20.0,
            }
            regime_score = regime_score_map.get(regime.regime, 50.0)
            # Учесть уверенность классификации
            regime_score *= regime.confidence
        else:
            regime_score = 40.0  # Нет данных → нейтральный

        # ── Impulse компонент ─────────────────────────────────
        impulse = self.intelligence.impulse_cache.get(symbol)
        if impulse:
            # Нормировать ratio: 0.5 → 0%, 1.0 → 50%, 1.5 → 100%
            ratio = float(impulse.ratio)
            impulse_score = min(100.0, max(0.0, (ratio - 0.5) / 1.0 * 100.0))
        else:
            impulse_score = 50.0

        # ── Liquidity компонент ────────────────────────────────
        liq_map = self.intelligence.liquidity_engine.get_liquidity_map(symbol)
        if liq_map and signal:
            entry = float(signal.entry_price)
            min_distance_pct = min(
                abs(float(level.price) - entry) / entry
                for level in liq_map.levels
            ) if liq_map.levels else 0.05
            # Чем ближе уровень ликвидности → тем выше score (есть точки разворота)
            # 0% → 100 (уровень на цене), 5% и выше → 0
            liquidity_score = max(0.0, (0.05 - min_distance_pct) / 0.05 * 100.0)
        else:
            liquidity_score = 50.0

        # ── RR компонент ──────────────────────────────────────
        if signal:
            rr = float(signal.get_risk_reward_ratio())
            # RR 1.5 → 40%, 2.0 → 60%, 3.0 → 100%
            rr_score = min(100.0, max(0.0, (rr - 1.5) / 1.5 * 100.0))
        else:
            rr_score = 0.0

        # ── Взвешенный итог ───────────────────────────────────
        total_score = (
            confidence_score * 0.35 +
            regime_score     * 0.25 +
            impulse_score    * 0.20 +
            liquidity_score  * 0.10 +
            rr_score         * 0.10
        )

        if total_score < 20.0:
            return None  # Слишком низкий score — исключить

        return OpportunityScore(
            symbol=symbol,
            total_score=round(total_score, 2),
            rank=0,  # Назначается после сортировки
            confidence_score=round(confidence_score, 1),
            regime_score=round(regime_score, 1),
            impulse_score=round(impulse_score, 1),
            liquidity_score=round(liquidity_score, 1),
            rr_score=round(rr_score, 1),
            best_signal=signal,
            regime=regime.regime.value if regime else "",
        )
```

---

## 🔧 ТРЕБОВАНИЕ 3: MetaClassifier (src/signals/meta_classifier.py)

```python
"""
MetaClassifier — разрешение конфликтов между стратегиями.

Проблема: несколько стратегий могут генерировать противоречивые сигналы
для одного символа одновременно:
    DonchianBreakout → BUY (confidence: 78)
    MomentumStrategy → SELL (confidence: 65)
    MeanReversion    → None (нет сигнала)

MetaClassifier должен:
1. Выбрать победителя если разница confidence > порога
2. Проверить согласованность с режимом рынка
3. Проверить согласованность с Impulse Factor и HTF направлением
4. ABSTAIN если консенсус невозможен
5. Полностью логировать причину решения (для аудита)

Результаты:
    WINNER(strategy, signal) — победивший сигнал
    ABSTAIN                  — не торговать (конфликт неразрешим)
"""

from typing import Dict, Optional, List, Tuple
from datetime import datetime

from src.core.logger import get_logger
from src.signals.models import TradingSignal, SignalDirection
from src.intelligence.models import RegimeType

logger = get_logger("MetaClassifier")


class ConflictResolution:
    """Результат разрешения конфликта."""
    WINNER  = "WINNER"   # Один сигнал победил
    ABSTAIN = "ABSTAIN"  # Конфликт — не торговать


class MetaClassifier:
    """
    Мета-классификатор для разрешения конфликтов стратегий.

    Алгоритм (приоритет сверху вниз):
    1. Если только один сигнал → он победитель (нет конфликта)
    2. Если все сигналы в одном направлении → winner с макс. confidence
    3. Если конфликт BUY vs SELL:
       a. Проверить разницу confidence → если > confidence_gap_threshold → winner
       b. Проверить согласованность с режимом рынка → если согласован → winner
       c. Проверить Impulse Factor направление
       d. Если ни одно не помогло → ABSTAIN
    """

    def __init__(self, config_manager, intelligence_layer):
        """
        Аргументы:
            config_manager: Параметры (confidence_gap_threshold)
            intelligence_layer: Для RegimeClusterEngine
        """
        self.config = config_manager
        self.intelligence = intelligence_layer

    async def resolve(
        self,
        symbol: str,
        signals: Dict[str, Optional[TradingSignal]],
    ) -> Tuple[str, Optional[TradingSignal], str]:
        """
        Разрешить конфликт между сигналами стратегий.

        Аргументы:
            symbol: Торговый символ
            signals: {strategy_name: TradingSignal или None}

        Возвращает:
            (resolution, winning_signal, reason)
            resolution: "WINNER" или "ABSTAIN"
            winning_signal: TradingSignal или None
            reason: Объяснение для аудита
        """
        # Отфильтровать None сигналы
        active_signals = {
            name: sig for name, sig in signals.items()
            if sig is not None
        }

        # ── Случай 1: Нет сигналов ───────────────────────────
        if not active_signals:
            return ConflictResolution.ABSTAIN, None, "нет активных сигналов"

        # ── Случай 2: Один сигнал → нет конфликта ────────────
        if len(active_signals) == 1:
            name, sig = next(iter(active_signals.items()))
            reason = f"единственный сигнал от {name}"
            logger.debug("Конфликт отсутствует", symbol=symbol, reason=reason)
            return ConflictResolution.WINNER, sig, reason

        # ── Случай 3: Все в одном направлении ────────────────
        directions = {sig.direction for sig in active_signals.values()}
        if len(directions) == 1:
            winner = max(active_signals.values(), key=lambda s: s.confidence)
            reason = (f"все {len(active_signals)} стратегии согласованы "
                      f"в направлении {winner.direction.value}")
            logger.info("Консенсус стратегий", symbol=symbol, reason=reason,
                        winner=winner.strategy, confidence=winner.confidence)
            return ConflictResolution.WINNER, winner, reason

        # ── Случай 4: Конфликт BUY vs SELL ───────────────────
        buy_signals  = {n: s for n, s in active_signals.items()
                        if s.direction == SignalDirection.BUY}
        sell_signals = {n: s for n, s in active_signals.items()
                        if s.direction == SignalDirection.SELL}

        best_buy  = max(buy_signals.values(),  key=lambda s: s.confidence) if buy_signals  else None
        best_sell = max(sell_signals.values(), key=lambda s: s.confidence) if sell_signals else None

        confidence_gap_threshold = int(self.config.get(
            "signals.meta_classifier.confidence_gap", default=20
        ))

        # Шаг 4a: Разница confidence
        if best_buy and best_sell:
            gap = abs(best_buy.confidence - best_sell.confidence)
            if gap >= confidence_gap_threshold:
                winner = best_buy if best_buy.confidence > best_sell.confidence else best_sell
                reason = (f"confidence gap {gap} >= {confidence_gap_threshold}: "
                          f"победил {winner.strategy} (confidence={winner.confidence})")
                await self._log_conflict(symbol, signals, ConflictResolution.WINNER, reason)
                return ConflictResolution.WINNER, winner, reason

        # Шаг 4b: Согласованность с режимом рынка
        regime = self.intelligence.regime_engine.get_current_regime(symbol)
        if regime:
            if regime.regime == RegimeType.TRENDING_UP and best_buy:
                reason = (f"режим TRENDING_UP поддерживает BUY "
                          f"(стратегия: {best_buy.strategy})")
                await self._log_conflict(symbol, signals, ConflictResolution.WINNER, reason)
                return ConflictResolution.WINNER, best_buy, reason

            elif regime.regime == RegimeType.TRENDING_DOWN and best_sell:
                reason = (f"режим TRENDING_DOWN поддерживает SELL "
                          f"(стратегия: {best_sell.strategy})")
                await self._log_conflict(symbol, signals, ConflictResolution.WINNER, reason)
                return ConflictResolution.WINNER, best_sell, reason

        # Шаг 4c: Impulse Factor направление
        impulse = self.intelligence.impulse_cache.get(symbol)
        if impulse and float(impulse.ratio) > 1.2:
            # Сильный импульс → доверяем направлению с большим ADX di
            if best_buy and best_sell:
                if best_buy.adx_value > 0 and best_sell.adx_value > 0:
                    # Тот у кого выше confidence при высоком impulse → победитель
                    winner = best_buy if best_buy.confidence >= best_sell.confidence else best_sell
                    reason = (f"Impulse Factor {float(impulse.ratio):.2f} > 1.2, "
                              f"победил {winner.strategy}")
                    await self._log_conflict(symbol, signals, ConflictResolution.WINNER, reason)
                    return ConflictResolution.WINNER, winner, reason

        # Шаг 4d: Консенсус невозможен → ABSTAIN
        strategies_str = ", ".join(
            f"{n}({s.direction.value},{s.confidence})"
            for n, s in active_signals.items()
        )
        reason = f"неразрешимый конфликт: {strategies_str}"
        await self._log_conflict(symbol, signals, ConflictResolution.ABSTAIN, reason)

        logger.warning(
            "Конфликт стратегий — ABSTAIN",
            symbol=symbol,
            strategies=strategies_str,
        )

        return ConflictResolution.ABSTAIN, None, reason

    async def _log_conflict(
        self,
        symbol: str,
        signals: Dict[str, Optional[TradingSignal]],
        resolution: str,
        reason: str,
    ) -> None:
        """Залогировать конфликт в БД для аудита."""
        # Сохранить в conflict_log таблицу
        pass  # Реализовать через db.execute INSERT INTO conflict_log
```

---

## 🔧 ТРЕБОВАНИЕ 4: PyramidingManager (src/signals/pyramiding.py)

```python
"""
PyramidingManager — масштабирование прибыльной позиции.

Концепция (из v4.3.1 чеклист Tier-1 Trailing):
    3 tiers с уменьшающимся размером:
    Tier 1: 100% начального R-risk (начальная позиция)
    Tier 2: 50%  начального R-risk (при подтверждении — 1-й новый HH)
    Tier 3: 25%  начального R-risk (при подтверждении — 2-й новый HH)

Условия для Tier 2:
    1. Позиция в прибыли >= 1.5R
    2. Обнаружен новый Higher High (для LONG)
    3. ADX > 25 (сильный тренд)
    4. Impulse Factor > 1.0
    5. RiskLedger подтверждает наличие свободного R-budget

Условия для Tier 3:
    1. Позиция в прибыли >= 3R
    2. Обнаружен 2-й новый Higher High
    3. Стоп перенесён выше entry (breakeven или лучше)
    4. RiskLedger подтверждает свободный R-budget

Управление риском пирамидинга:
    - Новый стоп для ВСЕЙ позиции (включая добавление) = стоп Tier 2/3
    - Стоп ТОЛЬКО поднимается (никогда не опускается)
    - Суммарный риск позиции после добавления не превышает 1.5R от начального
    - RiskLedger обновляется ОБЯЗАТЕЛЬНО после каждого добавления
"""

from decimal import Decimal
from typing import Optional, Dict
from datetime import datetime

from src.core.logger import get_logger
from src.signals.models import PyramidTier, TradingSignal, SignalDirection

logger = get_logger("PyramidingManager")


class PyramidingManager:
    """
    Менеджер пирамидинга — добавление к прибыльным позициям.

    Интегрируется с:
    - RiskEngine (Фаза 5): проверка RiskLedger перед добавлением
    - TrailingPolicy (Фаза 5): учёт новых HH из _confirmed_hh
    - ImpulseAnalyzer (Фаза 7): фильтр по Impulse Factor
    """

    # Размеры тиров (в % от начального R-risk)
    TIER_SIZES = {
        1: Decimal("1.0"),   # 100% — начальная позиция
        2: Decimal("0.5"),   # 50%
        3: Decimal("0.25"),  # 25%
    }

    # Минимальный P&L для добавления
    TIER_MIN_PNL_R = {
        2: Decimal("1.5"),  # Tier 2: позиция должна быть +1.5R
        3: Decimal("3.0"),  # Tier 3: позиция должна быть +3.0R
    }

    def __init__(self, config_manager, risk_engine, intelligence_layer, event_bus):
        """
        Аргументы:
            config_manager: Параметры пирамидинга
            risk_engine: Для проверки RiskLedger перед добавлением
            intelligence_layer: Для ImpulseAnalyzer и confirmed HH tracking
            event_bus: Для публикации PYRAMID_SIGNAL
        """
        self.config = config_manager
        self.risk_engine = risk_engine
        self.intelligence = intelligence_layer
        self.event_bus = event_bus

        # Текущий тир для каждой позиции: {position_id: current_tier}
        self._position_tiers: Dict[str, int] = {}

    async def check_pyramid_opportunity(
        self,
        position,
        market_data: dict,
    ) -> Optional[PyramidTier]:
        """
        Проверить возможность добавить к позиции (пирамидинг).

        Вызывается из SignalGenerator.on_bar_completed() для открытых позиций.

        Аргументы:
            position: Открытая позиция {position_id, symbol, side, entry_price,
                       current_stop, current_pnl_r, initial_risk_r}
            market_data: {close, high, low, atr, adx, volume}

        Возвращает:
            PyramidTier если нужно добавить, None иначе
        """
        position_id  = position.position_id
        symbol       = position.symbol
        current_tier = self._position_tiers.get(position_id, 1)

        # Максимум 3 тира
        if current_tier >= 3:
            return None

        next_tier    = current_tier + 1
        min_pnl_r    = self.TIER_MIN_PNL_R[next_tier]
        current_pnl_r = Decimal(str(position.current_pnl_r))

        # Условие 1: Достаточная прибыль
        if current_pnl_r < min_pnl_r:
            return None

        # Условие 2: Новый Higher High (для LONG) / Lower Low (для SHORT)
        adx_val = float(market_data.get("adx", 0))
        if adx_val < 25.0:
            return None

        # Получить статистику подтверждённых HH от TrailingPolicy
        confirmed_hh = getattr(
            self.risk_engine.trailing_policy,
            "_confirmed_hh", {}
        ).get(position_id, [])

        required_hh = 1 if next_tier == 2 else 2
        if len(confirmed_hh) < required_hh:
            return None

        # Условие 3: Impulse Factor > 1.0
        impulse = self.intelligence.impulse_cache.get(symbol)
        if impulse and float(impulse.ratio) < 1.0:
            return None

        # Условие 4: Для Tier 3 — стоп должен быть выше entry (breakeven+)
        if next_tier == 3:
            if position.side == "long":
                if position.current_stop <= position.entry_price:
                    return None
            else:
                if position.current_stop >= position.entry_price:
                    return None

        # Условие 5: RiskLedger — достаточно свободного R-budget
        total_r_used = await self.risk_engine.risk_ledger.get_total_risk_r()
        limits       = self.risk_engine._get_risk_limits()
        additional_r = position.initial_risk_r * self.TIER_SIZES[next_tier]

        if total_r_used + additional_r > limits.max_total_r:
            logger.debug(
                "Пирамидинг отклонён: недостаточно R-budget",
                position_id=position_id,
                total_r_used=float(total_r_used),
                additional_r=float(additional_r),
                max_r=float(limits.max_total_r),
            )
            return None

        # ── Рассчитать новый стоп ─────────────────────────────
        atr_val = Decimal(str(market_data.get("atr", 0)))
        entry_new = Decimal(str(market_data["close"]))  # Вход по текущей цене

        if position.side == "long":
            # Стоп = последний подтверждённый HH - 1.1×ATR
            if confirmed_hh:
                tightened_stop = Decimal(str(confirmed_hh[-1])) - atr_val * Decimal("1.1")
            else:
                tightened_stop = entry_new - atr_val * Decimal("1.5")
            # Стоп не ниже текущего
            tightened_stop = max(tightened_stop, position.current_stop)
        else:
            if confirmed_hh:
                tightened_stop = Decimal(str(confirmed_hh[-1])) + atr_val * Decimal("1.1")
            else:
                tightened_stop = entry_new + atr_val * Decimal("1.5")
            tightened_stop = min(tightened_stop, position.current_stop)

        # ── Обновить RiskLedger (ОБЯЗАТЕЛЬНО) ────────────────
        new_risk_r = position.current_risk_r + additional_r
        await self.risk_engine.risk_ledger.update_position_risk(
            position_id=position_id,
            old_risk_r=position.current_risk_r,
            new_risk_r=new_risk_r,
            new_stop=tightened_stop,
            trailing_state="ACTIVE",
        )

        tier = PyramidTier(
            tier_number=next_tier,
            position_id=position_id,
            symbol=symbol,
            additional_size_r=additional_r,
            entry_price=entry_new,
            tightened_stop=tightened_stop,
            trigger_reason=f"подтверждение тренда: {len(confirmed_hh)}-й Higher High",
        )

        # Обновить текущий тир
        self._position_tiers[position_id] = next_tier

        # Опубликовать событие
        await self.event_bus.publish({
            "type": "PYRAMID_SIGNAL",
            "priority": "HIGH",
            "payload": {
                "position_id": position_id,
                "tier": next_tier,
                "additional_size_r": float(additional_r),
                "new_entry": float(entry_new),
                "tightened_stop": float(tightened_stop),
                "reason": tier.trigger_reason,
            }
        })

        logger.info(
            "Пирамидинг добавлен",
            position_id=position_id,
            symbol=symbol,
            tier=next_tier,
            additional_size_r=float(additional_r),
            tightened_stop=float(tightened_stop),
            current_pnl_r=float(current_pnl_r),
        )

        return tier
```

---

## 🔧 ТРЕБОВАНИЕ 5: RegimeAdaptiveStrategy (src/signals/strategies/regime_adaptive.py)

```python
"""
RegimeAdaptiveStrategy — стратегия, адаптирующаяся к рыночному режиму.

Логика:
    TRENDING_UP/DOWN  → делегирует DonchianBreakoutStrategy
    RANGING           → делегирует MeanReversionStrategy (Bollinger + RSI)
    VOLATILE          → уменьшает размер позиции, тесные параметры
    QUIET             → ожидает пробой (squeeze detection по Bollinger)

Особенности:
    - Нет собственной entry-логики, делегирует другим стратегиям
    - Добавляет слой масштабирования: VOLATILE → position size × 0.5
    - При смене режима: закрывает противоречивые позиции (через Portfolio Governor)
    - Логирует все решения с причиной (для аудита)
"""

from src.core.logger import get_logger
from src.signals.strategies.base import BaseStrategy
from src.signals.strategies.donchian_breakout import DonchianBreakoutStrategy
from src.signals.strategies.mean_reversion import MeanReversionStrategy
from src.signals.models import TradingSignal
from src.intelligence.models import RegimeType

logger = get_logger("RegimeAdaptiveStrategy")


class RegimeAdaptiveStrategy(BaseStrategy):
    """
    Адаптивная стратегия — выбирает sub-стратегию по режиму рынка.

    Position size scaling по режиму:
        TRENDING:    scale = 1.0 (стандартный размер)
        VOLATILE:    scale = 0.5 (вдвое меньше — высокий ATR)
        RANGING:     scale = 0.7 (немного меньше — неопределённость)
        QUIET:       scale = 0.3 (ждём пробой squeeze)
    """

    STRATEGY_NAME = "regime_adaptive"

    POSITION_SCALE = {
        RegimeType.TRENDING_UP:   1.0,
        RegimeType.TRENDING_DOWN: 1.0,
        RegimeType.VOLATILE:      0.5,
        RegimeType.RANGING:       0.7,
        RegimeType.QUIET:         0.3,
    }

    def __init__(self, config_manager, indicator_engine, intelligence_layer):
        self.config         = config_manager
        self.indicators     = indicator_engine
        self.intelligence   = intelligence_layer

        # Sub-стратегии
        self._donchian    = DonchianBreakoutStrategy(config_manager, indicator_engine, intelligence_layer)
        self._mean_rev    = MeanReversionStrategy(config_manager, indicator_engine, intelligence_layer)

    async def generate(
        self,
        symbol: str,
        timeframe: str,
        bar: dict,
        prev_bars: list,
        context: dict,
    ):
        """
        Сгенерировать сигнал с учётом режима рынка.

        Делегирует в sub-стратегию, затем масштабирует position size.
        """
        regime = context.get("regime")
        if not regime:
            logger.debug("Режим рынка не определён, пропуск", symbol=symbol)
            return None

        rt = regime.regime

        # ── Выбор sub-стратегии ──────────────────────────────
        if rt in (RegimeType.TRENDING_UP, RegimeType.TRENDING_DOWN):
            signal = await self._donchian.generate(symbol, timeframe, bar, prev_bars, context)
            sub_name = "donchian_breakout"

        elif rt == RegimeType.RANGING:
            signal = await self._mean_rev.generate(symbol, timeframe, bar, prev_bars, context)
            sub_name = "mean_reversion"

        elif rt == RegimeType.VOLATILE:
            # В волатильном режиме → Donchian с ужесточёнными параметрами
            strict_context = dict(context)
            signal = await self._donchian.generate(symbol, timeframe, bar, prev_bars, strict_context)
            sub_name = "donchian_breakout(volatile)"

        elif rt == RegimeType.QUIET:
            # Squeeze: ждём выход из Bollinger squeeze
            signal = await self._check_squeeze_breakout(symbol, timeframe, bar, context)
            sub_name = "squeeze_breakout"

        else:
            return None

        if signal is None:
            return None

        # ── Масштабирование position size ─────────────────────
        scale = self.POSITION_SCALE.get(rt, 1.0)
        if scale < 1.0:
            # Уменьшить confidence (Strategy Manager учтёт это в sizing)
            original_confidence = signal.confidence
            signal.confidence   = int(signal.confidence * scale)
            signal.metadata["position_scale"] = scale
            signal.metadata["scale_reason"]   = f"режим {rt.value}"

            logger.info(
                "Position size масштабирован по режиму",
                symbol=symbol,
                regime=rt.value,
                scale=scale,
                confidence_before=original_confidence,
                confidence_after=signal.confidence,
                sub_strategy=sub_name,
            )

        signal.strategy = self.STRATEGY_NAME
        return signal

    async def _check_squeeze_breakout(
        self,
        symbol: str,
        timeframe: str,
        bar: dict,
        context: dict,
    ):
        """
        Обнаружить выход из Bollinger squeeze (QUIET режим).

        Squeeze = Bollinger bandwidth < 3% (очень тесные полосы).
        Breakout = цена выходит за верхнюю/нижнюю полосу с объёмом.
        """
        bb = await self.indicators.get_bollinger(symbol, timeframe, period=20)
        if not bb:
            return None

        bandwidth = float(bb.get("bandwidth", 5.0))
        close     = float(bar["close"])
        volume    = float(bar["volume"])

        # Squeeze подтверждён?
        if bandwidth > 3.0:
            return None  # Не squeeze, не интересно

        upper = float(bb.get("upper", 0))
        lower = float(bb.get("lower", 0))

        avg_vol = context.get("avg_volume", volume)
        vol_ratio = volume / avg_vol if avg_vol > 0 else 1.0

        # Breakout вверх
        if close > upper and vol_ratio > 1.5:
            logger.info("Squeeze breakout вверх обнаружен", symbol=symbol,
                        bandwidth=bandwidth, vol_ratio=vol_ratio)
            # Создать BUY сигнал (делегируем уровни в DonchianBreakout)
            return await self._donchian.generate(symbol, timeframe, bar,
                                                  [], context)

        # Breakout вниз
        if close < lower and vol_ratio > 1.5:
            logger.info("Squeeze breakout вниз обнаружен", symbol=symbol,
                        bandwidth=bandwidth, vol_ratio=vol_ratio)
            return await self._donchian.generate(symbol, timeframe, bar,
                                                  [], context)

        return None
```

---

## 📊 DATABASE SCHEMA (PostgreSQL)

```sql
-- Торговые сигналы
CREATE TABLE trading_signals (
    signal_id        VARCHAR(50) PRIMARY KEY,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    symbol           VARCHAR(20) NOT NULL,
    timeframe        VARCHAR(5) NOT NULL,
    strategy         VARCHAR(50) NOT NULL,
    direction        VARCHAR(4) NOT NULL,       -- BUY / SELL
    entry_price      NUMERIC(20, 8) NOT NULL,
    stop_loss        NUMERIC(20, 8) NOT NULL,
    take_profit      NUMERIC(20, 8) NOT NULL,
    confidence       INTEGER NOT NULL,
    regime           VARCHAR(20),
    impulse_factor   NUMERIC(6, 3),
    stop_hunt_score  INTEGER,
    adx_value        NUMERIC(6, 2),
    atr_value        NUMERIC(20, 8),
    metadata         JSONB,
    status           VARCHAR(20) DEFAULT 'PENDING',
    executed_at      TIMESTAMPTZ,
    execution_price  NUMERIC(20, 8),
    outcome          VARCHAR(20),               -- WIN / LOSS / BREAKEVEN
    pnl_r            NUMERIC(10, 4)
);
CREATE INDEX idx_signals_created  ON trading_signals(created_at DESC);
CREATE INDEX idx_signals_symbol   ON trading_signals(symbol, created_at DESC);
CREATE INDEX idx_signals_strategy ON trading_signals(strategy, status);
CREATE INDEX idx_signals_regime   ON trading_signals(regime, direction);

-- Opportunity scores (история ранжирования)
CREATE TABLE opportunity_scores (
    id               SERIAL PRIMARY KEY,
    symbol           VARCHAR(20) NOT NULL,
    total_score      NUMERIC(6, 2) NOT NULL,
    rank_position    INTEGER NOT NULL,
    confidence_score NUMERIC(6, 2),
    regime_score     NUMERIC(6, 2),
    impulse_score    NUMERIC(6, 2),
    liquidity_score  NUMERIC(6, 2),
    rr_score         NUMERIC(6, 2),
    regime           VARCHAR(20),
    scored_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_oppscore_symbol ON opportunity_scores(symbol, scored_at DESC);

-- Лог конфликтов MetaClassifier
CREATE TABLE conflict_log (
    id               SERIAL PRIMARY KEY,
    symbol           VARCHAR(20) NOT NULL,
    strategies       TEXT[],               -- Массив имён стратегий
    signals          TEXT[],               -- Массив направлений (BUY/SELL/None)
    confidences      INTEGER[],
    resolution       VARCHAR(20) NOT NULL, -- WINNER / ABSTAIN
    winning_strategy VARCHAR(50),
    reason           TEXT NOT NULL,
    resolved_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_conflict_symbol ON conflict_log(symbol, resolved_at DESC);

-- Лог пирамидинга
CREATE TABLE pyramid_log (
    id               SERIAL PRIMARY KEY,
    position_id      VARCHAR(50) NOT NULL,
    symbol           VARCHAR(20) NOT NULL,
    tier_number      INTEGER NOT NULL,
    additional_size_r NUMERIC(10, 4),
    entry_price      NUMERIC(20, 8),
    tightened_stop   NUMERIC(20, 8),
    trigger_reason   TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_pyramid_position ON pyramid_log(position_id, created_at DESC);
```

---

## 🚀 ПРОИЗВОДИТЕЛЬНОСТЬ

```
Операция                                     Target      Частота
──────────────────────────────────────────────────────────────────
SignalGenerator.generate_all_symbols()       <2s         каждый бар
DonchianBreakoutStrategy.generate()          <200ms      каждый бар
RegimeAdaptiveStrategy.generate()            <250ms      каждый бар
OpportunityEngine.score_all()                <500ms      каждый бар
MetaClassifier.resolve()                     <50ms       при конфликте
PyramidingManager.check_pyramid()            <100ms      каждый бар на позицию
SignalDeduplicator.is_duplicate()            <1ms        Redis LRU
persist_signal()                             background  async queue
──────────────────────────────────────────────────────────────────
```

---

## ⚠️ КРИТИЧЕСКИЕ ОГРАНИЧЕНИЯ ФАЗЫ 8

### ✅ Что реализовано:
- **DonchianBreakoutStrategy** — Donchian + ADX + Volume + Impulse + StopHunt фильтр
- **MomentumStrategy** — RSI + MACD + EMA + Volume
- **MeanReversionStrategy** — Bollinger Bands + RSI
- **RegimeAdaptiveStrategy** — делегирует по режиму, масштабирует position size
- **OpportunityEngine** — скоринг 5 компонентов, топ-N ранжирование
- **MetaClassifier** — 4-шаговое разрешение конфликтов + ABSTAIN
- **PyramidingManager** — 3 тира (100%/50%/25%), обязательное обновление RiskLedger
- **StopHuntFilter** — интегрирован в DonchianBreakout (score порог)
- Signal persistence, deduplication (LRU + Redis), all filters

### ❌ Что НЕ реализовано (future phases):
- ML-сигналы (LSTM, Reinforcement Learning) → Фаза 21
- Sentiment analysis (news, social media)
- Order flow / tape reading
- Inter-market correlation signals
- Portfolio-level signals (pair trading, delta-neutral)

---

## ACCEPTANCE CRITERIA

### Стратегии
- [ ] DonchianBreakoutStrategy: BUY/SELL по Donchian upper/lower + ADX + Volume
- [ ] Все стратегии фильтруют stop hunt score (порог из конфига)
- [ ] RegimeAdaptiveStrategy масштабирует confidence по режиму
- [ ] Все стратегии проверяют Impulse Factor перед входом

### OpportunityEngine
- [ ] Рассчитывает 5 компонентов score для каждого символа
- [ ] Возвращает топ-N (configurable) символов
- [ ] Символы с total_score < 20 исключаются

### MetaClassifier
- [ ] Шаг 1: Один сигнал → всегда победитель
- [ ] Шаг 2: Все согласованны → победитель с макс. confidence
- [ ] Шаг 3a: Confidence gap >= threshold → победитель
- [ ] Шаг 3b: Согласован с режимом рынка → победитель
- [ ] Шаг 3d: Консенсус невозможен → ABSTAIN + лог
- [ ] Все решения логируются в conflict_log

### PyramidingManager
- [ ] Tier 2 при +1.5R + 1 подтверждённый HH + ADX > 25
- [ ] Tier 3 при +3.0R + 2 подтверждённых HH + стоп выше entry
- [ ] RiskLedger обновляется ОБЯЗАТЕЛЬНО после каждого добавления
- [ ] Суммарный R-risk не превышает max_total_r

### Performance
- [ ] generate_all_symbols() < 2s (asyncio.gather)
- [ ] MetaClassifier.resolve() < 50ms
- [ ] Dedup cache hit < 1ms

---

**Version:** CRYPTOTEHNOLOG v4.4 (Фаза 8 — полная редакция)
**Dependencies:** Phases 0-7
**Next:** Phase 9 - Portfolio Governor (CapitalManager, position sizing orchestration)

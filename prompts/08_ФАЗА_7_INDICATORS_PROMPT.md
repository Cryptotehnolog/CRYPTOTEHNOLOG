# AI ПРОМТ: ФАЗА 7 - TECHNICAL INDICATORS + INTELLIGENCE LAYER (v2.0 — ПОЛНАЯ РЕДАКЦИЯ)

## КОНТЕКСТ

Вы — Senior Quantitative Developer, специализирующийся на technical analysis,
indicator mathematics, market microstructure, и high-performance numerical computing.

**Фазы 0-6 завершены.** Доступны:
- Event Bus (Rust + Python) — работает с persistence
- Control Plane (State Machine, Watchdog) — работает
- Config Manager — hot reload, GPG signatures, Vault
- Risk Engine v4.4 — R-unit, TrailingPolicy, RiskLedger, FundingManager
- Market Data Layer — WebSocket, ticks, OHLCV bars, orderbook
- Database Layer, Logging, Metrics — готовы

**Текущая задача:** Реализовать production-ready Technical Indicators library v4.4, включающую:
1. **20+ классических индикаторов** (MA, EMA, RSI, MACD, Bollinger, ATR, ADX, OBV...)
2. **RegimeClusterEngine** — определение рыночного режима (Trending/Ranging/Volatile/Quiet)
3. **ImpulseAnalyzer** — Impulse Factor ATR5/ATR20, momentum scoring
4. **LiquidityIntelligence** — HTF Liquidity Map (VWAP + H4 levels), Stop Hunt Detection
5. **MAE/MFE Tracker** — Maximum Adverse/Favorable Excursion для каждой позиции
6. **Donchian Channels** — breakout detection для стратегий
7. **Delta Divergence** — Volume Delta анализ (bid/ask imbalance)

---

## ⚠️ КРИТИЧЕСКИ ВАЖНО: РУССКИЙ ЯЗЫК

**ВСЕ** комментарии, docstrings, логи и сообщения об ошибках должны быть **НА РУССКОМ ЯЗЫКЕ**.

### Python docstrings — ТОЛЬКО русский:

```python
class IndicatorEngine:
    """
    Движок технических индикаторов v4.4.

    Особенности:
    - 20+ классических индикаторов (MA, EMA, RSI, MACD, Bollinger, ATR, ADX, OBV)
    - RegimeClusterEngine — классификация рыночного режима
    - ImpulseAnalyzer — Impulse Factor (ATR5/ATR20), momentum scoring
    - LiquidityIntelligence — HTF уровни, Stop Hunt detection
    - MAE/MFE Tracker — отслеживание экстремумов позиции
    - Donchian Channels — breakout detection
    - Delta Divergence — volume delta дивергенция
    - Инкрементальные обновления (O(1) на новый бар)
    - Векторизация через NumPy (10x–100x быстрее циклов)
    - Двухуровневый кэш (L1 in-memory + L2 Redis)
    - Multi-timeframe (1m, 5m, 15m, 1h, 4h, 1d)
    """

class RegimeClusterEngine:
    """
    Определение рыночного режима методом кластеризации.

    Режимы:
    - TRENDING_UP:   ADX > 25, +DI > -DI, цена выше EMA200
    - TRENDING_DOWN: ADX > 25, -DI > +DI, цена ниже EMA200
    - RANGING:       ADX < 20, Bollinger Bandwidth < порога
    - VOLATILE:      ATR/price > порога волатильности
    - QUIET:         ATR/price < нижнего порога, узкий диапазон

    Используется:
    - TrailingPolicy: выбор structural vs ATR trailing
    - RiskEngine: коэффициент масштабирования позиций
    - StrategyManager: разрешение/запрет стратегий по режиму
    """
```

### Логи — ТОЛЬКО русский:

```python
logger.info("Режим рынка определён", symbol="BTC/USDT", regime="TRENDING_UP",
            adx=32.5, atr_ratio=0.018)
logger.warning("Stop Hunt обнаружен", symbol="SOL/USDT", score=78,
               swept_level=102.5, recovery_candles=2)
logger.info("Impulse Factor рассчитан", symbol="ETH/USDT", impulse=1.42,
            atr5=85.0, atr20=60.0, interpretation="сильный импульс")
logger.warning("HTF уровень обновлён", symbol="BTC/USDT", level_type="H4_high",
               price=52000.0, timeframe="4h")
logger.info("MAE/MFE обновлён", position_id="SOL-123",
            mae_r=-0.8, mfe_r=3.2, current_pnl_r=2.1)
```

---

## 🔗 КОМПОНЕНТНЫЕ ИНТЕГРАЦИИ

### Роль компонента в системе:
Indicator Engine + Intelligence Layer — вычислительное ядро системы.
Не только считает классические индикаторы, но и обеспечивает:
- Контекст рынка (режим) для Risk Engine и TrailingPolicy
- Обнаружение структурных уровней и stop hunt для умного трейлинга
- Impulse Factor для масштабирования трейлинга
- MAE/MFE для performance attribution (Фаза 15)

### Входящие зависимости:

#### 1. Market Data Layer (Фаза 6) → BAR_COMPLETED
- Payload: `{symbol, timeframe, open, high, low, close, volume, bid_volume, ask_volume, timestamp}`
- Действие: инкрементальное обновление всех индикаторов + Impulse + Regime
- Критичность: HIGH

#### 2. Market Data Layer (Фаза 6) → TICK_RECEIVED
- Payload: `{symbol, price, bid_size, ask_size, timestamp}`
- Действие: обновление Delta Divergence, MAE/MFE в реальном времени
- Критичность: MEDIUM

#### 3. Strategy Manager (Фаза 14) → запросы индикаторов
- `get_indicator(symbol, timeframe, name, params) → IndicatorValue`
- `get_regime(symbol) → MarketRegime`
- `get_impulse_factor(symbol, timeframe) → ImpulseFactor`
- `get_liquidity_levels(symbol) → LiquidityMap`
- Timeout: 100ms

#### 4. Risk Engine (Фаза 5) → запрашивает ADX + ATR для TrailingPolicy
- `get_adx(symbol, timeframe) → float`
- `get_atr(symbol, timeframe, period) → Decimal`
- `get_confirmed_hh_count(symbol) → int`
- Timeout: 20ms (вызывается на каждом баре)

#### 5. Portfolio Governor (Фаза 9) → запрашивает MAE/MFE
- `get_mae_mfe(position_id) → MAEMFERecord`
- Используется для performance attribution

#### 6. Config Manager (Фаза 4) → CONFIG_UPDATED
- Hot reload параметров (ADX_THRESHOLD, ATR periods, Regime thresholds)

### Исходящие зависимости:

#### 1. → Event Bus → INDICATOR_UPDATED (priority: NORMAL)
```json
{
  "symbol": "BTC/USDT",
  "timeframe": "5m",
  "indicator": "RSI",
  "value": 65.5,
  "timestamp": "2025-01-01T00:00:00Z"
}
```

#### 2. → Event Bus → INDICATOR_SIGNAL (priority: HIGH)
```json
{
  "symbol": "BTC/USDT",
  "indicator": "RSI",
  "signal": "oversold",
  "value": 27.3,
  "timeframe": "1h"
}
```

#### 3. → Event Bus → REGIME_CHANGED (priority: HIGH)
```json
{
  "symbol": "BTC/USDT",
  "old_regime": "RANGING",
  "new_regime": "TRENDING_UP",
  "adx": 28.5,
  "atr_ratio": 0.019,
  "confidence": 0.82
}
```

#### 4. → Event Bus → STOP_HUNT_DETECTED (priority: HIGH)
```json
{
  "symbol": "SOL/USDT",
  "score": 78,
  "swept_level": 102.5,
  "direction": "long_sweep",
  "recovery_candles": 2,
  "action_recommendation": "hold_position"
}
```

#### 5. → Event Bus → HTF_LEVEL_UPDATED (priority: NORMAL)
```json
{
  "symbol": "BTC/USDT",
  "level_type": "H4_high",
  "price": 52000.0,
  "timeframe": "4h",
  "strength": 3
}
```

#### 6. → Database → таблицы indicator_values, regime_history,
                       stop_hunt_events, htf_levels, mae_mfe_records

---

## 📐 АРХИТЕКТУРА ФАЙЛОВ

```
CRYPTOTEHNOLOG/
├── src/
│   ├── indicators/
│   │   ├── __init__.py
│   │   ├── engine.py                         # Главный IndicatorEngine
│   │   ├── library.py                        # Классические индикаторы (static methods)
│   │   ├── incremental.py                    # IncrementalEMA, IncrementalRSI, IncrementalATR
│   │   ├── cache.py                          # IndicatorCache (L1 in-memory + L2 Redis)
│   │   ├── price_windows.py                  # PriceWindowManager
│   │   ├── signals.py                        # SignalDetector (crosses, thresholds)
│   │   └── models.py                         # IndicatorValue, MarketRegime, etc.
│   │
│   └── intelligence/                         # ★ НОВЫЙ СЛОЙ v4.4
│       ├── __init__.py
│       ├── regime_cluster_engine.py          # ★ RegimeClusterEngine
│       ├── impulse_analyzer.py               # ★ ImpulseAnalyzer
│       ├── liquidity_intelligence.py         # ★ LiquidityIntelligence
│       ├── mae_mfe_tracker.py                # ★ MAE/MFE Tracker
│       └── models.py                         # MarketRegime, ImpulseFactor, LiquidityMap, MAEMFERecord
│
└── tests/
    ├── unit/
    │   ├── test_rsi.py
    │   ├── test_macd.py
    │   ├── test_bollinger.py
    │   ├── test_donchian.py                  # ★ НОВЫЙ
    │   ├── test_incremental.py
    │   ├── test_cache.py
    │   ├── test_regime_cluster.py            # ★ НОВЫЙ
    │   ├── test_impulse_analyzer.py          # ★ НОВЫЙ
    │   ├── test_liquidity_intelligence.py    # ★ НОВЫЙ
    │   └── test_mae_mfe_tracker.py           # ★ НОВЫЙ
    ├── integration/
    │   ├── test_indicator_engine.py
    │   ├── test_regime_detection.py          # ★ НОВЫЙ
    │   └── test_stop_hunt_detection.py       # ★ НОВЫЙ
    └── benchmarks/
        └── bench_indicators.py
```

---

## 📋 КОНТРАКТЫ ДАННЫХ

### IndicatorValue (базовый, без изменений):

```python
@dataclass
class IndicatorValue:
    """Значение технического индикатора."""

    symbol: str
    timeframe: str
    indicator_name: str
    params: Dict[str, Any]

    value: Optional[Decimal]
    timestamp: datetime

    is_valid: bool
    warming_bars_left: int
    metadata: Dict[str, Any]
```

### MarketRegime (НОВЫЙ):

```python
from enum import Enum
from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime

class RegimeType(Enum):
    """Тип рыночного режима."""
    TRENDING_UP   = "TRENDING_UP"    # Сильный восходящий тренд
    TRENDING_DOWN = "TRENDING_DOWN"  # Сильный нисходящий тренд
    RANGING       = "RANGING"        # Боковое движение (низкий ADX)
    VOLATILE      = "VOLATILE"       # Высокая волатильность (ATR/price выше нормы)
    QUIET         = "QUIET"          # Низкая волатильность (tight range, squeeze)


@dataclass
class MarketRegime:
    """
    Результат классификации рыночного режима.

    Используется:
    - TrailingPolicy: TRENDING → структурный trailing, RANGING → ATR trailing
    - RiskEngine: VOLATILE → уменьшить position size
    - StrategyManager: разрешить/запретить стратегии по режиму
    """

    symbol: str
    timeframe: str
    regime: RegimeType

    # Метрики для классификации
    adx: float             # Значение ADX (0–100)
    atr_ratio: float       # ATR / price (нормированная волатильность)
    bb_bandwidth: float    # Bollinger Bandwidth (squeeze detection)
    di_plus: float         # +DI компонент ADX
    di_minus: float        # -DI компонент ADX
    price_vs_ema200: float # (price - EMA200) / EMA200 (позиция относительно тренда)

    confidence: float      # 0.0–1.0 (уверенность классификации)
    detected_at: datetime
    prev_regime: Optional[RegimeType] = None  # Предыдущий режим (для REGIME_CHANGED event)
```

### ImpulseFactor (НОВЫЙ):

```python
@dataclass
class ImpulseFactor:
    """
    Impulse Factor — соотношение краткосрочной и долгосрочной волатильности.

    Формула: ATR(5) / ATR(20)

    Интерпретация:
    - > 1.5:  Сильный импульс (увеличить trailing агрессивность)
    - 1.0–1.5: Нормальное движение
    - < 0.7:  Слабое движение / консолидация (ослабить trailing)

    Применение в TrailingPolicy:
        trail_mult_adjusted = trail_mult_base × impulse_factor.adjustment
    """

    symbol: str
    timeframe: str

    atr5: Decimal     # ATR за 5 баров
    atr20: Decimal    # ATR за 20 баров
    ratio: Decimal    # ATR5 / ATR20

    # Скорректированный мультипликатор для TrailingPolicy
    adjustment: Decimal   # Как множитель trail_mult: <1 → tight, >1 → loose

    interpretation: str   # "сильный импульс" / "нормальное движение" / "консолидация"
    calculated_at: datetime
```

### LiquidityMap (НОВЫЙ):

```python
@dataclass
class LiquidityLevel:
    """Один структурный уровень ликвидности."""

    price: Decimal
    level_type: str     # "H4_high", "H4_low", "daily_high", "daily_low",
                        # "vwap", "prev_day_high", "prev_week_high"
    timeframe: str      # "4h", "1d", "1w"
    strength: int       # 1–5 (сколько раз уровень тестировался)
    last_tested: Optional[datetime]


@dataclass
class LiquidityMap:
    """
    HTF Liquidity Map — карта структурных уровней ликвидности.

    Содержит:
    - VWAP (Volume Weighted Average Price) сессии
    - H4 highs/lows (4-часовые экстремумы)
    - Дневные/недельные high/low
    - Предыдущий день/неделя open/close

    Используется:
    - TrailingPolicy: не ставить стоп за значимый уровень
    - LiquidityIntelligence: определять Stop Hunt зоны
    - Signal Generator: входы вблизи ключевых уровней
    """

    symbol: str
    levels: List[LiquidityLevel]
    vwap: Decimal              # Текущий VWAP (daily)
    session_high: Decimal
    session_low: Decimal
    updated_at: datetime


@dataclass
class StopHuntSignal:
    """
    Сигнал обнаружения Stop Hunt.

    Stop Hunt = резкий пробой уровня ликвидности с быстрым возвратом.
    Паттерн: свеча пробивает high/low → сразу разворот → закрытие внутри диапазона.

    Score 0–100:
    - 0–30:  Слабый сигнал (обычное движение)
    - 30–60: Умеренный (возможный stop hunt)
    - 60–80: Сильный (вероятный stop hunt)
    - 80–100: Очень сильный (классический stop hunt паттерн)
    """

    symbol: str
    score: int                  # 0–100
    swept_level: Decimal        # Уровень который был пробит
    direction: str              # "long_sweep" (пробой снизу) / "short_sweep" (пробой сверху)
    penetration_percent: float  # На сколько % пробил уровень
    recovery_candles: int       # За сколько баров вернулся
    volume_spike: float         # Аномальный объём (ratio к среднему)
    action_recommendation: str  # "hold_position" / "add_to_position" / "ignore"
    detected_at: datetime
```

### MAEMFERecord (НОВЫЙ):

```python
@dataclass
class MAEMFERecord:
    """
    Maximum Adverse Excursion / Maximum Favorable Excursion.

    MAE = максимальное движение ПРОТИВ позиции (в R-единицах)
    MFE = максимальное движение В ПОЛЬЗУ позиции (в R-единицах)

    Применение:
    - Performance Attribution (Фаза 15): оценка качества входа/выхода
    - Оптимизация стопов: если MAE/MFE ratio хорошее — стратегия работает
    - TrailingPolicy: понимать "нормальную" глубину отката
    """

    position_id: str
    symbol: str
    strategy_id: str

    entry_price: Decimal
    entry_time: datetime
    initial_stop: Decimal

    # Текущие экстремумы
    mae_price: Decimal      # Худшая цена для позиции
    mfe_price: Decimal      # Лучшая цена для позиции
    mae_r: Decimal          # MAE в R-единицах (отрицательное)
    mfe_r: Decimal          # MFE в R-единицах (положительное)

    # Текущее состояние
    current_price: Decimal
    current_pnl_r: Decimal

    # Метаданные
    updated_at: datetime
    closed_at: Optional[datetime] = None
    exit_reason: Optional[str] = None       # trailing/hard_stop/take_profit/emergency
    final_pnl_r: Optional[Decimal] = None
```

---

## 🔧 ТРЕБОВАНИЕ 1: Классические индикаторы (src/indicators/library.py)

```python
"""
Библиотека технических индикаторов — статические методы, NumPy векторизация.

Все методы:
- Принимают np.ndarray (не Decimal — для скорости)
- Возвращают Decimal только на выходе
- Защита от division by zero
- Русские docstrings
"""
import numpy as np
from decimal import Decimal
from typing import Optional, Dict


class Indicators:
    """
    Библиотека классических технических индикаторов.

    Все вычисления векторизованы через NumPy.
    Входные данные: np.ndarray (float64).
    Выходные данные: Decimal (для точности в торговых решениях).
    """

    # ═══════════════════════════════════════════
    # MOVING AVERAGES
    # ═══════════════════════════════════════════

    @staticmethod
    def sma(prices: np.ndarray, period: int) -> Decimal:
        """
        Simple Moving Average (простое скользящее среднее).

        Формула: SMA = Sum(prices[-period:]) / period

        Аргументы:
            prices: Массив цен закрытия
            period: Период усреднения

        Возвращает:
            SMA за последний период или Decimal(0) если мало данных

        Warming period: period баров
        """
        if len(prices) < period:
            return Decimal(0)
        return Decimal(str(round(float(np.mean(prices[-period:])), 8)))

    @staticmethod
    def ema(prices: np.ndarray, period: int) -> Decimal:
        """
        Exponential Moving Average (экспоненциальное скользящее среднее).

        Формула:
            multiplier = 2 / (period + 1)
            EMA_t = price_t × multiplier + EMA_{t-1} × (1 - multiplier)

        Аргументы:
            prices: Массив цен (минимум period * 2 для стабилизации)
            period: Период EMA

        Возвращает:
            EMA последнего бара

        Warming period: period * 2 баров (для стабилизации)
        """
        if len(prices) < period:
            return Decimal(0)
        k = 2.0 / (period + 1)
        ema_val = float(np.mean(prices[:period]))  # Seed: SMA первых period баров
        for price in prices[period:]:
            ema_val = float(price) * k + ema_val * (1 - k)
        return Decimal(str(round(ema_val, 8)))

    @staticmethod
    def ema_series(prices: np.ndarray, period: int) -> np.ndarray:
        """
        EMA как серия значений (для MACD и ADX).

        Аргументы:
            prices: Массив цен
            period: Период EMA

        Возвращает:
            np.ndarray — EMA для каждого бара начиная с period-го
        """
        k = 2.0 / (period + 1)
        result = np.zeros(len(prices))
        result[period - 1] = np.mean(prices[:period])  # Seed
        for i in range(period, len(prices)):
            result[i] = prices[i] * k + result[i - 1] * (1 - k)
        return result

    # ═══════════════════════════════════════════
    # MOMENTUM INDICATORS
    # ═══════════════════════════════════════════

    @staticmethod
    def rsi(prices: np.ndarray, period: int = 14) -> Decimal:
        """
        Relative Strength Index (индекс относительной силы).

        Формула:
            deltas = diff(prices)
            gains = where(deltas > 0, deltas, 0)
            losses = where(deltas < 0, abs(deltas), 0)
            avg_gain = EMA(gains, period)
            avg_loss = EMA(losses, period)
            RS = avg_gain / avg_loss
            RSI = 100 − (100 / (1 + RS))

        Диапазон: 0–100
        Сигналы: < 30 oversold, > 70 overbought

        Аргументы:
            prices: Массив цен закрытия (минимум period + 1)
            period: Период RSI (default: 14)

        Возвращает:
            RSI 0–100

        Warming period: period + 1 баров
        """
        if len(prices) < period + 1:
            return Decimal(0)

        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0.0)
        losses = np.where(deltas < 0, -deltas, 0.0)

        avg_gain = float(np.mean(gains[-period:]))
        avg_loss = float(np.mean(losses[-period:]))

        # Защита от division by zero
        if avg_loss == 0:
            return Decimal("100") if avg_gain > 0 else Decimal("50")

        rs = avg_gain / avg_loss
        rsi_val = 100.0 - (100.0 / (1.0 + rs))
        return Decimal(str(round(rsi_val, 2)))

    @staticmethod
    def macd(
        prices: np.ndarray,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9,
    ) -> Dict[str, Decimal]:
        """
        Moving Average Convergence Divergence.

        Формула:
            MACD Line   = EMA(fast) − EMA(slow)
            Signal Line = EMA(MACD Line, signal)
            Histogram   = MACD Line − Signal Line

        Аргументы:
            prices: Массив цен закрытия
            fast: Быстрый период EMA (default: 12)
            slow: Медленный период EMA (default: 26)
            signal: Период signal line (default: 9)

        Возвращает:
            {"macd": Decimal, "signal": Decimal, "histogram": Decimal}

        Сигналы:
            - MACD crosses above Signal → bullish
            - MACD crosses below Signal → bearish

        Warming period: slow + signal баров
        """
        if len(prices) < slow + signal:
            return {"macd": Decimal(0), "signal": Decimal(0), "histogram": Decimal(0)}

        ema_fast = Indicators.ema_series(prices, fast)
        ema_slow = Indicators.ema_series(prices, slow)

        macd_line = ema_fast - ema_slow
        # Signal line = EMA(macd_line, signal) — только с slow-го бара
        valid_macd = macd_line[slow - 1:]
        if len(valid_macd) < signal:
            return {"macd": Decimal(0), "signal": Decimal(0), "histogram": Decimal(0)}

        signal_series = Indicators.ema_series(valid_macd, signal)
        macd_val = macd_line[-1]
        signal_val = signal_series[-1]
        histogram_val = macd_val - signal_val

        return {
            "macd": Decimal(str(round(macd_val, 8))),
            "signal": Decimal(str(round(signal_val, 8))),
            "histogram": Decimal(str(round(histogram_val, 8))),
        }

    # ═══════════════════════════════════════════
    # VOLATILITY INDICATORS
    # ═══════════════════════════════════════════

    @staticmethod
    def bollinger_bands(
        prices: np.ndarray,
        period: int = 20,
        std_dev: float = 2.0,
    ) -> Dict[str, Decimal]:
        """
        Bollinger Bands (полосы Боллинджера).

        Формула:
            Middle  = SMA(prices, period)
            Upper   = Middle + (StdDev × std_dev)
            Lower   = Middle − (StdDev × std_dev)
            %B      = (price − Lower) / (Upper − Lower)
            BW      = (Upper − Lower) / Middle × 100

        Аргументы:
            prices: Массив цен закрытия
            period: Период SMA (default: 20)
            std_dev: Количество стандартных отклонений (default: 2.0)

        Возвращает:
            {"upper": Decimal, "middle": Decimal, "lower": Decimal,
             "bandwidth": Decimal, "percent_b": Decimal}

        Сигналы:
            - price > upper → overbought (потенциальный разворот)
            - price < lower → oversold (потенциальный разворот)
            - bandwidth < 5% → squeeze (ожидай breakout)

        Warming period: period баров
        """
        if len(prices) < period:
            return {k: Decimal(0) for k in ("upper", "middle", "lower", "bandwidth", "percent_b")}

        window = prices[-period:]
        middle = float(np.mean(window))
        std = float(np.std(window, ddof=1))  # ddof=1 — выборочное СКО

        upper = middle + std_dev * std
        lower = middle - std_dev * std
        bandwidth = (upper - lower) / middle * 100 if middle != 0 else 0
        current = float(prices[-1])
        percent_b = (current - lower) / (upper - lower) if (upper - lower) != 0 else 0.5

        return {
            "upper": Decimal(str(round(upper, 8))),
            "middle": Decimal(str(round(middle, 8))),
            "lower": Decimal(str(round(lower, 8))),
            "bandwidth": Decimal(str(round(bandwidth, 4))),
            "percent_b": Decimal(str(round(percent_b, 4))),
        }

    @staticmethod
    def atr(
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
        period: int = 14,
    ) -> Decimal:
        """
        Average True Range (средний истинный диапазон).

        Формула:
            TR = max(high − low,
                     abs(high − prev_close),
                     abs(low − prev_close))
            ATR = EMA(TR, period)

        Аргументы:
            high: Массив максимумов
            low: Массив минимумов
            close: Массив цен закрытия
            period: Период ATR (default: 14)

        Возвращает:
            ATR последнего бара

        Применение:
            - Масштаб TrailingPolicy (trail_mult × ATR)
            - ImpulseAnalyzer (ATR5 / ATR20)
            - RegimeClusterEngine (ATR ratio для VOLATILE режима)

        Warming period: period + 1 баров
        """
        if len(close) < period + 1:
            return Decimal(0)

        prev_close = close[:-1]
        curr_high = high[1:]
        curr_low = low[1:]

        tr = np.maximum(
            curr_high - curr_low,
            np.maximum(
                np.abs(curr_high - prev_close),
                np.abs(curr_low - prev_close),
            )
        )

        # EMA ATR
        atr_series = Indicators.ema_series(tr, period)
        return Decimal(str(round(float(atr_series[-1]), 8)))

    @staticmethod
    def atr_series_full(
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
        period: int = 14,
    ) -> np.ndarray:
        """
        ATR как полная серия (нужна для ImpulseAnalyzer ATR5/ATR20).

        Возвращает np.ndarray длиной len(close)-1.
        """
        if len(close) < period + 1:
            return np.zeros(len(close))
        prev_close = close[:-1]
        curr_high = high[1:]
        curr_low = low[1:]
        tr = np.maximum(
            curr_high - curr_low,
            np.maximum(np.abs(curr_high - prev_close), np.abs(curr_low - prev_close))
        )
        return Indicators.ema_series(tr, period)

    # ═══════════════════════════════════════════
    # TREND INDICATORS
    # ═══════════════════════════════════════════

    @staticmethod
    def adx(
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
        period: int = 14,
    ) -> Dict[str, float]:
        """
        Average Directional Index (индекс среднего направления).

        Формула:
            +DM = max(high[i] − high[i-1], 0) если > abs(low[i] − low[i-1])
            −DM = max(low[i-1] − low[i], 0) если > abs(high[i] − high[i-1])
            +DI = EMA(+DM / ATR, period) × 100
            −DI = EMA(−DM / ATR, period) × 100
            DX  = abs(+DI − −DI) / (+DI + −DI) × 100
            ADX = EMA(DX, period)

        Аргументы:
            high, low, close: OHLCV массивы
            period: Период (default: 14)

        Возвращает:
            {"adx": float, "di_plus": float, "di_minus": float}

        Интерпретация:
            - ADX < 20: слабый тренд / боковик (RANGING режим)
            - ADX 20–25: формирующийся тренд
            - ADX 25–40: умеренный тренд
            - ADX > 40: сильный тренд

        ❗ Используется TrailingPolicy для активации structural trailing
           (ADX > 18 + >= 2 подтверждённых Higher High)

        Warming period: period × 2 баров
        """
        if len(close) < period * 2:
            return {"adx": 0.0, "di_plus": 0.0, "di_minus": 0.0}

        # TR
        prev_close = close[:-1]
        curr_high = high[1:]
        curr_low = low[1:]
        tr = np.maximum(
            curr_high - curr_low,
            np.maximum(np.abs(curr_high - prev_close), np.abs(curr_low - prev_close))
        )

        # +DM, -DM
        up_move = np.diff(high)
        down_move = -np.diff(low)
        dm_plus = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
        dm_minus = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

        # Smoothed
        tr_smooth = Indicators.ema_series(tr, period)
        dm_plus_smooth = Indicators.ema_series(dm_plus, period)
        dm_minus_smooth = Indicators.ema_series(dm_minus, period)

        # DI
        di_plus = np.where(tr_smooth > 0, dm_plus_smooth / tr_smooth * 100, 0.0)
        di_minus = np.where(tr_smooth > 0, dm_minus_smooth / tr_smooth * 100, 0.0)

        # DX
        di_sum = di_plus + di_minus
        dx = np.where(di_sum > 0, np.abs(di_plus - di_minus) / di_sum * 100, 0.0)

        # ADX
        adx_series = Indicators.ema_series(dx[period - 1:], period)
        adx_val = float(adx_series[-1]) if len(adx_series) > 0 else 0.0

        return {
            "adx": round(adx_val, 2),
            "di_plus": round(float(di_plus[-1]), 2),
            "di_minus": round(float(di_minus[-1]), 2),
        }

    @staticmethod
    def donchian_channels(
        high: np.ndarray,
        low: np.ndarray,
        period: int = 20,
    ) -> Dict[str, Decimal]:
        """
        Donchian Channels (каналы Дончиана).

        Формула:
            Upper = max(high[-period:])
            Lower = min(low[-period:])
            Middle = (Upper + Lower) / 2

        Аргументы:
            high: Массив максимумов
            low: Массив минимумов
            period: Период (default: 20)

        Возвращает:
            {"upper": Decimal, "middle": Decimal, "lower": Decimal,
             "range_percent": Decimal}

        Сигналы (Donchian Breakout Strategy):
            - close > upper → long breakout сигнал
            - close < lower → short breakout сигнал
            - Используется как основа ADX + Donchian стратегии из v4.3.1

        Warming period: period баров
        """
        if len(high) < period or len(low) < period:
            return {k: Decimal(0) for k in ("upper", "middle", "lower", "range_percent")}

        upper_val = float(np.max(high[-period:]))
        lower_val = float(np.min(low[-period:]))
        middle_val = (upper_val + lower_val) / 2
        range_pct = (upper_val - lower_val) / middle_val * 100 if middle_val != 0 else 0

        return {
            "upper": Decimal(str(round(upper_val, 8))),
            "middle": Decimal(str(round(middle_val, 8))),
            "lower": Decimal(str(round(lower_val, 8))),
            "range_percent": Decimal(str(round(range_pct, 4))),
        }

    # ═══════════════════════════════════════════
    # VOLUME INDICATORS
    # ═══════════════════════════════════════════

    @staticmethod
    def obv(close: np.ndarray, volume: np.ndarray) -> np.ndarray:
        """
        On-Balance Volume (балансовый объём).

        Формула:
            if close[i] > close[i-1]: OBV += volume[i]
            if close[i] < close[i-1]: OBV -= volume[i]
            if close[i] == close[i-1]: OBV unchanged

        Аргументы:
            close: Массив цен закрытия
            volume: Массив объёмов

        Возвращает:
            np.ndarray — OBV для каждого бара

        Применение:
            - Подтверждение тренда (OBV растёт вместе с ценой → здоровый тренд)
            - Divergence: цена растёт, OBV падает → слабость движения

        Warming period: 1 бар
        """
        direction = np.sign(np.diff(close))
        obv_arr = np.zeros(len(close))
        for i in range(1, len(close)):
            obv_arr[i] = obv_arr[i - 1] + direction[i - 1] * volume[i]
        return obv_arr

    @staticmethod
    def vwap(
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
        volume: np.ndarray,
    ) -> Decimal:
        """
        Volume Weighted Average Price (средневзвешенная цена по объёму).

        Формула:
            Typical Price = (high + low + close) / 3
            VWAP = Sum(Typical Price × Volume) / Sum(Volume)

        Аргументы:
            high, low, close: Ценовые массивы
            volume: Массив объёмов

        Возвращает:
            VWAP — средневзвешенная цена

        Применение:
            - HTF Liquidity Map (дневной VWAP — ключевой уровень)
            - Определение позиции цены (выше/ниже VWAP)
            - Funding rate arbitrage (институциональные уровни)

        Warming period: 1 бар
        """
        if len(volume) == 0 or float(np.sum(volume)) == 0:
            return Decimal(0)
        typical_price = (high + low + close) / 3.0
        vwap_val = float(np.sum(typical_price * volume) / np.sum(volume))
        return Decimal(str(round(vwap_val, 8)))

    @staticmethod
    def delta_divergence(
        bid_volume: np.ndarray,
        ask_volume: np.ndarray,
        close: np.ndarray,
        period: int = 14,
    ) -> Dict[str, Decimal]:
        """
        Delta Divergence — дивергенция объёмного дельта.

        Формула:
            Delta[i] = ask_volume[i] − bid_volume[i]  (положительный → покупатели доминируют)
            Cumulative Delta = Sum(Delta)
            Divergence = цена растёт но дельта падает → слабость тренда

        Аргументы:
            bid_volume: Объём на стороне продавцов (bid)
            ask_volume: Объём на стороне покупателей (ask)
            close: Цены закрытия
            period: Период усреднения

        Возвращает:
            {"delta": Decimal,           — текущая дельта (>0 бычий, <0 медвежий)
             "cumulative_delta": Decimal, — накопленная дельта
             "divergence_score": Decimal} — 0–100 сила дивергенции

        Применение:
            - Подтверждение/опровержение ценового движения
            - Раннее предупреждение о развороте

        Warming period: period баров
        """
        if len(bid_volume) < period or len(ask_volume) < period:
            return {"delta": Decimal(0), "cumulative_delta": Decimal(0), "divergence_score": Decimal(0)}

        delta = ask_volume.astype(float) - bid_volume.astype(float)
        cumulative = float(np.sum(delta))

        # Дивергенция: корреляция между delta и ценовым движением
        price_changes = np.diff(close[-period:])
        delta_changes = delta[-period + 1:]
        if len(price_changes) >= 2 and len(delta_changes) >= 2:
            corr = np.corrcoef(price_changes, delta_changes)[0, 1]
            # corr = 1 → нет дивергенции, corr < 0 → дивергенция
            divergence = max(0.0, (1.0 - corr) / 2.0 * 100)
        else:
            divergence = 0.0

        return {
            "delta": Decimal(str(round(float(delta[-1]), 2))),
            "cumulative_delta": Decimal(str(round(cumulative, 2))),
            "divergence_score": Decimal(str(round(divergence, 2))),
        }
```

---

## 🔧 ТРЕБОВАНИЕ 2: RegimeClusterEngine (src/intelligence/regime_cluster_engine.py)

```python
"""
RegimeClusterEngine — классификация рыночного режима методом порогов.

Определяет один из 5 режимов на основе ADX, ATR ratio, Bollinger Bandwidth.
Публикует REGIME_CHANGED при смене режима.

Критически важен для:
- TrailingPolicy: TRENDING → structural trailing, RANGING → ATR trailing
- RiskEngine: VOLATILE → position size × 0.5
- StrategyManager: разрешить/запретить стратегии по режиму
"""

from decimal import Decimal
from typing import Optional, Dict
from datetime import datetime
import asyncio

from src.core.logger import get_logger
from src.intelligence.models import MarketRegime, RegimeType
from src.indicators.library import Indicators

logger = get_logger("RegimeClusterEngine")


class RegimeClusterEngine:
    """
    Движок классификации рыночного режима.

    Алгоритм классификации (приоритет сверху вниз):
    1. VOLATILE:      ATR/price > volatile_threshold (экстремальная волатильность)
    2. TRENDING_UP:   ADX > adx_threshold И +DI > -DI И price > EMA200
    3. TRENDING_DOWN: ADX > adx_threshold И -DI > +DI И price < EMA200
    4. QUIET:         ATR/price < quiet_threshold И BB bandwidth < bb_squeeze
    5. RANGING:       все остальные случаи (ADX < adx_threshold)

    Пороговые значения (конфигурируемые):
        adx_threshold = 25       (граница trending/ranging)
        volatile_threshold = 0.03 (3% ATR/price = очень волатильно)
        quiet_threshold = 0.005  (0.5% ATR/price = тихий рынок)
        bb_squeeze = 3.0         (bandwidth % — squeeze порог)
    """

    def __init__(self, config_manager, event_bus):
        """
        Аргументы:
            config_manager: Для чтения порогов классификации
            event_bus: Для публикации REGIME_CHANGED
        """
        self.config = config_manager
        self.event_bus = event_bus

        # Текущие режимы: {symbol: MarketRegime}
        self._current_regimes: Dict[str, MarketRegime] = {}

    async def classify_regime(
        self,
        symbol: str,
        timeframe: str,
        high: "np.ndarray",
        low: "np.ndarray",
        close: "np.ndarray",
        volume: "np.ndarray",
    ) -> MarketRegime:
        """
        Классифицировать текущий рыночный режим.

        Вызывается из IndicatorEngine.on_bar_completed() на каждом новом баре.

        Аргументы:
            symbol: Торговый символ
            timeframe: Таймфрейм для расчёта
            high, low, close, volume: OHLCV массивы (минимум 200 баров для EMA200)

        Возвращает:
            MarketRegime с типом, метриками и уверенностью
        """
        import numpy as np

        # Читать пороги из конфига
        adx_threshold = float(self.config.get("intelligence.regime.adx_threshold", default=25.0))
        volatile_thr  = float(self.config.get("intelligence.regime.volatile_threshold", default=0.03))
        quiet_thr     = float(self.config.get("intelligence.regime.quiet_threshold", default=0.005))
        bb_squeeze    = float(self.config.get("intelligence.regime.bb_squeeze_threshold", default=3.0))

        # Рассчитать индикаторы
        adx_result  = Indicators.adx(high, low, close, period=14)
        adx_val     = adx_result["adx"]
        di_plus     = adx_result["di_plus"]
        di_minus    = adx_result["di_minus"]

        atr_val     = float(Indicators.atr(high, low, close, period=14))
        current_price = float(close[-1])
        atr_ratio   = atr_val / current_price if current_price > 0 else 0.0

        bb_result   = Indicators.bollinger_bands(close, period=20)
        bb_bw       = float(bb_result["bandwidth"])

        ema200_val  = float(Indicators.ema(close, period=200)) if len(close) >= 200 else current_price

        # ── Классификация (приоритет сверху) ────────────────
        if atr_ratio > volatile_thr:
            regime_type = RegimeType.VOLATILE
            confidence = min(1.0, atr_ratio / volatile_thr * 0.7)

        elif adx_val > adx_threshold and di_plus > di_minus and current_price > ema200_val:
            regime_type = RegimeType.TRENDING_UP
            confidence = min(1.0, (adx_val - adx_threshold) / 40.0 + 0.5)

        elif adx_val > adx_threshold and di_minus > di_plus and current_price < ema200_val:
            regime_type = RegimeType.TRENDING_DOWN
            confidence = min(1.0, (adx_val - adx_threshold) / 40.0 + 0.5)

        elif atr_ratio < quiet_thr and bb_bw < bb_squeeze:
            regime_type = RegimeType.QUIET
            confidence = min(1.0, (quiet_thr - atr_ratio) / quiet_thr * 0.8)

        else:
            regime_type = RegimeType.RANGING
            confidence = min(1.0, (adx_threshold - adx_val) / adx_threshold * 0.7)

        # Нормализовать уверенность
        confidence = max(0.1, round(confidence, 2))

        new_regime = MarketRegime(
            symbol=symbol,
            timeframe=timeframe,
            regime=regime_type,
            adx=adx_val,
            atr_ratio=atr_ratio,
            bb_bandwidth=bb_bw,
            di_plus=di_plus,
            di_minus=di_minus,
            price_vs_ema200=(current_price - ema200_val) / ema200_val if ema200_val > 0 else 0.0,
            confidence=confidence,
            detected_at=datetime.utcnow(),
            prev_regime=self._current_regimes.get(symbol, {}).regime
                        if symbol in self._current_regimes else None,
        )

        # Публиковать REGIME_CHANGED только при реальной смене
        old_regime = self._current_regimes.get(symbol)
        if old_regime is None or old_regime.regime != regime_type:
            await self._publish_regime_changed(old_regime, new_regime)
            logger.info(
                "Режим рынка изменился",
                symbol=symbol,
                old=old_regime.regime.value if old_regime else "UNKNOWN",
                new=regime_type.value,
                adx=adx_val,
                atr_ratio=round(atr_ratio, 4),
                confidence=confidence,
            )

        self._current_regimes[symbol] = new_regime
        return new_regime

    def get_current_regime(self, symbol: str) -> Optional[MarketRegime]:
        """
        Получить текущий режим для символа (sync, без вычислений).

        Используется TrailingPolicy и RiskEngine в hot path.
        Latency: <1μs (чтение из словаря).
        """
        return self._current_regimes.get(symbol)

    async def _publish_regime_changed(
        self,
        old_regime: Optional[MarketRegime],
        new_regime: MarketRegime,
    ) -> None:
        """Опубликовать событие REGIME_CHANGED в Event Bus."""
        await self.event_bus.publish({
            "type": "REGIME_CHANGED",
            "priority": "HIGH",
            "payload": {
                "symbol": new_regime.symbol,
                "old_regime": old_regime.regime.value if old_regime else "UNKNOWN",
                "new_regime": new_regime.regime.value,
                "adx": new_regime.adx,
                "atr_ratio": new_regime.atr_ratio,
                "confidence": new_regime.confidence,
                "detected_at": new_regime.detected_at.isoformat(),
            }
        })
```

---

## 🔧 ТРЕБОВАНИЕ 3: ImpulseAnalyzer (src/intelligence/impulse_analyzer.py)

```python
"""
ImpulseAnalyzer — анализ силы импульса (ATR5/ATR20 ratio).

Назначение:
    Определять интенсивность текущего движения относительно нормы.
    Используется TrailingPolicy для адаптации агрессивности трейлинга:
    - Сильный импульс → более широкий трейлинг (не вышибить раньше времени)
    - Слабый импульс/консолидация → более тесный трейлинг (защитить прибыль)

Формула:
    ImpulseFactor = ATR(5) / ATR(20)

Интерпретация:
    > 1.5:  Очень сильный импульс → adjustment = 1.2 (ширина trailing +20%)
    1.2–1.5: Сильное движение → adjustment = 1.1
    0.8–1.2: Нормальное движение → adjustment = 1.0
    0.5–0.8: Слабое движение → adjustment = 0.9
    < 0.5:  Консолидация → adjustment = 0.8 (trailing тесный)
"""

from decimal import Decimal
from datetime import datetime
import numpy as np

from src.core.logger import get_logger
from src.indicators.library import Indicators
from src.intelligence.models import ImpulseFactor

logger = get_logger("ImpulseAnalyzer")


class ImpulseAnalyzer:
    """
    Анализатор силы импульса для адаптивного трейлинга.

    Рассчитывает Impulse Factor = ATR(5) / ATR(20) и предоставляет
    adjustment multiplier для TrailingPolicy.
    """

    # Пороги и соответствующие корректирующие коэффициенты
    ADJUSTMENT_TABLE = [
        (Decimal("1.5"), Decimal("1.2"),  "очень сильный импульс"),
        (Decimal("1.2"), Decimal("1.1"),  "сильное движение"),
        (Decimal("0.8"), Decimal("1.0"),  "нормальное движение"),
        (Decimal("0.5"), Decimal("0.9"),  "слабое движение"),
        (Decimal("0.0"), Decimal("0.8"),  "консолидация"),
    ]

    async def calculate(
        self,
        symbol: str,
        timeframe: str,
        high: np.ndarray,
        low: np.ndarray,
        close: np.ndarray,
    ) -> ImpulseFactor:
        """
        Рассчитать Impulse Factor для символа.

        Аргументы:
            symbol: Торговый символ
            timeframe: Таймфрейм
            high, low, close: OHLCV массивы (минимум 25 баров)

        Возвращает:
            ImpulseFactor с ratio и adjustment multiplier
        """
        if len(close) < 25:
            return ImpulseFactor(
                symbol=symbol, timeframe=timeframe,
                atr5=Decimal(0), atr20=Decimal(0), ratio=Decimal("1.0"),
                adjustment=Decimal("1.0"), interpretation="недостаточно данных",
                calculated_at=datetime.utcnow(),
            )

        atr5_val  = Indicators.atr(high, low, close, period=5)
        atr20_val = Indicators.atr(high, low, close, period=20)

        if atr20_val == 0:
            ratio = Decimal("1.0")
        else:
            ratio = atr5_val / atr20_val

        # Определить adjustment и интерпретацию
        adjustment = Decimal("1.0")
        interpretation = "нормальное движение"
        for threshold, adj, interp in self.ADJUSTMENT_TABLE:
            if ratio >= threshold:
                adjustment = adj
                interpretation = interp
                break

        logger.debug(
            "Impulse Factor рассчитан",
            symbol=symbol,
            atr5=float(atr5_val),
            atr20=float(atr20_val),
            ratio=float(ratio),
            adjustment=float(adjustment),
            interpretation=interpretation,
        )

        return ImpulseFactor(
            symbol=symbol,
            timeframe=timeframe,
            atr5=atr5_val,
            atr20=atr20_val,
            ratio=ratio,
            adjustment=adjustment,
            interpretation=interpretation,
            calculated_at=datetime.utcnow(),
        )
```

---

## 🔧 ТРЕБОВАНИЕ 4: LiquidityIntelligence (src/intelligence/liquidity_intelligence.py)

```python
"""
LiquidityIntelligence — HTF Liquidity Map и Stop Hunt Detection.

Назначение:
    1. Строить карту структурных уровней ликвидности (H4, Daily, Weekly VWAP)
    2. Обнаруживать Stop Hunt паттерны (sweep + быстрый возврат)
    3. Предоставлять TrailingPolicy информацию о значимых уровнях
       (не ставить стоп-лосс за ключевой структурный уровень)

Stop Hunt Detection:
    Признаки классического stop hunt:
    a) Свеча пробивает известный уровень (high/low)
    b) Быстрый возврат (в течение 1–3 баров)
    c) Аномальный объём при пробое (volume_spike > 2x средний)
    d) Тело свечи закрывается ВНУТРИ предыдущего диапазона

Score 0–100:
    0–30:  Обычное движение
    30–60: Умеренный стоп-хант
    60–80: Вероятный стоп-хант (рассмотреть удержание позиции)
    80–100: Классический стоп-хант (держать / добавить к позиции)
"""

from decimal import Decimal
from typing import List, Optional, Dict
from datetime import datetime, timedelta
import numpy as np
import asyncio

from src.core.logger import get_logger
from src.indicators.library import Indicators
from src.intelligence.models import LiquidityLevel, LiquidityMap, StopHuntSignal

logger = get_logger("LiquidityIntelligence")


class LiquidityIntelligence:
    """
    Карта ликвидности + обнаружение стоп-хантов.

    HTF Liquidity Map обновляется каждый час из 4h/1d данных.
    Stop Hunt Detection работает в реальном времени на каждом баре.
    """

    def __init__(self, config_manager, event_bus, market_data_store):
        """
        Аргументы:
            config_manager: Параметры (stop_hunt_min_score, sweep_min_penetration)
            event_bus: Для публикации STOP_HUNT_DETECTED
            market_data_store: Доступ к HTF данным (4h, 1d bars)
        """
        self.config = config_manager
        self.event_bus = event_bus
        self.market_data = market_data_store

        # Кэш ликвидностных карт: {symbol: LiquidityMap}
        self._liquidity_maps: Dict[str, LiquidityMap] = {}
        self._maps_updated_at: Dict[str, datetime] = {}

    async def update_htf_levels(self, symbol: str) -> LiquidityMap:
        """
        Обновить HTF Liquidity Map (вызывается каждый час).

        Строит карту из:
        - 4h highs/lows (последние 10 периодов)
        - Daily high/low (текущий день и предыдущий)
        - Weekly high/low
        - Дневной VWAP

        Аргументы:
            symbol: Торговый символ

        Возвращает:
            LiquidityMap с актуальными уровнями
        """
        levels: List[LiquidityLevel] = []

        try:
            # ── 4H уровни ────────────────────────────────────
            bars_4h = await self.market_data.get_bars(symbol, "4h", limit=20)
            if bars_4h and len(bars_4h) >= 2:
                for i, bar in enumerate(bars_4h[-10:]):  # Последние 10 H4 баров
                    # Проверить сколько раз уровень тестировался
                    h4_high_strength = self._count_level_tests(
                        float(bar["high"]), bars_4h, tolerance=0.002
                    )
                    h4_low_strength = self._count_level_tests(
                        float(bar["low"]), bars_4h, tolerance=0.002
                    )

                    levels.append(LiquidityLevel(
                        price=Decimal(str(bar["high"])),
                        level_type="H4_high",
                        timeframe="4h",
                        strength=h4_high_strength,
                        last_tested=None,
                    ))
                    levels.append(LiquidityLevel(
                        price=Decimal(str(bar["low"])),
                        level_type="H4_low",
                        timeframe="4h",
                        strength=h4_low_strength,
                        last_tested=None,
                    ))

            # ── Daily уровни ──────────────────────────────────
            bars_1d = await self.market_data.get_bars(symbol, "1d", limit=5)
            if bars_1d:
                today = bars_1d[-1]
                yesterday = bars_1d[-2] if len(bars_1d) >= 2 else today

                levels.extend([
                    LiquidityLevel(
                        price=Decimal(str(today["high"])),
                        level_type="daily_high",
                        timeframe="1d",
                        strength=3,
                        last_tested=None,
                    ),
                    LiquidityLevel(
                        price=Decimal(str(today["low"])),
                        level_type="daily_low",
                        timeframe="1d",
                        strength=3,
                        last_tested=None,
                    ),
                    LiquidityLevel(
                        price=Decimal(str(yesterday["high"])),
                        level_type="prev_day_high",
                        timeframe="1d",
                        strength=4,  # Предыдущий день важнее
                        last_tested=None,
                    ),
                    LiquidityLevel(
                        price=Decimal(str(yesterday["low"])),
                        level_type="prev_day_low",
                        timeframe="1d",
                        strength=4,
                        last_tested=None,
                    ),
                ])

            # ── VWAP (дневной) ────────────────────────────────
            bars_today = await self.market_data.get_bars(symbol, "1h", limit=24)
            if bars_today:
                high_arr  = np.array([float(b["high"])   for b in bars_today])
                low_arr   = np.array([float(b["low"])    for b in bars_today])
                close_arr = np.array([float(b["close"])  for b in bars_today])
                vol_arr   = np.array([float(b["volume"]) for b in bars_today])
                vwap_val  = Indicators.vwap(high_arr, low_arr, close_arr, vol_arr)

                levels.append(LiquidityLevel(
                    price=vwap_val,
                    level_type="vwap",
                    timeframe="1d",
                    strength=5,   # VWAP — самый важный уровень
                    last_tested=None,
                ))
            else:
                vwap_val = Decimal(0)

            # ── Собрать карту ─────────────────────────────────
            # Убрать дублирующиеся уровни (±0.1% друг от друга)
            levels = self._deduplicate_levels(levels, tolerance=0.001)
            # Оставить только наиболее значимые (strength >= 2)
            levels = sorted(levels, key=lambda x: -x.strength)[:20]

            # OHLCV для session high/low
            session_high = Decimal(str(max(float(b["high"]) for b in bars_today))) if bars_today else Decimal(0)
            session_low  = Decimal(str(min(float(b["low"])  for b in bars_today))) if bars_today else Decimal(0)

            liquidity_map = LiquidityMap(
                symbol=symbol,
                levels=levels,
                vwap=vwap_val,
                session_high=session_high,
                session_low=session_low,
                updated_at=datetime.utcnow(),
            )

            self._liquidity_maps[symbol] = liquidity_map
            self._maps_updated_at[symbol] = datetime.utcnow()

            logger.info(
                "HTF уровни ликвидности обновлены",
                symbol=symbol,
                levels_count=len(levels),
                vwap=float(vwap_val),
            )

            return liquidity_map

        except Exception as e:
            logger.error(
                "Ошибка обновления HTF уровней",
                symbol=symbol,
                error=str(e),
            )
            # Возвращаем последнюю известную карту
            return self._liquidity_maps.get(symbol, LiquidityMap(
                symbol=symbol, levels=[], vwap=Decimal(0),
                session_high=Decimal(0), session_low=Decimal(0),
                updated_at=datetime.utcnow(),
            ))

    async def detect_stop_hunt(
        self,
        symbol: str,
        bar: dict,
        prev_bars: list,
        liquidity_map: LiquidityMap,
    ) -> Optional[StopHuntSignal]:
        """
        Обнаружить Stop Hunt паттерн на текущем баре.

        Вызывается из IndicatorEngine.on_bar_completed() для каждого нового бара.

        Признаки Stop Hunt (каждый добавляет очки к score):
        a) Свеча пробила известный уровень ликвидности (+25 за каждый уровень)
        b) Цена быстро вернулась внутрь диапазона (+20 за возврат на той же свече)
        c) Аномальный объём при пробое (+20 если volume > 2x среднего)
        d) Тело закрылось внутри предыдущего диапазона (+15)
        e) Длинный хвост (wick > 2× тела) (+10)
        f) Уровень имеет высокую strength (+5 × strength)

        Аргументы:
            symbol: Торговый символ
            bar: Текущий бар {open, high, low, close, volume}
            prev_bars: Последние N баров для контекста
            liquidity_map: Текущая карта ликвидности

        Возвращает:
            StopHuntSignal если score >= min_score_threshold
            None если обычное движение
        """
        if not liquidity_map.levels or not prev_bars:
            return None

        min_score = int(self.config.get(
            "intelligence.stop_hunt.min_score", default=30
        ))

        bar_high  = float(bar["high"])
        bar_low   = float(bar["low"])
        bar_close = float(bar["close"])
        bar_open  = float(bar["open"])
        bar_vol   = float(bar["volume"])

        # Средний объём за последние 20 баров
        avg_volume = float(np.mean([float(b["volume"]) for b in prev_bars[-20:]]))
        volume_ratio = bar_vol / avg_volume if avg_volume > 0 else 1.0

        # Параметры свечи
        body_size  = abs(bar_close - bar_open)
        upper_wick = bar_high - max(bar_close, bar_open)
        lower_wick = min(bar_close, bar_open) - bar_low
        total_range = bar_high - bar_low

        swept_level = None
        direction   = None
        score       = 0

        # ── Проверить каждый уровень ──────────────────────────
        for level in liquidity_map.levels:
            level_price = float(level.price)
            min_penetration = float(self.config.get(
                "intelligence.stop_hunt.min_penetration", default=0.001  # 0.1%
            ))

            # Пробой сверху вниз (long sweep — вышибает лонги)
            if bar_low < level_price * (1 - min_penetration):
                penetration = (level_price - bar_low) / level_price
                recovery    = bar_close > level_price * 0.999  # Закрылся выше уровня

                if recovery:
                    # Подтверждённый sweep
                    score += 25 + level.strength * 5
                    if bar_low < level_price and bar_close > level_price:
                        score += 20  # Возврат на той же свече
                    swept_level = Decimal(str(level_price))
                    direction   = "long_sweep"

            # Пробой снизу вверх (short sweep — вышибает шорты)
            elif bar_high > level_price * (1 + min_penetration):
                penetration = (bar_high - level_price) / level_price
                recovery    = bar_close < level_price * 1.001

                if recovery:
                    score += 25 + level.strength * 5
                    if bar_high > level_price and bar_close < level_price:
                        score += 20
                    swept_level = Decimal(str(level_price))
                    direction   = "short_sweep"

        if swept_level is None:
            return None  # Нет пробоя уровня

        # ── Дополнительные очки ───────────────────────────────
        if volume_ratio > 2.0:
            score += 20  # Аномальный объём

        if body_size > 0 and (upper_wick > 2 * body_size or lower_wick > 2 * body_size):
            score += 10  # Длинный хвост

        # Проверка prev_bar (тело закрылось в prev диапазоне)
        if prev_bars:
            prev_high = float(prev_bars[-1]["high"])
            prev_low  = float(prev_bars[-1]["low"])
            if prev_low <= bar_close <= prev_high:
                score += 15

        score = min(100, score)  # Ограничить 100

        if score < min_score:
            return None  # Слишком слабый сигнал

        # Рекомендация действия
        if score >= 70:
            action = "hold_position"   # Уверенный стоп-хант → держать
        elif score >= 50:
            action = "hold_position"   # Вероятный → тоже держать
        else:
            action = "ignore"          # Слабый → игнорировать

        signal = StopHuntSignal(
            symbol=symbol,
            score=score,
            swept_level=swept_level,
            direction=direction,
            penetration_percent=float(penetration) * 100,
            recovery_candles=1,   # Текущий бар
            volume_spike=round(volume_ratio, 2),
            action_recommendation=action,
            detected_at=datetime.utcnow(),
        )

        # Публиковать событие
        await self.event_bus.publish({
            "type": "STOP_HUNT_DETECTED",
            "priority": "HIGH",
            "payload": {
                "symbol": symbol,
                "score": score,
                "swept_level": float(swept_level),
                "direction": direction,
                "action": action,
                "volume_spike": round(volume_ratio, 2),
                "detected_at": datetime.utcnow().isoformat(),
            }
        })

        logger.warning(
            "Stop Hunt обнаружен",
            symbol=symbol,
            score=score,
            swept_level=float(swept_level),
            direction=direction,
            volume_spike=round(volume_ratio, 2),
            recommendation=action,
        )

        return signal

    def get_liquidity_map(self, symbol: str) -> Optional[LiquidityMap]:
        """
        Получить текущую карту ликвидности (sync, без вычислений).

        Используется TrailingPolicy для размещения стопов.
        Latency: <1μs.
        """
        return self._liquidity_maps.get(symbol)

    def _count_level_tests(
        self,
        level: float,
        bars: list,
        tolerance: float = 0.002,
    ) -> int:
        """Подсчитать сколько раз уровень тестировался (strength)."""
        count = 0
        for bar in bars:
            bar_high = float(bar.get("high", 0))
            bar_low  = float(bar.get("low", 0))
            if (abs(bar_high - level) / level < tolerance or
                    abs(bar_low - level) / level < tolerance):
                count += 1
        return min(5, count)  # Ограничить 5

    def _deduplicate_levels(
        self,
        levels: List[LiquidityLevel],
        tolerance: float = 0.001,
    ) -> List[LiquidityLevel]:
        """Удалить дублирующиеся уровни (±tolerance друг от друга)."""
        if not levels:
            return levels
        result = [levels[0]]
        for level in levels[1:]:
            is_dup = any(
                abs(float(level.price) - float(existing.price)) / float(existing.price) < tolerance
                for existing in result
            )
            if not is_dup:
                result.append(level)
        return result
```

---

## 🔧 ТРЕБОВАНИЕ 5: MAE/MFE Tracker (src/intelligence/mae_mfe_tracker.py)

```python
"""
MAE/MFE Tracker — Maximum Adverse/Favorable Excursion.

Назначение:
    Отслеживать экстремальные движения ПО и ПРОТИВ каждой позиции.

    MAE (Maximum Adverse Excursion):
        Максимальное движение ПРОТИВ позиции в R-единицах.
        Показывает: насколько глубоко позиция уходила в минус до закрытия.
        Идеальная система: MAE < 1R (позиция почти сразу идёт в прибыль).

    MFE (Maximum Favorable Excursion):
        Максимальное движение В ПОЛЬЗУ позиции в R-единицах.
        Показывает: сколько было доступно максимум.
        Сравнение MFE vs actual exit: коэффициент использования прибыли.

Применение (Фаза 15 — Performance Attribution):
    - MAE/initial_stop ratio → качество входов (хорошие входы: MAE < 0.3R)
    - MFE/exit_pnl ratio    → качество выходов (хорошие выходы: >70% MFE использовано)
    - Oптимизация trailing: если avg MFE = 5R но avg exit = 2R → trailing слишком тесный
"""

from decimal import Decimal
from typing import Dict, Optional
from datetime import datetime
import asyncio

from src.core.logger import get_logger
from src.intelligence.models import MAEMFERecord

logger = get_logger("MAEMFETracker")


class MAEMFETracker:
    """
    Трекер MAE/MFE для всех открытых позиций.

    Обновляется на каждом тике (TICK_RECEIVED) или баре (BAR_COMPLETED).
    Сохраняет данные в PostgreSQL при закрытии позиции.
    """

    def __init__(self, db, event_bus):
        """
        Аргументы:
            db: PostgreSQLManager для сохранения записей
            event_bus: Подписка на события позиций
        """
        self.db = db
        self.event_bus = event_bus

        # Активные записи: {position_id: MAEMFERecord}
        self._records: Dict[str, MAEMFERecord] = {}

    async def register_position(
        self,
        position_id: str,
        symbol: str,
        strategy_id: str,
        entry_price: Decimal,
        initial_stop: Decimal,
        side: str,
        entry_time: datetime,
    ) -> None:
        """
        Зарегистрировать новую позицию для MAE/MFE tracking.

        Вызывается при открытии позиции (ORDER_FILLED event).

        Аргументы:
            position_id: Уникальный ID позиции
            symbol: Торговый символ
            strategy_id: ID стратегии (для attribution)
            entry_price: Цена входа
            initial_stop: Начальный стоп-лосс
            side: "long" / "short"
            entry_time: Время открытия
        """
        initial_risk_r = Decimal("1.0")  # По определению: начальный стоп = 1R

        record = MAEMFERecord(
            position_id=position_id,
            symbol=symbol,
            strategy_id=strategy_id,
            entry_price=entry_price,
            entry_time=entry_time,
            initial_stop=initial_stop,
            mae_price=entry_price,    # Начально = entry (ещё нет движения)
            mfe_price=entry_price,    # Начально = entry
            mae_r=Decimal(0),
            mfe_r=Decimal(0),
            current_price=entry_price,
            current_pnl_r=Decimal(0),
            updated_at=datetime.utcnow(),
        )

        self._records[position_id] = record

        logger.info(
            "MAE/MFE tracking начат",
            position_id=position_id,
            symbol=symbol,
            strategy_id=strategy_id,
            entry=float(entry_price),
            initial_stop=float(initial_stop),
        )

    async def update_price(
        self,
        position_id: str,
        current_price: Decimal,
        side: str,
    ) -> None:
        """
        Обновить MAE/MFE при изменении цены.

        Вызывается на каждом тике или при BAR_COMPLETED.
        Обновление в памяти — быстро (<1μs).

        Аргументы:
            position_id: ID позиции
            current_price: Текущая цена
            side: "long" / "short"
        """
        record = self._records.get(position_id)
        if not record:
            return

        initial_risk = abs(record.entry_price - record.initial_stop)
        if initial_risk == 0:
            return

        # Рассчитать текущий P&L в R
        if side == "long":
            current_pnl = current_price - record.entry_price
            # MAE: лучший (максимальный) убыток — минимальная цена для LONG
            if current_price < record.mae_price:
                record.mae_price = current_price
            # MFE: максимальная прибыль — максимальная цена для LONG
            if current_price > record.mfe_price:
                record.mfe_price = current_price
        else:
            current_pnl = record.entry_price - current_price
            # SHORT: MAE = максимальная цена
            if current_price > record.mae_price:
                record.mae_price = current_price
            # MFE = минимальная цена
            if current_price < record.mfe_price:
                record.mfe_price = current_price

        # Обновить в R-единицах
        if side == "long":
            mae_pnl = record.mae_price - record.entry_price   # Отрицательный
            mfe_pnl = record.mfe_price - record.entry_price   # Положительный
        else:
            mae_pnl = record.entry_price - record.mae_price
            mfe_pnl = record.entry_price - record.mfe_price

        record.mae_r           = mae_pnl / initial_risk
        record.mfe_r           = mfe_pnl / initial_risk
        record.current_price   = current_price
        record.current_pnl_r   = current_pnl / initial_risk
        record.updated_at      = datetime.utcnow()

    async def close_position(
        self,
        position_id: str,
        exit_price: Decimal,
        side: str,
        exit_reason: str,
    ) -> Optional[MAEMFERecord]:
        """
        Закрыть tracking и сохранить финальную запись.

        Вызывается при закрытии позиции.
        Сохраняет данные в PostgreSQL для Performance Attribution (Фаза 15).

        Аргументы:
            position_id: ID позиции
            exit_price: Цена выхода
            side: "long" / "short"
            exit_reason: "trailing" / "hard_stop" / "take_profit" / "emergency" / "manual"

        Возвращает:
            Финальную MAEMFERecord или None если позиция не найдена
        """
        record = self._records.get(position_id)
        if not record:
            logger.warning("MAE/MFE запись не найдена", position_id=position_id)
            return None

        # Финальное обновление
        await self.update_price(position_id, exit_price, side)

        initial_risk = abs(record.entry_price - record.initial_stop)
        if initial_risk > 0:
            if side == "long":
                final_pnl = exit_price - record.entry_price
            else:
                final_pnl = record.entry_price - exit_price
            record.final_pnl_r = final_pnl / initial_risk
        else:
            record.final_pnl_r = Decimal(0)

        record.closed_at    = datetime.utcnow()
        record.exit_reason  = exit_reason

        # Сохранить в БД
        await self._save_to_db(record)

        # Удалить из активных
        del self._records[position_id]

        logger.info(
            "MAE/MFE tracking завершён",
            position_id=position_id,
            symbol=record.symbol,
            strategy_id=record.strategy_id,
            mae_r=float(record.mae_r),
            mfe_r=float(record.mfe_r),
            final_pnl_r=float(record.final_pnl_r),
            exit_reason=exit_reason,
            mfe_utilization=round(
                float(record.final_pnl_r / record.mfe_r * 100) if record.mfe_r > 0 else 0, 1
            ),
        )

        return record

    def get_record(self, position_id: str) -> Optional[MAEMFERecord]:
        """
        Получить текущую MAE/MFE запись (sync, без вычислений).

        Latency: <1μs.
        """
        return self._records.get(position_id)

    async def _save_to_db(self, record: MAEMFERecord) -> None:
        """Сохранить финальную запись в таблицу mae_mfe_records."""
        await self.db.execute("""
            INSERT INTO mae_mfe_records (
                position_id, symbol, strategy_id,
                entry_price, initial_stop, entry_time,
                mae_price, mfe_price, mae_r, mfe_r,
                final_pnl_r, exit_reason,
                opened_at, closed_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
        """,
            record.position_id, record.symbol, record.strategy_id,
            record.entry_price, record.initial_stop, record.entry_time,
            record.mae_price, record.mfe_price, record.mae_r, record.mfe_r,
            record.final_pnl_r, record.exit_reason,
            record.entry_time, record.closed_at,
        )
```

---

## 📊 DATABASE SCHEMA (PostgreSQL)

```sql
-- История значений индикаторов (опционально)
CREATE TABLE indicator_values (
    time             TIMESTAMPTZ NOT NULL,
    symbol           VARCHAR(20) NOT NULL,
    timeframe        VARCHAR(5) NOT NULL,
    indicator_name   VARCHAR(50) NOT NULL,
    params           JSONB NOT NULL,
    value            NUMERIC(20, 8),
    metadata         JSONB,
    PRIMARY KEY (time, symbol, timeframe, indicator_name)
);
CREATE INDEX idx_indicator_symbol_time ON indicator_values(symbol, time DESC);

-- История смен режима рынка
CREATE TABLE regime_history (
    id               SERIAL PRIMARY KEY,
    symbol           VARCHAR(20) NOT NULL,
    timeframe        VARCHAR(5) NOT NULL,
    regime           VARCHAR(20) NOT NULL,
    adx              NUMERIC(6, 2),
    atr_ratio        NUMERIC(8, 6),
    bb_bandwidth     NUMERIC(8, 4),
    di_plus          NUMERIC(6, 2),
    di_minus         NUMERIC(6, 2),
    confidence       NUMERIC(4, 2),
    detected_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_regime_symbol ON regime_history(symbol, detected_at DESC);

-- HTF уровни ликвидности (последнее состояние)
CREATE TABLE htf_levels (
    id               SERIAL PRIMARY KEY,
    symbol           VARCHAR(20) NOT NULL,
    price            NUMERIC(20, 8) NOT NULL,
    level_type       VARCHAR(30) NOT NULL,
    timeframe        VARCHAR(5) NOT NULL,
    strength         INTEGER NOT NULL DEFAULT 1,
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_htf_levels_symbol ON htf_levels(symbol, updated_at DESC);

-- Stop Hunt события
CREATE TABLE stop_hunt_events (
    id               SERIAL PRIMARY KEY,
    symbol           VARCHAR(20) NOT NULL,
    score            INTEGER NOT NULL,
    swept_level      NUMERIC(20, 8),
    direction        VARCHAR(20),
    penetration_pct  NUMERIC(6, 4),
    recovery_candles INTEGER,
    volume_spike     NUMERIC(8, 2),
    action           VARCHAR(30),
    detected_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_stop_hunt_symbol ON stop_hunt_events(symbol, detected_at DESC);

-- MAE/MFE записи (финальные, при закрытии позиции)
CREATE TABLE mae_mfe_records (
    id               SERIAL PRIMARY KEY,
    position_id      VARCHAR(50) NOT NULL UNIQUE,
    symbol           VARCHAR(20) NOT NULL,
    strategy_id      VARCHAR(50),
    entry_price      NUMERIC(20, 8) NOT NULL,
    initial_stop     NUMERIC(20, 8) NOT NULL,
    mae_price        NUMERIC(20, 8),
    mfe_price        NUMERIC(20, 8),
    mae_r            NUMERIC(10, 4),   -- Отрицательное число
    mfe_r            NUMERIC(10, 4),   -- Положительное число
    final_pnl_r      NUMERIC(10, 4),
    exit_reason      VARCHAR(30),      -- trailing/hard_stop/take_profit/emergency
    entry_time       TIMESTAMPTZ NOT NULL,
    opened_at        TIMESTAMPTZ NOT NULL,
    closed_at        TIMESTAMPTZ
);
CREATE INDEX idx_mae_mfe_symbol    ON mae_mfe_records(symbol, closed_at DESC);
CREATE INDEX idx_mae_mfe_strategy  ON mae_mfe_records(strategy_id, closed_at DESC);
```

---

## 🚀 ПРОИЗВОДИТЕЛЬНОСТЬ

```
Операция                                    Target       Частота
──────────────────────────────────────────────────────────────────
calculate_single_indicator()               <10ms        каждый бар
calculate_batch_indicators()               <50ms        каждый бар
RegimeClusterEngine.classify_regime()      <30ms        каждый бар (1h/4h)
ImpulseAnalyzer.calculate()                <10ms        каждый бар
LiquidityIntelligence.update_htf_levels()  <2s          каждый час
LiquidityIntelligence.detect_stop_hunt()   <5ms         каждый бар
MAEMFETracker.update_price()               <1μs         каждый тик
cache_lookup()                             <1ms         100/сек
incremental_ema_update()                   <1ms         каждый бар
──────────────────────────────────────────────────────────────────
```

---

## ⚠️ КРИТИЧЕСКИЕ ОГРАНИЧЕНИЯ ФАЗЫ 7

### ✅ Что реализовано:
- 20+ классических индикаторов (SMA, EMA, RSI, MACD, Bollinger, ATR, ADX, OBV, VWAP, Donchian, Delta)
- **RegimeClusterEngine** — 5 режимов (TRENDING_UP/DOWN, RANGING, VOLATILE, QUIET)
- **ImpulseAnalyzer** — ATR5/ATR20, adjustment multiplier для TrailingPolicy
- **LiquidityIntelligence** — HTF Liquidity Map + Stop Hunt Detection (score 0–100)
- **MAE/MFE Tracker** — tracking и performance attribution данные
- NumPy векторизация, инкрементальные обновления, двухуровневый кэш
- Multi-timeframe (1m, 5m, 15m, 1h, 4h, 1d)

### ❌ Что НЕ реализовано (future phases):
- ML-индикаторы и предсказательные модели (→ Фаза 21)
- Pattern recognition (head & shoulders, triangles)
- Footprint charts / order flow
- Adaptive parameters (auto-optimization)
- Custom user-defined indicators

---

## ACCEPTANCE CRITERIA

### Классические индикаторы
- [ ] SMA, EMA, RSI, MACD, Bollinger, ATR, ADX, OBV, VWAP, Donchian, Delta
- [ ] Все с защитой division by zero
- [ ] Warming period tracking (is_valid / warming_bars_left)
- [ ] NumPy vectorization (10x vs pure Python)

### RegimeClusterEngine
- [ ] 5 режимов классифицируются корректно на исторических данных
- [ ] REGIME_CHANGED event при смене
- [ ] get_current_regime() < 1μs (sync read)
- [ ] Уверенность confidence 0.0–1.0

### ImpulseAnalyzer
- [ ] ATR5/ATR20 ratio рассчитывается корректно
- [ ] Adjustment table возвращает корректные множители (0.8–1.2)
- [ ] Используется TrailingPolicy для масштабирования trail_mult

### LiquidityIntelligence
- [ ] HTF уровни обновляются каждый час (4h + 1d + VWAP)
- [ ] Дедупликация уровней (±0.1%)
- [ ] Stop Hunt score 0–100 на реальных данных
- [ ] STOP_HUNT_DETECTED event при score >= 30

### MAE/MFE Tracker
- [ ] Регистрация при открытии позиции
- [ ] Обновление на каждом тике/баре (<1μs)
- [ ] Сохранение в БД при закрытии
- [ ] exit_reason: trailing/hard_stop/take_profit/emergency

### Performance
- [ ] Batch indicators <50ms
- [ ] RegimeCluster <30ms
- [ ] StopHunt detection <5ms
- [ ] MAE/MFE update <1μs

---

**Version:** CRYPTOTEHNOLOG v4.4 (Фаза 7 — полная редакция)
**Dependencies:** Phases 0-6
**Next:** Phase 8 - Signal Generator (OpportunityEngine, MetaClassifier, Donchian Breakout Strategy)

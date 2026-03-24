# AI ПРОМТ: ФАЗА 20 - ADVANCED EXECUTION ALGORITHMS

## КОНТЕКСТ

Вы — Senior Algorithmic Trading Engineer, специализирующийся на advanced execution strategies, market microstructure, и transaction cost optimization.

**Фазы 0-19 завершены.** Доступны:
- Полная торговая система (19 фаз)
- Production deployment на Kubernetes
- Historical data (3 years, quality validated)
- Все компоненты работают

**Текущая задача:** Реализовать production-ready Advanced Execution Algorithms (TWAP, VWAP, Iceberg, Adaptive) для минимизации market impact и transaction costs.

---

## ⚠️ КРИТИЧЕСКИ ВАЖНО: РУССКИЙ ЯЗЫК

**ВСЕ** комментарии, docstrings, логи и сообщения об ошибках должны быть **НА РУССКОМ ЯЗЫКЕ**.

### Python docstrings — ТОЛЬКО русский:

```python
class AdvancedExecutionEngine:
    """
    Движок продвинутых алгоритмов исполнения для минимизации market impact.
    
    Особенности:
    - TWAP (Time-Weighted Average Price) — равномерное исполнение
    - VWAP (Volume-Weighted Average Price) — follow volume profile
    - Iceberg — скрытие реального размера ордера
    - Adaptive — динамическая адаптация к market conditions
    - POV (Percentage of Volume) — процент от рыночного объема
    - Implementation Shortfall — минимизация отклонения от benchmark
    - Market impact modeling — предсказание влияния на цену
    - Smart order routing — оптимальное распределение между venues
    """
    
    async def execute_twap(
        self,
        symbol: str,
        side: OrderSide,
        total_quantity: Decimal,
        duration_minutes: int,
        num_slices: int = None,
    ) -> TWAPExecutionResult:
        """
        Исполнить ордер через TWAP (Time-Weighted Average Price).
        
        Аргументы:
            symbol: Торговая пара
            side: BUY или SELL
            total_quantity: Общее количество
            duration_minutes: Период исполнения (минуты)
            num_slices: Количество частей (auto если None)
        
        Процесс:
        1. Разбить total_quantity на равные части (slices)
        2. Рассчитать interval между slices
        3. Для каждого slice:
           a. Wait до scheduled time
           b. Place limit order (с tolerance)
           c. Monitor fill
           d. Если не filled → adjust price
        4. Track average fill price
        5. Calculate TWAP benchmark vs actual
        
        Example:
        - Total: 10 BTC
        - Duration: 60 minutes
        - Slices: 12 (каждые 5 минут)
        - Each slice: 0.833 BTC
        """
        pass
```

### Логи — ТОЛЬКО русский:

```python
logger.info("🎯 TWAP execution запущен", symbol="BTC/USDT", quantity=10, duration_min=60, slices=12)
logger.debug("TWAP slice executed", slice=3, quantity=0.833, fill_price=50050, scheduled_time="10:15")
logger.warning("⚠️  Slice partially filled", slice=5, filled=0.5, total=0.833, timeout_sec=30)
logger.info("✅ TWAP execution завершен", avg_price=50075, benchmark=50100, slippage=-0.05)
```

---

## 🔗 КОМПОНЕНТНЫЕ ИНТЕГРАЦИИ

### Роль компонента в системе:
Advanced Execution Engine — оптимизация исполнения крупных ордеров. Разбивает большие ордера на маленькие части, исполняет постепенно для минимизации market impact, адаптируется к market conditions, и обеспечивает лучшие цены чем simple market orders.

### Входящие зависимости:

#### 1. **Strategy Manager (Фаза 14)** → request для smart execution
   - Trigger: Large orders (> $50,000)
   - Algo: TWAP для scheduled execution
   - Критичность: HIGH

#### 2. **Market Data Layer (Фаза 6)** → real-time orderbook
   - Data: L2 orderbook depth
   - Частота: continuous updates
   - Критичность: HIGH (для adaptive algos)

#### 3. **Execution Layer (Фаза 10)** → базовое исполнение
   - Reuse: Basic order placement
   - Критичность: HIGH

### Исходящие зависимости:

#### 1. → Exchange APIs (через Execution Layer)
   - Orders: Multiple child orders
   - Frequency: Every slice (TWAP) или volume trigger (VWAP)

#### 2. → PostgreSQL (execution analytics)
   - **Table: `advanced_executions`**
     ```sql
     CREATE TABLE advanced_executions (
         execution_id SERIAL PRIMARY KEY,
         started_at TIMESTAMPTZ NOT NULL,
         completed_at TIMESTAMPTZ,
         
         symbol VARCHAR(20) NOT NULL,
         side VARCHAR(4) NOT NULL,
         
         algorithm VARCHAR(20) NOT NULL,  -- TWAP, VWAP, ICEBERG, ADAPTIVE
         
         total_quantity NUMERIC(20, 8),
         filled_quantity NUMERIC(20, 8),
         
         average_fill_price NUMERIC(20, 8),
         benchmark_price NUMERIC(20, 8),  -- VWAP или arrival price
         
         -- Performance metrics
         slippage_bps NUMERIC(10, 4),  -- Basis points
         market_impact_bps NUMERIC(10, 4),
         implementation_shortfall NUMERIC(20, 2),
         
         -- Execution quality
         num_child_orders INTEGER,
         fill_rate NUMERIC(5, 4),  -- % filled
         
         metadata JSONB
     );
     ```

#### 3. → Notifications (Фаза 13)
   - Alert: Algo execution completed
   - Report: Execution quality metrics

### Контракты данных:

#### TWAP Algorithm:

```python
from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime, timedelta
from typing import List

@dataclass
class TWAPConfig:
    """Конфигурация TWAP algorithm."""
    
    symbol: str
    side: OrderSide
    total_quantity: Decimal
    
    # Timing
    duration_minutes: int
    num_slices: Optional[int] = None  # Auto-calculate если None
    
    # Execution params
    price_tolerance_percent: Decimal = Decimal("0.1")  # 0.1% от market
    slice_timeout_seconds: int = 60  # Max time per slice
    
    # Adaptive params
    adapt_to_market: bool = True  # Adjust на market volatility

class TWAPExecutor:
    """
    TWAP (Time-Weighted Average Price) executor.
    
    Разбивает большой ордер на равные части и исполняет через равные интервалы.
    """
    
    async def execute(self, config: TWAPConfig) -> TWAPExecutionResult:
        """
        Execute TWAP strategy.
        """
        # Calculate slices
        if config.num_slices is None:
            # Auto: 1 slice per 5 minutes
            config.num_slices = max(2, config.duration_minutes // 5)
        
        slice_quantity = config.total_quantity / config.num_slices
        slice_interval = timedelta(minutes=config.duration_minutes / config.num_slices)
        
        logger.info(
            "🎯 TWAP execution started",
            symbol=config.symbol,
            total_quantity=config.total_quantity,
            num_slices=config.num_slices,
            slice_quantity=slice_quantity,
            interval_minutes=slice_interval.total_seconds() / 60,
        )
        
        # Execute slices
        fills = []
        start_time = datetime.now(timezone.utc)
        
        for slice_num in range(config.num_slices):
            # Wait до scheduled time
            scheduled_time = start_time + (slice_interval * slice_num)
            wait_seconds = (scheduled_time - datetime.now(timezone.utc)).total_seconds()
            
            if wait_seconds > 0:
                await asyncio.sleep(wait_seconds)
            
            # Get current market price
            market_price = await self.market_data.get_current_price(config.symbol)
            
            # Place limit order (с tolerance)
            if config.side == OrderSide.BUY:
                limit_price = market_price * (1 + config.price_tolerance_percent / 100)
            else:
                limit_price = market_price * (1 - config.price_tolerance_percent / 100)
            
            # Execute slice
            fill = await self._execute_slice(
                symbol=config.symbol,
                side=config.side,
                quantity=slice_quantity,
                limit_price=limit_price,
                timeout_seconds=config.slice_timeout_seconds,
            )
            
            fills.append(fill)
            
            logger.debug(
                "TWAP slice executed",
                slice=slice_num + 1,
                quantity=fill.filled_quantity,
                price=fill.fill_price,
                scheduled=scheduled_time,
                actual=fill.filled_at,
            )
        
        # Calculate results
        total_filled = sum(f.filled_quantity for f in fills)
        avg_price = sum(f.fill_price * f.filled_quantity for f in fills) / total_filled
        
        # Benchmark (start price)
        benchmark_price = fills[0].market_price_at_start if fills else Decimal("0")
        
        # Slippage
        if config.side == OrderSide.BUY:
            slippage = (avg_price - benchmark_price) / benchmark_price * 10000  # BPS
        else:
            slippage = (benchmark_price - avg_price) / benchmark_price * 10000
        
        logger.info(
            "✅ TWAP execution completed",
            filled=total_filled,
            avg_price=avg_price,
            benchmark=benchmark_price,
            slippage_bps=slippage,
        )
        
        return TWAPExecutionResult(
            total_quantity=config.total_quantity,
            filled_quantity=total_filled,
            average_fill_price=avg_price,
            benchmark_price=benchmark_price,
            slippage_bps=slippage,
            num_slices=config.num_slices,
            fills=fills,
        )
```

#### VWAP Algorithm:

```python
class VWAPExecutor:
    """
    VWAP (Volume-Weighted Average Price) executor.
    
    Распределяет исполнение согласно historical volume profile.
    """
    
    async def execute(self, config: VWAPConfig) -> VWAPExecutionResult:
        """
        Execute VWAP strategy.
        
        Процесс:
        1. Get historical volume profile (обычно intraday)
        2. Calculate target participation rate для каждого периода
        3. Execute согласно volume profile
        """
        # Get volume profile (last 7 days average для этого времени суток)
        volume_profile = await self._get_volume_profile(
            symbol=config.symbol,
            duration_minutes=config.duration_minutes,
        )
        
        # Calculate target quantity для каждого периода
        total_volume = sum(v.volume for v in volume_profile)
        slices = []
        
        for period in volume_profile:
            period_weight = period.volume / total_volume
            period_quantity = config.total_quantity * period_weight
            
            slices.append(VWAPSlice(
                start_time=period.start_time,
                end_time=period.end_time,
                target_quantity=period_quantity,
                expected_volume=period.volume,
            ))
        
        logger.info(
            "🎯 VWAP execution started",
            symbol=config.symbol,
            total_quantity=config.total_quantity,
            num_periods=len(slices),
        )
        
        # Execute slices
        fills = []
        
        for slice_num, slice_config in enumerate(slices):
            # Wait до начала периода
            wait_seconds = (slice_config.start_time - datetime.now(timezone.utc)).total_seconds()
            if wait_seconds > 0:
                await asyncio.sleep(wait_seconds)
            
            # Execute slice (target = POV * market volume)
            fill = await self._execute_vwap_slice(slice_config)
            fills.append(fill)
        
        # Calculate VWAP benchmark
        vwap_benchmark = await self._calculate_vwap_benchmark(
            symbol=config.symbol,
            start_time=slices[0].start_time,
            end_time=slices[-1].end_time,
        )
        
        # Results
        total_filled = sum(f.filled_quantity for f in fills)
        avg_price = sum(f.fill_price * f.filled_quantity for f in fills) / total_filled
        
        # Slippage vs VWAP
        if config.side == OrderSide.BUY:
            slippage = (avg_price - vwap_benchmark) / vwap_benchmark * 10000
        else:
            slippage = (vwap_benchmark - avg_price) / vwap_benchmark * 10000
        
        logger.info(
            "✅ VWAP execution completed",
            filled=total_filled,
            avg_price=avg_price,
            vwap_benchmark=vwap_benchmark,
            slippage_bps=slippage,
        )
        
        return VWAPExecutionResult(
            total_quantity=config.total_quantity,
            filled_quantity=total_filled,
            average_fill_price=avg_price,
            vwap_benchmark=vwap_benchmark,
            slippage_bps=slippage,
            num_periods=len(slices),
            fills=fills,
        )
```

#### Iceberg Orders:

```python
class IcebergExecutor:
    """
    Iceberg orders — скрывает полный размер ордера.
    
    Показывает только малую часть (tip of iceberg), остальное скрыто.
    """
    
    async def execute(self, config: IcebergConfig) -> IcebergExecutionResult:
        """
        Execute Iceberg strategy.
        
        Процесс:
        1. Place visible order (clip_size)
        2. Wait for fill
        3. When filled → place next clip
        4. Repeat до полного исполнения
        """
        remaining_quantity = config.total_quantity
        fills = []
        
        logger.info(
            "🧊 Iceberg execution started",
            symbol=config.symbol,
            total_quantity=config.total_quantity,
            clip_size=config.clip_size,
            estimated_clips=int(config.total_quantity / config.clip_size),
        )
        
        while remaining_quantity > 0:
            # Calculate current clip size
            clip_quantity = min(config.clip_size, remaining_quantity)
            
            # Place visible order
            fill = await self._execute_clip(
                symbol=config.symbol,
                side=config.side,
                quantity=clip_quantity,
                limit_price=config.limit_price,
            )
            
            fills.append(fill)
            remaining_quantity -= fill.filled_quantity
            
            logger.debug(
                "Iceberg clip filled",
                clip=len(fills),
                filled=fill.filled_quantity,
                remaining=remaining_quantity,
            )
            
            # Wait между clips (избежать detection)
            if remaining_quantity > 0:
                await asyncio.sleep(config.clip_interval_seconds)
        
        # Results
        total_filled = sum(f.filled_quantity for f in fills)
        avg_price = sum(f.fill_price * f.filled_quantity for f in fills) / total_filled
        
        logger.info(
            "✅ Iceberg execution completed",
            total_clips=len(fills),
            filled=total_filled,
            avg_price=avg_price,
        )
        
        return IcebergExecutionResult(
            total_quantity=config.total_quantity,
            filled_quantity=total_filled,
            average_fill_price=avg_price,
            num_clips=len(fills),
            fills=fills,
        )
```

---

## ⚠️ КРИТИЧЕСКИЕ ОГРАНИЧЕНИЯ ФАЗЫ 20

**✅ Что реализовано:**
- TWAP (Time-Weighted Average Price)
- VWAP (Volume-Weighted Average Price)
- Iceberg (Hidden orders)
- Adaptive execution (market conditions)
- Market impact modeling (basic)
- Execution analytics (slippage, benchmark)

**❌ Что НЕ реализовано:**
- Advanced ML-based execution (reinforcement learning)
- Multi-venue SOR (Smart Order Routing across exchanges)
- Dark pool integration
- Advanced market impact models (Almgren-Chriss)
- Real-time optimization (dynamic programming)

---

## 🚀 ПРОИЗВОДИТЕЛЬНОСТЬ

### Критические требования:

```
Операция                         Latency Target
────────────────────────────────────────────────────────
twap_slice_execution()           <2s per slice
vwap_period_execution()          <5s per period
iceberg_clip_execution()         <1s per clip
────────────────────────────────────────────────────────
```

---

## ФАЙЛОВАЯ СТРУКТУРА

```
CRYPTOTEHNOLOG/
├── src/
│   └── advanced_execution/
│       ├── __init__.py
│       ├── engine.py                     # AdvancedExecutionEngine
│       ├── algorithms/
│       │   ├── twap.py                   # TWAPExecutor
│       │   ├── vwap.py                   # VWAPExecutor
│       │   ├── iceberg.py                # IcebergExecutor
│       │   └── adaptive.py               # AdaptiveExecutor
│       ├── analytics.py                  # Execution analytics
│       └── models.py                     # Config dataclasses
│
└── tests/
    ├── unit/
    │   └── test_algorithms.py
    └── integration/
        └── test_advanced_execution.py
```

---

## ACCEPTANCE CRITERIA

### TWAP
- [ ] Equal time slices
- [ ] Scheduled execution
- [ ] Price tolerance
- [ ] Benchmark vs actual

### VWAP
- [ ] Volume profile analysis
- [ ] Participation rate
- [ ] VWAP benchmark
- [ ] Adaptive to volume

### Iceberg
- [ ] Hidden quantity
- [ ] Clip size control
- [ ] Detection avoidance

### Performance
- [ ] Slippage < 5 BPS
- [ ] Fill rate > 95%
- [ ] Market impact minimized

---

## ИТОГОВАЯ ГОТОВНОСТЬ

**Фаза 20: Advanced Execution Algorithms** готова к реализации! 🚀

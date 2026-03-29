# AI ПРОМТ: ФАЗА 19 - HISTORICAL DATA MANAGER

## КОНТЕКСТ

Вы — Senior Data Engineer, специализирующийся на time-series data management, data pipelines, и high-performance storage systems.

**Фазы 0-18 завершены.** Доступны:
- Полная торговая система (18 фаз)
- Production deployment на Kubernetes
- Все компоненты работают

**Текущая задача:** Реализовать production-ready Historical Data Manager для сбора, хранения, и управления историческими market data с efficient storage, fast queries, data validation, и automated maintenance.

---

## ⚠️ КРИТИЧЕСКИ ВАЖНО: РУССКИЙ ЯЗЫК

**ВСЕ** комментарии, docstrings, логи и сообщения об ошибках должны быть **НА РУССКОМ ЯЗЫКЕ**.

### Python docstrings — ТОЛЬКО русский:

```python
class HistoricalDataManager:
    """
    Менеджер исторических данных для backtesting и анализа.
    
    Особенности:
    - Multi-source data collection (Bybit, OKX, Binance, CoinGecko)
    - TimescaleDB storage (optimized для time-series)
    - Automated data download (daily/hourly sync)
    - Data validation (gaps, outliers, duplicates)
    - Data compression (save 70% storage)
    - Fast queries (hypertables, indexes)
    - Data retention policies (auto-cleanup старых данных)
    - Export/import (CSV, Parquet для analysis)
    """
    
    async def download_historical_data(
        self,
        symbol: str,
        timeframe: str,
        start_date: date,
        end_date: date,
        source: str = "bybit",
    ) -> int:
        """
        Скачать исторические OHLCV данные.
        
        Аргументы:
            symbol: Торговая пара (e.g. "BTC/USDT")
            timeframe: Таймфрейм (e.g. "1m", "5m", "1h")
            start_date: Дата начала
            end_date: Дата окончания
            source: Источник данных
        
        Возвращает:
            Количество скачанных баров
        
        Процесс:
        1. Проверить что уже есть в базе (избежать дублирования)
        2. Рассчитать gaps (недостающие периоды)
        3. Скачать данные от exchange API (batches по 1000 баров)
        4. Validate данные (gaps, outliers)
        5. Сохранить в TimescaleDB
        6. Создать continuous aggregates (для fast queries)
        """
        pass
```

### Логи — ТОЛЬКО русский:

```python
logger.info("📥 Скачивание исторических данных", symbol="BTC/USDT", period="2023-01-01 to 2024-01-01")
logger.debug("Batch downloaded", bars=1000, progress="50/100")
logger.warning("⚠️  Gap обнаружен", symbol="ETH/USDT", missing_bars=120, period="2023-06-15 to 2023-06-16")
logger.info("✅ Данные загружены", total_bars=525600, duration_sec=180)
```

---

## 🔗 КОМПОНЕНТНЫЕ ИНТЕГРАЦИИ

### Роль компонента в системе:
Historical Data Manager — фундамент для backtesting и анализа. Собирает historical OHLCV данные от exchanges, валидирует качество, эффективно хранит в TimescaleDB, предоставляет fast queries для Backtesting Engine, и автоматически поддерживает актуальность данных.

### Входящие зависимости:

#### 1. **Exchange APIs** → source для historical data
   - Bybit: `/v5/market/kline`
   - OKX: `/api/v5/market/candles`
   - Binance: `/api/v3/klines`
   - Rate limits: 10-20 requests/sec
   - Критичность: HIGH

#### 2. **Market Data Layer (Фаза 6)** → real-time updates
   - Event: Подписка на `BAR_COMPLETED`
   - Автоматически сохранять новые bars
   - Критичность: MEDIUM

#### 3. **Backtesting Engine (Фаза 16)** → query historical data
   - Query: `get_historical_bars(symbol, timeframe, start, end)`
   - Частота: при каждом backtest
   - Критичность: HIGH

### Исходящие зависимости:

#### 1. → TimescaleDB (optimized storage)
   - **Hypertable: `ohlcv_bars`**
     ```sql
     -- TimescaleDB hypertable для time-series data
     CREATE TABLE ohlcv_bars (
         time TIMESTAMPTZ NOT NULL,
         symbol VARCHAR(20) NOT NULL,
         timeframe VARCHAR(5) NOT NULL,
         
         open NUMERIC(20, 8) NOT NULL,
         high NUMERIC(20, 8) NOT NULL,
         low NUMERIC(20, 8) NOT NULL,
         close NUMERIC(20, 8) NOT NULL,
         volume NUMERIC(20, 8) NOT NULL,
         
         -- Metadata
         source VARCHAR(20),  -- 'bybit', 'okx', 'binance'
         verified BOOLEAN DEFAULT FALSE,
         
         PRIMARY KEY (time, symbol, timeframe)
     );
     
     -- Преобразовать в hypertable (TimescaleDB magic)
     SELECT create_hypertable('ohlcv_bars', 'time');
     
     -- Compression policy (save 70% storage)
     ALTER TABLE ohlcv_bars SET (
         timescaledb.compress,
         timescaledb.compress_segmentby = 'symbol,timeframe'
     );
     
     -- Auto-compress data старше 7 дней
     SELECT add_compression_policy('ohlcv_bars', INTERVAL '7 days');
     
     -- Retention policy (auto-delete data старше 3 лет)
     SELECT add_retention_policy('ohlcv_bars', INTERVAL '3 years');
     
     -- Indexes для fast queries
     CREATE INDEX idx_ohlcv_symbol_time ON ohlcv_bars (symbol, timeframe, time DESC);
     ```

   - **Continuous Aggregates** (pre-computed для fast queries)
     ```sql
     -- Hourly aggregates (из 1-minute bars)
     CREATE MATERIALIZED VIEW ohlcv_hourly
     WITH (timescaledb.continuous) AS
     SELECT
         time_bucket('1 hour', time) AS bucket,
         symbol,
         FIRST(open, time) AS open,
         MAX(high) AS high,
         MIN(low) AS low,
         LAST(close, time) AS close,
         SUM(volume) AS volume
     FROM ohlcv_bars
     WHERE timeframe = '1m'
     GROUP BY bucket, symbol;
     
     -- Auto-refresh policy
     SELECT add_continuous_aggregate_policy('ohlcv_hourly',
         start_offset => INTERVAL '1 day',
         end_offset => INTERVAL '1 hour',
         schedule_interval => INTERVAL '1 hour'
     );
     ```

#### 2. → S3/Object Storage (cold storage для backups)
   - Daily backups compressed data
   - Long-term archival (>3 years)

#### 3. → Metrics (Prometheus)
   - Gauge: `historical_data_bars_total{symbol, timeframe}`
   - Counter: `data_download_requests_total{source, status}`

### Контракты данных:

#### DataDownloadRequest:

```python
from dataclasses import dataclass
from datetime import date
from typing import Optional

@dataclass
class DataDownloadRequest:
    """Запрос на скачивание исторических данных."""
    
    symbol: str
    timeframe: str
    start_date: date
    end_date: date
    source: str = "bybit"
    
    # Validation
    validate_data: bool = True
    fill_gaps: bool = True
    
    # Metadata
    requested_by: Optional[str] = None
    priority: str = "NORMAL"  # NORMAL, HIGH, LOW
```

#### DataQualityReport:

```python
@dataclass
class DataQualityReport:
    """Отчет о качестве данных."""
    
    symbol: str
    timeframe: str
    period_start: date
    period_end: date
    
    # Completeness
    expected_bars: int
    actual_bars: int
    missing_bars: int
    completeness_percent: Decimal
    
    # Gaps
    gaps_detected: int
    largest_gap_hours: int
    
    # Outliers
    outliers_detected: int
    outlier_bars: List[Dict]  # List of suspicious bars
    
    # Duplicates
    duplicates_removed: int
    
    # Overall quality
    quality_score: Decimal  # 0-100
    is_acceptable: bool  # True если quality > 95%
```

#### Data Downloader:

```python
class ExchangeDataDownloader:
    """
    Скачивание данных от exchange API.
    """
    
    async def download_ohlcv(
        self,
        symbol: str,
        timeframe: str,
        start_timestamp: int,
        end_timestamp: int,
        batch_size: int = 1000,
    ) -> List[OHLCVBar]:
        """
        Скачать OHLCV bars от exchange.
        
        Batching:
        - Exchanges ограничивают 1000 bars per request
        - Нужно делать multiple requests для long periods
        
        Rate limiting:
        - Respecting exchange rate limits (10-20 req/sec)
        - Exponential backoff при errors
        """
        all_bars = []
        current_start = start_timestamp
        
        while current_start < end_timestamp:
            try:
                # Calculate batch end
                batch_end = min(
                    current_start + (batch_size * self._get_timeframe_seconds(timeframe)),
                    end_timestamp,
                )
                
                # Request от exchange
                response = await self.client.get_klines(
                    symbol=symbol,
                    interval=timeframe,
                    start_time=current_start,
                    end_time=batch_end,
                    limit=batch_size,
                )
                
                # Parse response
                bars = self._parse_klines(response)
                all_bars.extend(bars)
                
                logger.debug(
                    "Batch downloaded",
                    symbol=symbol,
                    bars=len(bars),
                    period=f"{datetime.fromtimestamp(current_start)} to {datetime.fromtimestamp(batch_end)}",
                )
                
                # Move to next batch
                current_start = batch_end
                
                # Rate limiting: wait между requests
                await asyncio.sleep(0.1)  # 10 req/sec
                
            except ExchangeRateLimitError:
                logger.warning("Rate limit hit, waiting 60s")
                await asyncio.sleep(60)
                continue
                
            except Exception as e:
                logger.error(
                    "Download error",
                    error=str(e),
                    retry_in=5,
                )
                await asyncio.sleep(5)
                continue
        
        return all_bars
```

#### Data Validator:

```python
class DataValidator:
    """
    Валидация качества исторических данных.
    """
    
    def validate_ohlcv_data(
        self,
        bars: List[OHLCVBar],
        expected_count: int,
    ) -> DataQualityReport:
        """
        Проверить качество данных.
        
        Checks:
        1. Completeness (все ли bars присутствуют)
        2. Gaps (пропуски в time series)
        3. Outliers (аномальные значения)
        4. Duplicates (дубликаты)
        5. OHLC consistency (open <= high, low <= close)
        """
        # Check 1: Completeness
        actual_count = len(bars)
        missing = expected_count - actual_count
        completeness = (actual_count / expected_count) * 100 if expected_count > 0 else 0
        
        # Check 2: Gaps
        gaps = self._detect_gaps(bars)
        
        # Check 3: Outliers
        outliers = self._detect_outliers(bars)
        
        # Check 4: Duplicates
        duplicates = self._detect_duplicates(bars)
        
        # Check 5: OHLC consistency
        inconsistent = self._check_ohlc_consistency(bars)
        
        # Calculate quality score
        quality_score = Decimal("100")
        quality_score -= (missing / expected_count) * 50  # Missing bars: -50%
        quality_score -= len(gaps) * 5  # Each gap: -5%
        quality_score -= len(outliers) * 2  # Each outlier: -2%
        quality_score -= len(duplicates) * 1  # Each duplicate: -1%
        quality_score = max(Decimal("0"), quality_score)
        
        is_acceptable = quality_score >= Decimal("95")
        
        if not is_acceptable:
            logger.warning(
                "⚠️  Низкое качество данных",
                quality_score=quality_score,
                missing=missing,
                gaps=len(gaps),
                outliers=len(outliers),
            )
        
        return DataQualityReport(
            symbol=bars[0].symbol if bars else "",
            timeframe=bars[0].timeframe if bars else "",
            expected_bars=expected_count,
            actual_bars=actual_count,
            missing_bars=missing,
            completeness_percent=Decimal(str(completeness)),
            gaps_detected=len(gaps),
            outliers_detected=len(outliers),
            duplicates_removed=len(duplicates),
            quality_score=quality_score,
            is_acceptable=is_acceptable,
        )
    
    def _detect_gaps(self, bars: List[OHLCVBar]) -> List[Dict]:
        """Обнаружить gaps в time series."""
        gaps = []
        
        for i in range(1, len(bars)):
            expected_time = bars[i-1].time + self._get_timeframe_delta(bars[i].timeframe)
            actual_time = bars[i].time
            
            if actual_time > expected_time:
                gap_duration = (actual_time - expected_time).total_seconds() / 3600  # hours
                gaps.append({
                    "start": bars[i-1].time,
                    "end": bars[i].time,
                    "duration_hours": gap_duration,
                })
        
        return gaps
    
    def _detect_outliers(self, bars: List[OHLCVBar]) -> List[Dict]:
        """Обнаружить outliers (аномальные значения)."""
        outliers = []
        
        # Calculate rolling mean и std
        prices = [float(bar.close) for bar in bars]
        window = 20
        
        for i in range(window, len(bars)):
            window_prices = prices[i-window:i]
            mean = np.mean(window_prices)
            std = np.std(window_prices)
            
            current_price = prices[i]
            
            # Outlier если > 3 standard deviations от mean
            if abs(current_price - mean) > 3 * std:
                outliers.append({
                    "time": bars[i].time,
                    "price": current_price,
                    "mean": mean,
                    "std": std,
                    "z_score": (current_price - mean) / std,
                })
        
        return outliers
```

### Обработка ошибок:

#### 1. Gap filling:

```python
class HistoricalDataManager:
    async def fill_data_gaps(
        self,
        symbol: str,
        timeframe: str,
    ) -> int:
        """
        Заполнить gaps в исторических данных.
        
        Процесс:
        1. Detect gaps в существующих данных
        2. Download missing data от exchange
        3. Validate и insert
        """
        # Get existing data
        existing_bars = await self.database.query(
            """
            SELECT time FROM ohlcv_bars
            WHERE symbol = $1 AND timeframe = $2
            ORDER BY time ASC
            """,
            symbol, timeframe,
        )
        
        if len(existing_bars) < 2:
            logger.info("Недостаточно данных для gap detection")
            return 0
        
        # Detect gaps
        gaps = []
        timeframe_delta = self._get_timeframe_delta(timeframe)
        
        for i in range(1, len(existing_bars)):
            expected = existing_bars[i-1] + timeframe_delta
            actual = existing_bars[i]
            
            if actual > expected:
                gaps.append((expected, actual))
        
        if not gaps:
            logger.info("Gaps не обнаружены")
            return 0
        
        logger.info(
            "📊 Gaps обнаружены",
            count=len(gaps),
            total_missing_hours=sum((end - start).total_seconds() / 3600 for start, end in gaps),
        )
        
        # Fill each gap
        total_filled = 0
        
        for gap_start, gap_end in gaps:
            filled = await self.download_historical_data(
                symbol=symbol,
                timeframe=timeframe,
                start_date=gap_start.date(),
                end_date=gap_end.date(),
            )
            total_filled += filled
        
        logger.info(f"✅ Gaps заполнены, bars added: {total_filled}")
        
        return total_filled
```

---

## ⚠️ КРИТИЧЕСКИЕ ОГРАНИЧЕНИЯ ФАЗЫ 19

**✅ Что реализовано:**
- Multi-source data collection (Bybit, OKX, Binance)
- TimescaleDB storage (compression, retention)
- Data validation (gaps, outliers, duplicates)
- Automated maintenance (fill gaps, cleanup)
- Fast queries (hypertables, indexes)
- Continuous aggregates (pre-computed)

**❌ Что НЕ реализовано:**
- Real-time tick data (только OHLCV bars)
- Orderbook snapshots (historical L2 data)
- Trade data (individual trades)
- Alternative data sources (sentiment, on-chain)
- Data quality ML models

---

## 🚀 ПРОИЗВОДИТЕЛЬНОСТЬ

### Критические требования:

```
Операция                         Latency Target
────────────────────────────────────────────────────────
query_1_year_1m_bars()           <2s (525,600 bars)
download_1_year_data()           <300s (5 min)
validate_data()                  <10s
fill_gaps()                      <60s per gap
────────────────────────────────────────────────────────
```

---

## ФАЙЛОВАЯ СТРУКТУРА

```
CRYPTOTEHNOLOG/
├── src/
│   └── historical_data/
│       ├── __init__.py
│       ├── manager.py                    # HistoricalDataManager
│       ├── downloader.py                 # ExchangeDataDownloader
│       ├── validator.py                  # DataValidator
│       ├── storage.py                    # TimescaleDB integration
│       └── models.py                     # DataQualityReport
│
└── tests/
    ├── unit/
    │   ├── test_validator.py
    │   └── test_downloader.py
    └── integration/
        └── test_historical_data.py
```

---

## ACCEPTANCE CRITERIA

### Data Collection
- [ ] Multi-source downloads (Bybit, OKX, Binance)
- [ ] Batch processing (1000 bars/request)
- [ ] Rate limiting (respect exchange limits)
- [ ] Automated daily sync

### Data Quality
- [ ] Gap detection
- [ ] Outlier detection
- [ ] Duplicate removal
- [ ] OHLC consistency checks
- [ ] Quality score > 95%

### Storage
- [ ] TimescaleDB hypertables
- [ ] Compression (70% savings)
- [ ] Retention policies (3 years)
- [ ] Fast queries (<2s для 1 year)

### Maintenance
- [ ] Automated gap filling
- [ ] Continuous aggregates
- [ ] Backup to S3

---

## ИТОГОВАЯ ГОТОВНОСТЬ

**Фаза 19: Historical Data Manager** готова к реализации! 🚀

# AI ПРОМТ: ФАЗА 21 - ML RISK MODELS

## КОНТЕКСТ

Вы — Senior ML Engineer, специализирующийся на machine learning для trading, risk prediction, и quantitative finance.

**Фазы 0-20 завершены.** Доступны:
- Полная торговая система (20 фаз)
- Production deployment на Kubernetes
- Historical data (3 years, quality validated)
- Advanced execution algorithms
- Все компоненты работают

**Текущая задача:** Реализовать production-ready ML Risk Models для прогнозирования drawdown, volatility prediction, price forecasting, и risk-adjusted position sizing.

---

## ⚠️ КРИТИЧЕСКИ ВАЖНО: РУССКИЙ ЯЗЫК

**ВСЕ** комментарии, docstrings, логи должны быть **НА РУССКОМ ЯЗЫКЕ**.

### Python docstrings — ТОЛЬКО русский:

```python
class MLRiskEngine:
    """
    ML-движок для прогнозирования рисков и оптимизации позиций.
    
    Особенности:
    - Drawdown prediction (LSTM neural networks)
    - Volatility forecasting (GARCH + ML ensemble)
    - Price prediction (Transformer models)
    - Risk-adjusted sizing (reinforcement learning)
    - Regime detection (unsupervised clustering)
    - Anomaly detection (Isolation Forest)
    - Feature engineering (100+ technical/fundamental features)
    - Online learning (incremental model updates)
    """
    
    async def predict_next_day_drawdown(
        self,
        symbol: str,
        current_portfolio_state: PortfolioState,
    ) -> DrawdownPrediction:
        """
        Предсказать максимальный drawdown на следующий день.
        
        Аргументы:
            symbol: Торговая пара
            current_portfolio_state: Текущее состояние портфеля
        
        Возвращает:
            DrawdownPrediction с вероятностями разных уровней DD
        
        Модель:
        - LSTM (3 layers, 128 units)
        - Input: последние 30 дней OHLCV + portfolio metrics
        - Output: probability distribution для DD ranges
        
        Features (40 total):
        - Price: returns, volatility, ATR
        - Volume: volume profile, OBV
        - Portfolio: exposure, current DD, correlation
        - Market: VIX, BTC dominance, funding rates
        
        Training:
        - Dataset: 3 years historical (550+ samples per symbol)
        - Validation: walk-forward (20% test)
        - Loss: MSE на predicted vs actual DD
        - Metric: R² > 0.6 считается acceptable
        """
        pass
```

### Логи — ТОЛЬКО русский:

```python
logger.info("🤖 ML prediction запущен", model="drawdown_lstm", symbol="BTC/USDT")
logger.debug("Features extracted", count=40, timespan="30_days")
logger.info("✅ Prediction готов", predicted_dd=8.5, confidence=0.82, actual_range="5-10%")
logger.warning("⚠️  Low confidence prediction", confidence=0.45, threshold=0.70)
```

---

## 🔗 КОМПОНЕНТНЫЕ ИНТЕГРАЦИИ

### Роль компонента в системы:
ML Risk Engine — предсказание будущих рисков используя machine learning. Прогнозирует drawdown, volatility, prices для улучшения risk management и position sizing. Дополняет классический Risk Engine (Фаза 5) ML-based insights.

### Входящие зависимости:

#### 1. **Historical Data Manager (Фаза 19)** → training data
   - Query: 3 years OHLCV для обучения моделей
   - Критичность: HIGH

#### 2. **Portfolio Governor (Фаза 9)** → portfolio state
   - Current: exposure, positions, P&L
   - Критичность: HIGH

#### 3. **Risk Engine (Фаза 5)** → classical metrics
   - Combine: ML predictions + classical risk
   - Критичность: MEDIUM

### Исходящие зависимости:

#### 1. → PostgreSQL (model storage + predictions)
   - **Table: `ml_models`**
     ```sql
     CREATE TABLE ml_models (
         model_id SERIAL PRIMARY KEY,
         model_name VARCHAR(50) NOT NULL,
         model_type VARCHAR(20) NOT NULL,  -- LSTM, GARCH, RF, etc
         
         trained_at TIMESTAMPTZ NOT NULL,
         training_samples INTEGER,
         
         -- Performance metrics
         r2_score NUMERIC(5, 4),
         mae NUMERIC(10, 4),
         rmse NUMERIC(10, 4),
         
         -- Model artifacts (serialized)
         model_weights BYTEA,
         scaler_params JSONB,
         
         metadata JSONB
     );
     ```

   - **Table: `ml_predictions`**
     ```sql
     CREATE TABLE ml_predictions (
         prediction_id SERIAL PRIMARY KEY,
         created_at TIMESTAMPTZ NOT NULL,
         
         model_id INTEGER REFERENCES ml_models(model_id),
         symbol VARCHAR(20),
         
         prediction_type VARCHAR(20),  -- DRAWDOWN, VOLATILITY, PRICE
         
         -- Predictions
         predicted_value NUMERIC(20, 8),
         confidence NUMERIC(5, 4),
         
         -- Actual (заполняется позже для validation)
         actual_value NUMERIC(20, 8),
         actual_recorded_at TIMESTAMPTZ,
         
         prediction_error NUMERIC(10, 4)  -- abs(predicted - actual)
     );
     ```

#### 2. → Risk Engine (Фаза 5)
   - Input: ML-predicted volatility/drawdown
   - Adjust: Position sizing based на ML forecasts

### Контракты данных:

#### Drawdown Prediction Model:

```python
import torch
import torch.nn as nn

class DrawdownLSTM(nn.Module):
    """
    LSTM model для предсказания drawdown.
    
    Architecture:
    - Input: (batch, sequence_length=30, features=40)
    - LSTM layers: 3 layers, 128 hidden units
    - Output: (batch, 1) — predicted max DD next day
    """
    
    def __init__(self, input_size=40, hidden_size=128, num_layers=3):
        super(DrawdownLSTM, self).__init__()
        
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=0.2,
        )
        
        self.fc = nn.Sequential(
            nn.Linear(hidden_size, 64),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(64, 1),
            nn.Sigmoid(),  # Output 0-1 (DD as percentage)
        )
    
    def forward(self, x):
        # x shape: (batch, seq_len, features)
        lstm_out, _ = self.lstm(x)
        
        # Take last timestep output
        last_output = lstm_out[:, -1, :]
        
        # Predict DD
        prediction = self.fc(last_output)
        
        return prediction

class DrawdownPredictor:
    """Wrapper для DrawdownLSTM model."""
    
    def __init__(self, model_path: str = None):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = DrawdownLSTM().to(self.device)
        
        if model_path:
            self.load_model(model_path)
        
        self.scaler = StandardScaler()
    
    async def train(
        self,
        symbol: str,
        lookback_days: int = 30,
    ):
        """
        Обучить модель на исторических данных.
        
        Процесс:
        1. Extract features (3 years data)
        2. Create sequences (sliding window 30 days)
        3. Split train/validation (80/20 walk-forward)
        4. Train LSTM
        5. Validate
        6. Save model
        """
        # Get historical data
        bars = await self.data_manager.get_historical_bars(
            symbol=symbol,
            timeframe="1d",
            start_date=date.today() - timedelta(days=3*365),
            end_date=date.today(),
        )
        
        # Extract features
        features = self._extract_features(bars)
        
        # Create sequences
        X, y = self._create_sequences(features, lookback=lookback_days)
        
        # Split (walk-forward)
        split_idx = int(len(X) * 0.8)
        X_train, X_val = X[:split_idx], X[split_idx:]
        y_train, y_val = y[:split_idx], y[split_idx:]
        
        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train.reshape(-1, X_train.shape[-1]))
        X_train_scaled = X_train_scaled.reshape(X_train.shape)
        
        X_val_scaled = self.scaler.transform(X_val.reshape(-1, X_val.shape[-1]))
        X_val_scaled = X_val_scaled.reshape(X_val.shape)
        
        # Train
        self._train_model(X_train_scaled, y_train, X_val_scaled, y_val)
        
        # Evaluate
        r2 = self._evaluate(X_val_scaled, y_val)
        
        logger.info(
            "✅ Model trained",
            symbol=symbol,
            train_samples=len(X_train),
            val_samples=len(X_val),
            r2_score=r2,
        )
        
        return r2
    
    def _extract_features(self, bars: List[OHLCVBar]) -> np.ndarray:
        """
        Extract 40 features от OHLCV bars.
        
        Features:
        - Price: returns (1d, 7d, 30d), volatility (7d, 30d), ATR
        - Volume: volume_change, OBV
        - Technical: RSI, MACD, Bollinger %B
        - Market: correlation с BTC, market cap dominance
        """
        features = []
        
        for i in range(len(bars)):
            if i < 30:  # Need 30 days history
                continue
            
            window = bars[i-30:i]
            
            # Price features
            returns_1d = (window[-1].close - window[-2].close) / window[-2].close
            returns_7d = (window[-1].close - window[-8].close) / window[-8].close
            returns_30d = (window[-1].close - window[-31].close) / window[-31].close
            
            volatility_7d = np.std([b.close for b in window[-7:]])
            volatility_30d = np.std([b.close for b in window])
            
            atr = self._calculate_atr(window)
            
            # Volume features
            volume_change = (window[-1].volume - window[-2].volume) / window[-2].volume
            obv = self._calculate_obv(window)
            
            # Technical indicators
            rsi = self._calculate_rsi(window)
            macd = self._calculate_macd(window)
            bb_percent = self._calculate_bollinger_percent(window)
            
            # Combine
            feature_vector = np.array([
                returns_1d, returns_7d, returns_30d,
                volatility_7d, volatility_30d,
                atr, volume_change, obv,
                rsi, macd, bb_percent,
                # ... 40 features total
            ])
            
            features.append(feature_vector)
        
        return np.array(features)
    
    async def predict(
        self,
        symbol: str,
        current_state: PortfolioState,
    ) -> DrawdownPrediction:
        """
        Предсказать drawdown на следующий день.
        """
        # Get recent 30 days
        recent_bars = await self.data_manager.get_historical_bars(
            symbol=symbol,
            timeframe="1d",
            start_date=date.today() - timedelta(days=35),
            end_date=date.today(),
        )
        
        # Extract features
        features = self._extract_features(recent_bars)
        recent_features = features[-30:]  # Last 30 days
        
        # Scale
        features_scaled = self.scaler.transform(recent_features)
        
        # Prepare input
        x = torch.FloatTensor(features_scaled).unsqueeze(0).to(self.device)
        
        # Predict
        self.model.eval()
        with torch.no_grad():
            prediction = self.model(x)
            predicted_dd = prediction.item() * 100  # Convert to percentage
        
        # Confidence (based на prediction variance от ensemble)
        confidence = self._calculate_confidence(prediction)
        
        logger.info(
            "🤖 Drawdown prediction",
            symbol=symbol,
            predicted_dd=predicted_dd,
            confidence=confidence,
        )
        
        return DrawdownPrediction(
            symbol=symbol,
            predicted_drawdown_percent=Decimal(str(predicted_dd)),
            confidence=Decimal(str(confidence)),
            prediction_date=date.today() + timedelta(days=1),
        )
```

#### Volatility Forecasting (GARCH):

```python
from arch import arch_model

class VolatilityForecaster:
    """
    GARCH model для предсказания volatility.
    """
    
    async def forecast_volatility(
        self,
        symbol: str,
        horizon_days: int = 5,
    ) -> VolatilityForecast:
        """
        Forecast volatility на следующие N дней.
        
        Model: GARCH(1,1)
        - Широко используется в finance
        - Captures volatility clustering
        - Good short-term forecasts
        """
        # Get returns
        bars = await self.data_manager.get_historical_bars(
            symbol=symbol,
            timeframe="1d",
            start_date=date.today() - timedelta(days=365),
            end_date=date.today(),
        )
        
        returns = [(bars[i].close - bars[i-1].close) / bars[i-1].close * 100
                   for i in range(1, len(bars))]
        
        # Fit GARCH(1,1)
        model = arch_model(returns, vol='Garch', p=1, q=1)
        fitted = model.fit(disp='off')
        
        # Forecast
        forecast = fitted.forecast(horizon=horizon_days)
        predicted_variance = forecast.variance.values[-1, :]
        predicted_volatility = np.sqrt(predicted_variance)
        
        logger.info(
            "📊 Volatility forecast",
            symbol=symbol,
            horizon_days=horizon_days,
            current_vol=predicted_volatility[0],
            avg_forecast=np.mean(predicted_volatility),
        )
        
        return VolatilityForecast(
            symbol=symbol,
            horizon_days=horizon_days,
            forecasted_volatility=predicted_volatility,
            confidence_interval=(
                predicted_volatility * 0.8,
                predicted_volatility * 1.2,
            ),
        )
```

---

## ⚠️ КРИТИЧЕСКИЕ ОГРАНИЧЕНИЯ ФАЗЫ 21

**✅ Что реализовано:**
- Drawdown prediction (LSTM)
- Volatility forecasting (GARCH)
- Feature engineering (40+ features)
- Model training/validation (walk-forward)
- Prediction storage (audit trail)

**❌ Что НЕ реализовано:**
- Reinforcement learning (RL agents для position sizing)
- Ensemble models (multiple models voting)
- Real-time model updating (online learning)
- Explainable AI (SHAP values)
- Adversarial robustness

---

## 🚀 ПРОИЗВОДИТЕЛЬНОСТЬ

### Критические требования:

```
Операция                         Latency Target
────────────────────────────────────────────────────────
predict_drawdown()               <500ms
forecast_volatility()            <1s
train_model()                    <10min (3 years data)
────────────────────────────────────────────────────────
```

---

## ФАЙЛОВАЯ СТРУКТУРА

```
CRYPTOTEHNOLOG/
├── src/
│   └── ml_risk/
│       ├── __init__.py
│       ├── engine.py                     # MLRiskEngine
│       ├── models/
│       │   ├── drawdown_lstm.py          # DrawdownLSTM
│       │   ├── volatility_garch.py       # GARCH model
│       │   └── price_transformer.py      # Transformer
│       ├── features.py                   # Feature engineering
│       ├── training.py                   # Training pipeline
│       └── inference.py                  # Prediction serving
│
└── tests/
    ├── unit/
    │   └── test_models.py
    └── integration/
        └── test_ml_risk.py
```

---

## ACCEPTANCE CRITERIA

### Models
- [ ] Drawdown LSTM (R² > 0.6)
- [ ] Volatility GARCH
- [ ] Feature extraction (40+ features)

### Training
- [ ] Walk-forward validation
- [ ] Training <10min
- [ ] Model persistence

### Inference
- [ ] Prediction <500ms
- [ ] Confidence scores
- [ ] Prediction logging

---

## ИТОГОВАЯ ГОТОВНОСТЬ

**Фаза 21: ML Risk Models** готова к реализации! 🚀

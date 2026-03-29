# AI ПРОМТ: ФАЗА 22 - WEB UI DASHBOARD

## КОНТЕКСТ

Вы — Senior Full-Stack Engineer, специализирующийся на React, real-time dashboards, WebSocket streaming, и trading UX.

**Фазы 0-21 завершены.** Это ФИНАЛЬНАЯ фаза проекта CRYPTOTEHNOLOG.
Полная ML-powered trading система с 21 фазой backend готова.

**Текущая задача:** Реализовать production-ready Web UI Dashboard — React-приложение с real-time charts, portfolio tracking, strategy management, risk monitoring, и full system control.

---

## ⚠️ КРИТИЧЕСКИ ВАЖНО: РУССКИЙ ЯЗЫК

**ВСЕ** комментарии, JSDoc, логи должны быть **НА РУССКОМ ЯЗЫКЕ**.

### React components — ТОЛЬКО русский JSDoc:

```tsx
/**
 * Главный Dashboard компонент.
 *
 * Отображает:
 * - Real-time equity curve (WebSocket)
 * - Open positions с live P&L
 * - Active orders
 * - Risk metrics (exposure, drawdown)
 * - Recent signals
 * - System health status
 *
 * @component
 */
export const TradingDashboard: React.FC = () => {
    // ...
};

/**
 * Хук для WebSocket подключения к бэкенду.
 *
 * Подписывается на:
 * - BAR_COMPLETED — обновление charts
 * - POSITION_OPENED / POSITION_CLOSED — portfolio updates
 * - ORDER_FILLED — order status
 * - TRADING_SIGNAL — signal notifications
 * - SYSTEM_HEALTH — health metrics
 *
 * @param url WebSocket URL
 * @returns Текущие данные и статус подключения
 */
export const useTradingWebSocket = (url: string) => {
    // ...
};
```

### Logs — ТОЛЬКО русский:

```typescript
console.info("📊 Dashboard подключен", { url, status: "connected" });
console.warn("⚠️  WebSocket переподключение", { attempt: 3, delay: "5s" });
console.error("❌ Ошибка загрузки данных", { endpoint: "/api/positions", error });
```

---

## 🔗 КОМПОНЕНТНЫЕ ИНТЕГРАЦИИ

### Роль компонента в системе:
Web UI Dashboard — визуальный интерфейс управления всей торговой платформой. Real-time отображение trading activity, portfolio state, risk metrics, ML predictions. Предоставляет операторам полный контроль через браузер — от открытия позиций до активации kill switch.

### Backend API (REST + WebSocket):

#### 1. REST API (FastAPI backend)

```python
# FastAPI router для Dashboard API
from fastapi import FastAPI, WebSocket

app = FastAPI(title="CRYPTOTEHNOLOG Dashboard API")

# ─── Portfolio ───────────────────────────────────
@app.get("/api/portfolio/state")
async def get_portfolio_state() -> PortfolioStateDTO:
    """Текущее состояние портфеля."""

@app.get("/api/portfolio/equity-history")
async def get_equity_history(
    period: str = "30d",  # 1d, 7d, 30d, 90d, 1y, all
) -> List[EquityPoint]:
    """История equity curve."""

@app.get("/api/portfolio/positions")
async def get_positions(
    status: str = "open",  # open, closed, all
    limit: int = 100,
) -> List[PositionDTO]:
    """Список позиций."""

# ─── Trades & Orders ─────────────────────────────
@app.get("/api/trades")
async def get_trades(
    strategy: Optional[str] = None,
    symbol: Optional[str] = None,
    limit: int = 100,
) -> List[TradeDTO]:
    """История сделок."""

@app.get("/api/orders")
async def get_orders(
    status: str = "active",  # active, all
) -> List[OrderDTO]:
    """Список ордеров."""

# ─── Signals ─────────────────────────────────────
@app.get("/api/signals/recent")
async def get_recent_signals(limit: int = 20) -> List[SignalDTO]:
    """Последние торговые сигналы."""

# ─── Risk ─────────────────────────────────────────
@app.get("/api/risk/metrics")
async def get_risk_metrics() -> RiskMetricsDTO:
    """Текущие риск-метрики."""

@app.get("/api/risk/ml-predictions")
async def get_ml_predictions() -> MLPredictionsDTO:
    """ML predictions (drawdown, volatility)."""

# ─── Performance ─────────────────────────────────
@app.get("/api/performance/metrics")
async def get_performance_metrics(
    period: str = "30d",
    strategy: Optional[str] = None,
) -> PerformanceMetricsDTO:
    """Performance metrics (Sharpe, Win Rate, etc)."""

@app.get("/api/performance/strategies")
async def get_strategies_comparison() -> List[StrategyPerformanceDTO]:
    """Сравнение стратегий."""

# ─── Control ─────────────────────────────────────
@app.post("/api/control/kill-switch")
async def trigger_kill_switch(
    reason: str,
    severity: str,
) -> ActionResultDTO:
    """Активировать kill switch."""

@app.post("/api/control/strategy/{strategy_id}/toggle")
async def toggle_strategy(strategy_id: str) -> ActionResultDTO:
    """Включить/выключить стратегию."""

# ─── System Health ────────────────────────────────
@app.get("/api/system/health")
async def get_system_health() -> SystemHealthDTO:
    """Статус всех компонентов системы."""

# ─── WebSocket ────────────────────────────────────
@app.websocket("/ws/trading")
async def trading_websocket(websocket: WebSocket):
    """
    Real-time WebSocket для Dashboard.
    
    Публикует:
    - equity_update: каждый бар
    - position_update: при изменении позиции
    - order_update: при изменении ордера
    - signal: новый торговый сигнал
    - risk_alert: превышение лимитов
    - system_health: каждые 30 секунд
    - kill_switch: при активации
    """
```

#### 2. DTO контракты (Python → TypeScript):

```python
# Python DTOs (FastAPI)
from pydantic import BaseModel

class PortfolioStateDTO(BaseModel):
    """Состояние портфеля для Dashboard."""
    timestamp: datetime
    equity_usd: Decimal
    cash_balance_usd: Decimal
    open_positions_count: int
    total_exposure_percent: Decimal
    unrealized_pnl_usd: Decimal
    daily_return_percent: Decimal
    current_drawdown_percent: Decimal

class PositionDTO(BaseModel):
    """Позиция для Dashboard."""
    position_id: str
    symbol: str
    direction: str         # LONG или SHORT
    entry_price: Decimal
    current_price: Decimal
    quantity: Decimal
    size_usd: Decimal
    unrealized_pnl_usd: Decimal
    unrealized_pnl_percent: Decimal
    stop_loss: Optional[Decimal]
    take_profit: Optional[Decimal]
    strategy: str
    opened_at: datetime
    holding_time_hours: float

class RiskMetricsDTO(BaseModel):
    """Риск-метрики для Dashboard."""
    total_exposure_percent: Decimal
    current_drawdown_percent: Decimal
    max_drawdown_percent: Decimal
    win_rate: Decimal
    profit_factor: Decimal
    sharpe_ratio: Decimal
    positions_count: int
    correlation_max: Decimal
    circuit_breaker_status: str  # NORMAL, WARNING, CRITICAL
    ml_drawdown_prediction: Optional[Decimal]
    ml_volatility_forecast: Optional[Decimal]
```

### Frontend React Components:

#### Main Dashboard Layout:

```tsx
// src/components/Dashboard.tsx
import React, { useState, useEffect } from "react";
import { EquityChart } from "./charts/EquityChart";
import { PositionsTable } from "./portfolio/PositionsTable";
import { RiskPanel } from "./risk/RiskPanel";
import { SignalFeed } from "./signals/SignalFeed";
import { SystemHealth } from "./system/SystemHealth";
import { useTradingWebSocket } from "../hooks/useTradingWebSocket";
import { KillSwitchButton } from "./controls/KillSwitchButton";

/**
 * Главный торговый Dashboard.
 *
 * Layout:
 * ┌─────────────────────────────────────────────────┐
 * │  Header: Equity, Daily P&L, Status              │
 * ├─────────────────────────────────────────────────┤
 * │  Equity Chart (70%)  │  Risk Panel (30%)        │
 * ├─────────────────────────────────────────────────┤
 * │  Positions Table                                 │
 * ├─────────────────────────────────────────────────┤
 * │  Signal Feed (50%)  │  System Health (50%)      │
 * └─────────────────────────────────────────────────┘
 */
export const TradingDashboard: React.FC = () => {
    const { data, connected, error } = useTradingWebSocket(
        process.env.REACT_APP_WS_URL || "ws://localhost:8080/ws/trading"
    );

    if (!connected) {
        return <ConnectionStatus error={error} />;
    }

    return (
        <div className="dashboard-container">
            {/* Header */}
            <DashboardHeader
                equity={data.portfolio?.equity_usd}
                dailyReturn={data.portfolio?.daily_return_percent}
                status={data.systemHealth?.overall_status}
            />

            {/* Main Content */}
            <div className="dashboard-main">
                {/* Left: Charts */}
                <div className="dashboard-charts">
                    <EquityChart
                        data={data.equityHistory}
                        realtimePoint={data.portfolio}
                    />
                    <PositionsTable
                        positions={data.positions}
                        onClosePosition={(id) => handleClosePosition(id)}
                    />
                </div>

                {/* Right: Risk & Signals */}
                <div className="dashboard-sidebar">
                    <RiskPanel
                        metrics={data.riskMetrics}
                        mlPredictions={data.mlPredictions}
                    />
                    <SignalFeed
                        signals={data.recentSignals}
                    />
                </div>
            </div>

            {/* Footer: System Health */}
            <div className="dashboard-footer">
                <SystemHealth health={data.systemHealth} />
                <KillSwitchButton
                    onActivate={(reason) => handleKillSwitch(reason)}
                />
            </div>
        </div>
    );
};
```

#### Real-time Equity Chart:

```tsx
// src/components/charts/EquityChart.tsx
import React, { useMemo } from "react";
import {
    AreaChart,
    Area,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    ReferenceLine,
} from "recharts";

/**
 * Real-time equity curve chart.
 *
 * Features:
 * - Continuous updates через WebSocket
 * - Period selector (1d, 7d, 30d, 90d)
 * - Benchmark overlay (BTC buy-and-hold)
 * - Drawdown shading (красная зона ниже peak)
 * - Tooltip с детализацией
 */
export const EquityChart: React.FC<EquityChartProps> = ({
    data,
    realtimePoint,
    period = "30d",
}) => {
    // Добавить real-time точку к историческим данным
    const chartData = useMemo(() => {
        if (!realtimePoint) return data;
        return [...data, {
            date: new Date().toISOString(),
            equity: realtimePoint.equity_usd,
            drawdown: realtimePoint.current_drawdown_percent,
        }];
    }, [data, realtimePoint]);

    // Рассчитать peak для drawdown shading
    const peakEquity = useMemo(() => {
        return Math.max(...chartData.map(d => d.equity));
    }, [chartData]);

    return (
        <div className="equity-chart-container">
            {/* Period selector */}
            <PeriodSelector
                periods={["1d", "7d", "30d", "90d", "1y", "all"]}
                selected={period}
                onChange={onPeriodChange}
            />

            {/* Chart */}
            <ResponsiveContainer width="100%" height={300}>
                <AreaChart data={chartData}>
                    <defs>
                        {/* Gradient для equity curve */}
                        <linearGradient id="equityGradient" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                            <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                        </linearGradient>

                        {/* Красный gradient для drawdown зоны */}
                        <linearGradient id="drawdownGradient" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#ef4444" stopOpacity={0.2} />
                            <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                        </linearGradient>
                    </defs>

                    <CartesianGrid strokeDasharray="3 3" stroke="#374151" />

                    <XAxis
                        dataKey="date"
                        tickFormatter={(val) => formatDate(val, period)}
                        stroke="#9ca3af"
                    />

                    <YAxis
                        tickFormatter={(val) => `$${(val / 1000).toFixed(1)}k`}
                        stroke="#9ca3af"
                    />

                    {/* Peak reference line */}
                    <ReferenceLine
                        y={peakEquity}
                        stroke="#6b7280"
                        strokeDasharray="4 4"
                        label="Peak"
                    />

                    {/* Equity Area */}
                    <Area
                        type="monotone"
                        dataKey="equity"
                        stroke="#10b981"
                        strokeWidth={2}
                        fill="url(#equityGradient)"
                    />

                    <Tooltip
                        formatter={(value, name) => [
                            `$${Number(value).toLocaleString()}`,
                            name === "equity" ? "Equity" : "Drawdown"
                        ]}
                        contentStyle={{
                            backgroundColor: "#1f2937",
                            border: "1px solid #374151",
                        }}
                    />
                </AreaChart>
            </ResponsiveContainer>
        </div>
    );
};
```

#### Positions Table с Live P&L:

```tsx
// src/components/portfolio/PositionsTable.tsx

/**
 * Таблица открытых позиций с real-time P&L.
 *
 * Колонки:
 * - Symbol (с иконкой direction)
 * - Entry Price
 * - Current Price (live update)
 * - Quantity + Size USD
 * - Unrealized P&L (цвет: зеленый/красный)
 * - SL / TP
 * - Duration
 * - Strategy
 * - Actions (Close button)
 */
export const PositionsTable: React.FC<PositionsTableProps> = ({
    positions,
    onClosePosition,
}) => {
    return (
        <div className="positions-table-container">
            <div className="table-header">
                <h3>📊 Открытые позиции ({positions.length})</h3>
                <span className="total-pnl">
                    Total P&L: {formatPnL(totalUnrealizedPnL)}
                </span>
            </div>

            <table className="positions-table">
                <thead>
                    <tr>
                        <th>Symbol</th>
                        <th>Entry</th>
                        <th>Current</th>
                        <th>Size (USD)</th>
                        <th>P&L</th>
                        <th>SL / TP</th>
                        <th>Duration</th>
                        <th>Strategy</th>
                        <th>Action</th>
                    </tr>
                </thead>
                <tbody>
                    {positions.map((pos) => (
                        <PositionRow
                            key={pos.position_id}
                            position={pos}
                            onClose={() => onClosePosition(pos.position_id)}
                        />
                    ))}
                </tbody>
            </table>
        </div>
    );
};

const PositionRow: React.FC<{ position: PositionDTO; onClose: () => void }> = ({
    position,
    onClose,
}) => {
    const pnlColor = position.unrealized_pnl_usd >= 0 ? "text-green" : "text-red";

    return (
        <tr className="position-row">
            <td>
                {/* Direction badge */}
                <span className={`direction-badge ${position.direction.toLowerCase()}`}>
                    {position.direction === "LONG" ? "▲" : "▼"}
                </span>
                {position.symbol}
            </td>
            <td>${formatPrice(position.entry_price)}</td>
            <td className="live-price">
                ${formatPrice(position.current_price)}
            </td>
            <td>${formatUSD(position.size_usd)}</td>
            <td className={pnlColor}>
                {formatPnL(position.unrealized_pnl_usd)}
                <span className="pnl-percent">
                    ({formatPercent(position.unrealized_pnl_percent)})
                </span>
            </td>
            <td>
                <span className="stop-loss">{formatPrice(position.stop_loss)}</span>
                <span className="separator"> / </span>
                <span className="take-profit">{formatPrice(position.take_profit)}</span>
            </td>
            <td>{formatDuration(position.holding_time_hours)}</td>
            <td>
                <span className="strategy-badge">{position.strategy}</span>
            </td>
            <td>
                <button
                    className="close-btn"
                    onClick={onClose}
                    title="Закрыть позицию"
                >
                    ✕ Close
                </button>
            </td>
        </tr>
    );
};
```

#### Risk Panel с ML Predictions:

```tsx
// src/components/risk/RiskPanel.tsx

/**
 * Панель риск-метрик с ML predictions.
 *
 * Секции:
 * 1. Current Risk: Exposure, Drawdown, Positions
 * 2. ML Predictions: predicted DD, volatility forecast
 * 3. Circuit Breakers: status, thresholds
 */
export const RiskPanel: React.FC<RiskPanelProps> = ({
    metrics,
    mlPredictions,
}) => {
    const riskLevel = getRiskLevel(metrics);  // LOW, MEDIUM, HIGH, CRITICAL

    return (
        <div className={`risk-panel risk-level-${riskLevel.toLowerCase()}`}>
            <h3>⚠️ Risk Dashboard</h3>

            {/* Risk Level Badge */}
            <RiskLevelBadge level={riskLevel} />

            {/* Current Metrics */}
            <section className="risk-current">
                <MetricRow
                    label="Exposure"
                    value={`${metrics.total_exposure_percent}%`}
                    threshold={80}
                    current={metrics.total_exposure_percent}
                />
                <MetricRow
                    label="Drawdown"
                    value={`${metrics.current_drawdown_percent}%`}
                    threshold={20}
                    current={metrics.current_drawdown_percent}
                />
                <MetricRow
                    label="Sharpe (30d)"
                    value={metrics.sharpe_ratio.toFixed(2)}
                />
                <MetricRow
                    label="Win Rate"
                    value={`${(metrics.win_rate * 100).toFixed(1)}%`}
                />
            </section>

            {/* ML Predictions */}
            {mlPredictions && (
                <section className="risk-ml">
                    <h4>🤖 ML Predictions</h4>
                    <MLPredictionWidget
                        label="Predicted DD (tomorrow)"
                        value={mlPredictions.predicted_drawdown}
                        confidence={mlPredictions.drawdown_confidence}
                    />
                    <MLPredictionWidget
                        label="Volatility (5d)"
                        value={mlPredictions.volatility_forecast}
                        confidence={mlPredictions.volatility_confidence}
                    />
                </section>
            )}

            {/* Circuit Breakers */}
            <section className="circuit-breakers">
                <h4>🔌 Circuit Breakers</h4>
                <CircuitBreakerStatus status={metrics.circuit_breaker_status} />
            </section>
        </div>
    );
};
```

#### Kill Switch Button:

```tsx
// src/components/controls/KillSwitchButton.tsx

/**
 * Кнопка Kill Switch с confirmation dialog.
 *
 * Требует подтверждения от оператора перед активацией.
 * Только для авторизованных пользователей.
 */
export const KillSwitchButton: React.FC<KillSwitchProps> = ({ onActivate }) => {
    const [showDialog, setShowDialog] = useState(false);
    const [reason, setReason] = useState("");

    const handleConfirm = async () => {
        if (!reason.trim()) return;

        await onActivate(reason);
        setShowDialog(false);
    };

    return (
        <>
            {/* Emergency Stop Button */}
            <button
                className="kill-switch-btn"
                onClick={() => setShowDialog(true)}
            >
                🔴 EMERGENCY STOP
            </button>

            {/* Confirmation Dialog */}
            {showDialog && (
                <div className="kill-switch-dialog">
                    <div className="dialog-content">
                        <h2>⚠️ Подтвердите аварийную остановку</h2>
                        <p>
                            Это действие немедленно:
                            <ul>
                                <li>Отменит все pending ордера</li>
                                <li>Закроет все открытые позиции (market orders)</li>
                                <li>Заморозит систему</li>
                            </ul>
                        </p>
                        <textarea
                            placeholder="Укажите причину активации..."
                            value={reason}
                            onChange={(e) => setReason(e.target.value)}
                            rows={3}
                        />
                        <div className="dialog-actions">
                            <button
                                className="confirm-btn danger"
                                onClick={handleConfirm}
                                disabled={!reason.trim()}
                            >
                                🔴 Подтвердить EMERGENCY STOP
                            </button>
                            <button
                                className="cancel-btn"
                                onClick={() => setShowDialog(false)}
                            >
                                Отмена
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </>
    );
};
```

#### WebSocket Hook:

```tsx
// src/hooks/useTradingWebSocket.ts

/**
 * Хук для real-time WebSocket данных.
 *
 * Auto-reconnect при разрыве соединения.
 * Exponential backoff (1s, 2s, 4s, max 30s).
 */
export const useTradingWebSocket = (url: string): TradingWebSocketState => {
    const [data, setData] = useState<TradingData>(initialData);
    const [connected, setConnected] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const wsRef = useRef<WebSocket | null>(null);
    const reconnectAttempt = useRef(0);

    const connect = useCallback(() => {
        try {
            const ws = new WebSocket(url);

            ws.onopen = () => {
                console.info("📊 WebSocket подключен", { url });
                setConnected(true);
                setError(null);
                reconnectAttempt.current = 0;
            };

            ws.onmessage = (event) => {
                const message = JSON.parse(event.data);

                switch (message.type) {
                    case "equity_update":
                        setData(prev => ({
                            ...prev,
                            portfolio: message.payload,
                        }));
                        break;

                    case "position_update":
                        setData(prev => ({
                            ...prev,
                            positions: updatePositions(prev.positions, message.payload),
                        }));
                        break;

                    case "signal":
                        setData(prev => ({
                            ...prev,
                            recentSignals: [message.payload, ...prev.recentSignals.slice(0, 19)],
                        }));
                        break;

                    case "kill_switch":
                        // Flash emergency overlay
                        showEmergencyOverlay(message.payload);
                        break;
                }
            };

            ws.onclose = () => {
                setConnected(false);
                scheduleReconnect();
            };

            ws.onerror = (err) => {
                console.error("❌ WebSocket ошибка", err);
                setError("Ошибка соединения");
            };

            wsRef.current = ws;

        } catch (err) {
            setError(`Не удалось подключиться: ${err}`);
        }
    }, [url]);

    const scheduleReconnect = useCallback(() => {
        const delay = Math.min(
            1000 * Math.pow(2, reconnectAttempt.current),
            30000  // Max 30 seconds
        );

        console.warn("⚠️  WebSocket переподключение", {
            attempt: reconnectAttempt.current + 1,
            delay: `${delay / 1000}s`,
        });

        reconnectAttempt.current++;

        setTimeout(connect, delay);
    }, [connect]);

    useEffect(() => {
        connect();
        return () => wsRef.current?.close();
    }, [connect]);

    return { data, connected, error };
};
```

---

## ⚠️ КРИТИЧЕСКИЕ ОГРАНИЧЕНИЯ ФАЗЫ 22

**✅ Что реализовано:**
- Real-time Dashboard (WebSocket)
- Equity chart (Recharts)
- Positions table (live P&L)
- Risk panel (metrics + ML predictions)
- Signal feed
- System health status
- Kill switch UI (с confirmation)
- Strategy controls

**❌ Что НЕ реализовано:**
- Mobile app (iOS/Android)
- Advanced charting (TradingView)
- Backtesting UI
- Configuration editor (full)
- Multi-user (roles, permissions)

---

## 🚀 ПРОИЗВОДИТЕЛЬНОСТЬ

### Критические требования:
```
Операция                         Target
────────────────────────────────────────
Initial load                     <3s
WebSocket update latency         <500ms
Chart render (1000 points)       <100ms
Table update (100 rows)          <50ms
────────────────────────────────────────
```

---

## ФАЙЛОВАЯ СТРУКТУРА

```
CRYPTOTEHNOLOG/
├── dashboard/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Dashboard.tsx
│   │   │   ├── charts/EquityChart.tsx
│   │   │   ├── portfolio/PositionsTable.tsx
│   │   │   ├── risk/RiskPanel.tsx
│   │   │   ├── signals/SignalFeed.tsx
│   │   │   ├── system/SystemHealth.tsx
│   │   │   └── controls/KillSwitchButton.tsx
│   │   ├── hooks/
│   │   │   └── useTradingWebSocket.ts
│   │   ├── api/
│   │   │   └── tradingApi.ts
│   │   └── types/
│   │       └── trading.ts
│   └── package.json
│
└── src/
    └── api/
        └── dashboard_api.py      # FastAPI backend
```

---

## ACCEPTANCE CRITERIA

### Real-time
- [ ] WebSocket connection (auto-reconnect)
- [ ] Equity chart (live updates)
- [ ] Positions P&L (real-time)
- [ ] System alerts (kill switch)

### Controls
- [ ] Kill switch (confirmation dialog)
- [ ] Strategy toggle (on/off)
- [ ] Position close button

### Performance
- [ ] Load <3s
- [ ] Updates <500ms
- [ ] Chart render <100ms

---

## ИТОГОВАЯ ГОТОВНОСТЬ

**Фаза 22: Web UI Dashboard** готова к реализации! 🚀

### ЭТО ФИНАЛЬНАЯ ФАЗА ПРОЕКТА CRYPTOTEHNOLOG! 🎉

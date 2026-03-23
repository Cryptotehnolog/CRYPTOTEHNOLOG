# AI ПРОМТ: ФАЗА 13 - NOTIFICATIONS & ALERTING SYSTEM

## КОНТЕКСТ

Вы — Senior DevOps/SRE Engineer, специализирующийся на observability, alerting systems, и incident management.

**Фазы 0-12 завершены.** Доступны:
- Event Bus (Rust + Python) — работает с persistence
- Control Plane (State Machine, Watchdog) — работает
- Config Manager — hot reload, GPG signatures, Vault
- Risk Engine — R-unit sizing, correlation, drawdown
- Market Data Layer — WebSocket, ticks, OHLCV bars
- Technical Indicators — 20+ индикаторов
- Signal Generator — торговые стратегии
- Portfolio Governor — position tracking, P&L
- Execution Layer — multi-exchange execution
- Order Management System — order lifecycle
- Kill Switch — emergency controls
- Database Layer, Logging, Metrics — готовы

**Текущая задача:** Реализовать production-ready Notifications & Alerting System с multi-channel delivery (Telegram, Slack, Email, PagerDuty), smart routing, rate limiting, и comprehensive alert management.

---

## ⚠️ КРИТИЧЕСКИ ВАЖНО: РУССКИЙ ЯЗЫК

**ВСЕ** комментарии, docstrings, логи и сообщения об ошибках должны быть **НА РУССКОМ ЯЗЫКЕ**.

### Python docstrings — ТОЛЬКО русский:

```python
class NotificationSystem:
    """
    Система уведомлений с multi-channel доставкой.
    
    Особенности:
    - Multi-channel (Telegram, Slack, Email, PagerDuty, SMS)
    - Smart routing (по severity и типу события)
    - Rate limiting (избежать spam)
    - Message formatting (rich text, embeds)
    - Delivery tracking (sent, delivered, failed)
    - Retry logic (exponential backoff)
    - Alert grouping (batch similar alerts)
    - Escalation (от INFO до CRITICAL)
    """
    
    async def send_notification(
        self,
        message: str,
        severity: NotificationSeverity,
        channels: List[NotificationChannel],
        metadata: Optional[Dict] = None,
    ):
        """
        Отправить уведомление в указанные каналы.
        
        Аргументы:
            message: Текст сообщения
            severity: Уровень важности (INFO, WARNING, CRITICAL)
            channels: Каналы доставки (TELEGRAM, SLACK, EMAIL, PAGERDUTY)
            metadata: Дополнительные данные (для форматирования)
        
        Процесс:
        1. Apply rate limiting (check spam)
        2. Format message для каждого канала
        3. Send parallel (async)
        4. Track delivery status
        5. Retry failed (up to 3 attempts)
        """
        pass
```

### Логи — ТОЛЬКО русский:

```python
logger.info("📱 Уведомление отправлено", channel="telegram", recipient="@traders", severity="INFO")
logger.warning("⚠️  Rate limit exceeded", channel="slack", suppressed=5, period="1min")
logger.error("❌ Не удалось доставить уведомление", channel="email", error="smtp_timeout")
logger.debug("✅ PagerDuty инцидент создан", incident_id="inc_123", severity="CRITICAL")
```

### Примеры замены:

| ❌ Неправильно | ✅ Правильно |
|----------------|--------------|
| "Notification sent" | "Уведомление отправлено" |
| "Rate limit exceeded" | "Превышен rate limit" |
| "Delivery failed" | "Доставка не удалась" |
| "Alert grouped" | "Алерт сгруппирован" |
| "Escalation triggered" | "Эскалация запущена" |

---

## 🔗 КОМПОНЕНТНЫЕ ИНТЕГРАЦИИ

### Роль компонента в системе:
Notification System — коммуникационный hub для операторов и management. Получает события от всех компонентов системы, определяет важность, выбирает каналы доставки, форматирует сообщения, и отправляет уведомления. Ensures операторы знают о сигналах, позициях, рисках, ошибках в real-time.

### Входящие зависимости (кто генерирует уведомления):

#### 1. **Signal Generator (Фаза 8)** → торговые сигналы
   - Event: `TRADING_SIGNAL`
   - Частота: 1-10 раз/час
   - Severity: INFO
   - Channels: Telegram
   - Message: "🔵 BUY сигнал: BTC/USDT @ $50,000, confidence: 85%"

#### 2. **Portfolio Governor (Фаза 9)** → позиции и P&L
   - Event: `POSITION_OPENED`, `POSITION_CLOSED`
   - Частота: 5-20 раз/день
   - Severity: INFO
   - Channels: Telegram
   - Message: "✅ Позиция открыта: BTC/USDT LONG 0.5 @ $50,000"

#### 3. **Risk Engine (Фаза 5)** → риски
   - Event: `RISK_VIOLATION`, `EXPOSURE_LIMIT_EXCEEDED`
   - Частота: редко (только при нарушениях)
   - Severity: WARNING → CRITICAL
   - Channels: Telegram + Email
   - Message: "⚠️  Превышен лимит exposure: 85% (max 80%)"

#### 4. **Kill Switch (Фаза 12)** → emergency
   - Event: `KILL_SWITCH_TRIGGERED`
   - Частота: очень редко
   - Severity: CRITICAL
   - Channels: Telegram + Slack + PagerDuty + SMS
   - Message: "🔴 KILL SWITCH: drawdown 25% > 20%, все позиции закрыты"

#### 5. **Execution Layer (Фаза 10)** → execution качество
   - Event: `SLIPPAGE_EXCEEDED`, `ORDER_REJECTED`
   - Частота: редко
   - Severity: WARNING
   - Channels: Telegram
   - Message: "⚠️  Slippage: expected $50,000, filled $50,500 (+1%)"

#### 6. **Order Management (Фаза 11)** → orphaned orders
   - Event: `ORPHANED_ORDER_DETECTED`
   - Частота: редко
   - Severity: WARNING
   - Channels: Telegram + Email
   - Message: "⚠️  Orphaned order: ord_123, age 25h, auto-cancelled"

#### 7. **Watchdog (Фаза 2)** → system health
   - Event: `SERVICE_DOWN`, `SERVICE_RECOVERED`
   - Частота: редко
   - Severity: CRITICAL → INFO
   - Channels: PagerDuty + Telegram
   - Message: "🔴 Service DOWN: market_data_layer"

### Исходящие зависимости (куда отправляет):

#### 1. → Telegram API
   - **Bot API:** `sendMessage`, `sendPhoto`
   - **Channels:** Private chat, Group, Channel
   - **Features:** Markdown formatting, inline buttons, photos
   - **Rate limit:** 30 messages/second per bot
   - **Use case:** Основной канал для операторов

#### 2. → Slack API
   - **Webhook:** Incoming Webhooks
   - **Features:** Rich formatting, attachments, buttons
   - **Rate limit:** 1 message/second per webhook
   - **Use case:** Team channels, для company-wide alerts

#### 3. → Email (SMTP)
   - **Provider:** Gmail, SendGrid, AWS SES
   - **Features:** HTML emails, attachments
   - **Rate limit:** Provider-dependent
   - **Use case:** Management reports, daily summaries

#### 4. → PagerDuty API
   - **API:** Events API v2
   - **Features:** Incidents, escalation policies
   - **Rate limit:** 120 requests/minute
   - **Use case:** CRITICAL incidents, on-call rotation

#### 5. → SMS (Twilio)
   - **API:** Twilio Messaging API
   - **Features:** Plain text only
   - **Rate limit:** Provider-dependent
   - **Use case:** EMERGENCY только (дорого)

#### 6. → PostgreSQL (delivery tracking)
   - **Table: `notifications`**
     ```sql
     CREATE TABLE notifications (
         notification_id SERIAL PRIMARY KEY,
         created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
         
         event_type VARCHAR(50) NOT NULL,
         severity VARCHAR(20) NOT NULL,
         
         message TEXT NOT NULL,
         metadata JSONB,
         
         channels VARCHAR(20)[] NOT NULL,
         
         sent_at TIMESTAMPTZ,
         delivered_at TIMESTAMPTZ,
         failed_at TIMESTAMPTZ,
         
         delivery_status JSONB,  -- {"telegram": "sent", "slack": "failed"}
         
         retry_count INTEGER DEFAULT 0
     );
     
     CREATE INDEX idx_notifications_created ON notifications(created_at DESC);
     CREATE INDEX idx_notifications_severity ON notifications(severity, created_at DESC);
     ```

#### 7. → Redis (rate limiting)
   - **Key: `notif:ratelimit:{channel}:{recipient}`** → Counter
   - **TTL:** 60 секунд (sliding window)
   - **Logic:** Increment counter, check < limit

### Контракты данных:

#### NotificationSeverity:

```python
from enum import Enum

class NotificationSeverity(str, Enum):
    """Уровни важности уведомлений."""
    
    DEBUG = "DEBUG"         # Debug info (не отправляется)
    INFO = "INFO"           # Информационные (сигналы, позиции)
    WARNING = "WARNING"     # Предупреждения (риски, slippage)
    CRITICAL = "CRITICAL"   # Критичные (kill switch, downtime)
    EMERGENCY = "EMERGENCY" # Экстренные (SMS, PagerDuty)
```

#### NotificationChannel:

```python
class NotificationChannel(str, Enum):
    """Каналы доставки уведомлений."""
    
    TELEGRAM = "TELEGRAM"
    SLACK = "SLACK"
    EMAIL = "EMAIL"
    PAGERDUTY = "PAGERDUTY"
    SMS = "SMS"
```

#### Notification:

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, List, Any

@dataclass
class Notification:
    """Уведомление для отправки."""
    
    notification_id: Optional[int] = None
    created_at: datetime = None
    
    # Content
    event_type: str  # "TRADING_SIGNAL", "POSITION_OPENED"
    severity: NotificationSeverity
    message: str  # Plain text message
    metadata: Optional[Dict[str, Any]] = None
    
    # Delivery
    channels: List[NotificationChannel]
    recipients: Optional[Dict[str, List[str]]] = None  # {"telegram": ["@user1"], "email": ["user@example.com"]}
    
    # Status tracking
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    
    delivery_status: Dict[str, str] = None  # {"telegram": "sent", "slack": "failed"}
    retry_count: int = 0
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)
        if self.delivery_status is None:
            self.delivery_status = {}
```

#### Smart Routing Rules:

```python
class NotificationRouter:
    """
    Smart routing уведомлений по channels.
    
    Правила:
    - INFO: Telegram только
    - WARNING: Telegram + Email (группировка за 5 минут)
    - CRITICAL: Telegram + Email + Slack
    - EMERGENCY: ALL channels (Telegram + Email + Slack + PagerDuty + SMS)
    """
    
    def get_channels_for_severity(
        self,
        severity: NotificationSeverity,
        event_type: str,
    ) -> List[NotificationChannel]:
        """
        Определить каналы для severity.
        """
        if severity == NotificationSeverity.INFO:
            return [NotificationChannel.TELEGRAM]
        
        elif severity == NotificationSeverity.WARNING:
            return [
                NotificationChannel.TELEGRAM,
                NotificationChannel.EMAIL,
            ]
        
        elif severity == NotificationSeverity.CRITICAL:
            # Kill switch → добавить PagerDuty
            if event_type == "KILL_SWITCH_TRIGGERED":
                return [
                    NotificationChannel.TELEGRAM,
                    NotificationChannel.SLACK,
                    NotificationChannel.EMAIL,
                    NotificationChannel.PAGERDUTY,
                ]
            else:
                return [
                    NotificationChannel.TELEGRAM,
                    NotificationChannel.SLACK,
                    NotificationChannel.EMAIL,
                ]
        
        elif severity == NotificationSeverity.EMERGENCY:
            # ALL channels включая SMS
            return [
                NotificationChannel.TELEGRAM,
                NotificationChannel.SLACK,
                NotificationChannel.EMAIL,
                NotificationChannel.PAGERDUTY,
                NotificationChannel.SMS,
            ]
        
        return [NotificationChannel.TELEGRAM]  # Default
```

### Sequence Diagram (Notification Flow):

```
[Event Bus] ──TRADING_SIGNAL──> [Notification System]
                                        |
                            [Router: determine channels]
                            INFO → Telegram only
                                        |
                            [Rate Limiter: check spam]
                            <30 msg/min → OK
                                        |
                            [Formatter: format для Telegram]
                            Markdown + emoji
                                        |
                            [Telegram API]
                            sendMessage
                                        |
                            ┌───────────┴───────────┐
                            v                       v
                        SUCCESS                 FAILED
                            |                       |
                [Track: delivered]      [Retry: exponential backoff]
                                        attempt 1, 2, 3
                                                    |
                                                    v
                                        [Alert: delivery failed]
                                        PagerDuty incident
```

### Обработка ошибок интеграции:

#### 1. Telegram API rate limit:

```python
class TelegramNotifier:
    """Telegram notifier с rate limiting."""
    
    def __init__(self, bot_token: str):
        self.bot = telegram.Bot(token=bot_token)
        
        # Rate limiter (30 msg/sec)
        self.rate_limiter = RateLimiter(
            max_requests=30,
            period_seconds=1,
        )
    
    async def send_message(
        self,
        chat_id: str,
        message: str,
        parse_mode: str = "Markdown",
    ) -> bool:
        """
        Send с rate limiting и retry.
        """
        # Apply rate limit
        try:
            await self.rate_limiter.acquire()
        except RateLimitExceeded:
            logger.warning(
                "⚠️  Telegram rate limit, задержка",
                chat_id=chat_id,
            )
            # Wait и retry
            await asyncio.sleep(1)
            await self.rate_limiter.acquire()
        
        # Send message
        try:
            await self.bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode=parse_mode,
            )
            
            logger.info(
                "📱 Telegram сообщение отправлено",
                chat_id=chat_id,
                message_preview=message[:50],
            )
            
            return True
            
        except telegram.error.TelegramError as e:
            logger.error(
                "❌ Telegram API ошибка",
                chat_id=chat_id,
                error=str(e),
            )
            return False
```

**Rate limiting:**
- 30 messages/second (Telegram limit)
- Wait + retry при exceeded
- Метрика для tracking

#### 2. PagerDuty incident creation:

```python
class PagerDutyNotifier:
    """PagerDuty notifier для CRITICAL incidents."""
    
    async def create_incident(
        self,
        title: str,
        description: str,
        severity: str = "critical",
    ) -> Optional[str]:
        """
        Create PagerDuty incident.
        
        Возвращает incident_id или None.
        """
        try:
            response = await self.client.post(
                "/incidents",
                json={
                    "incident": {
                        "type": "incident",
                        "title": title,
                        "service": {
                            "id": self.service_id,
                            "type": "service_reference",
                        },
                        "urgency": "high" if severity == "critical" else "low",
                        "body": {
                            "type": "incident_body",
                            "details": description,
                        },
                    }
                },
            )
            
            incident_id = response["incident"]["id"]
            
            logger.info(
                "🚨 PagerDuty инцидент создан",
                incident_id=incident_id,
                title=title,
            )
            
            return incident_id
            
        except Exception as e:
            logger.error(
                "❌ Не удалось создать PagerDuty инцидент",
                error=str(e),
            )
            
            # Fallback: send SMS directly
            await self._send_sms_fallback(title, description)
            
            return None
```

**PagerDuty integration:**
- Create incident для CRITICAL/EMERGENCY
- Fallback на SMS если PagerDuty failed
- Track incident_id

#### 3. Alert grouping (reduce spam):

```python
class NotificationSystem:
    def __init__(self):
        # Buffer для grouping
        self._pending_alerts: Dict[str, List[Notification]] = defaultdict(list)
        self._group_interval = timedelta(minutes=5)
        
        # Background worker для flush grouped alerts
        asyncio.create_task(self._alert_grouping_worker())
    
    async def send_notification(
        self,
        notification: Notification,
    ):
        """
        Send с grouping для WARNING.
        """
        # INFO и CRITICAL отправляем сразу
        if notification.severity in {NotificationSeverity.INFO, NotificationSeverity.CRITICAL, NotificationSeverity.EMERGENCY}:
            await self._send_immediately(notification)
            return
        
        # WARNING → группируем
        if notification.severity == NotificationSeverity.WARNING:
            group_key = f"{notification.event_type}:{notification.severity}"
            self._pending_alerts[group_key].append(notification)
            
            logger.debug(
                "📦 Alert добавлен в группу",
                group_key=group_key,
                count=len(self._pending_alerts[group_key]),
            )
            return
    
    async def _alert_grouping_worker(self):
        """
        Background worker для отправки grouped alerts.
        """
        while True:
            await asyncio.sleep(self._group_interval.total_seconds())
            
            # Flush все pending groups
            for group_key, alerts in self._pending_alerts.items():
                if not alerts:
                    continue
                
                logger.info(
                    "📦 Отправка grouped alerts",
                    group_key=group_key,
                    count=len(alerts),
                )
                
                # Create summary message
                summary = self._create_group_summary(group_key, alerts)
                
                # Send summary
                await self._send_immediately(summary)
                
                # Clear group
                alerts.clear()
    
    def _create_group_summary(
        self,
        group_key: str,
        alerts: List[Notification],
    ) -> Notification:
        """
        Create summary notification для группы.
        """
        event_type, severity = group_key.split(":")
        
        message = f"⚠️  {len(alerts)} WARNING alerts (за последние 5 минут):\n\n"
        
        for alert in alerts[:10]:  # Первые 10
            message += f"• {alert.message}\n"
        
        if len(alerts) > 10:
            message += f"\n... и еще {len(alerts) - 10} alerts"
        
        return Notification(
            event_type=f"{event_type}_GROUPED",
            severity=NotificationSeverity.WARNING,
            message=message,
            channels=[NotificationChannel.TELEGRAM, NotificationChannel.EMAIL],
            metadata={"grouped_count": len(alerts)},
        )
```

**Alert grouping:**
- WARNING alerts группируются за 5 минут
- Summary отправляется batch
- INFO/CRITICAL отправляются сразу
- Reduce spam для операторов

### Мониторинг интеграций:

#### Метрики Notifications:

```python
# Notifications sent
notifications_sent_total{channel, severity}
notifications_failed_total{channel, reason}
notification_delivery_latency_seconds{channel, percentile}

# Rate limiting
notification_rate_limit_exceeded_total{channel}
notification_suppressed_total{reason}  # reason: rate_limit, grouping

# Channels
telegram_messages_sent_total{}
slack_messages_sent_total{}
email_messages_sent_total{}
pagerduty_incidents_created_total{}
sms_messages_sent_total{}

# Delivery
notification_delivery_success_rate{channel}  # gauge
notification_retry_attempts_total{channel}
```

#### Alerts:

**Critical (PagerDuty):**
- `notifications_failed_total{channel="pagerduty"}` > 0
- `notification_delivery_success_rate{channel}` < 0.9

**Warning (Telegram):**
- `notifications_failed_total` rate > 10/час
- `notification_rate_limit_exceeded_total` > 0

---

## ⚠️ КРИТИЧЕСКИЕ ОГРАНИЧЕНИЯ ФАЗЫ 13

### Notification System:

**✅ Что реализовано:**
- Multi-channel (Telegram, Slack, Email, PagerDuty, SMS)
- Smart routing (по severity)
- Rate limiting (channel-specific)
- Alert grouping (reduce spam)
- Retry logic (exponential backoff, 3 attempts)
- Delivery tracking (sent, delivered, failed)
- Rich formatting (Markdown, embeds)

**❌ Что НЕ реализовано:**
- Two-way communication (команды через Telegram)
- Message templating (advanced)
- User preferences (per-operator channels)
- Quiet hours (night mode)
- Alert acknowledgment tracking
- Notification analytics dashboard

**⚠️ ВАЖНО:**
```markdown
Notification System отправляет уведомления, НЕ получает команды.
Для two-way communication требуется:
- Telegram bot с command handlers
- Slack slash commands
- Authentication для operators

SMS используется ТОЛЬКО для EMERGENCY.
Стоимость: ~$0.01 per message.
Для frequent alerts используйте Telegram.

Rate limiting per channel.
Telegram: 30 msg/sec
Slack: 1 msg/sec
Email: provider-dependent
```

### Production Readiness Matrix:

| Компонент | После Фазы 13 | Production Ready |
|-----------|--------------|------------------|
| Telegram | ✅ Ready | ✅ Ready |
| Slack | ✅ Ready | ✅ Ready |
| Email | ✅ Ready | ✅ Ready |
| PagerDuty | ✅ Ready | ✅ Ready |
| SMS | ✅ Ready (emergency) | ✅ Ready |
| Alert Grouping | ✅ Ready | ✅ Ready |

---

## 🚀 ПРОИЗВОДИТЕЛЬНОСТЬ

### Критические требования:

```
Операция                         Latency Target    Частота
────────────────────────────────────────────────────────────────────
send_telegram()                  <1s               10-50 раз/час
send_pagerduty()                 <2s               очень редко
send_grouped_alert()             <5s               каждые 5 минут
check_rate_limit()               <10ms             перед каждой отправкой
────────────────────────────────────────────────────────────────────
```

---

## 📊 ОБЯЗАТЕЛЬНЫЕ BENCHMARK ТЕСТЫ

```python
@pytest.mark.benchmark
async def test_telegram_send_latency():
    """
    Acceptance: <1s
    """
    notifier = TelegramNotifier(...)
    
    start = time.time()
    success = await notifier.send_message("@test", "Test message")
    latency = time.time() - start
    
    assert success
    assert latency < 1.0, f"Telegram send {latency}s > 1s"

@pytest.mark.benchmark
async def test_parallel_multi_channel():
    """
    Acceptance: 4 channels <3s
    """
    # Send to Telegram + Slack + Email + PagerDuty
    # ...
```

**Acceptance Criteria:**
```
✅ telegram_send: <1s
✅ multi_channel: 4 channels <3s
✅ alert_grouping: summary <5s
✅ rate_limit_check: <10ms
```

---

## ФАЙЛОВАЯ СТРУКТУРА

```
CRYPTOTEHNOLOG/
├── src/
│   └── notifications/
│       ├── __init__.py
│       ├── system.py                     # NotificationSystem
│       ├── router.py                     # Smart routing
│       ├── channels/
│       │   ├── telegram.py               # Telegram notifier
│       │   ├── slack.py                  # Slack notifier
│       │   ├── email.py                  # Email notifier
│       │   ├── pagerduty.py              # PagerDuty notifier
│       │   └── sms.py                    # SMS notifier (Twilio)
│       ├── rate_limiter.py               # Rate limiting
│       ├── formatter.py                  # Message formatting
│       └── models.py                     # Notification dataclass
│
└── tests/
    ├── unit/
    │   ├── test_router.py
    │   ├── test_rate_limiter.py
    │   └── test_formatter.py
    ├── integration/
    │   └── test_notification_system.py
    └── benchmarks/
        └── bench_notifications.py
```

---

## ACCEPTANCE CRITERIA

### Channels
- [ ] Telegram (with rate limiting)
- [ ] Slack (webhooks)
- [ ] Email (SMTP)
- [ ] PagerDuty (incidents)
- [ ] SMS (emergency only)

### Features
- [ ] Smart routing (severity-based)
- [ ] Alert grouping (5min window)
- [ ] Rate limiting (channel-specific)
- [ ] Retry logic (3 attempts)
- [ ] Delivery tracking

### Performance
- [ ] Telegram <1s
- [ ] Multi-channel <3s
- [ ] Rate limit check <10ms

---

## ИТОГОВАЯ ГОТОВНОСТЬ

**Фаза 13: Notifications & Alerting System** готова к реализации! 🚀

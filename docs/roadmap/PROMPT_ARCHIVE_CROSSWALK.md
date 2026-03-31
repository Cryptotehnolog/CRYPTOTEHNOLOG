# PROMPT ARCHIVE CROSSWALK
## Mapping Historical Prompts to Current Roadmap and Phase Truth

---

## Назначение

Этот документ связывает archived prompts из:

- `prompts/reference/russian_archive/`

с текущими authoritative phase plans и deferred roadmap lines.

Он нужен, чтобы historical archive был не просто складом файлов, а рабочим
navigation layer:

- что уже реализовано;
- что было нормализовано в реальные phase plans;
- что осталось deferred;
- что относится к parallel tracks.

---

## Правила чтения

Для каждого archived prompt фиксируется один из статусов:

- `implemented` — смысл prompt уже отражён в authoritative phase documents и коде
- `normalized` — исходный prompt был переработан в более узкую phase truth
- `deferred` — идеи prompt сохранены, но вынесены в future lines
- `parallel track` — относится к отдельной линии, не к main phase version line

---

## Crosswalk

### 00_ОГЛАВЛЕНИЕ_И_ВВЕДЕНИЕ.md

- Статус: `reference only`
- Роль: historical overview / context
- Authoritative replacement:
  - `README.md`
  - `docs/roadmap/MASTER_ROADMAP.md`

### 01_ФАЗА_0_ПОДГОТОВКА_СРЕДЫ.md

- Статус: `implemented`
- Authoritative replacement:
  - `prompts/plan/P_1.md`
  - фактический код / tooling / infra truth

### 02_ФАЗА_1_ЯДРО_ИНФРАСТРУКТУРЫ_PROMPT.md

- Статус: `implemented`
- Authoritative replacement:
  - `prompts/plan/P_1.md`

### 03_ФАЗА_2_CONTROL_PLANE_PROMPT.md

- Статус: `implemented`
- Authoritative replacement:
  - `prompts/plan/P_2.md`

### 04_ФАЗА_3_EVENT_BUS_PROMPT.md

- Статус: `implemented`
- Authoritative replacement:
  - `prompts/plan/P_3.md`

### 05_ФАЗА_4_CONFIG_MANAGER_PROMPT.md

- Статус: `implemented`
- Authoritative replacement:
  - `prompts/plan/P_4.md`

### 06_ФАЗА_5_RISK_ENGINE_PROMPT.md

- Статус: `implemented`
- Authoritative replacement:
  - `prompts/plan/P_5.md`
  - `prompts/plan/P_5_1.md`
  - `prompts/plan/P_5_RESULT.md`

### 07_ФАЗА_6_MARKET_DATA_PROMPT.md

- Статус: `implemented`
- Authoritative replacement:
  - `prompts/plan/P_6.md`

### 08_ФАЗА_7_INDICATORS_PROMPT.md

- Статус: `normalized`
- Authoritative replacement:
  - `prompts/plan/P_7.md`
  - `prompts/plan/P_7_RESULT.md`
  - `docs/adr/0026-phase7-indicators-intelligence-foundation-and-derya-runtime-boundary.md`
- Deferred extraction:
  - `docs/roadmap/DEFERRED_SCOPE.md`
  - `Broad classical indicator runtime / library`
  - `Stop-hunt / liquidity intelligence как отдельная foundation-line`

### 09_ФАЗА_8_SIGNAL_GENERATOR_PROMPT.md

- Статус: `normalized`
- Authoritative replacement:
  - `prompts/plan/P_8.md`
  - `prompts/plan/P_8_RESULT.md`
- Deferred extraction:
  - `OpportunityEngine`
  - `MetaClassifier`
  - `StrategyManager`
  - `Multi-strategy orchestration`
  - `Pyramiding`
  - `Signal persistence как обязательный first-pass scope`
  - `Execution semantics beyond signal foundation`

### 10_ФАЗА_9_PORTFOLIO_GOVERNOR_PROMPT.md
### 10_ФАЗА_9_1_PORTFOLIO_GOVERNOR_PROMPT.md

- Статус: `deferred`
- Deferred line:
  - `Portfolio / supervisor logic`

### 11_ФАЗА_10_EXECUTION_LAYER_PROMPT.md
### 12_ФАЗА_11_OMS_PROMPT.md

- Статус: `normalized`
- Authoritative replacement:
  - `prompts/plan/P_10.md`
  - `prompts/plan/P_10_RESULT.md`
  - `prompts/plan/P_16.md`
  - `prompts/plan/P_16_RESULT.md`
- Deferred remainder:
  - broader execution / OMS expansion beyond already closed foundations

### 13_ФАЗА_12_KILL_SWITCH_PROMPT.md
### 14_ФАЗА_13_NOTIFICATIONS_PROMPT.md

- Статус: `normalized + deferred remainder`
- Authoritative replacement:
  - `prompts/plan/P_15.md`
  - `prompts/plan/P_15_RESULT.md`
- Deferred remainder:
  - broader operational / notification / approval expansion beyond `P_15`

### 15_ФАЗА_14_STRATEGY_MANAGER_PROMPT.md

- Статус: `normalized + deferred remainder`
- Authoritative replacement:
  - `prompts/plan/P_17.md`
  - `prompts/plan/P_17_RESULT.md`
- Deferred remainder:
  - broader `StrategyManager`
  - full multi-strategy orchestration beyond already closed workflow foundation

### 16_ФАЗА_15_PERFORMANCE_ANALYTICS_PROMPT.md
### 17_ФАЗА_16_BACKTESTING_PROMPT.md
### 18_ФАЗА_17_PAPER_TRADING_PROMPT.md

- Статус: `normalized + deferred remainder`
- Authoritative replacement:
  - `prompts/plan/P_18.md`
  - `prompts/plan/P_18_RESULT.md`
  - `prompts/plan/P_19.md`
  - `prompts/plan/P_19_RESULT.md`
  - `prompts/plan/P_20.md`
  - `prompts/plan/P_20_RESULT.md`
- Deferred remainder:
  - broader performance analytics
  - optimization / research-lab territory beyond already closed foundations

### 19_ФАЗА_18_DISTRIBUTED_DEPLOYMENT_PROMPT.md

- Статус: `future line`
- Role:
  - later deployment / infrastructure expansion

### 20_ФАЗА_19_HISTORICAL_DATA_PROMPT.md
### 21_ФАЗА_20_ADVANCED_EXECUTION_PROMPT.md
### 22_ФАЗА_21_ML_RISK_MODELS_PROMPT.md

- Статус: `deferred`
- Deferred line:
  - `Historical data / advanced execution / ML overlays`

### 23_ФАЗА_22_WEB_UI_DASHBOARD_PROMPT.md

- Статус: `parallel track`
- Historical note:
  - prompt numbering больше не должен читаться как future `P_22`, потому что authoritative `P_22` уже закрыта как `Live Feed Connectivity Foundation`
- Deferred line:
  - `Dashboard / UI line`
- Rule:
  - не входит в main phase version line без отдельного решения

---

## Как использовать crosswalk

При открытии новой фазы:

1. сначала проверяется `prompts/plan/P_X.md`;
2. затем relevant ADR;
3. затем `DEFERRED_SCOPE.md`;
4. и только потом archived prompts через этот crosswalk.

Это позволяет:

- не потерять идеи;
- не давать historical prompt диктовать текущий scope напрямую;
- быстро видеть, какие блоки уже ждут своей будущей фазы.

# DEFERRED SCOPE REGISTER
## Official Registry of Scope Deferred Beyond Current Phases

---

## Назначение

Этот документ хранит всё, что было сознательно вынесено из реализуемых фаз,
чтобы не терять идеи и не раздувать текущий release scope.

Для каждой записи фиксируется:

- что именно отложено;
- из какой фазы вынесено;
- на какие reference prompts это опирается;
- почему вынесено;
- какие prerequisite нужны;
- куда предварительно относится будущая работа.

---

## Статусы

- `deferred` — признано полезным, но не входит в текущую фазу
- `revisit` — требует пересмотра после завершения ближайшего foundation-step
- `promoted` — уже переведено в scope новой фазы и должно жить в authoritative plan

---

## Реестр

### OpportunityEngine

- Источник: `P_8`
- Reference prompts:
  - `prompts/reference/russian_archive/09_ФАЗА_8_SIGNAL_GENERATOR_PROMPT.md`
- Статус: `promoted`
- Причина: historical broad `OpportunityEngine` уже нормализован в узкую authoritative line `P_11 Opportunity / Selection Foundation`
- Prerequisite:
  - стабильный signal foundation
  - понятная strategy/consumer line
- Нормализовано в:
  - `P_11 Opportunity / Selection Foundation`
  - `prompts/plan/P_11.md`
  - `prompts/plan/P_11_RESULT.md`

### MetaClassifier

- Источник: `P_8`
- Reference prompts:
  - `prompts/reference/russian_archive/09_ФАЗА_8_SIGNAL_GENERATOR_PROMPT.md`
- Статус: `deferred`
- Причина: требует multi-strategy existence и conflict-resolution contour
- Prerequisite:
  - несколько реальных signal/strategy contours
  - policy for conflict ownership
- Предварительная цель: separate post-`P_12` line / `P_13+`

### StrategyManager

- Источник: `P_8`
- Reference prompts:
  - `prompts/reference/russian_archive/15_ФАЗА_14_STRATEGY_MANAGER_PROMPT.md`
  - `prompts/reference/russian_archive/09_ФАЗА_8_SIGNAL_GENERATOR_PROMPT.md`
- Статус: `revisit`
- Причина: historical broad `StrategyManager` уже частично нормализован через `P_12 Strategy Orchestration / Meta Layer`, но broader manager / workflow ownership остаётся вне реализованного scope
- Prerequisite:
  - signal foundation
  - strategy runtime foundation
- Уже нормализованная promoted territory:
  - `P_12 Strategy Orchestration / Meta Layer`
  - `prompts/plan/P_12.md`
  - `prompts/plan/P_12_RESULT.md`
- Deferred remainder:
  - broader manager ownership
  - cross-runtime workflow coordination
  - future post-`P_16` manager line

### Multi-strategy orchestration

- Источник: `P_8`
- Reference prompts:
  - `prompts/reference/russian_archive/09_ФАЗА_8_SIGNAL_GENERATOR_PROMPT.md`
  - `prompts/reference/russian_archive/15_ФАЗА_14_STRATEGY_MANAGER_PROMPT.md`
- Статус: `revisit`
- Причина: narrow orchestration foundation уже promoted через `P_12`, но full multi-strategy line всё ещё не реализована
- Prerequisite:
  - несколько production-ready strategy contours
- Уже нормализованная promoted territory:
  - `P_12 Strategy Orchestration / Meta Layer`
  - `prompts/plan/P_12.md`
  - `prompts/plan/P_12_RESULT.md`
- Deferred remainder:
  - full multi-strategy coordination
  - policy ownership between multiple production strategies
  - broader workflow line

### Pyramiding

- Источник: `P_8`
- Reference prompts:
  - `prompts/reference/russian_archive/09_ФАЗА_8_SIGNAL_GENERATOR_PROMPT.md`
- Статус: `promoted`
- Причина: historical broad `Pyramiding` уже нормализован в узкую authoritative line `P_13 Position Expansion Foundation`
- Prerequisite:
  - strategy/runtime orchestration
  - подтверждённый execution contour
- Нормализовано в:
  - `P_13 Position Expansion Foundation`
  - `prompts/plan/P_13.md`
  - `prompts/plan/P_13_RESULT.md`

### Portfolio / supervisor logic

- Источник: `P_8`
- Reference prompts:
  - `prompts/reference/russian_archive/10_ФАЗА_9_PORTFOLIO_GOVERNOR_PROMPT.md`
  - `prompts/reference/russian_archive/10_ФАЗА_9_1_PORTFOLIO_GOVERNOR_PROMPT.md`
- Статус: `revisit`
- Причина: historical broad portfolio / supervisor territory уже распалась на две promoted mainline lines, а broader ops/liquidation/approval territory остаётся deferred
- Prerequisite:
  - strategy management
  - ranking / selection semantics
- Уже нормализованная promoted territory:
  - `P_14 Portfolio Governor / Capital Governance Foundation`
  - `prompts/plan/P_14.md`
  - `prompts/plan/P_14_RESULT.md`
  - `P_15 Protection / Supervisor Foundation`
  - `prompts/plan/P_15.md`
  - `prompts/plan/P_15_RESULT.md`
- Deferred remainder:
  - broader liquidation / ops territory
  - approval workflow / escalation territory
  - order-lifecycle-adjacent supervisor behavior beyond `P_15`

### Broad classical indicator runtime / library

- Источник: `P_7`, `P_8`
- Reference prompts:
  - `prompts/reference/russian_archive/08_ФАЗА_7_INDICATORS_PROMPT.md`
  - `prompts/reference/russian_archive/09_ФАЗА_8_SIGNAL_GENERATOR_PROMPT.md`
- Статус: `deferred`
- Причина: DERYA-first line и narrow signal foundation не должны задним числом объявляться полной indicator platform
- Prerequisite:
  - отдельное решение по ownership и runtime boundary
- Предварительная цель: separate foundation line / future phase

### Stop-hunt / liquidity intelligence как отдельная foundation-line

- Источник: старые prompts `P_7`, `P_8`
- Reference prompts:
  - `prompts/reference/russian_archive/08_ФАЗА_7_INDICATORS_PROMPT.md`
  - `prompts/reference/russian_archive/09_ФАЗА_8_SIGNAL_GENERATOR_PROMPT.md`
- Статус: `deferred`
- Причина: foundation truth для этого contour не зафиксирована
- Prerequisite:
  - отдельные contracts
  - честный source of truth
- Предварительная цель: future intelligence/analysis line

### FMIM как inefficiency-filter line

- Источник: post-`P_8` roadmap expansion
- Reference prompts:
  - `prompts/reference/russian_archive/00_ОГЛАВЛЕНИЕ_И_ВВЕДЕНИЕ.md`
- Статус: `deferred`
- Причина: `FMIM` может усилить quality gating, но не должна попадать в уже закрытые `P_7/P_8` задним числом
- Prerequisite:
  - стабильные market-data / analysis / intelligence foundations
  - отдельное решение по ownership между `analysis`, `intelligence` и signal consumers
- Предварительная цель: future analysis/intelligence expansion line

### Multi-Trend Analysis как explainable MFT line

- Источник: post-`P_8` roadmap expansion
- Reference prompts:
  - `prompts/reference/russian_archive/00_ОГЛАВЛЕНИЕ_И_ВВЕДЕНИЕ.md`
- Статус: `deferred`
- Причина: multi-timeframe trend semantics может усилить future signal quality, но это уже отдельный contour beyond current `Signal Generation Foundation`
- Prerequisite:
  - стабильный signal foundation
  - отдельное решение по месту ownership: `analysis` vs `intelligence`
  - честный backtesting / evaluation path для trend hypotheses
- Предварительная цель: future analysis/intelligence expansion line with signal consumers

### Signal persistence как обязательный first-pass scope

- Источник: `P_8`
- Reference prompts:
  - `prompts/reference/russian_archive/09_ФАЗА_8_SIGNAL_GENERATOR_PROMPT.md`
- Статус: `deferred`
- Причина: signal contracts и runtime были важнее persistence schema
- Prerequisite:
  - устойчивый signal lifecycle
  - определённая retention/audit policy
- Предварительная цель: future hardening / post-`P_8`

### Dashboard / UI line

- Источник: cross-phase
- Reference prompts:
  - `prompts/reference/russian_archive/23_ФАЗА_22_WEB_UI_DASHBOARD_PROMPT.md`
  - `prompts/План Разработки Панели Управления CRYPTOTEHNOLOG.md`
- Статус: `revisit`
- Причина: dashboard foundation уже собрана как parallel/supporting contour, но broader dashboard expansion всё ещё не входит в mainline version line
- Prerequisite:
  - отдельный dashboard track
- Уже реализованная parallel/supporting territory:
  - dashboard foundation как separate supporting contour
- Deferred remainder:
  - richer overview interactions
  - отдельные operator-facing surfaces
  - broader dashboard expansion beyond current foundation

### Execution semantics beyond signal foundation

- Источник: `P_8`
- Reference prompts:
  - `prompts/reference/russian_archive/11_ФАЗА_10_EXECUTION_LAYER_PROMPT.md`
  - `prompts/reference/russian_archive/12_ФАЗА_11_OMS_PROMPT.md`
- Статус: `promoted`
- Причина: execution ownership уже нормализована и реализована как отдельная authoritative line `P_10 Execution Foundation`
- Prerequisite:
  - execution phase opening
- Нормализовано в:
  - `P_10 Execution Foundation`
  - `prompts/plan/P_10.md`
  - `prompts/plan/P_10_RESULT.md`

### Backtesting / paper trading / performance analytics

- Источник: future roadmap
- Reference prompts:
  - `prompts/reference/russian_archive/16_ФАЗА_15_PERFORMANCE_ANALYTICS_PROMPT.md`
  - `prompts/reference/russian_archive/17_ФАЗА_16_BACKTESTING_PROMPT.md`
  - `prompts/reference/russian_archive/18_ФАЗА_17_PAPER_TRADING_PROMPT.md`
- Статус: `deferred`
- Причина: это отдельные validation/analytics lines, а не часть текущего signal foundation
- Prerequisite:
  - стабильные signal / strategy / execution contours
- Предварительная цель: later validation phases

### Historical data / advanced execution / ML overlays

- Источник: future roadmap
- Reference prompts:
  - `prompts/reference/russian_archive/20_ФАЗА_19_HISTORICAL_DATA_PROMPT.md`
  - `prompts/reference/russian_archive/21_ФАЗА_20_ADVANCED_EXECUTION_PROMPT.md`
  - `prompts/reference/russian_archive/22_ФАЗА_21_ML_RISK_MODELS_PROMPT.md`
- Статус: `deferred`
- Причина: это дальние capability-lines, не относящиеся к текущим foundation релизам
- Prerequisite:
  - зрелые data / execution / analytics contours
- Предварительная цель: later major roadmap stages

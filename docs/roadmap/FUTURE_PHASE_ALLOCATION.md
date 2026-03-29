# FUTURE PHASE ALLOCATION
## Предварительное распределение deferred scope по будущим фазам

---

## Назначение

Этот документ не открывает новые фазы автоматически.

Он нужен, чтобы:

- не терять deferred scope;
- заранее видеть вероятную логику будущих фаз;
- не держать future decomposition только “в голове”.

Это **предварительное** распределение.
Окончательная truth каждой будущей фазы всё равно должна появляться в
отдельном `prompts/plan/P_X.md`.

---

## Текущее предварительное распределение

### P_9 — Strategy Foundation

Кандидат на scope:

- первый production-compatible strategy contour поверх `Signal Generation Foundation`
- narrow strategy runtime boundary
- strategy-level consumption signal truth
- возможно один минимальный strategy consumer path

Что не должно автоматически входить:

- `OpportunityEngine`
- `MetaClassifier`
- широкий `StrategyManager`
- portfolio/supervisor logic

---

### P_10 — Execution Foundation

Кандидат на scope:

- первый production-compatible execution contour поверх `Strategy Foundation`
- narrow execution runtime boundary
- strategy-action consumption без portfolio governance
- возможно один минимальный execution request / order-intent path

Что не должно автоматически входить:

- OMS как широкая order-management платформа
- advanced execution algos
- portfolio-level supervisor
- multi-exchange smart-routing platform

---

### P_11 — Opportunity / Selection Foundation

Кандидат на scope:

- typed opportunity / selection contracts
- ranking / opportunity-selection semantics
- explicit runtime boundary поверх existing execution truth

Что не должно автоматически входить:

- `OpportunityEngine`
- `MetaClassifier`
- full multi-strategy orchestration
- portfolio-level supervisor

---

### P_12 — Strategy Orchestration / Meta Layer

Кандидат на scope:

- typed orchestration / meta contracts
- narrow arbitration / meta-decision semantics
- explicit `FORWARD` / `ABSTAIN` semantics
- strategy coordination semantics в узкой foundation-форме

Что не должно автоматически входить:

- `MetaClassifier`
- full `StrategyManager`
- pyramiding
- portfolio / supervisor logic
- broad execution orchestration

---

### P_13+ — Position Expansion / Portfolio / Execution Expansion

Кандидат на scope:

- pyramiding
- portfolio / supervisor logic
- OMS / broader execution coordination

---

## Дополнительные ближайшие candidate lines

### Analysis / Intelligence Expansion after `P_8`

Кандидат на scope:

- `FMIM` как market inefficiency filter
- `Multi-Trend Analysis` как explainable multi-timeframe trend line
- узкие consumer contracts для signal/strategy layers поверх этих inputs

Что не должно автоматически входить:

- full unsupervised regime clustering
- broad indicator platform
- HFT arbitrage / transformer lines
- execution-layer expansion

---

## Отдельные supporting / parallel lines

### Broad classical indicator runtime / library

- Не обязана совпадать с ближайшей основной фазой
- Может потребовать отдельную foundation-line

### Stop-hunt / liquidity intelligence

- Вероятно отдельная analysis/intelligence expansion line
- Не должна автоматически попадать в strategy или signal фазу

### Signal persistence

- Вероятно отдельный hardening step после стабилизации signal/strategy ownership

### Dashboard / UI

- Parallel track
- Не часть основной version line без отдельного решения

### Backtesting / paper trading / performance analytics

- Отдельные validation/analytics lines
- Логично открывать после stabilizing strategy/runtime contours

### Historical data / advanced execution / ML overlays

- Дальние major lines
- Не должны диктовать ближайшие foundation phases

---

## Правило использования

Этот документ нужен для roadmap coordination.

Он **не заменяет**:

- `README.md`
- `prompts/plan/P_X.md`
- `prompts/plan/P_X_RESULT.md`
- `docs/adr/*.md`

При конфликте с actual phase truth выигрывает actual phase truth.

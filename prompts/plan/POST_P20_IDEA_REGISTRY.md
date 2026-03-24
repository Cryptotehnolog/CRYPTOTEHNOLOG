# Post-P20 Idea Registry

**Дата:** 2026-03-24  
**Статус:** Принято

## Назначение

Этот документ фиксирует post-`P_20` truth по сильным идеям проекта, чтобы:

- не терять их между phase docs, README и historical prompts;
- отделять уже реализованное от future candidates;
- сохранять safe narrow version каждой идеи;
- не возвращаться позже к исходным широким формулировкам без нормализации.

Документ не открывает новую фазу и не задаёт implementation truth автоматически.

## Статусы

- `implemented`
- `partially_absorbed`
- `future_candidate`
- `supporting_track`
- `do_not_implement_in_original_form`

## Registry

### Historical prompts and broad historical expectations

#### Idea: broad historical analytics / reporting platform
- `type`: historical prompts / future territory
- `source`: historical prompts, [README.md](/D:/CRYPTOTEHNOLOG/README.md), [0030-validation-foundation-boundary.md](/D:/CRYPTOTEHNOLOG/docs/adr/0030-validation-foundation-boundary.md), [0031-paper-trading-foundation-boundary.md](/D:/CRYPTOTEHNOLOG/docs/adr/0031-paper-trading-foundation-boundary.md), [0032-backtesting-replay-foundation-boundary.md](/D:/CRYPTOTEHNOLOG/docs/adr/0032-backtesting-replay-foundation-boundary.md)
- `status`: `future_candidate`
- `safe_narrow_version`: `Reporting Artifact Foundation`
- `why_not_now`: широкая analytics/reporting semantics всё ещё слишком легко расползается в dashboard, comparison, benchmarking, optimization и broader research platform
- `likely_future_line`: future `P_21` candidate, но пока не open-ready

#### Idea: broad dashboard-led operator platform
- `type`: historical prompts / parallel future territory
- `source`: historical prompts, [README.md](/D:/CRYPTOTEHNOLOG/README.md), [P_18_RESULT.md](/D:/CRYPTOTEHNOLOG/prompts/plan/P_18_RESULT.md), [P_19_RESULT.md](/D:/CRYPTOTEHNOLOG/prompts/plan/P_19_RESULT.md), [P_20_RESULT.md](/D:/CRYPTOTEHNOLOG/prompts/plan/P_20_RESULT.md)
- `status`: `supporting_track`
- `safe_narrow_version`: read-only dashboard/operator presentation surface поверх existing truths
- `why_not_now`: остаётся supporting/parallel direction и не имеет достаточно узкой mainline opening truth
- `likely_future_line`: supporting dashboard/operator line

#### Idea: broad optimization / Monte Carlo / walk-forward / research lab
- `type`: historical prompts / broad future territory
- `source`: historical prompts, [0032-backtesting-replay-foundation-boundary.md](/D:/CRYPTOTEHNOLOG/docs/adr/0032-backtesting-replay-foundation-boundary.md), [P_20.md](/D:/CRYPTOTEHNOLOG/prompts/plan/P_20.md)
- `status`: `do_not_implement_in_original_form`
- `safe_narrow_version`: none before separate decomposition and boundary lock
- `why_not_now`: territory слишком широка, не имеет current narrow core и легко поглощает replay, analytics и historical-data semantics
- `likely_future_line`: distant future research/optimization line

### Current authoritative phase foundations

#### Idea: DERYA-first intelligence truth
- `type`: implemented phase foundation
- `source`: [README.md](/D:/CRYPTOTEHNOLOG/README.md), [P_7.md](/D:/CRYPTOTEHNOLOG/prompts/plan/P_7.md), [P_7_RESULT.md](/D:/CRYPTOTEHNOLOG/prompts/plan/P_7_RESULT.md), [0026-phase7-indicators-intelligence-foundation-and-derya-runtime-boundary.md](/D:/CRYPTOTEHNOLOG/docs/adr/0026-phase7-indicators-intelligence-foundation-and-derya-runtime-boundary.md)
- `status`: `implemented`
- `safe_narrow_version`: DERYA как state/query-first `OHLCV bar-efficiency proxy` intelligence factor
- `why_not_now`: broader indicator runtime, dashboard-level visualization и signal/strategy expansion не входят в current DERYA truth
- `likely_future_line`: possible future intelligence-supporting follow-up only if separately normalized

#### Idea: Validation as analytics hub
- `type`: rejected broad interpretation of implemented phase
- `source`: [P_18.md](/D:/CRYPTOTEHNOLOG/prompts/plan/P_18.md), [P_18_RESULT.md](/D:/CRYPTOTEHNOLOG/prompts/plan/P_18_RESULT.md), [0030-validation-foundation-boundary.md](/D:/CRYPTOTEHNOLOG/docs/adr/0030-validation-foundation-boundary.md)
- `status`: `do_not_implement_in_original_form`
- `safe_narrow_version`: narrow review / evaluation layer
- `why_not_now`: analytics / reporting ownership уже отдельно вынесена за boundary `Validation`
- `likely_future_line`: analytics / reporting as separate future line

#### Idea: Paper as comparison / reporting platform
- `type`: rejected broad interpretation of implemented phase
- `source`: [P_19.md](/D:/CRYPTOTEHNOLOG/prompts/plan/P_19.md), [P_19_RESULT.md](/D:/CRYPTOTEHNOLOG/prompts/plan/P_19_RESULT.md), [0031-paper-trading-foundation-boundary.md](/D:/CRYPTOTEHNOLOG/docs/adr/0031-paper-trading-foundation-boundary.md)
- `status`: `do_not_implement_in_original_form`
- `safe_narrow_version`: narrow rehearsal / controlled-simulation layer
- `why_not_now`: comparison / reporting ownership уже отделена от `Paper`
- `likely_future_line`: analytics / reporting as separate future line

#### Idea: Replay as analytics / ranking / historical-data platform
- `type`: rejected broad interpretation of implemented phase
- `source`: [P_20.md](/D:/CRYPTOTEHNOLOG/prompts/plan/P_20.md), [P_20_RESULT.md](/D:/CRYPTOTEHNOLOG/prompts/plan/P_20_RESULT.md), [0032-backtesting-replay-foundation-boundary.md](/D:/CRYPTOTEHNOLOG/docs/adr/0032-backtesting-replay-foundation-boundary.md)
- `status`: `do_not_implement_in_original_form`
- `safe_narrow_version`: narrow replay/backtest foundation with ingress, runtime and integrity truth
- `why_not_now`: ranking/reporting/historical-data/optimization semantics уже explicitly excluded from `P_20`
- `likely_future_line`: analytics / reporting, historical data, optimization as separate future lines

### Suggested strengthening ideas already absorbed

#### Idea: replay integrity hardening
- `type`: strengthening idea
- `source`: post-`P_20` hardening decisions, [backtest/models.py](/D:/CRYPTOTEHNOLOG/src/cryptotechnolog/backtest/models.py), [backtest/runtime.py](/D:/CRYPTOTEHNOLOG/src/cryptotechnolog/backtest/runtime.py)
- `status`: `implemented`
- `safe_narrow_version`: anti-lookahead, regression/drift guards, duplicate/ordering/coverage integrity
- `why_not_now`: immediate replay-adjacent integrity tails уже закрыты
- `likely_future_line`: none immediate

#### Idea: Rust/Python boundary hardening
- `type`: strengthening idea
- `source`: [0033-rust-python-boundary-and-ffi-packaging-truth.md](/D:/CRYPTOTEHNOLOG/docs/adr/0033-rust-python-boundary-and-ffi-packaging-truth.md), [pyproject.toml](/D:/CRYPTOTEHNOLOG/pyproject.toml)
- `status`: `implemented`
- `safe_narrow_version`: authoritative Python-facing bridge truth plus packaging normalization for optional `cryptotechnolog_rust`
- `why_not_now`: immediate mixed-language ambiguity уже закрыта
- `likely_future_line`: none immediate

### Explicit named ideas from user-side strategy language

#### Idea: FMIM
- `type`: named strategy/intelligence idea
- `source`: user-provided idea inventory and historical strategy language
- `status`: `do_not_implement_in_original_form`
- `safe_narrow_version`: only if later normalized into explicit typed intelligence/signal factor with narrow mathematical and boundary truth
- `why_not_now`: current authoritative docs/code не содержат честно нормализованного `FMIM` contour; как исходная идея слишком расплывчата и легко уходит в broad strategy mythology
- `likely_future_line`: possible future intelligence/signal decomposition only after separate audit

#### Idea: Multi-Trend Analysis
- `type`: named analysis idea
- `source`: user-provided idea inventory and historical analysis language
- `status`: `do_not_implement_in_original_form`
- `safe_narrow_version`: only as future typed analysis artifact or shared-analysis extension with explicit boundary
- `why_not_now`: current authoritative truth не фиксирует narrow contour для этой идеи; в исходной широкой форме она слишком легко смешивается с analytics, intelligence, dashboard и research
- `likely_future_line`: possible future analysis-supporting line after separate normalization

### Borrowing discipline from external systems

#### Idea: Freqtrade borrowings
- `type`: external borrowing discipline
- `source`: post-`P_20` decisions around replay ingress/integrity
- `status`: `partially_absorbed`
- `safe_narrow_version`: historical ingress discipline, conversion discipline, inventory visibility, replay anti-bias/integrity checks
- `why_not_now`: broad Freqtrade universe включает analytics, optimization, reporting, comparison и strategy-lab semantics, которые проект не должен тянуть автоматически
- `likely_future_line`: future reporting or historical-data supporting work, but only via separate decomposition

#### Idea: NautilusTrader borrowings
- `type`: external borrowing discipline
- `source`: mixed-language architecture discussions, [0033-rust-python-boundary-and-ffi-packaging-truth.md](/D:/CRYPTOTEHNOLOG/docs/adr/0033-rust-python-boundary-and-ffi-packaging-truth.md)
- `status`: `partially_absorbed`
- `safe_narrow_version`: Rust/Python boundary discipline, selected performance/bridge ownership, packaging/runtime truth normalization
- `why_not_now`: broad NautilusTrader-style engine/platform semantics не соответствуют current phase-by-phase project boundary truth
- `likely_future_line`: supporting architectural hardening only when a new concrete boundary drift appears

#### Idea: OsEngine reconnect-aware subscription recovery / resubscribe truth
- `type`: external borrowing discipline
- `source`: OsEngine exchange-connectivity audit after `P_22`, [0035-live-feed-connectivity-foundation-boundary.md](/D:/CRYPTOTEHNOLOG/docs/adr/0035-live-feed-connectivity-foundation-boundary.md), [README.md](/D:/CRYPTOTEHNOLOG/README.md)
- `status`: `future_candidate`
- `safe_narrow_version`: explicit reconnect-aware subscription recovery / resubscribe boundary for live-feed session recovery without broad connector-platform semantics
- `why_not_now`: после `P_22` идея уже выглядит сильной, но пока не должна открываться как full connector platform, adapter ecosystem или reliability/orchestration line
- `likely_future_line`: narrow post-`P_22` connectivity follow-up around subscription recovery / resubscribe truth

### Most probable future line

#### Idea: analytics / reporting
- `type`: future phase candidate
- `source`: [POST_P20_NEXT_LINE_NORMALIZATION.md](/D:/CRYPTOTEHNOLOG/prompts/plan/POST_P20_NEXT_LINE_NORMALIZATION.md), [0030-validation-foundation-boundary.md](/D:/CRYPTOTEHNOLOG/docs/adr/0030-validation-foundation-boundary.md), [0031-paper-trading-foundation-boundary.md](/D:/CRYPTOTEHNOLOG/docs/adr/0031-paper-trading-foundation-boundary.md), [0032-backtesting-replay-foundation-boundary.md](/D:/CRYPTOTEHNOLOG/docs/adr/0032-backtesting-replay-foundation-boundary.md)
- `status`: `partially_absorbed`
- `safe_narrow_version`: `Reporting Artifact Foundation`
- `why_not_now`: broad analytics/reporting territory в исходной широкой форме по-прежнему не должна автоматически расширяться в runtime/service/platform semantics после уже formalized `P_21`
- `likely_future_line`: possible future richer reporting/runtime follow-up only after separate normalization

#### Idea: Reporting Artifact Foundation
- `type`: future phase candidate narrow core
- `source`: post-`P_20` decomposition audits, [P_21.md](/D:/CRYPTOTEHNOLOG/prompts/plan/P_21.md), [P_21_RESULT.md](/D:/CRYPTOTEHNOLOG/prompts/plan/P_21_RESULT.md), [0034-reporting-artifact-foundation-boundary.md](/D:/CRYPTOTEHNOLOG/docs/adr/0034-reporting-artifact-foundation-boundary.md), [validation/models.py](/D:/CRYPTOTEHNOLOG/src/cryptotechnolog/validation/models.py), [paper/models.py](/D:/CRYPTOTEHNOLOG/src/cryptotechnolog/paper/models.py), [backtest/models.py](/D:/CRYPTOTEHNOLOG/src/cryptotechnolog/backtest/models.py)
- `status`: `implemented`
- `safe_narrow_version`: typed reporting contracts and report artifacts with read-only aggregation over `ValidationReviewCandidate`, `PaperRehearsalCandidate` and `ReplayCandidate`
- `why_not_now`: broad reporting/runtime continuation по-прежнему не должна автоматически выводиться из уже закрытой artifact-first линии
- `likely_future_line`: possible future reporting follow-up only after separate normalization

#### Idea: dashboard / operator surface
- `type`: supporting future direction
- `source`: [README.md](/D:/CRYPTOTEHNOLOG/README.md), [P_18_RESULT.md](/D:/CRYPTOTEHNOLOG/prompts/plan/P_18_RESULT.md), [P_19_RESULT.md](/D:/CRYPTOTEHNOLOG/prompts/plan/P_19_RESULT.md), [P_20_RESULT.md](/D:/CRYPTOTEHNOLOG/prompts/plan/P_20_RESULT.md)
- `status`: `supporting_track`
- `safe_narrow_version`: presentation/UI layer consuming diagnostics and future reporting truth read-only
- `why_not_now`: остаётся supporting/parallel contour и не должен смешиваться с analytics/reporting ownership
- `likely_future_line`: supporting dashboard/operator direction, not current `P_21`

## Current registry verdict

- `P_20 / v1.20.0`, `P_21 / v1.21.0` и `P_22 / v1.22.0` уже formalized.
- broad analytics / reporting platform в исходной широкой форме по-прежнему не должна реализовываться напрямую.
- `Reporting Artifact Foundation` уже absorbed в project truth как formalized `P_21`.
- strongest new borrowing candidate после `P_22`: reconnect-aware subscription recovery / resubscribe truth из OsEngine audit.
- эта borrowing idea пока не открывает новую фазу сама по себе и должна оставаться узким future candidate.

# Shared Analysis Source of Truth для derived bar inputs active risk contour

**Дата:** 2026-03-20  
**Статус:** Принято  

## Контекст

После выполнения Phase 6 и Phase 7 в проекте уже зафиксированы две важные truth-линии:

- raw market-data truth живёт в `src/cryptotechnolog/market_data`;
- DERYA-first intelligence truth Phase 7 живёт в `src/cryptotechnolog/intelligence`.

В ходе повторного аудита перед closure `P_7` был обнаружен системный blocker:

- active `Phase 5` risk contour требует отдельный `RISK_BAR_COMPLETED` input path;
- risk-specific payload для этого path требует:
  - `mark_price`
  - `best_bid`
  - `best_ask`
  - `atr`
  - `adx`
- raw `BAR_COMPLETED` из Phase 6 честно содержит только market-data bar contract и не должен
  обратно смешиваться с risk-specific derived payload;
- после разделения `BAR_COMPLETED` и `RISK_BAR_COMPLETED` boundary больше не конфликтует по
  semantics, но в текущем production runtime нет полного source of truth для `atr` и `adx`.

Критические ограничения для решения:

- raw `BAR_COMPLETED` должен оставаться честным market-data/intelligence event;
- synthetic `ATR/ADX` недопустимы;
- active risk contour не должен silently ослаблять свой contract;
- DERYA-first truth `P_7` нельзя задним числом переписывать в broad indicator runtime;
- решение должно оставаться совместимым с composition-root discipline и runtime-truth discipline.

Из этого следует, что blocker нельзя закрыть простым wiring fix без явного архитектурного выбора:
где именно в системе должны жить shared derived inputs для risk contour.

## Рассмотренные варианты

### Вариант 1. Future indicator/intelligence foundation

`ATR/ADX` становятся частью future indicator/intelligence foundation и затем используются risk contour.

### Вариант 2. Local risk-layer source

Risk contour получает собственный локальный source для `ATR/ADX` внутри risk layer.

### Вариант 3. Shared analysis source/truth layer

Появляется отдельный shared analysis source/truth layer, из которого risk contour получает
`ATR/ADX` и другие derived bar inputs, без смешения raw market-data и intelligence semantics.

## Анализ вариантов

### Вариант 1. Future indicator/intelligence foundation

Где живёт source of truth:

- внутри indicator/intelligence foundation.

Кто владеет вычислением:

- future indicator runtime / analysis runtime.

Кто публикует или экспонирует данные:

- indicator/intelligence layer через query/state contracts или typed analysis events.

Совместимость с уже принятой truth:

- raw market-data truth `P_6` не ломает;
- но создаёт давление на `P_7`, потому что текущая truth этой фазы нормализована как
  `DERYA-first intelligence foundation`, а не как полная indicator runtime/library line.

Размер scope:

- выше узкого corrective fix;
- фактически это продолжение незакрытой broader indicator line.

Допустимость как corrective path:

- архитектурно допустим;
- как маленький blocker-fix перед closure — нет.

Риски и trade-offs:

- плюс: derived indicator-like values живут в подходящем analysis слое;
- плюс: risk contour остаётся consumer-ом analysis truth;
- минус: фактически превращает corrective step в расширение `P_7`;
- минус: создаёт риск scope inflation в сторону broader indicator runtime.

### Вариант 2. Local risk-layer source

Где живёт source of truth:

- внутри `src/cryptotechnolog/risk`.

Кто владеет вычислением:

- active risk contour.

Кто публикует или экспонирует данные:

- risk runtime или локальный risk input builder.

Совместимость с уже принятой truth:

- raw market-data truth `P_6` напрямую не ломает;
- DERYA-first truth `P_7` тоже напрямую не ломает;
- но нарушает принцип ownership, потому что indicator-like derived values начинают жить
  в risk layer.

Размер scope:

- средний;
- требует отдельного local foundation внутри risk contour.

Допустимость как corrective path:

- только как осознанный компромисс;
- не как предпочтительное архитектурное решение.

Риски и trade-offs:

- плюс: кажется самым быстрым путём к восстановлению active trailing path;
- плюс: не требует немедленного расширения intelligence line;
- минус: создаёт дублирование truth-источников;
- минус: повышает шанс будущего конфликта между risk-local calculations и shared analysis semantics;
- минус: risk contour начинает владеть вычислениями, которые не являются чисто risk-domain truth.

### Вариант 3. Shared analysis source/truth layer

Где живёт source of truth:

- в отдельном shared analysis source/truth layer;
- не в raw market-data layer;
- не внутри DERYA-first semantics;
- не внутри risk layer.

Кто владеет вычислением:

- отдельный analysis/derived-inputs foundation component.

Кто публикует или экспонирует данные:

- shared analysis runtime через explicit query/state contracts;
- при необходимости отдельный risk-input publisher может быть собран уже поверх этой truth.

Совместимость с уже принятой truth:

- raw market-data truth `P_6` сохраняется без изменений;
- `P_7` не переписывается задним числом в full indicator runtime;
- risk contour остаётся consumer-ом derived analysis truth, а не владельцем indicator-like вычислений.

Размер scope:

- средний или выше среднего;
- это уже отдельный corrective step, а не узкая интеграционная правка.

Допустимость как corrective path:

- да, это предпочтительный corrective path.

Риски и trade-offs:

- плюс: даёт один честный source of truth для shared derived inputs;
- плюс: не смешивает raw market-data contracts с risk-specific payload;
- плюс: лучше всего соответствует composition-root discipline;
- плюс: не искажает Phase 7 DERYA-first truth;
- минус: требует отдельного contract/runtime implementation step;
- минус: откладывает release-level closure `P_7` до завершения `C_7R`.

## Решение

Принят Вариант 3.

### 1. Где должны жить `ATR/ADX`

- `ATR` и `ADX` для active risk contour должны жить в отдельном shared analysis source/truth layer.
- Эти данные не являются raw market-data truth.
- Эти данные не должны вычисляться локально внутри risk layer как основной источник истины.
- Эти данные не должны неявно “приписываться” DERYA-first линии как будто `P_7` уже стала
  полной indicator runtime.

### 2. Кто владеет вычислением

- ownership вычисления принадлежит отдельному analysis-derived inputs foundation.
- Этот foundation должен детерминированно формировать shared derived inputs поверх уже имеющихся
  bar/orderbook/runtime contracts.

### 3. Кто потребляет данные

- active risk contour остаётся consumer-ом derived analysis truth.
- Risk contour не должен владеть indicator-like вычислениями как primary truth.

### 4. Что остаётся неизменным

- raw `BAR_COMPLETED` остаётся честным event Phase 6 для market-data/intelligence path;
- `RISK_BAR_COMPLETED` не смешивается обратно с raw market-data payload;
- DERYA-first truth `P_7` не переписывается задним числом в broad indicator runtime;
- `P_7` не считается закрытой до реализации corrective step `C_7R`.

### 5. Что открывается следующим шагом

Следующим шагом после этого ADR становится отдельная implementation line:

- `C_7R: Risk Bar Input Truth Recovery`

Её задача:

- ввести shared derived-input contracts/runtime truth;
- определить operator-visible readiness для этих inputs;
- только после этого честно восстановить production publisher `RISK_BAR_COMPLETED`.

## Последствия

### Плюсы

- Сохраняется честная граница между raw market-data truth и derived analysis truth.
- Risk contour остаётся consumer-ом, а не владельцем indicator-like вычислений.
- DERYA-first truth `P_7` не раздувается задним числом.
- У проекта появляется архитектурно чистый путь к восстановлению active trailing path.

### Минусы

- Нельзя закрыть blocker одной маленькой wiring-правкой.
- Появляется отдельный corrective scope после `P_7`.
- Closure `P_7` откладывается до завершения `C_7R`.

### Что это означает для Phase 7

- `P_7` не финализируется как release-step на основании одного только DERYA-first success path.
- До завершения `C_7R` Phase 7 остаётся не закрытой на release-level truth.

### Следующий шаг

- открыть отдельную implementation line `C_7R`;
- определить contracts/runtime boundary для shared derived inputs;
- реализовать их без synthetic `ATR/ADX`;
- только после этого возвращаться к вопросу release-level closure `P_7`.

## Связанные ADR

- Связан с `0024-production-alignment-composition-root-and-runtime-truth.md`
- Связан с `0025-market-data-contract-layer-and-universe-semantics.md`
- Связан с `0026-phase7-indicators-intelligence-foundation-and-derya-runtime-boundary.md`

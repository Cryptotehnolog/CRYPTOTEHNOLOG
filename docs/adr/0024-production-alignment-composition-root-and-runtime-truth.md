# Production alignment: единый composition root, single risk path и runtime truth

**Дата:** 2026-03-19  
**Статус:** Принято  

## Контекст
Фаза `P_5_1` запускается после релиза `v1.5.0` как этап архитектурной консолидации, а не как новая feature-phase.

К этому моменту проект уже имеет сильное доменное и системное ядро:
- `RiskLedger` зафиксирован как source of truth по риску открытых позиций;
- `TrailingPolicy` встроен в `Risk Engine` и не может двигать стоп без `RiskLedger sync`;
- новый `Risk Engine` реализован как отдельный современный runtime path;
- controlled coexistence нового и legacy risk-path было осознанно принято в рамках `v1.5.0`.

Одновременно phase summary и оба аудита зафиксировали опасный разрыв между `prompt -> plan -> code -> runtime`:
- верхнеуровневый production bootstrap не собран как единая runtime-сборка;
- legacy/new risk paths сосуществуют без единого bootstrap policy;
- import-time singleton и скрытая инициализация создают хрупкость runtime и тестового bootstrap;
- часть critical runtime metadata расходится между package/settings/health/main;
- в критичных местах остаются мягкие fallback-path, которые маскируют деградацию.

Для работы с реальными деньгами такое состояние недостаточно: платформа должна иметь не просто сильные модули, а однозначный, наблюдаемый и детерминированный production runtime.

Этот ADR нужен как архитектурный мост между:
- итогом Фазы 5 (`P_5_RESULT.md`);
- ADR `0021`, `0022`, `0023`;
- аудитами `AUDIT_P1_P5_BY_PLANS.md` и `AUDIT_P1_P5_BY_PROMPTS.md`;
- следующими шагами `P_5_1`, начиная с `Composition Root`.

## Проблемы текущего состояния
1. У платформы нет одного официального production composition root.
2. В проекте временно сосуществуют два risk-path, но production policy выбора не зафиксирована как обязательный runtime-контракт.
3. Import-time bootstrap и singleton-инициализация создают скрытый runtime state и ломают изолируемость.
4. Ошибки критичных компонентов могут маскироваться через silent fallback вместо fail-fast или явной деградации.
5. Version/config/runtime identity не сведены к одному источнику истины.
6. Без явной архитектурной фиксации следующий рефакторинг снова может оставить частичную консолидацию и новую двусмысленность.

## Рассмотренные альтернативы
1. Оставить текущую структуру и выполнять `P_5_1` как набор локальных рефакторингов без нового ADR.
2. Немедленно перейти к runtime/bootstrap refactor без формальной архитектурной фиксации целевого состояния.
3. Сохранить controlled coexistence как допустимый production-режим и ограничиться мягким bootstrap policy.
4. Зафиксировать для `P_5_1` новый архитектурный контракт: единый composition root, один активный risk path в production, fail-fast/degraded startup policy, запрет import-time bootstrap и единый source of truth для version/config/runtime identity.

## Решение
Принят вариант 4.

### 1. Единый production composition root
- Production runtime платформы должен собираться через один официальный composition root.
- Этот root становится единственной точкой wiring для critical runtime components:
  - settings/config;
  - logging;
  - database / redis;
  - event bus;
  - state machine / system controller / watchdog;
  - metrics / health;
  - listeners;
  - нового `Risk Engine` runtime;
  - startup validation;
  - shutdown lifecycle.
- Никакой другой entrypoint не считается production-валидным, если он обходит этот root или собирает только часть runtime.

### 2. Один активный risk path в production runtime
- В production runtime разрешён ровно один активный risk path.
- Для `P_5_1` production path должен быть новым Phase 5 `Risk Engine` path.
- Legacy `core/listeners/risk.py` может существовать только как:
  - compatibility path;
  - test-only path;
  - явно непроизводственный режим.
- Controlled coexistence из ADR `0023` признаётся допустимым только как переходное состояние для `v1.5.0`, но не как нормальный production режим после architecture lock `P_5_1`.
- Composition root обязан явно выбирать risk path и исключать двойную регистрацию risk listeners.

### 3. Fail-fast / degraded startup policy
- Критичные bootstrap-ошибки не должны маскироваться silent fallback-path.
- Для каждого critical dependency должен существовать явный policy-level outcome:
  - `startup blocked` — запуск запрещён;
  - `startup degraded` — запуск разрешён в явном деградированном режиме;
  - `startup ready` — система готова к работе.
- Решение о `fatal` vs `degraded` принимается явно в bootstrap policy и отражается в observability/runtime metadata.
- Любая деградация должна быть:
  - зафиксирована;
  - наблюдаема;
  - объяснима оператору;
  - связана с Control Plane semantics, а не скрыта внутри singleton/fallback-кода.

### 4. Запрет import-time bootstrap и скрытой singleton-инициализации
- Импорт пакета или модуля не должен:
  - создавать критичный runtime state;
  - поднимать подключения;
  - выбирать bootstrap policy;
  - инициировать production wiring;
  - создавать скрытые global instances как часть обычного import path.
- Lazy factory, explicit bootstrap и controlled test assembly допускаются.
- Import-time singleton допустим только для truly inert metadata, но не для runtime-компонентов, влияющих на wiring, состояние системы или внешние подключения.

### 5. Single source of truth для version/config/runtime identity
- У платформы должен быть один authoritative source для release version.
- Runtime metadata не могут поддерживаться вручную в нескольких местах независимо друг от друга.
- Health, readiness, startup logs, runtime metadata и operator-facing diagnostics обязаны отражать:
  - фактическую версию системы;
  - active risk path;
  - bootstrap mode;
  - config identity / config revision;
  - состояние degraded/fail-fast policy.
- Если часть identity не может быть отражена надёжно, она не должна имитироваться фиктивными строками.

### 6. Обязательный контракт для следующих шагов P_5_1
Начиная с этого ADR, следующие шаги `P_5_1` обязаны:
- строить production runtime только через единый composition root;
- удалять двусмысленность legacy/new risk coexistence из production bootstrap;
- убирать import-time runtime state и скрытую singleton-инициализацию;
- заменять silent fallback на explicit fail-fast/degraded behavior;
- сводить version/config/runtime identity к одному source of truth;
- выравнивать runtime/event contracts только после фиксации composition root и risk-path policy.

Это означает, что локальные изменения, которые сохраняют старую bootstrap-двусмысленность, больше не считаются допустимыми “временными” решениями в рамках `P_5_1`.

## Последствия
- **Плюсы:** дальнейший runtime-refactor получает жёсткий архитектурный ориентир; production bootstrap становится проверяемым, а не договорным; risk cutover перестаёт быть расплывчатым; observability начинает отражать правду о runtime.
- **Плюсы:** ADR `0021` и `0022` получают верхнеуровневую runtime-рамку, в которой их инварианты реально становятся production-инвариантами, а не только доменными правилами отдельных модулей.
- **Плюсы:** ADR `0023` не отменяется задним числом, а аккуратно ограничивается по времени и по режиму применения: controlled coexistence остаётся частью истории `v1.5.0`, но не целевым состоянием production runtime.
- **Минусы:** следующие шаги `P_5_1` становятся жёстче и исключают мягкие обходные решения; часть текущих helper/singleton-path придётся пересмотреть.
- **Минусы:** bootstrap policy и runtime identity потребуют дополнительной дисциплины в коде, тестах, health metadata и документации.
- **Минусы:** некоторые ранее допустимые “удобные” import/fallback-patterns теперь считаются архитектурным нарушением и подлежат удалению.

## Что становится обязательным для следующих шагов P_5_1
1. Шаг 2 `Composition Root`: определить и реализовать единственный production composition root в соответствии с этим ADR.
2. Шаг 3 `Risk Path Consolidation`: вывести legacy risk path из production wiring и сделать новый `Risk Engine` единственным production risk path.
3. Шаг 4 `Import-Time Cleanup`: убрать import-time bootstrap, eager settings/singleton wiring и скрытую global initialization.
4. Шаг 5 `Runtime Truth Alignment`: свести version/config/runtime identity к одному источнику истины и пробросить её в observability.
5. Шаг 6 `Event Contract Alignment`: выравнивать runtime vocabulary только после того, как risk path и composition root уже однозначно определены.
6. Шаг 7 `Observability + Tests`: проверять не отдельные модули, а именно целевой runtime contract, зафиксированный этим ADR.

## Связанные ADR
- Связан с `0021-risk-ledger-source-of-truth.md`
- Связан с `0022-trailing-policy-risk-engine-invariant.md`
- Связан с `0023-risk-engine-controlled-coexistence.md`

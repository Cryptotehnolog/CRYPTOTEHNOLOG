> Historical audit snapshot.
>
> Этот документ не является current project truth.
> Часть findings уже была закрыта последующими фазами и релизами.
> Для актуальной truth нужно смотреть:
> `README.md`, `prompts/plan/P_X.md`, `prompts/plan/P_X_RESULT.md` и текущий код.

## Статус historical findings

### No-longer-current findings

- замечание о том, что [main.py](/D:/CRYPTOTEHNOLOG/src/cryptotechnolog/main.py) остаётся placeholder entrypoint, больше не соответствует текущему коду;
- замечание про version metadata `1.0.0 / 1.4.0 / 1.5.0` больше не является актуальной current issue;
- замечание про import-time settings drift в старой формулировке частично устарело после нормализации runtime identity и lazy settings path.

### Historical architectural context

- observations про более широкий prompt-level scope vs фактический foundation scope остаются полезным historical context;
- observations про funding/eventing/persistence breadth остаются historical context, а не current project truth;
- observations про legacy/new risk-path coexistence и ранний bootstrap adoption нужно читать как historical audit material, а не как current release status.

1. **Высокая серьёзность: новый `Risk Engine` в prompt задуман как рабочий runtime-контур системы, а в коде остаётся отдельной веткой без реального верхнеуровневого adoption.**  
Тип: `prompt -> plan -> code drift`.  
Prompt: в [`06_ФАЗА_5_RISK_ENGINE_PROMPT.md`](/D:/CRYPTOTEHNOLOG/prompts/06_ФАЗА_5_RISK_ENGINE_PROMPT.md) фаза описана как рабочий `Risk Engine`, который реагирует на `ORDER_FILLED`, `BAR_COMPLETED`, `STATE_TRANSITION`, публикует risk-события и живёт в системном event-driven контуре.  
План: [`P_5.md`](/D:/CRYPTOTEHNOLOG/prompts/plan/P_5.md) это в целом сохранил, включая runtime integration и listener integration.  
Код: новый runtime действительно есть в [`runtime.py`](/D:/CRYPTOTEHNOLOG/src/cryptotechnolog/risk/runtime.py#L129), но основной entrypoint платформы остаётся заглушкой в [`main.py`](/D:/CRYPTOTEHNOLOG/src/cryptotechnolog/main.py#L12), а legacy listener registry по умолчанию всё ещё регистрирует старый risk path в [`core/listeners/__init__.py`](/D:/CRYPTOTEHNOLOG/src/cryptotechnolog/core/listeners/__init__.py#L31).  
Что не совпадает: prompt предполагал фазово завершённый рабочий системный контур, а code даёт только готовый foundation/runtime path для controlled adoption.  
Почему это риск: архитектурно `Risk Engine` сильный, но фактически не стал единственным или основным risk runtime платформы. Это создаёт разрыв между “релиз v1.5.0 завершён” и “основной runtime реально живёт на нём”.  
Что лучше сделать: в следующем шаге собрать единый bootstrap/composition root и формально выбрать новый risk path как активный системный контур.

2. **Высокая серьёзность: eventing-контракт Фазы 5 в prompt и плане заметно уже в коде.**  
Тип: `prompt -> plan -> code drift`.  
Prompt: [`06_ФАЗА_5_RISK_ENGINE_PROMPT.md`](/D:/CRYPTOTEHNOLOG/prompts/06_ФАЗА_5_RISK_ENGINE_PROMPT.md#L176) и далее требовал публикации `RISK_VIOLATION`, `DRAWDOWN_ALERT`, `VELOCITY_KILLSWITCH_TRIGGERED`, `FUNDING_ARBITRAGE_FOUND`, а также подписку на `CONFIG_UPDATED`.  
План: [`P_5.md`](/D:/CRYPTOTEHNOLOG/prompts/plan/P_5.md#L310) сохранил эти подписки и публикации почти целиком.  
Код: новый listener обрабатывает только `ORDER_FILLED`, `POSITION_CLOSED`, `BAR_COMPLETED`, `STATE_TRANSITION` и публикует только `RISK_POSITION_REGISTERED`, `RISK_POSITION_RELEASED`, `TRAILING_STOP_MOVED`, `TRAILING_STOP_BLOCKED`, `RISK_ENGINE_STATE_UPDATED` в [`risk/listeners.py`](/D:/CRYPTOTEHNOLOG/src/cryptotechnolog/risk/listeners.py#L67) и [`engine.py`](/D:/CRYPTOTEHNOLOG/src/cryptotechnolog/risk/engine.py#L53).  
Что не совпадает: существенная часть risk-event контракта из prompt/plan не реализована новым path.  
Почему это риск: observability и audit слоям будут не хватать важных risk-domain сигналов, а controlled coexistence станет ещё сложнее из-за разного event vocabulary у legacy и new path.  
Что лучше сделать: либо честно сузить контракт Фазы 5 в документах, либо довести новый listener до публикации хотя бы `RISK_VIOLATION`, `DRAWDOWN_ALERT`, `VELOCITY_KILLSWITCH_TRIGGERED`.

3. **Высокая серьёзность: `FundingManager` в исходном prompt задуман глубже, чем реально реализован.**  
Тип: `prompt -> plan -> code drift`.  
Prompt: [`06_ФАЗА_5_RISK_ENGINE_PROMPT.md`](/D:/CRYPTOTEHNOLOG/prompts/06_ФАЗА_5_RISK_ENGINE_PROMPT.md#L1741) требовал не только detector, но и публикацию `FUNDING_ARBITRAGE_FOUND`, логирование ставок в `funding_rates`, и явную DB-схему [`funding_rates`](/D:/CRYPTOTEHNOLOG/prompts/06_ФАЗА_5_RISK_ENGINE_PROMPT.md#L1961).  
План: [`P_5.md`](/D:/CRYPTOTEHNOLOG/prompts/plan/P_5.md#L228) оставил послабление про v1 read-only detector, но всё равно сохранил `FUNDING_ARBITRAGE_FOUND`, integration в `RiskEngine` и таблицу `funding_rates` в schema section [`P_5.md`](/D:/CRYPTOTEHNOLOG/prompts/plan/P_5.md#L294).  
Код: `FundingManager` автономен и сам это декларирует в [`funding_manager.py`](/D:/CRYPTOTEHNOLOG/src/cryptotechnolog/risk/funding_manager.py#L4); `RiskEngine` прямо говорит, что funding пока не включает в [`engine.py`](/D:/CRYPTOTEHNOLOG/src/cryptotechnolog/risk/engine.py#L173); в migration нет `funding_rates`, только risk/trailing таблицы в [`011_risk_engine_foundation.sql`](/D:/CRYPTOTEHNOLOG/scripts/migrations/011_risk_engine_foundation.sql#L12).  
Что не совпадает: funding остался доменным foundation-модулем, а не частью завершённого risk loop или persistence/eventing слоя.  
Почему это риск: по prompt и даже по plan можно ожидать больше, чем реально даёт релиз `v1.5.0`; особенно это касается audit и event-driven интеграции funding-сценариев.  
Что лучше сделать: либо формально понизить scope funding в документах до foundation-only, либо довести до event/persistence integration.

4. **Средняя серьёзность: PyO3 bindings из исходного Phase 1 prompt так и не были реализованы как требовалось.**  
Тип: `prompt -> plan -> code drift`.  
Prompt: [`02_ФАЗА_1_ЯДРО_ИНФРАСТРУКТУРЫ_PROMPT.md`](/D:/CRYPTOTEHNOLOG/prompts/02_ФАЗА_1_ЯДРО_ИНФРАСТРУКТУРЫ_PROMPT.md#L1063) требовал `crates/eventbus/src/python_bindings.rs`, `PyEventBus`, bridge `tokio <-> asyncio`, а также fast-path `publish_fast`/`publish_batch` [`02_ФАЗА_1_...`](/D:/CRYPTOTEHNOLOG/prompts/02_ФАЗА_1_ЯДРО_ИНФРАСТРУКТУРЫ_PROMPT.md#L528).  
План: [`P_1.md`](/D:/CRYPTOTEHNOLOG/prompts/plan/P_1.md#L54) это требование сохранил, хотя в acceptance уже ослабил формулировку до “реализован Python wrapper в rust_bridge.py” [`P_1.md`](/D:/CRYPTOTEHNOLOG/prompts/plan/P_1.md#L220).  
Код: зависимости `pyo3` и `pyo3-async-runtimes` в `Cargo.toml` есть, но файла `crates/eventbus/src/python_bindings.rs` нет вообще; фактически живёт Python wrapper path.  
Что не совпадает: исходный prompt ожидал рабочую FFI-реализацию, а проект завершил фазу wrapper-решением.  
Почему это риск: это не ломает систему прямо сейчас, но это реальный исторический drift между исходным архитектурным замыслом и реализацией performance-sensitive границы Python/Rust.  
Что лучше сделать: либо оформить это как сознательный ADR и закрепить отказ от PyO3 path, либо действительно вернуть задачу в roadmap и реализовать bindings.

5. **Средняя серьёзность: исходные prompt-файлы системно запрещали TODO/placeholders, но основной runtime проекта всё ещё placeholder.**  
Тип: `prompt -> code gap`.  
Prompt: в Phase 1 prompt есть прямой запрет на TODO/placeholders [`02_ФАЗА_1_...`](/D:/CRYPTOTEHNOLOG/prompts/02_ФАЗА_1_ЯДРО_ИНФРАСТРУКТУРЫ_PROMPT.md#L1537), в Phase 2 prompt этот запрет повторяется [`03_ФАЗА_2_CONTROL_PLANE_PROMPT.md`](/D:/CRYPTOTEHNOLOG/prompts/03_ФАЗА_2_CONTROL_PLANE_PROMPT.md#L1615).  
План: планы в явном виде это уже не форсируют на уровне общего entrypoint.  
Код: [`main.py`](/D:/CRYPTOTEHNOLOG/src/cryptotechnolog/main.py#L44) до сих пор содержит `TODO` и текстовый placeholder, плюс логирует устаревшую версию `1.0.0` [`main.py`](/D:/CRYPTOTEHNOLOG/src/cryptotechnolog/main.py#L41).  
Что не совпадает: формально фазовая линия закрыта до `v1.5.0`, но главный entrypoint остаётся не production-grade, а демонстрационной заглушкой.  
Почему это риск: это снижает архитектурную целостность между “готовыми фазами” и реальной собираемостью платформы как единой системы.  
Что лучше сделать: заменить placeholder на реальный bootstrap или явно убрать `main.py` из роли основного runtime entrypoint.

6. **Средняя серьёзность: релизная/version metadata не доведена до полного соответствия фазовым prompt-версиям.**  
Тип: `prompt -> code gap`.  
Prompt: фазовые prompt-файлы жёстко задают version line `v1.1.0 -> v1.5.0`, а release summary закрепляет `v1.5.0` как завершённый этап.  
План: планы тоже исходят из корректного версионирования каждой фазы.  
Код: `pyproject.toml` и пакет уже на `1.5.0`, но `Settings.project_version` остаётся `1.0.0` в [`settings.py`](/D:/CRYPTOTEHNOLOG/src/cryptotechnolog/config/settings.py#L20), `main.py` логирует `1.0.0` в [`main.py`](/D:/CRYPTOTEHNOLOG/src/cryptotechnolog/main.py#L41), `HealthChecker` возвращает `1.4.0` в [`health.py`](/D:/CRYPTOTEHNOLOG/src/cryptotechnolog/core/health.py#L672).  
Что не совпадает: исходный phase/release замысел выполнен в git и документах, но не синхронизирован во всех runtime metadata путях.  
Почему это риск: мониторинг, support и audit могут видеть неправильную версию системы, что плохо для инцидентов и controlled rollout.  
Что лучше сделать: свести version metadata к одному источнику истины и убрать ручные строки версии из runtime модулей.

7. **Средняя серьёзность: требование prompt-файлов о полной русификации кода и сообщений соблюдено не везде.**  
Тип: `prompt -> code gap`.  
Prompt: Phase 1 и правила проекта требовали русские комментарии, docstrings и логи как обязательное правило [`02_ФАЗА_1_...`](/D:/CRYPTOTEHNOLOG/prompts/02_ФАЗА_1_ЯДРО_ИНФРАСТРУКТУРЫ_PROMPT.md#L1537).  
План: планы это тоже повторяли для фазовых модулей.  
Код: в ряде ключевых файлов остались английские docstrings и сообщения, например [`settings.py`](/D:/CRYPTOTEHNOLOG/src/cryptotechnolog/config/settings.py#L10), [`main.py`](/D:/CRYPTOTEHNOLOG/src/cryptotechnolog/main.py#L13), [`global_instances.py`](/D:/CRYPTOTEHNOLOG/src/cryptotechnolog/core/global_instances.py#L22).  
Что не совпадает: не всё критичное нарушено, но принцип проекта соблюдён не полностью.  
Почему это риск: это не критичный runtime-баг, но это drift от исходного инженерного стандарта, который ухудшает единообразие и снижает дисциплину кода.  
Что лучше сделать: пройтись по core/config entrypoints и выровнять язык сообщений и docstrings до единого проектного стандарта.

**Краткий общий вывод**

По сравнению именно с исходными фазовыми prompt-файлами проект соответствует замыслу не полностью, но по основному направлению довольно близок. Самое важное: доменные и системные ядра реально построены, особенно в `Control Plane`, `Enhanced Event Bus` и новом `Risk Engine`. Самый заметный drift возникает там, где исходные prompt-файлы ожидали не просто foundation, а уже полностью собранный production-like runtime и более широкий event/persistence контракт.

Иначе говоря: проект хорошо соответствует **архитектурному направлению** исходных prompts, но слабее соответствует их **полноте внедрения**. В prompts замысел был жёстче и амбициознее, чем то, что в итоге стало зафиксированным release-state.

**Топ-3 самых важных расхождения между prompt, plan и code**

1. `Risk Engine` по prompt задуман как полноценно встроенный системный runtime-контур, а в code он пока остаётся отдельной современной веткой с controlled coexistence и без полного bootstrap adoption.  
2. Funding-срез в prompt/plan требовал eventing и persistence (`FUNDING_ARBITRAGE_FOUND`, `funding_rates`), а в code остался в основном на уровне автономного domain foundation.  
3. Phase 1 prompt требовал реальный PyO3 bridge `python_bindings.rs`, но фактическая реализация ушла в Python wrapper path и так и не вернулась к исходному FFI-замыслу.

**Findings**

1. Новый `Risk Engine` не подключён к реальному верхнеуровневому bootstrap приложения.  
Что не так: основной entrypoint всё ещё остаётся заглушкой, не собирает `SystemController`, не вызывает `create_risk_runtime(...)` и не поднимает event-driven риск-контур.  
Где: [main.py](/d:/CRYPTOTEHNOLOG/src/cryptotechnolog/main.py#L12), [runtime.py](/d:/CRYPTOTEHNOLOG/src/cryptotechnolog/risk/runtime.py#L129).  
Почему это риск: Фаза 5 заявлена как завершённая, но основной runtime path платформы не использует новый `Risk Engine`; это оставляет критичный разрыв между “реализовано в коде” и “реально работает в приложении”.  
Что лучше сделать: ввести единый composition root для основной платформы и сделать его единственной точкой wiring `SystemController`, `Event Bus`, listeners и нового risk runtime.

2. Controlled coexistence legacy/new risk paths зафиксирован документами, но не зафиксирован единым механизмом выбора в bootstrap.  
Что не так: `register_all_listeners()` по умолчанию регистрирует legacy `RiskListener`, а новый `RiskEngineListener` живёт отдельно; глобального переключателя или единого policy-layer нет.  
Где: [core/listeners/__init__.py](/d:/CRYPTOTEHNOLOG/src/cryptotechnolog/core/listeners/__init__.py#L31), [core/listeners/risk.py](/d:/CRYPTOTEHNOLOG/src/cryptotechnolog/core/listeners/risk.py#L31), [runtime.py](/d:/CRYPTOTEHNOLOG/src/cryptotechnolog/risk/runtime.py#L129).  
Почему это риск: при дальнейшем adoption очень легко получить двойную регистрацию, расхождение логики риска или случайный возврат к legacy-path без явного решения.  
Что лучше сделать: вынести выбор risk-path в один bootstrap policy и гарантировать, что в одном runtime активен ровно один risk listener.

3. Конфигурационный слой остаётся хрупким из-за import-time singleton и побочных эффектов при обычном импорте пакета.  
Что не так: `settings = Settings()` создаётся на import-time, а пакет `cryptotechnolog` сразу импортирует подмодули; это делает импорт зависимым от окружения и создаёт скрытую связность между фазами.  
Где: [settings.py](/d:/CRYPTOTEHNOLOG/src/cryptotechnolog/config/settings.py#L314), [settings.py](/d:/CRYPTOTEHNOLOG/src/cryptotechnolog/config/settings.py#L385), [__init__.py](/d:/CRYPTOTEHNOLOG/src/cryptotechnolog/__init__.py#L12).  
Почему это риск: такие side effects уже ломали test bootstrap и дальше будут мешать bootstrap/runtime refactoring, CLI-инструментам и изолированным тестам.  
Что лучше сделать: сделать settings ленивым cached factory, а пакетный `__init__` оставить максимально side-effect free.

4. Версионная и release metadata расходится между модулями.  
Что не так: пакет и `pyproject.toml` уже на `1.5.0`, но `Settings.project_version` остаётся `1.0.0`, `main.py` логирует `1.0.0`, а `HealthChecker` возвращает `1.4.0`.  
Где: [pyproject.toml](/d:/CRYPTOTEHNOLOG/pyproject.toml#L9), [__init__.py](/d:/CRYPTOTEHNOLOG/src/cryptotechnolog/__init__.py#L7), [settings.py](/d:/CRYPTOTEHNOLOG/src/cryptotechnolog/config/settings.py#L20), [main.py](/d:/CRYPTOTEHNOLOG/src/cryptotechnolog/main.py#L41), [health.py](/d:/CRYPTOTEHNOLOG/src/cryptotechnolog/core/health.py#L672).  
Почему это риск: для operator-facing observability, audit и incident analysis версия системы станет недостоверной.  
Что лучше сделать: держать версию в одном источнике истины и пробрасывать её в settings/health/logging автоматически.

5. `FundingManager` реализован как foundation, но не как реальный risk gate, хотя фазовый план описывал более глубокую интеграцию.  
Что не так: `RiskEngine` сам явно документирует, что funding пока не включает, `FundingManager` автономен, а migration не создаёт `funding_rates`.  
Где: [engine.py](/d:/CRYPTOTEHNOLOG/src/cryptotechnolog/risk/engine.py#L173), [funding_manager.py](/d:/CRYPTOTEHNOLOG/src/cryptotechnolog/risk/funding_manager.py#L4), [011_risk_engine_foundation.sql](/d:/CRYPTOTEHNOLOG/scripts/migrations/011_risk_engine_foundation.sql#L12).  
Почему это риск: релиз `v1.5.0` можно интерпретировать как “funding уже входит в risk loop”, хотя фактически это ещё подготовленный доменный модуль без enforcement и persistence-path.  
Что лучше сделать: в следующем шаге либо честно оставить funding вне risk gate в документах, либо довести его до явного pre-trade/runtime integration со своей схемой хранения.

6. Глобальный `EnhancedEventBus` слишком мягко деградирует при ошибке и может незаметно выключить persistence.  
Что не так: при ошибке создания bus используется fallback-конфигурация без persistence вместо явного провала startup или контролируемой деградации через `SystemController`.  
Где: [global_instances.py](/d:/CRYPTOTEHNOLOG/src/cryptotechnolog/core/global_instances.py#L38).  
Почему это риск: для фаз `P_1–P_5` audit и event durability уже являются критичными; тихое отключение persistence ухудшает наблюдаемость и может скрыть реальную деградацию инфраструктуры.  
Что лучше сделать: поднимать это как явную startup/degradation ошибку и связывать с health/state machine, а не silently fallback в singleton.

**Общий вывод**

Фазы `P_1–P_5` реализованы качественно выше среднего по доменной строгости: особенно сильны `State Machine`, event-driven foundation и новый risk-domain (`RiskLedger`, `TrailingPolicy`, тесты на инварианты, типизированные контракты). Самая сильная сторона проекта сейчас — именно системное мышление в risk-контуре и хорошая тестовая проработка критических сценариев.

Главный риск не в локальной логике модулей, а в стыках между фазами: верхнеуровневый bootstrap всё ещё не догнал архитектуру, controlled coexistence legacy/new path пока остаётся ручным, а конфигурационный/import layer создаёт скрытую хрупкость. То есть ядро стало сильнее, чем текущий способ его сборки в приложение.

**Топ-3 улучшения дальше**

1. Собрать единый production-grade composition root для основной платформы и подключить туда новый `Risk Engine` как единственный выбранный risk path.  
2. Убрать import-time side effects из `settings` и пакетного `__init__`, одновременно выровняв всю release/version metadata к одному источнику истины.  
3. Формализовать policy перехода legacy risk path -> phase5 risk path, чтобы controlled coexistence перестал быть договорённостью и стал проверяемым bootstrap-правилом.
# Тесты CRYPTOTEHNOLOG

> Архивная testing note: этот документ не является authoritative truth для текущего test/CI contour.
> Актуальную truth следует читать по `README.md`, `.github/workflows/ci.yml` и текущему содержимому `tests/`.

Список всех тестов проекта с описанием что проверяется.

---

## CI/CD Jobs

| Job | Где найти в GitHub |
|-----|-------------------|
| **test-python** | Actions → CI → test-python |
| **test-rust** | Actions → CI → test-rust |
| **test-rust-property** | Actions → CI → Rust Property-Based Tests |

---

## Python Tests (99 тестов)

### Unit Tests (`tests/unit/`) — 49 тестов

#### test_data_frame.py (12) — DataFrame утилиты (Pandas/Polars)
- test_pandas_to_polars — конвертация pandas → polars
- test_polars_to_pandas — конвертация polars → pandas
- test_polars_to_polars — polars → polars (pass-through)
- test_pandas_to_pandas — pandas → pandas (pass-through)
- test_invalid_type_to_polars — ошибка при невалидном типе в polars
- test_invalid_type_to_pandas — ошибка при невалидном типе в pandas
- test_calculate_returns_polars — расчёт returns в polars
- test_calculate_returns_pandas — расчёт returns в pandas
- test_calculate_returns_series_error — ошибка при невалидных данных
- test_resample_ohlcv_polars — resample OHLCV в polars
- test_resample_ohlcv_pandas — resample OHLCV в pandas
- test_benchmark_conversion — бенчмарк конвертации

#### test_logging.py (8) — Логирование
- test_configure_logging — настройка логирования
- test_get_logger_returns_logger — получение логгера
- test_get_logger_default_name — имя логгера по умолчанию
- test_get_logger_custom_name — кастомное имя логгера
- test_log_context_binds_values — контекст логирования
- test_log_context_cleanup — очистка контекста
- test_log_exception — логирование исключений
- test_log_performance — логирование производительности

#### test_rust_bridge.py (10) — Rust FFI мост
- test_rust_availability — проверка доступности Rust
- test_get_rust_version — получение версии Rust
- test_calculate_position_size — расчёт размера позиции
- test_calculate_portfolio_risk — расчёт риска портфеля
- test_calculate_expected_return — расчёт ожидаемой доходности
- test_async_calculate_position_size — async версия
- test_async_calculate_portfolio_risk — async версия
- test_calculate_position_size_large_values — большие значения
- test_calculate_portfolio_risk_many_positions — много позиций
- test_calculate_expected_return_edge_cases — граничные случаи

#### test_settings.py (19) — Конфигурация и настройки
- test_settings_load_default_values — значения по умолчанию
- test_settings_load_from_environment — загрузка из env
- test_settings_postgres_url_construction — URL PostgreSQL
- test_settings_postgres_async_url_construction — async URL
- test_settings_redis_url_construction — URL Redis
- test_settings_redis_url_with_password — URL с паролем
- test_settings_log_level_validation — валидация уровня логов
- test_settings_log_format_validation — валидация формата
- test_settings_event_bus_type_validation — валидация event bus
- test_settings_postgres_pool_settings — настройки пула PostgreSQL
- test_settings_redis_pool_settings — настройки пула Redis
- test_settings_repr_hides_secrets — скрытие паролей в repr
- test_validate_settings_success — успешная валидация
- test_validate_settings_invalid_* — ошибки валидации

### Integration Tests (`tests/integration/`) — 50 тестов

#### test_config_layer.py (9) — Слой конфигурации
- test_default_settings — настройки по умолчанию
- test_environment_override — переопределение через env
- test_database_settings — настройки БД
- test_redis_settings — настройки Redis
- test_api_settings — настройки API
- test_configure_logging — настройка логирования
- test_logging_with_environment — логирование с env
- test_settings_and_logging_integration — интеграция
- test_config_validation — валидация конфига

#### test_data_layer.py (13) — Слой данных
- test_to_polars_from_pandas — конвертация в polars
- test_to_pandas_from_polars — конвертация в pandas
- test_to_polars_passthrough — pass-through polars
- test_to_pandas_passthrough — pass-through pandas
- test_invalid_type_raises_error — ошибка при невалидном типе
- test_calculate_returns_pandas — расчёт returns pandas
- test_calculate_returns_polars — расчёт returns polars
- test_resample_ohlcv_pandas — resample pandas
- test_resample_ohlcv_polars — resample polars
- test_benchmark_conversion_pandas — бенчмарк pandas
- test_benchmark_conversion_polars — бенчмарк polars
- test_roundtrip_pandas_polars_pandas — pandas → polars → pandas
- test_roundtrip_polars_pandas_polars — polars → pandas → polars

#### test_infrastructure.py (10) — Инфраструктура
- test_redis_connection — подключение к Redis
- test_redis_set_get — set/get операции
- test_redis_list_operations — list операции
- test_redis_hash_operations — hash операции
- test_postgresql_connection — подключение к PostgreSQL
- test_postgresql_create_table — создание таблицы
- test_postgresql_jsonb_operations — JSONB операции
- test_postgresql_transaction — транзакции
- test_redis_postgresql_integration — интеграция Redis + PostgreSQL
- test_concurrent_operations — параллельные операции

#### test_rust_components.py (18) — Интеграция с Rust
- test_rust_extension_check — проверка доступности Rust
- test_rust_version_retrieval — получение версии Rust
- test_position_serialization — сериализация позиции
- test_event_data_serialization — сериализация событий
- test_risk_metrics_serialization — сериализация метрик риска
- test_float_precision — точность float
- test_string_encoding — кодировка строк
- test_timestamp_formats — форматы timestamp
- test_python_fallback_works — fallback на Python
- test_async_python_fallback_works — async fallback
- test_invalid_input_handling — обработка невалидного ввода
- test_empty_positions_handling — обработка пустых позиций
- test_event_publishing — публикация событий
- test_event_subscription — подписка на события
- test_position_update — обновление позиции
- test_position_retrieval — получение позиции
- test_audit_trail_access — доступ к аудиту

---

## Rust Tests (127 тестов)

### Unit Tests — 83 теста

#### audit-chain (7) — Цепочка аудита
- test_append_record — добавление записи
- test_audit_chain_creation — создание цепочки
- test_chain_linking — связывание
- test_current_hash — текущий хеш
- test_get_records_by_type — получение по типу
- test_integrity_verification — проверка целостности

#### common/error (3) — Обработка ошибок
- test_error_display — отображение ошибки
- test_error_from_io — конвертация IO
- test_result_type — работа с Result

#### common/utils (6) — Утилиты
- test_clamp — ограничение значения
- test_compute_hash — вычисление хеша
- test_compute_hash_deterministic — детерминированность
- test_percentage — проценты
- test_round — округление
- test_validate_range_* — валидация диапазона

#### eventbus/bus (10) — Шина событий
- test_eventbus_capacity — ёмкость
- test_eventbus_is_full — проверка заполненности
- test_eventbus_multiple_events — множество событий
- test_eventbus_multiple_subscribers — множество подписчиков
- test_eventbus_new_channel_based — channel-based
- test_eventbus_new_default — default
- test_eventbus_publish_full_buffer — публикация в полный буфер
- test_eventbus_publish_subscribe — publish/subscribe
- test_eventbus_subscriber_count — количество подписчиков
- test_eventbus_try_recv — try receive

#### eventbus/event (5) — События
- test_event_age — возраст события
- test_event_correlation — корреляция
- test_event_creation — создание
- test_event_with_correlation_id — с correlation ID
- test_event_with_metadata — с метаданными

#### execution-core (8) — Движок исполнения
- test_execution_engine_creation — создание движка
- test_order_creation — создание ордера
- test_stop_loss_order — stop-loss
- test_trailing_stop_order — trailing-stop
- test_order_fill — исполнение
- test_order_matching — сопоставление
- test_order_cancellation — отмена
- test_oco_group — OCO группа

#### execution-core FFI (4) — FFI интерфейс
- test_calculate_expected_return — расчёт доходности
- test_calculate_portfolio_risk — расчёт риска
- test_calculate_position_size — расчёт позиции
- test_calculate_position_size_zero_risk — нулевой риск

#### risk-ledger/ledger (7) — Реестр рисков
- test_audit_integration — интеграция аудита
- test_audit_multiple_updates — множественные обновления
- test_merkle_proof — Merkle proof
- test_portfolio_calculation — расчёт портфеля
- test_risk_ledger_creation — создание
- test_update_position — обновление позиции
- test_wal_replay — replay WAL

#### risk-ledger/risk (2) — Калькулятор рисков
- test_risk_calculator_creation — создание
- test_risk_metrics_serialization — сериализация

#### risk-ledger/merkle (6) — Дерево Меркла
- test_merkle_proof_generation — генерация proof
- test_merkle_proof_verification — верификация
- test_merkle_tree_creation — создание дерева
- test_merkle_tree_empty — пустое дерево
- test_merkle_tree_odd_leaves — нечётные листья
- test_merkle_tree_root — корень

#### risk-ledger/validation (8) — Валидация
- test_double_entry_validation_imbalance — дисбаланс
- test_double_entry_validation_success — успех
- test_transaction_creation — создание транзакции
- test_validate_amount_invalid — невалидная сумма
- test_validate_amount_valid — валидная сумма
- test_validate_balance_insufficient — недостаточный баланс
- test_validate_balance_success — успешная проверка
- test_validator_with_tolerance — с допуском

#### risk-ledger/wal (3) — Write-Ahead Log
- test_wal_append_and_replay — append и replay
- test_wal_entry_creation — создание entry
- test_wal_multiple_entries — множественные entries

#### ring_buffer (4) — Кольцевой буфер
- test_ring_buffer_new — создание
- test_ring_buffer_push_pop — push/pop
- test_ring_buffer_overwrite — перезапись
- test_ring_buffer_is_full — проверка полноты

---

### Property-Based Tests (44 × 10,000 итераций)

#### property_merkle.rs (10) — Job: test-rust-property
- test_merkle_proof_verification — верификация proof
- test_merkle_proof_wrong_leaf — proof для другого листа
- test_merkle_root_consistency — консистентность root
- test_merkle_modified_leaf — изменение листа
- test_merkle_empty_tree — пустое дерево
- test_merkle_single_leaf — один лист
- test_merkle_leaves_count — подсчёт листьев
- test_merkle_height — высота дерева
- test_merkle_odd_leaves — нечётное кол-во
- test_merkle_proof_path_length — длина path

#### property_validation.rs (8) — Job: test-rust-property
- test_double_entry_balanced_transactions — баланс дебет/кредит
- test_double_entry_unbalanced_transactions — несбалансированные
- test_double_entry_validation_consistency — консистентность
- test_single_balanced_pair — одна пара
- test_multiple_accounts_net_zero — несколько аккаунтов
- test_amount_validation_rejects_invalid — невалидные суммы
- test_amount_validation_accepts_valid — валидные суммы
- test_balance_validation — баланс аккаунта

#### property_order_matching.rs (8) — Job: test-rust-property
- test_trades_not_exceed_quantity — лимит сделок
- test_trade_price_within_spread — цена в спреде
- test_trade_value_calculation — расчёт стоимости
- test_market_order_executes — market ордера
- test_different_symbols_no_match — разные символы
- test_same_side_no_match — одна сторона
- test_partial_fill — частичное исполнение
- test_trade_order_ids — ID ордеров в сделках

#### property_risk_calculation.rs (18) — Job: test-rust-property
- test_position_size_non_negative — позиция не отрицательная
- test_risk_within_balance — риск в балансе
- test_stop_loss_long_below_entry — stop-loss long
- test_stop_loss_short_above_entry — stop-loss short
- test_long_pnl_positive — long PnL +
- test_long_pnl_negative — long PnL -
- test_short_pnl_positive — short PnL +
- test_short_pnl_negative — short PnL -
- test_pnl_zero_at_entry — PnL = 0
- test_margin_non_negative — маржа не отрицательная
- test_higher_leverage_less_margin — плечо и маржа
- test_liquidation_long_calculation — ликвидация long
- test_liquidation_short_calculation — ликвидация short
- test_liquidation_on_losing_side — ликвидация на проигрышной
- test_position_size_scales_with_balance — масштабирование
- test_risk_percent_independent_ratio — независимость
- test_amount_validation_accepts_valid — валидация
- test_balance_validation — баланс

---

## Итого

| Категория | Количество |
|-----------|------------|
| Python Unit | 49 |
| Python Integration | 50 |
| Rust Unit | 83 |
| Rust Property-Based | 44 × 10,000 итераций |

**Всего: 226 тестов**

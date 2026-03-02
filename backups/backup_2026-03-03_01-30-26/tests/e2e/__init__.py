# ==================== CRYPTOTEHNOLOG E2E Tests ====================
# End-to-End test suite for trading system

# E2E тесты проверяют систему от начала до конца, как настоящий пользователь.
# Запускаются через: pytest tests/e2e/ -v
#
# Структура:
# - test_trading_flow.py      -> Core Trading Flow (15 тестов)
# - test_risk_management.py   -> Risk Management (20 тестов)
# - test_multi_asset.py       -> Multi-Asset & Multi-Market (15 тестов)
# - test_performance.py       -> Performance & Stability (12 тестов)
# - test_data_integrity.py    -> Data Integrity (12 тестов)
# - test_edge_cases.py        -> Edge Cases & Failures (15 тестов)
# - test_compliance.py        -> Compliance & Audit (10 тестов)
#
# Запуск всех E2E тестов:
#   pytest tests/e2e/ -v --tb=short
#
# Запуск конкретной категории:
#   pytest tests/e2e/test_trading_flow.py -v

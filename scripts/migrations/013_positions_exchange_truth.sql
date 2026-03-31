-- ==================== CRYPTOTEHNOLOG SQL Migration ====================
-- Version: 013
-- Description: Surface canonical exchange truth for open/closed positions
-- Author: CRYPTOTEHNOLOG Team
-- Created: 2026-03-30
-- ============================================================

ALTER TABLE position_risk_ledger
    ADD COLUMN IF NOT EXISTS exchange_id VARCHAR(50) NOT NULL DEFAULT 'bybit';

ALTER TABLE closed_position_history
    ADD COLUMN IF NOT EXISTS exchange_id VARCHAR(50) NOT NULL DEFAULT 'bybit';

CREATE INDEX IF NOT EXISTS idx_position_risk_ledger_exchange_symbol
    ON position_risk_ledger(exchange_id, symbol);

CREATE INDEX IF NOT EXISTS idx_closed_position_history_exchange_closed_at
    ON closed_position_history(exchange_id, closed_at DESC);

COMMENT ON COLUMN position_risk_ledger.exchange_id IS 'Каноническая биржа активной позиции';
COMMENT ON COLUMN closed_position_history.exchange_id IS 'Каноническая биржа закрытой позиции';

INSERT INTO schema_migrations (version, description)
VALUES ('013', 'Surface canonical exchange truth for positions')
ON CONFLICT (version) DO NOTHING;

BEGIN;

ALTER TABLE position_risk_ledger
    ADD COLUMN IF NOT EXISTS current_price NUMERIC(20, 8) NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS unrealized_pnl_usd NUMERIC(20, 8) NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS unrealized_pnl_percent NUMERIC(20, 8) NOT NULL DEFAULT 0;

CREATE INDEX IF NOT EXISTS idx_position_risk_ledger_mark_price
    ON position_risk_ledger(current_price, updated_at DESC);

COMMIT;

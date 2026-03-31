BEGIN;

ALTER TABLE closed_position_history
    ADD COLUMN IF NOT EXISTS realized_pnl_usd NUMERIC(20, 8),
    ADD COLUMN IF NOT EXISTS realized_pnl_percent NUMERIC(20, 8);

CREATE INDEX IF NOT EXISTS idx_closed_position_history_realized_pnl_usd
    ON closed_position_history(realized_pnl_usd, closed_at DESC);

COMMIT;

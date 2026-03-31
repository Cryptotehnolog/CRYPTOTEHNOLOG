BEGIN;

ALTER TABLE closed_position_history
    ADD COLUMN IF NOT EXISTS exit_price NUMERIC(20, 8),
    ADD COLUMN IF NOT EXISTS exit_reason TEXT;

CREATE INDEX IF NOT EXISTS idx_closed_position_history_exit_reason_closed_at
    ON closed_position_history(exit_reason, closed_at DESC);

COMMIT;

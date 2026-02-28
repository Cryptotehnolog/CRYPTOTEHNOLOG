-- ============================================================
-- Migration 007: Add status columns to orders and positions
-- ============================================================

-- Add status column to orders if not exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'orders' AND column_name = 'status'
    ) THEN
        ALTER TABLE orders ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'pending';
    END IF;
END $$;

-- Add status column to positions if not exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'positions' AND column_name = 'status'
    ) THEN
        ALTER TABLE positions ADD COLUMN status VARCHAR(20) DEFAULT 'open';
    END IF;
END $$;

-- Add additional columns to orders if not exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'orders' AND column_name = 'client_order_id'
    ) THEN
        ALTER TABLE orders ADD COLUMN client_order_id VARCHAR(100);
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'orders' AND column_name = 'exchange_order_id'
    ) THEN
        ALTER TABLE orders ADD COLUMN exchange_order_id VARCHAR(100);
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'orders' AND column_name = 'state'
    ) THEN
        ALTER TABLE orders ADD COLUMN state VARCHAR(50) DEFAULT 'pending';
    END IF;
END $$;

-- Add additional columns to positions if not exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'positions' AND column_name = 'position_id'
    ) THEN
        ALTER TABLE positions ADD COLUMN position_id VARCHAR(100);
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'positions' AND column_name = 'leverage'
    ) THEN
        ALTER TABLE positions ADD COLUMN leverage REAL DEFAULT 1.0;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'positions' AND column_name = 'margin_used'
    ) THEN
        ALTER TABLE positions ADD COLUMN margin_used REAL DEFAULT 0;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'positions' AND column_name = 'liquidation_price'
    ) THEN
        ALTER TABLE positions ADD COLUMN liquidation_price REAL;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'positions' AND column_name = 'closed_at'
    ) THEN
        ALTER TABLE positions ADD COLUMN closed_at TIMESTAMP;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'positions' AND column_name = 'metadata'
    ) THEN
        ALTER TABLE positions ADD COLUMN metadata JSONB DEFAULT '{}'::jsonb;
    END IF;
END $$;

-- Migration Metadata
INSERT INTO schema_migrations (version, description)
VALUES ('007', 'Add status columns to orders and positions')
ON CONFLICT (version) DO NOTHING;

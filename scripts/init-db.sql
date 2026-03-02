-- ==================== CRYPTOTEHNOLOG Database Initialization Script ====================
-- PostgreSQL + TimescaleDB initialization for development environment
-- NOTE: This script only creates extensions. Tables are created via migrations.
-- Run: psql -f scripts/init-db.sql -d trading_dev
-- Then: psql -f scripts/migrations/001_initial_schema.sql -d trading_dev
-- ... and all subsequent migrations

-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Create UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create pgcrypto extension for cryptographic functions
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Output message
DO $$
BEGIN
    RAISE NOTICE '========================================';
    RAISE NOTICE 'CRYPTOTEHNOLOG Database Extensions';
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Extensions installed: timescaledb, uuid-ossp, pgcrypto';
    RAISE NOTICE 'Tables should be created via migrations';
    RAISE NOTICE '========================================';
END $$;

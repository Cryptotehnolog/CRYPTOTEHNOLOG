-- ==================== CRYPTOTEHNOLOG SQL Migration ====================
-- Version: 005
-- Description: Backup, Recovery, and Maintenance Tables
-- Created: 2026-02-28
-- Author: CRYPTOTEHNOLOG Team
-- ============================================================

-- ============================================================
-- Section 1: Backup Records
-- ============================================================

-- Backup History (track all backups)
CREATE TABLE IF NOT EXISTS backup_history (
    id SERIAL PRIMARY KEY,
    backup_type VARCHAR(20) NOT NULL,
    backup_method VARCHAR(50) NOT NULL,
    file_path TEXT,
    file_size_bytes BIGINT,
    checksum VARCHAR(64),
    status VARCHAR(20) NOT NULL DEFAULT 'in_progress',
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    
    CONSTRAINT chk_backup_type CHECK (backup_type IN ('full', 'incremental', 'config', 'state')),
    CONSTRAINT chk_backup_method CHECK (backup_method IN ('pg_dump', 'custom', 's3', 'gcs', 'azure')),
    CONSTRAINT chk_backup_status CHECK (status IN ('in_progress', 'completed', 'failed', 'verified'))
);

-- ============================================================
-- Section 2: Point-in-Time Recovery
-- ============================================================

-- Recovery Points (PITR markers)
CREATE TABLE IF NOT EXISTS recovery_points (
    id SERIAL PRIMARY KEY,
    recovery_time TIMESTAMP WITH TIME ZONE NOT NULL UNIQUE,
    backup_id INTEGER REFERENCES backup_history(id),
    wal_location TEXT,
    is_consistent BOOLEAN DEFAULT FALSE,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================
-- Section 3: System State Snapshots
-- ============================================================

-- System State Snapshots (periodic state captures)
CREATE TABLE IF NOT EXISTS system_snapshots (
    id BIGSERIAL PRIMARY KEY,
    snapshot_type VARCHAR(50) NOT NULL,
    snapshot_data JSONB NOT NULL,
    version INTEGER NOT NULL,
    checksum VARCHAR(64),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    description TEXT,
    
    CONSTRAINT chk_snapshot_type CHECK (
        snapshot_type IN ('full', 'positions', 'orders', 'risk_state', 'state_machine')
    )
);

-- ============================================================
-- Section 4: Health and Monitoring
-- ============================================================

-- System Health Checks
CREATE TABLE IF NOT EXISTS health_checks (
    id BIGSERIAL PRIMARY KEY,
    check_name VARCHAR(100) NOT NULL,
    component VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL,
    message TEXT,
    details JSONB DEFAULT '{}'::jsonb,
    checked_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT chk_health_status CHECK (status IN ('healthy', 'degraded', 'unhealthy', 'unknown'))
);

-- Component Heartbeats
CREATE TABLE IF NOT EXISTS component_heartbeats (
    id SERIAL PRIMARY KEY,
    component_name VARCHAR(100) NOT NULL UNIQUE,
    last_heartbeat TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    status VARCHAR(20) DEFAULT 'alive',
    version VARCHAR(50),
    metadata JSONB DEFAULT '{}'::jsonb,
    
    CONSTRAINT chk_heartbeat_status CHECK (status IN ('alive', 'stalled', 'dead'))
);

-- ============================================================
-- Section 5: Maintenance Tasks
-- ============================================================

-- Scheduled Maintenance Tasks
CREATE TABLE IF NOT EXISTS maintenance_tasks (
    id SERIAL PRIMARY KEY,
    task_name VARCHAR(100) NOT NULL UNIQUE,
    task_type VARCHAR(50) NOT NULL,
    schedule_expr VARCHAR(100),
    enabled BOOLEAN DEFAULT TRUE,
    last_run_at TIMESTAMP WITH TIME ZONE,
    next_run_at TIMESTAMP WITH TIME ZONE,
    run_count INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    failure_count INTEGER DEFAULT 0,
    last_error TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT chk_task_type CHECK (
        task_type IN ('vacuum', 'analyze', 'reindex', 'backup', 'cleanup', 'snapshot', 'health_check')
    )
);

-- Maintenance Task History
CREATE TABLE IF NOT EXISTS maintenance_task_history (
    id BIGSERIAL PRIMARY KEY,
    task_id INTEGER NOT NULL REFERENCES maintenance_tasks(id),
    status VARCHAR(20) NOT NULL,
    started_at TIMESTAMP WITH TIME ZONE NOT NULL,
    completed_at TIMESTAMP WITH TIME ZONE,
    rows_affected BIGINT DEFAULT 0,
    error_message TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    
    CONSTRAINT chk_task_history_status CHECK (status IN ('running', 'completed', 'failed', 'cancelled'))
);

-- ============================================================
-- Section 6: Indexes
-- ============================================================

-- Backup History indexes
CREATE INDEX IF NOT EXISTS idx_backup_history_status ON backup_history(status);
CREATE INDEX IF NOT EXISTS idx_backup_history_type ON backup_history(backup_type);
CREATE INDEX IF NOT EXISTS idx_backup_history_started ON backup_history(started_at DESC);

-- Recovery Points indexes
CREATE INDEX IF NOT EXISTS idx_recovery_points_time ON recovery_points(recovery_time DESC);

-- System Snapshots indexes
CREATE INDEX IF NOT EXISTS idx_system_snapshots_type ON system_snapshots(snapshot_type);
CREATE INDEX IF NOT EXISTS idx_system_snapshots_created ON system_snapshots(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_system_snapshots_version ON system_snapshots(snapshot_type, version DESC);

-- Health Checks indexes
CREATE INDEX IF NOT EXISTS idx_health_checks_component ON health_checks(component);
CREATE INDEX IF NOT EXISTS idx_health_checks_status ON health_checks(status);
CREATE INDEX IF NOT EXISTS idx_health_checks_checked ON health_checks(checked_at DESC);

-- Component Heartbeats indexes
CREATE INDEX IF NOT EXISTS idx_component_heartbeats_status ON component_heartbeats(status) WHERE status != 'dead';
CREATE INDEX IF NOT EXISTS idx_component_heartbeats_last ON component_heartbeats(last_heartbeat DESC);

-- Maintenance Tasks indexes
CREATE INDEX IF NOT EXISTS idx_maintenance_tasks_enabled ON maintenance_tasks(enabled) WHERE enabled = TRUE;
CREATE INDEX IF NOT EXISTS idx_maintenance_tasks_next_run ON maintenance_tasks(next_run_at) WHERE next_run_at IS NOT NULL;

-- Maintenance Task History indexes
CREATE INDEX IF NOT EXISTS idx_maintenance_task_history_task ON maintenance_task_history(task_id);
CREATE INDEX IF NOT EXISTS idx_maintenance_task_history_started ON maintenance_task_history(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_maintenance_task_history_status ON maintenance_task_history(status);

-- ============================================================
-- Default Maintenance Tasks
-- ============================================================

INSERT INTO maintenance_tasks (task_name, task_type, schedule_expr, enabled) VALUES
    ('daily_vacuum', 'vacuum', '0 2 * * *', TRUE),
    ('hourly_analyze', 'analyze', '0 * * * *', TRUE),
    ('daily_backup', 'backup', '0 3 * * *', TRUE),
    ('daily_snapshot', 'snapshot', '0 4 * * *', TRUE),
    ('hourly_health_check', 'health_check', '0 * * * *', TRUE),
    ('cleanup_old_events', 'cleanup', '0 5 * * 0', TRUE)
ON CONFLICT (task_name) DO NOTHING;

-- ============================================================
-- Migration Metadata
-- ============================================================

INSERT INTO schema_migrations (version, description)
VALUES ('005', 'Backup, Recovery, and Maintenance Tables')
ON CONFLICT (version) DO NOTHING;

-- ============================================================
-- Comments for Documentation
-- ============================================================

COMMENT ON TABLE backup_history IS 'Track all database backups';
COMMENT ON TABLE recovery_points IS 'Point-in-time recovery markers';
COMMENT ON TABLE system_snapshots IS 'Periodic system state captures';
COMMENT ON TABLE health_checks IS 'System health check results';
COMMENT ON TABLE component_heartbeats IS 'Component alive tracking';
COMMENT ON TABLE maintenance_tasks IS 'Scheduled maintenance task definitions';
COMMENT ON TABLE maintenance_task_history IS 'Maintenance task execution history';

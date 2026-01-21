-- ═══════════════════════════════════════════════════════
-- Database Fix Script - Add Missing Columns and Tables
-- ═══════════════════════════════════════════════════════
-- 
-- This script fixes the database schema by adding missing columns and tables
-- Run this in phpMyAdmin after selecting the '200account' database
-- ═══════════════════════════════════════════════════════

USE `200account`;

-- ═══════════════════════════════════════════════════════
-- 1. ADD MISSING COLUMN: is_active to accounts table
-- ═══════════════════════════════════════════════════════
-- Check if column exists and add it if missing
SET @column_exists = (
    SELECT COUNT(*)
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = '200account'
    AND TABLE_NAME = 'accounts'
    AND COLUMN_NAME = 'is_active'
);

-- Add the column if it doesn't exist
SET @sql = IF(@column_exists = 0,
    'ALTER TABLE accounts ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT TRUE AFTER login_url',
    'SELECT "Column is_active already exists in accounts table" AS message'
);

PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Add index on is_active
SET @index_exists = (
    SELECT COUNT(*)
    FROM INFORMATION_SCHEMA.STATISTICS
    WHERE TABLE_SCHEMA = '200account'
    AND TABLE_NAME = 'accounts'
    AND INDEX_NAME = 'idx_accounts_is_active'
);

SET @sql_index = IF(@index_exists = 0,
    'CREATE INDEX idx_accounts_is_active ON accounts(is_active)',
    'SELECT "Index idx_accounts_is_active already exists" AS message'
);

PREPARE stmt FROM @sql_index;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Create composite index for is_active and status
SET @composite_index_exists = (
    SELECT COUNT(*)
    FROM INFORMATION_SCHEMA.STATISTICS
    WHERE TABLE_SCHEMA = '200account'
    AND TABLE_NAME = 'accounts'
    AND INDEX_NAME = 'idx_accounts_status_active'
);

SET @sql_composite = IF(@composite_index_exists = 0,
    'CREATE INDEX idx_accounts_status_active ON accounts(is_active, status)',
    'SELECT "Composite index idx_accounts_status_active already exists" AS message'
);

PREPARE stmt FROM @sql_composite;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- ═══════════════════════════════════════════════════════
-- 2. CREATE TABLE: account_logs (if not exists)
-- ═══════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS account_logs (
    id CHAR(36) PRIMARY KEY,
    account_id CHAR(36) NOT NULL,
    
    -- Action Details
    action_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL,
    message TEXT,
    error_detail JSON,
    execution_time FLOAT,
    
    -- Tracing
    request_id VARCHAR(100),
    
    -- Code Location (for linking to source code)
    file_path VARCHAR(500),
    function_name VARCHAR(200),
    line_number INTEGER,
    
    -- Timestamp
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- Indexes (create indexes before foreign key)
    INDEX idx_account_logs_account_id (account_id),
    INDEX idx_account_logs_action_type (action_type),
    INDEX idx_account_logs_status (status),
    INDEX idx_account_logs_created_at (created_at DESC),
    INDEX idx_account_logs_request_id (request_id),
    INDEX idx_account_logs_account_created (account_id, created_at DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Add foreign key constraint separately to avoid charset issues
SET @fk_exists = (
    SELECT COUNT(*)
    FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
    WHERE TABLE_SCHEMA = '200account'
    AND TABLE_NAME = 'account_logs'
    AND CONSTRAINT_TYPE = 'FOREIGN KEY'
    AND CONSTRAINT_NAME LIKE '%account_id%'
);

SET @sql_fk = IF(@fk_exists = 0,
    'ALTER TABLE account_logs ADD CONSTRAINT fk_account_logs_account_id FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE',
    'SELECT "Foreign key constraint already exists" AS message'
);

PREPARE stmt FROM @sql_fk;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- ═══════════════════════════════════════════════════════
-- 3. CREATE TABLE: session_histories (if not exists)
-- ═══════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS session_histories (
    id CHAR(36) PRIMARY KEY,
    account_id CHAR(36) NOT NULL,
    
    -- Detection Info
    detection_type VARCHAR(50) NOT NULL,
    is_manual_operation BOOLEAN NOT NULL DEFAULT FALSE,
    conflict_detected BOOLEAN NOT NULL DEFAULT FALSE,
    action_taken VARCHAR(50),
    
    -- Session Info
    session_token TEXT,
    detection_data JSON,
    
    -- Timestamp
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- Indexes
    INDEX idx_session_histories_account_id (account_id),
    INDEX idx_session_histories_created_at (created_at DESC),
    INDEX idx_session_histories_conflict (conflict_detected, created_at DESC),
    INDEX idx_session_histories_detection_type (detection_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Add foreign key constraint separately
SET @fk_exists2 = (
    SELECT COUNT(*)
    FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
    WHERE TABLE_SCHEMA = '200account'
    AND TABLE_NAME = 'session_histories'
    AND CONSTRAINT_TYPE = 'FOREIGN KEY'
    AND CONSTRAINT_NAME LIKE '%account_id%'
);

SET @sql_fk2 = IF(@fk_exists2 = 0,
    'ALTER TABLE session_histories ADD CONSTRAINT fk_session_histories_account_id FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE',
    'SELECT "Foreign key constraint already exists" AS message'
);

PREPARE stmt FROM @sql_fk2;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- ═══════════════════════════════════════════════════════
-- 4. CREATE TABLE: system_configs (if not exists)
-- ═══════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS system_configs (
    id CHAR(36) PRIMARY KEY,
    key VARCHAR(100) UNIQUE NOT NULL,
    value JSON NOT NULL,
    description TEXT,
    is_system BOOLEAN NOT NULL DEFAULT FALSE,
    
    -- Timestamps
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    -- Index
    INDEX idx_system_configs_key (key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ═══════════════════════════════════════════════════════
-- 5. INSERT DEFAULT SYSTEM CONFIGS (if not exists)
-- ═══════════════════════════════════════════════════════
INSERT INTO system_configs (id, key, value, description, is_system) VALUES
    (UUID(), 'schedule_update_enabled', 'true', 'スケジュール自動更新の有効/無効', TRUE),
    (UUID(), 'wait_reception_enabled', 'true', '待機接客自動設定の有効/無効', TRUE),
    (UUID(), 'max_concurrent_accounts', '10', '最大並列処理数', TRUE),
    (UUID(), 'session_check_interval', '5', 'セッション監視間隔（秒）', TRUE),
    (UUID(), 'manual_operation_window', '30', '手動操作検知ウィンドウ（秒）', TRUE),
    (UUID(), 'max_retry_count', '3', '最大リトライ回数', TRUE)
ON DUPLICATE KEY UPDATE key=key;

-- ═══════════════════════════════════════════════════════
-- SUCCESS MESSAGE
-- ═══════════════════════════════════════════════════════
SELECT 'Database fix completed successfully!' AS message;
SELECT 'The following changes were made:' AS info;
SELECT '1. Added is_active column to accounts table (if missing)' AS change1;
SELECT '2. Created account_logs table (if missing)' AS change2;
SELECT '3. Created session_histories table (if missing)' AS change3;
SELECT '4. Created system_configs table (if missing)' AS change4;
SELECT '5. Inserted default system configs' AS change5;

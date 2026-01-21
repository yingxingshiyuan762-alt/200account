-- ═══════════════════════════════════════════════════════
-- MySQL Database Schema for 200 Accounts Automation
-- ═══════════════════════════════════════════════════════
-- 
-- Instructions:
-- 1. Open phpMyAdmin: http://localhost/phpmyadmin/
-- 2. Create database '200account' if it doesn't exist
-- 3. Select the '200account' database
-- 4. Go to SQL tab
-- 5. Copy and paste this entire file
-- 6. Click "Go" or execute the SQL
-- ═══════════════════════════════════════════════════════

-- Create database if it doesn't exist
CREATE DATABASE IF NOT EXISTS `200account` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE `200account`;

-- ═══════════════════════════════════════════════════════
-- 1. ACCOUNTS TABLE (Main table for 200 accounts)
-- ═══════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS accounts (
    id CHAR(36) PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    password_encrypted TEXT NOT NULL,
    store_name VARCHAR(200) NOT NULL,
    login_url VARCHAR(255),
    
    -- Status Management
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    status VARCHAR(50) NOT NULL DEFAULT 'IDLE',
    
    -- Session Management
    session_token TEXT,
    last_login_at DATETIME,
    last_success_at DATETIME,
    
    -- Error Tracking
    error_count INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    
    -- Metadata (MySQL uses JSON type)
    metadata_json JSON,
    
    -- Timestamps
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    -- Indexes
    INDEX idx_accounts_username (username),
    INDEX idx_accounts_is_active (is_active),
    INDEX idx_accounts_status (status),
    INDEX idx_accounts_status_active (is_active, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ═══════════════════════════════════════════════════════
-- 2. ACCOUNT_LOGS TABLE (Operation history)
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
    
    -- Foreign Key
    FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE,
    
    -- Indexes
    INDEX idx_account_logs_account_id (account_id),
    INDEX idx_account_logs_action_type (action_type),
    INDEX idx_account_logs_status (status),
    INDEX idx_account_logs_created_at (created_at DESC),
    INDEX idx_account_logs_request_id (request_id),
    INDEX idx_account_logs_account_created (account_id, created_at DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ═══════════════════════════════════════════════════════
-- 3. SESSION_HISTORIES TABLE (Conflict detection logs)
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
    
    -- Foreign Key
    FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE,
    
    -- Indexes
    INDEX idx_session_histories_account_id (account_id),
    INDEX idx_session_histories_created_at (created_at DESC),
    INDEX idx_session_histories_conflict (conflict_detected, created_at DESC),
    INDEX idx_session_histories_detection_type (detection_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ═══════════════════════════════════════════════════════
-- 4. SYSTEM_CONFIGS TABLE (System settings)
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
-- 5. INSERT DEFAULT SYSTEM CONFIGS
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
SELECT 'Database schema created successfully!' AS message;
SELECT 'Tables created: accounts, account_logs, session_histories, system_configs' AS info;

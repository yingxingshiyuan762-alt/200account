-- ═══════════════════════════════════════════════════════
-- Supabase Database Schema for 200 Accounts Automation
-- ═══════════════════════════════════════════════════════
-- 
-- Instructions:
-- 1. Open Supabase Dashboard
-- 2. Go to SQL Editor
-- 3. Click "New Query"
-- 4. Copy and paste this entire file
-- 5. Click "Run" (or press Ctrl+Enter)
-- 6. Verify: You should see "Success. No rows returned"
--
-- ═══════════════════════════════════════════════════════

-- ═══════════════════════════════════════════════════════
-- 1. ACCOUNTS TABLE (Main table for 200 accounts)
-- ═══════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(100) UNIQUE NOT NULL,
    password_encrypted TEXT NOT NULL,
    store_name VARCHAR(200) NOT NULL,
    login_url VARCHAR(255),
    
    -- Status Management
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    status VARCHAR(50) NOT NULL DEFAULT 'IDLE',
    
    -- Session Management
    session_token TEXT,
    last_login_at TIMESTAMP WITH TIME ZONE,
    last_success_at TIMESTAMP WITH TIME ZONE,
    
    -- Error Tracking
    error_count INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    
    -- Metadata
    metadata_json JSONB,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_accounts_username ON accounts(username);
CREATE INDEX IF NOT EXISTS idx_accounts_status_active ON accounts(is_active, status);
CREATE INDEX IF NOT EXISTS idx_accounts_status ON accounts(status) WHERE is_active = TRUE;

-- ═══════════════════════════════════════════════════════
-- 2. ACCOUNT_LOGS TABLE (Operation history)
-- ═══════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS account_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    
    -- Action Details
    action_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL,
    message TEXT,
    error_detail JSONB,
    execution_time FLOAT,
    
    -- Tracing
    request_id VARCHAR(100),
    
    -- Timestamp
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_account_logs_account_id ON account_logs(account_id);
CREATE INDEX IF NOT EXISTS idx_account_logs_created_at ON account_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_account_logs_account_created ON account_logs(account_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_account_logs_action_status ON account_logs(action_type, status);
CREATE INDEX IF NOT EXISTS idx_account_logs_request_id ON account_logs(request_id);

-- ═══════════════════════════════════════════════════════
-- 3. SESSION_HISTORIES TABLE (Conflict detection logs)
-- ═══════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS session_histories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    
    -- Detection Info
    detection_type VARCHAR(50) NOT NULL,
    is_manual_operation BOOLEAN NOT NULL DEFAULT FALSE,
    conflict_detected BOOLEAN NOT NULL DEFAULT FALSE,
    action_taken VARCHAR(50),
    
    -- Session Info
    session_token TEXT,
    detection_data JSONB,
    
    -- Timestamp
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_session_histories_account_id ON session_histories(account_id);
CREATE INDEX IF NOT EXISTS idx_session_histories_created_at ON session_histories(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_session_histories_conflict ON session_histories(conflict_detected, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_session_histories_detection_type ON session_histories(detection_type);

-- ═══════════════════════════════════════════════════════
-- 4. SYSTEM_CONFIGS TABLE (System settings)
-- ═══════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS system_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key VARCHAR(100) UNIQUE NOT NULL,
    value JSONB NOT NULL,
    description TEXT,
    is_system BOOLEAN NOT NULL DEFAULT FALSE,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create index
CREATE INDEX IF NOT EXISTS idx_system_configs_key ON system_configs(key);

-- ═══════════════════════════════════════════════════════
-- 5. UPDATE TRIGGER FUNCTION
-- ═══════════════════════════════════════════════════════
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for updated_at
DROP TRIGGER IF EXISTS update_accounts_updated_at ON accounts;
CREATE TRIGGER update_accounts_updated_at 
    BEFORE UPDATE ON accounts
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_system_configs_updated_at ON system_configs;
CREATE TRIGGER update_system_configs_updated_at 
    BEFORE UPDATE ON system_configs
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- ═══════════════════════════════════════════════════════
-- 6. INSERT DEFAULT SYSTEM CONFIGS
-- ═══════════════════════════════════════════════════════
INSERT INTO system_configs (key, value, description, is_system) VALUES
    ('schedule_update_enabled', 'true', 'スケジュール自動更新の有効/無効', true),
    ('wait_reception_enabled', 'true', '待機接客自動設定の有効/無効', true),
    ('max_concurrent_accounts', '10', '最大並列処理数', true),
    ('session_check_interval', '5', 'セッション監視間隔（秒）', true),
    ('manual_operation_window', '30', '手動操作検知ウィンドウ（秒）', true),
    ('max_retry_count', '3', '最大リトライ回数', true)
ON CONFLICT (key) DO NOTHING;

-- ═══════════════════════════════════════════════════════
-- 7. CREATE VIEWS FOR EASY QUERYING
-- ═══════════════════════════════════════════════════════

-- Active accounts view
CREATE OR REPLACE VIEW active_accounts AS
SELECT * FROM accounts
WHERE is_active = TRUE
ORDER BY username;

-- Recent logs view (last 1000)
CREATE OR REPLACE VIEW recent_logs AS
SELECT 
    al.*,
    a.username,
    a.store_name
FROM account_logs al
JOIN accounts a ON al.account_id = a.id
ORDER BY al.created_at DESC
LIMIT 1000;

-- Account statistics view
CREATE OR REPLACE VIEW account_statistics AS
SELECT 
    a.id,
    a.username,
    a.store_name,
    a.status,
    a.error_count,
    a.last_login_at,
    COUNT(DISTINCT al.id) as total_operations,
    COUNT(DISTINCT CASE WHEN al.status = 'SUCCESS' THEN al.id END) as successful_operations,
    COUNT(DISTINCT CASE WHEN al.status = 'FAILURE' THEN al.id END) as failed_operations
FROM accounts a
LEFT JOIN account_logs al ON a.id = al.account_id
GROUP BY a.id, a.username, a.store_name, a.status, a.error_count, a.last_login_at;

-- ═══════════════════════════════════════════════════════
-- 8. ROW LEVEL SECURITY (Optional - for production)
-- ═══════════════════════════════════════════════════════
-- Uncomment if you want to enable RLS
-- 
-- ALTER TABLE accounts ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE account_logs ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE session_histories ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE system_configs ENABLE ROW LEVEL SECURITY;
--
-- -- Allow service role full access (your backend)
-- CREATE POLICY "Allow service role full access" ON accounts
-- FOR ALL USING (true);
--
-- CREATE POLICY "Allow service role full access" ON account_logs
-- FOR ALL USING (true);
--
-- CREATE POLICY "Allow service role full access" ON session_histories
-- FOR ALL USING (true);
--
-- CREATE POLICY "Allow service role full access" ON system_configs
-- FOR ALL USING (true);

-- ═══════════════════════════════════════════════════════
-- SUCCESS MESSAGE
-- ═══════════════════════════════════════════════════════
-- If you see this message, the schema was created successfully!
-- 
-- Next steps:
-- 1. Verify tables in Supabase Table Editor
-- 2. Run: python test_supabase_connection.py
-- 3. Run: python src/database/migrations/init_db.py init
-- ═══════════════════════════════════════════════════════


"""
Database Initialization Script

MySQLデータベースの初期化とデフォルトデータ投入
"""
import sys
from pathlib import Path
from src.database.connection import db, init_database, check_database_health
from src.database.models import SystemConfig, Account
from src.database.repositories.account import AccountRepository
from src.database.repositories.base import BaseRepository
from src.core.logger import logger, setup_logger

# ロガー設定
logger = setup_logger("init_db")


def insert_default_configs():
    """デフォルトシステム設定を投入"""
    logger.info("Inserting default system configurations...")
    
    default_configs = [
        {
            'key': 'schedule_update_enabled',
            'value': True,
            'description': 'スケジュール自動更新の有効/無効',
            'is_system': True
        },
        {
            'key': 'wait_reception_enabled',
            'value': True,
            'description': '待機接客自動設定の有効/無効',
            'is_system': True
        },
        {
            'key': 'max_concurrent_accounts',
            'value': 10,
            'description': '最大並列処理数',
            'is_system': True
        },
        {
            'key': 'session_check_interval',
            'value': 5,
            'description': 'セッション監視間隔（秒）',
            'is_system': True
        },
        {
            'key': 'manual_operation_window',
            'value': 30,
            'description': '手動操作検知ウィンドウ（秒）',
            'is_system': True
        },
        {
            'key': 'max_retry_count',
            'value': 3,
            'description': '最大リトライ回数',
            'is_system': True
        },
    ]
    
    with db.get_session() as session:
        config_repo = BaseRepository(session, SystemConfig)
        
        inserted = 0
        skipped = 0
        
        for config_data in default_configs:
            # 既存チェック
            existing = session.query(SystemConfig).filter_by(
                key=config_data['key']
            ).first()
            
            if existing:
                logger.debug(f"Config '{config_data['key']}' already exists, skipping")
                skipped += 1
            else:
                config_repo.create(**config_data)
                logger.debug(f"Inserted config: {config_data['key']}")
                inserted += 1
        
        logger.info(f"✅ Configs inserted: {inserted}, skipped: {skipped}")


def create_test_account():
    """テストアカウントを作成（開発用）"""
    logger.info("Creating test account...")
    
    with db.get_session() as session:
        account_repo = AccountRepository(session)
        
        # 既存チェック
        existing = account_repo.get_by_username("test_account")
        
        if existing:
            logger.info("Test account already exists, skipping")
            return existing
        
        account = account_repo.create_account(
            username="test_account",
            password="test_password_123",
            store_name="テスト店舗",
            is_active=True
        )
        
        logger.info(f"✅ Test account created: {account.username} (ID: {account.id})")
        return account


def initialize_database():
    """
    データベースを初期化
    
    Process:
    1. 接続テスト
    2. テーブル存在確認
    3. デフォルトデータ投入
    """
    logger.info("=" * 60)
    logger.info("DATABASE INITIALIZATION")
    logger.info("=" * 60)
    
    try:
        # 1. 接続テスト
        logger.info("Step 1: Testing database connection...")
        if not db.test_connection():
            logger.error("❌ Database connection failed!")
            return False
        logger.info("✅ Connection successful")
        
        # 2. テーブル確認
        logger.info("\nStep 2: Checking database tables...")
        init_database()
        
        # 3. デフォルトデータ投入
        logger.info("\nStep 3: Inserting default data...")
        insert_default_configs()
        
        logger.info("\n" + "=" * 60)
        logger.info("✅ DATABASE INITIALIZATION COMPLETE")
        logger.info("=" * 60)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Initialization failed: {e}", exc_info=True)
        return False


def create_sample_accounts(count: int = 10):
    """
    サンプルアカウントを作成（開発用）
    
    Args:
        count: 作成するアカウント数
    """
    logger.info(f"Creating {count} sample accounts...")
    
    with db.get_session() as session:
        account_repo = AccountRepository(session)
        
        created = 0
        for i in range(1, count + 1):
            try:
                account = account_repo.create_account(
                    username=f"sample_user_{i:03d}",
                    password=f"password_{i:03d}",
                    store_name=f"サンプル店舗 {i}",
                    is_active=True
                )
                created += 1
                logger.debug(f"Created: {account.username}")
            except Exception as e:
                logger.warning(f"Failed to create account {i}: {e}")
        
        logger.info(f"✅ Created {created} sample accounts")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Database initialization script")
    parser.add_argument(
        'action',
        choices=['init', 'test', 'sample'],
        help='Action to perform'
    )
    parser.add_argument(
        '--count',
        type=int,
        default=10,
        help='Number of sample accounts to create (for sample action)'
    )
    
    args = parser.parse_args()
    
    if args.action == 'init':
        success = initialize_database()
        sys.exit(0 if success else 1)
    
    elif args.action == 'test':
        # 接続テストのみ
        logger.info("Testing database connection...")
        health = check_database_health()
        
        print("\n" + "=" * 60)
        print("DATABASE HEALTH CHECK")
        print("=" * 60)
        print(f"Connected:        {health.get('connected', False)}")
        print(f"Tables Exist:     {health.get('tables_exist', False)}")
        if 'connection_pool' in health:
            pool = health['connection_pool']
            print(f"Pool Size:        {pool.get('size', 0)}")
            print(f"Checked In:       {pool.get('checked_in', 0)}")
            print(f"Overflow:         {pool.get('overflow', 0)}")
        if 'error' in health:
            print(f"Error:            {health['error']}")
        print("=" * 60)
        
        sys.exit(0 if health.get('connected', False) else 1)
    
    elif args.action == 'sample':
        # サンプルアカウント作成
        if initialize_database():
            create_sample_accounts(args.count)
        else:
            logger.error("Initialization failed, cannot create sample accounts")
            sys.exit(1)


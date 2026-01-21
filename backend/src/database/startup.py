"""
Database Startup Module

プロジェクト起動時にデータベース接続を確立します。
"""
from src.database.connection import db, ensure_connection, init_database
from src.core.logger import logger, setup_logger

# ロガー設定
logger = setup_logger("database_startup")


def initialize_database_connection():
    """
    データベース接続を初期化（プロジェクト起動時に呼び出す）
    
    この関数をプロジェクトのエントリーポイントで呼び出すことで、
    常時接続が確立され、維持されます。
    
    Returns:
        bool: 初期化成功時True
    """
    logger.info("=" * 60)
    logger.info("DATABASE CONNECTION STARTUP")
    logger.info("=" * 60)
    
    try:
        # 1. 接続を確立
        logger.info("Step 1: Establishing persistent connection...")
        if not ensure_connection():
            logger.error("Failed to establish database connection")
            return False
        logger.info("Connection established successfully")
        
        # 2. テーブル確認
        logger.info("\nStep 2: Verifying database tables...")
        try:
            init_database()
        except Exception as e:
            logger.warning(f"Table verification warning: {e}")
            logger.warning("Please ensure SQL schema is run in MySQL (phpMyAdmin or MySQL command line)")
        
        logger.info("\n" + "=" * 60)
        logger.info("DATABASE CONNECTION READY")
        logger.info("=" * 60)
        logger.info("Persistent connection is active and will be maintained")
        logger.info("Keep-alive thread is running (30-second intervals)")
        logger.info("=" * 60)
        
        return True
        
    except Exception as e:
        logger.error(f"Database startup failed: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    # スタンドアロン実行時
    success = initialize_database_connection()
    if success:
        logger.info("\nDatabase connection is ready!")
        logger.info("Press Ctrl+C to stop...")
        try:
            import time
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("\nShutting down...")
            db.close()
    else:
        logger.error("Failed to initialize database connection")
        exit(1)


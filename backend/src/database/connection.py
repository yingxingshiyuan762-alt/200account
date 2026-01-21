"""
MySQL Database Connection Module

MySQL (XAMPP)への接続管理を行います。
常時接続を維持します。
"""
import os
import threading
import time
from contextlib import contextmanager
from typing import Generator, Optional
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool, NullPool
from config.config import settings
from src.core.logger import logger


class DatabaseConnection:
    """
    MySQLデータベース接続マネージャー（シングルトン）
    
    責務:
    - SQLAlchemy Engine の作成と管理
    - セッションファクトリの提供
    - 常時接続の維持
    - 接続の監視と自動再接続
    - トランザクション管理
    """
    
    _instance: Optional['DatabaseConnection'] = None
    _engine = None
    _session_factory = None
    _persistent_connection = None
    _keep_alive_thread = None
    _keep_alive_running = False
    _initialized = False
    _connection_lock = threading.Lock()
    
    def __new__(cls):
        """シングルトンパターン実装"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """初期化（1回のみ実行）"""
        if not self._initialized:
            self._initialize()
            DatabaseConnection._initialized = True
    
    def _initialize(self):
        """Engine とセッションファクトリを初期化、常時接続を確立"""
        database_url = settings.DATABASE_URL
        
        logger.info("Connecting to MySQL database...")
        logger.debug(f"Database URL: {database_url.split('@')[0]}@***")  # Hide password
        
        engine_kwargs = {
            'echo': settings.DEBUG,
            'future': True,
            'poolclass': QueuePool,
            'pool_size': settings.DB_POOL_SIZE,
            'max_overflow': settings.DB_MAX_OVERFLOW,
            'pool_timeout': settings.DB_POOL_TIMEOUT,
            'pool_pre_ping': True,  # 接続チェック
            'pool_recycle': 3600,  # 1時間ごとに接続をリサイクル
            'connect_args': {
                'connect_timeout': 10,
                'charset': 'utf8mb4',
                'autocommit': False,
            }
        }
        
        try:
            self._engine = create_engine(database_url, **engine_kwargs)
            
            # セッションファクトリ作成
            self._session_factory = sessionmaker(
                bind=self._engine,
                autocommit=False,
                autoflush=False,
                expire_on_commit=False,
            )
            
            # 常時接続を確立
            self._establish_persistent_connection()
            
            # Keep-aliveスレッドを開始
            self._start_keep_alive()
            
            logger.info("Database connection initialized and persistent connection established")
            
        except Exception as e:
            logger.error(f"Failed to initialize database connection: {e}")
            raise
    
    def _establish_persistent_connection(self):
        """常時接続を確立"""
        try:
            with self._connection_lock:
                if self._persistent_connection is None:
                    logger.info("Establishing persistent database connection...")
                    self._persistent_connection = self._engine.connect()
                    
                    # 接続テスト
                    result = self._persistent_connection.execute(text("SELECT 1"))
                    if result.fetchone()[0] == 1:
                        logger.info("Persistent connection established successfully")
                    else:
                        raise Exception("Connection test failed")
        except Exception as e:
            logger.error(f"Failed to establish persistent connection: {e}")
            if self._persistent_connection:
                try:
                    self._persistent_connection.close()
                except:
                    pass
            self._persistent_connection = None
            raise
    
    def _start_keep_alive(self):
        """Keep-aliveスレッドを開始（接続を維持）"""
        if self._keep_alive_thread is None or not self._keep_alive_thread.is_alive():
            self._keep_alive_running = True
            self._keep_alive_thread = threading.Thread(
                target=self._keep_alive_loop,
                daemon=True,
                name="DatabaseKeepAlive"
            )
            self._keep_alive_thread.start()
            logger.info("Keep-alive thread started")
    
    def _keep_alive_loop(self):
        """Keep-aliveループ（30秒ごとに接続をチェック）"""
        while self._keep_alive_running:
            try:
                time.sleep(30)  # 30秒ごとにチェック
                
                if self._persistent_connection is None:
                    logger.warning("Persistent connection lost, attempting to reconnect...")
                    self._establish_persistent_connection()
                else:
                    # 接続が生きているか確認
                    try:
                        result = self._persistent_connection.execute(text("SELECT 1"))
                        result.fetchone()
                        logger.debug("Keep-alive ping successful")
                    except Exception as e:
                        logger.warning(f"Keep-alive ping failed: {e}, reconnecting...")
                        try:
                            self._persistent_connection.close()
                        except:
                            pass
                        self._persistent_connection = None
                        self._establish_persistent_connection()
                        
            except Exception as e:
                logger.error(f"Error in keep-alive loop: {e}")
                time.sleep(10)  # エラー時は10秒待機
    
    def ensure_connected(self) -> bool:
        """
        接続が確立されていることを確認（必要に応じて再接続）
        
        Returns:
            bool: 接続成功時True
        """
        try:
            if self._persistent_connection is None:
                logger.info("Connection not established, establishing now...")
                self._establish_persistent_connection()
            
            # 接続テスト
            result = self._persistent_connection.execute(text("SELECT 1"))
            return result.fetchone()[0] == 1
            
        except Exception as e:
            logger.warning(f"Connection check failed: {e}, attempting reconnect...")
            try:
                if self._persistent_connection:
                    self._persistent_connection.close()
            except:
                pass
            self._persistent_connection = None
            
            try:
                self._establish_persistent_connection()
                return True
            except Exception as reconnect_error:
                logger.error(f"Reconnection failed: {reconnect_error}")
                return False
    
    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """
        セッションを取得（コンテキストマネージャー）
        
        自動的に:
        - 成功時: commit()
        - エラー時: rollback()
        - 常に: close()
        
        使用例:
            with db.get_session() as session:
                account = session.query(Account).first()
                account.status = 'PROCESSING'
                # 自動コミット
        """
        session = self._session_factory()
        
        try:
            yield session
            session.commit()
            logger.debug("Database transaction committed")
            
        except Exception as e:
            session.rollback()
            logger.error(f"Database error, rolling back: {e}")
            raise
            
        finally:
            session.close()
            logger.debug("Database session closed")
    
    def test_connection(self) -> bool:
        """
        データベース接続をテスト（常時接続を使用）
        
        Returns:
            bool: 接続成功時True
        """
        return self.ensure_connected()
    
    def close(self):
        """全接続を閉じる"""
        # Keep-aliveスレッドを停止
        self._keep_alive_running = False
        if self._keep_alive_thread and self._keep_alive_thread.is_alive():
            self._keep_alive_thread.join(timeout=5)
            logger.info("Keep-alive thread stopped")
        
        # 常時接続を閉じる
        if self._persistent_connection:
            try:
                self._persistent_connection.close()
                logger.info("Persistent connection closed")
            except Exception as e:
                logger.error(f"Error closing persistent connection: {e}")
            finally:
                self._persistent_connection = None
        
        # Engineを閉じる
        if self._engine:
            self._engine.dispose()
            logger.info("Database connections closed")


# グローバルインスタンス
db = DatabaseConnection()


# ヘルパー関数
def get_session():
    """セッションを取得（ショートカット）"""
    return db.get_session()


def ensure_connection():
    """
    接続が確立されていることを確認（プロジェクト起動時に呼び出す）
    
    この関数をプロジェクト起動時に呼び出すことで、
    常時接続が確立され、維持されます。
    
    Returns:
        bool: 接続成功時True
    """
    logger.info("Ensuring database connection is established...")
    return db.ensure_connected()


def init_database():
    """
    データベースを初期化（テーブル作成）
    
    注意: MySQLではSQLファイルでスキーマを実行する必要があります。
    この関数は既存のテーブルに基づいてモデルを確認するだけです。
    """
    from src.database.models import Base
    
    try:
        # テーブルが存在するか確認
        with db._engine.connect() as conn:
            result = conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = DATABASE()
                AND table_name IN ('accounts', 'account_logs', 'session_histories', 'system_configs')
            """))
            
            existing_tables = [row[0] for row in result.fetchall()]
            
            if len(existing_tables) == 4:
                logger.info(f"All required tables exist: {existing_tables}")
            else:
                missing = set(['accounts', 'account_logs', 'session_histories', 'system_configs']) - set(existing_tables)
                logger.warning(f"Missing tables: {missing}")
                logger.warning("Please run the SQL schema in MySQL (phpMyAdmin or MySQL command line)!")
                
    except Exception as e:
        logger.error(f"Database initialization check failed: {e}")
        raise


def test_connection() -> bool:
    """
    データベース接続をテスト（ショートカット）
    
    Returns:
        bool: 接続成功時True
    """
    return db.test_connection()


def check_database_health() -> dict:
    """
    データベースの健全性をチェック
    
    Returns:
        dict: ヘルスチェック結果
    """
    health = {
        'connected': False,
        'tables_exist': False,
        'connection_pool': {
            'size': 0,
            'checked_in': 0,
            'overflow': 0
        }
    }
    
    try:
        # 接続テスト
        health['connected'] = db.test_connection()
        
        if health['connected']:
            # テーブル存在確認
            with db._engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT COUNT(*) 
                    FROM information_schema.tables 
                    WHERE table_schema = DATABASE()
                    AND table_name IN ('accounts', 'account_logs', 'session_histories', 'system_configs')
                """))
                
                table_count = result.fetchone()[0]
                health['tables_exist'] = (table_count == 4)
            
            # コネクションプール情報
            pool = db._engine.pool
            health['connection_pool'] = {
                'size': pool.size(),
                'checked_in': pool.checkedin(),
                'overflow': pool.overflow(),
            }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        health['error'] = str(e)
    
    return health


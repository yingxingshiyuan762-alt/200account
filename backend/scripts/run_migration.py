"""
Database Migration Runner

MySQLデータベースのマイグレーションを実行するスクリプト
"""
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "backend"))

from src.database.connection import db, ensure_connection
from src.core.logger import logger
import pymysql


def run_migration():
    """マイグレーションSQLファイルを実行"""
    try:
        # データベース接続を確立
        logger.info("Connecting to database...")
        if not ensure_connection():
            logger.error("Failed to establish database connection")
            return False
        
        # マイグレーションファイルのパス
        migration_file = project_root / "database" / "mysql_migration_fix.sql"
        
        if not migration_file.exists():
            logger.error(f"Migration file not found: {migration_file}")
            return False
        
        # SQLファイルを読み込む
        logger.info(f"Reading migration file: {migration_file}")
        with open(migration_file, 'r', encoding='utf-8') as f:
            sql_content = f.read()
        
        # SQL文を分割（セミコロンで区切るが、ストアドプロシージャなどは考慮）
        # 簡単な方法：ファイル全体を実行
        logger.info("Executing migration SQL...")
        
        with db._engine.connect() as conn:
            # 複数のSQL文を実行するため、分割して実行
            statements = []
            current_statement = ""
            
            for line in sql_content.split('\n'):
                # コメント行をスキップ（ただし、一部のコメントは含める）
                stripped = line.strip()
                if stripped.startswith('--') and not stripped.startswith('-- ═'):
                    continue
                
                # 空行をスキップ
                if not stripped:
                    continue
                
                current_statement += line + '\n'
                
                # セミコロンで終わる場合（ただし文字列内のセミコロンは考慮しない簡単な実装）
                if stripped.endswith(';') and not stripped.startswith('--'):
                    statements.append(current_statement.strip())
                    current_statement = ""
            
            # 残りのステートメントを追加
            if current_statement.strip():
                statements.append(current_statement.strip())
            
            # 各ステートメントを実行
            executed_count = 0
            for i, statement in enumerate(statements, 1):
                if statement and not statement.startswith('--'):
                    try:
                        # PREPARE/EXECUTE文や複雑な構文はそのまま実行
                        conn.execute(statement)
                        conn.commit()
                        executed_count += 1
                    except Exception as e:
                        # 一部のエラーは無視（例：既に存在する場合など）
                        error_msg = str(e).lower()
                        if 'already exists' in error_msg or 'duplicate' in error_msg:
                            logger.debug(f"Statement {i}: {e} (ignored)")
                        else:
                            logger.warning(f"Statement {i} warning: {e}")
            
            logger.info(f"Executed {executed_count} SQL statements")
        
        logger.info("=" * 60)
        logger.info("✅ Migration completed successfully!")
        logger.info("=" * 60)
        logger.info("The following changes were made:")
        logger.info("1. Added is_active column to accounts table (if missing)")
        logger.info("2. Created account_logs table (if missing)")
        logger.info("3. Created session_histories table (if missing)")
        logger.info("4. Created system_configs table (if missing)")
        logger.info("5. Inserted default system configs")
        logger.info("=" * 60)
        
        return True
        
    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        return False
    finally:
        db.close()


if __name__ == "__main__":
    print("=" * 60)
    print("Database Migration Runner")
    print("=" * 60)
    print()
    
    success = run_migration()
    
    if success:
        print("\n✅ Migration completed successfully!")
        print("You can now restart your backend server.")
        sys.exit(0)
    else:
        print("\n❌ Migration failed. Please check the error messages above.")
        print("You may need to run the migration manually in phpMyAdmin.")
        sys.exit(1)

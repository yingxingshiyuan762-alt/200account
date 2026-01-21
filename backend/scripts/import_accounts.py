"""
Account Import Script

CSVファイルまたはテキストファイルからアカウントをインポートします。
"""
import sys
import csv
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.database.connection import get_session, ensure_connection
from src.database.repositories.account import AccountRepository
from src.core.logger import logger, setup_logger

# ロガー設定
logger = setup_logger("import_accounts")


def import_from_csv(csv_file: Path):
    """
    CSVファイルからアカウントをインポート
    
    CSV形式:
    username,password,store_name,login_url
    szo22_25794,s89ynkXR52,店舗名,https://doors1.shinchakun.info/dokodemo/#/
    """
    logger.info("=" * 60)
    logger.info("ACCOUNT IMPORT FROM CSV")
    logger.info("=" * 60)
    
    if not csv_file.exists():
        logger.error(f"CSV file not found: {csv_file}")
        return False
    
    try:
        # データベース接続確認
        logger.info("\nStep 1: Checking database connection...")
        if not ensure_connection():
            logger.error("Failed to establish database connection")
            return False
        logger.info("Database connection established")
        
        # CSVファイルを読み込み
        logger.info(f"\nStep 2: Reading CSV file: {csv_file}")
        accounts_data = []
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('username') and row.get('password'):
                    accounts_data.append({
                        'username': row['username'].strip(),
                        'password': row['password'].strip(),
                        'store_name': row.get('store_name', '').strip() or f"店舗 {row['username']}",
                        'login_url': row.get('login_url', '').strip() or 'https://doors1.shinchakun.info/dokodemo/#/'
                    })
        
        logger.info(f"Found {len(accounts_data)} accounts in CSV file")
        
        # アカウントをインポート
        logger.info("\nStep 3: Importing accounts...")
        with get_session() as session:
            account_repo = AccountRepository(session)
            
            existing_count = account_repo.count()
            logger.info(f"Existing accounts: {existing_count}")
            
            created_count = 0
            skipped_count = 0
            error_count = 0
            
            for account_data in accounts_data:
                username = account_data['username']
                
                # 既存のアカウントをチェック
                existing_account = account_repo.get_by_username(username)
                if existing_account:
                    logger.warning(f"Account {username} already exists, skipping...")
                    skipped_count += 1
                    continue
                
                # アカウント作成
                try:
                    account = account_repo.create_account(
                        username=username,
                        password=account_data['password'],
                        store_name=account_data['store_name'],
                        login_url=account_data['login_url'] if account_data['login_url'] else None,
                        is_active=True
                    )
                    created_count += 1
                    if created_count % 20 == 0:
                        logger.info(f"Imported {created_count}/{len(accounts_data)} accounts...")
                except Exception as e:
                    logger.error(f"Failed to create account {username}: {e}")
                    error_count += 1
                    continue
            
            # コミット
            session.commit()
            
            logger.info("\n" + "=" * 60)
            logger.info("IMPORT COMPLETE")
            logger.info("=" * 60)
            logger.info(f"Created: {created_count} accounts")
            logger.info(f"Skipped: {skipped_count} accounts (already exist)")
            logger.info(f"Errors: {error_count} accounts")
            logger.info(f"Total in database: {account_repo.count()} accounts")
            logger.info("=" * 60)
            
            return True
            
    except Exception as e:
        logger.error(f"Failed to import accounts: {e}", exc_info=True)
        return False


def import_from_text(text_file: Path):
    """
    テキストファイルからアカウントをインポート
    
    テキスト形式 (各行):
    username,password,store_name,login_url
    または
    username:password:store_name:login_url
    """
    logger.info("=" * 60)
    logger.info("ACCOUNT IMPORT FROM TEXT")
    logger.info("=" * 60)
    
    if not text_file.exists():
        logger.error(f"Text file not found: {text_file}")
        return False
    
    try:
        # データベース接続確認
        logger.info("\nStep 1: Checking database connection...")
        if not ensure_connection():
            logger.error("Failed to establish database connection")
            return False
        logger.info("Database connection established")
        
        # テキストファイルを読み込み
        logger.info(f"\nStep 2: Reading text file: {text_file}")
        accounts_data = []
        with open(text_file, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                # カンマまたはコロンで分割
                if ',' in line:
                    parts = [p.strip() for p in line.split(',')]
                elif ':' in line:
                    parts = [p.strip() for p in line.split(':')]
                else:
                    logger.warning(f"Line {line_num}: Invalid format, skipping")
                    continue
                
                if len(parts) >= 2:
                    accounts_data.append({
                        'username': parts[0],
                        'password': parts[1],
                        'store_name': parts[2] if len(parts) > 2 and parts[2] else f"店舗 {parts[0]}",
                        'login_url': parts[3] if len(parts) > 3 and parts[3] else 'https://doors1.shinchakun.info/dokodemo/#/'
                    })
        
        logger.info(f"Found {len(accounts_data)} accounts in text file")
        
        # アカウントをインポート（CSVと同じロジック）
        logger.info("\nStep 3: Importing accounts...")
        with get_session() as session:
            account_repo = AccountRepository(session)
            
            existing_count = account_repo.count()
            logger.info(f"Existing accounts: {existing_count}")
            
            created_count = 0
            skipped_count = 0
            error_count = 0
            
            for account_data in accounts_data:
                username = account_data['username']
                
                existing_account = account_repo.get_by_username(username)
                if existing_account:
                    logger.warning(f"Account {username} already exists, skipping...")
                    skipped_count += 1
                    continue
                
                try:
                    account = account_repo.create_account(
                        username=username,
                        password=account_data['password'],
                        store_name=account_data['store_name'],
                        login_url=account_data['login_url'] if account_data['login_url'] else None,
                        is_active=True
                    )
                    created_count += 1
                    if created_count % 20 == 0:
                        logger.info(f"Imported {created_count}/{len(accounts_data)} accounts...")
                except Exception as e:
                    logger.error(f"Failed to create account {username}: {e}")
                    error_count += 1
                    continue
            
            session.commit()
            
            logger.info("\n" + "=" * 60)
            logger.info("IMPORT COMPLETE")
            logger.info("=" * 60)
            logger.info(f"Created: {created_count} accounts")
            logger.info(f"Skipped: {skipped_count} accounts (already exist)")
            logger.info(f"Errors: {error_count} accounts")
            logger.info(f"Total in database: {account_repo.count()} accounts")
            logger.info("=" * 60)
            
            return True
            
    except Exception as e:
        logger.error(f"Failed to import accounts: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Import accounts from CSV or text file")
    parser.add_argument(
        "file",
        type=Path,
        help="Path to CSV or text file containing accounts"
    )
    parser.add_argument(
        "--format",
        choices=['csv', 'text', 'auto'],
        default='auto',
        help="File format (auto-detect if not specified)"
    )
    
    args = parser.parse_args()
    
    # ファイル形式を自動判定
    if args.format == 'auto':
        if args.file.suffix.lower() == '.csv':
            file_format = 'csv'
        else:
            file_format = 'text'
    else:
        file_format = args.format
    
    # インポート実行
    if file_format == 'csv':
        success = import_from_csv(args.file)
    else:
        success = import_from_text(args.file)
    
    if success:
        logger.info("\nAccount import completed successfully!")
        sys.exit(0)
    else:
        logger.error("\nAccount import failed!")
        sys.exit(1)

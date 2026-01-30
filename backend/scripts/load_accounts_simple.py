"""
Simple Account Loader from Google Sheets

Google Sheetsから126アカウントを読み込み（店舗名検証なし）
- 店舗名はユーザー名をデフォルト使用
- 後でシステムが自動的に取得・更新
"""
import sys
import os
import requests
from typing import List, Dict, Any
from pathlib import Path

# プロジェクトルートをPythonパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.config import settings
from src.database.connection import get_session, db
from src.database.models import Account, AccountStatus
from src.core.logger import logger
from cryptography.fernet import Fernet


# Google Sheets の公開CSV URL
GOOGLE_SHEET_ID = "1-2ydkZ1K08HxB73EkJ5kZ3a3_Gp_Av54X4j5RcGOCso"
GID = "556373435"
SHEET_CSV_URL = f"https://docs.google.com/spreadsheets/d/{GOOGLE_SHEET_ID}/export?format=csv&gid={GID}"

# 除外する行番号（1-indexed）
EXCLUDED_ROWS = [1, 11, 101, 105]

# デフォルトログインURL
DEFAULT_LOGIN_URL = "https://doors1.shinchakun.info/dokodemo/#/"


def fetch_accounts_from_google_sheets() -> List[Dict[str, str]]:
    """Google Sheetsからアカウント情報を取得"""
    logger.info("Fetching accounts from Google Sheets...")
    logger.info(f"Sheet URL: {SHEET_CSV_URL}")
    
    try:
        response = requests.get(SHEET_CSV_URL, timeout=30)
        response.raise_for_status()
        
        import csv
        from io import StringIO
        
        csv_data = StringIO(response.text)
        reader = csv.reader(csv_data)
        
        accounts = []
        row_num = 0
        
        for row in reader:
            row_num += 1
            
            # 除外行をスキップ
            if row_num in EXCLUDED_ROWS:
                logger.info(f"Skipping row {row_num} (excluded)")
                continue
            
            # ヘッダー行をスキップ
            if row_num == 1:
                continue
            
            # データがない行をスキップ
            if len(row) < 3 or not row[1] or not row[2]:
                continue
            
            account_data = {
                'no': row[0].strip() if row[0] else '',
                'username': row[1].strip(),
                'password': row[2].strip(),
                'note': row[3].strip() if len(row) > 3 else ''
            }
            
            accounts.append(account_data)
        
        logger.info(f"Fetched {len(accounts)} accounts from Google Sheets")
        return accounts
    
    except Exception as e:
        logger.error(f"Failed to fetch from Google Sheets: {e}", exc_info=True)
        raise


def encrypt_password(password: str) -> str:
    """パスワードを暗号化"""
    cipher = Fernet(settings.ENCRYPTION_KEY.encode())
    encrypted = cipher.encrypt(password.encode())
    return encrypted.decode()


def delete_all_accounts():
    """既存のすべてのアカウントを削除"""
    logger.info("Deleting all existing accounts...")
    
    try:
        with get_session() as session:
            deleted_count = session.query(Account).delete()
            session.commit()
            logger.info(f"Deleted {deleted_count} existing accounts")
            return deleted_count
    
    except Exception as e:
        logger.error(f"Failed to delete accounts: {e}", exc_info=True)
        raise


def load_accounts_to_database(accounts_data: List[Dict[str, str]]):
    """データベースに登録"""
    logger.info(f"Loading {len(accounts_data)} accounts to database...")
    
    success_count = 0
    failed_count = 0
    
    try:
        with get_session() as session:
            for account_data in accounts_data:
                username = account_data['username']
                password = account_data['password']
                
                try:
                    # パスワードを暗号化
                    encrypted_password = encrypt_password(password)
                    
                    # アカウントを作成（店舗名は後でシステムが自動取得）
                    account = Account(
                        username=username,
                        password_encrypted=encrypted_password,
                        store_name=username,  # デフォルトとしてユーザー名を使用
                        login_url=DEFAULT_LOGIN_URL,  # デフォルトURL
                        is_active=True,
                        status=AccountStatus.IDLE.value,
                        error_count=0
                    )
                    
                    session.add(account)
                    success_count += 1
                
                except Exception as e:
                    failed_count += 1
                    logger.error(f"Failed to add account {username}: {e}")
            
            # コミット
            session.commit()
            logger.info(f"Database load completed: {success_count} success, {failed_count} failed")
    
    except Exception as e:
        logger.error(f"Failed to load accounts to database: {e}", exc_info=True)
        raise


def main():
    """メイン処理"""
    logger.info("=" * 60)
    logger.info("SIMPLE ACCOUNT LOADING SCRIPT")
    logger.info("=" * 60)
    logger.info(f"Source: Google Sheets")
    logger.info(f"Excluded rows: {EXCLUDED_ROWS}")
    logger.info(f"Expected total: 126 accounts")
    logger.info("=" * 60)
    
    try:
        # Step 1: Google Sheetsから取得
        logger.info("\nStep 1: Fetching accounts from Google Sheets...")
        accounts_data = fetch_accounts_from_google_sheets()
        
        if not accounts_data:
            logger.error("No accounts fetched")
            return
        
        logger.info(f"✓ Fetched {len(accounts_data)} accounts")
        
        # Step 2: 確認
        print(f"\n📊 Found {len(accounts_data)} accounts")
        print(f"📋 First 5 accounts:")
        for i, acc in enumerate(accounts_data[:5], 1):
            print(f"  {i}. {acc['username']} (password: {acc['password'][:3]}***)")
        
        confirm = input("\n⚠️  Delete all existing accounts and load these? (yes/no): ").strip().lower()
        
        if confirm != 'yes':
            logger.info("Operation cancelled by user")
            return
        
        # Step 3: 既存削除
        logger.info("\nStep 2: Deleting existing accounts...")
        deleted_count = delete_all_accounts()
        logger.info(f"✓ Deleted {deleted_count} existing accounts")
        
        # Step 4: データベースに登録
        logger.info("\nStep 3: Loading accounts to database...")
        load_accounts_to_database(accounts_data)
        
        # Step 5: 確認
        logger.info("\nStep 4: Verification...")
        with get_session() as session:
            total = session.query(Account).count()
            active = session.query(Account).filter_by(is_active=True).count()
            
            logger.info(f"✓ Total accounts in database: {total}")
            logger.info(f"✓ Active accounts: {active}")
        
        logger.info("=" * 60)
        logger.info("✅ ACCOUNT LOADING COMPLETED")
        logger.info("=" * 60)
        logger.info(f"✓ Loaded: {total} accounts")
        logger.info(f"✓ Store names will be auto-updated on first login")
        logger.info(f"✓ Login URLs will be auto-resolved on first run")
        logger.info("=" * 60)
    
    except Exception as e:
        logger.error(f"❌ Account loading failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()

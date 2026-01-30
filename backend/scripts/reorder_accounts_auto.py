"""
Auto-confirm version of reorder_accounts.py
No user prompts - automatically proceeds with reordering
"""
import sys
import os
import requests
from typing import List, Dict, Any, Optional
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

# 除外する行番号（1-indexed, sheet rows = data rows + 1）
# Data rows 1, 11, 101, 105 = Sheet rows 2, 12, 102, 106
EXCLUDED_ROWS = [2, 12, 102, 106]


def fetch_accounts_from_google_sheets() -> List[Dict[str, Any]]:
    """Google Sheetsからアカウント情報を順序付きで取得"""
    logger.info("Fetching accounts from Google Sheets...")
    
    try:
        response = requests.get(SHEET_CSV_URL, timeout=30)
        response.raise_for_status()
        
        import csv
        from io import StringIO
        
        csv_data = StringIO(response.text)
        reader = csv.reader(csv_data)
        
        accounts = []
        row_num = 0
        display_order = 1
        
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
                'sheet_row': row_num,
                'display_order': display_order,
                'no': row[0].strip() if row[0] else '',
                'username': row[1].strip(),
                'password': row[2].strip(),
                'note': row[3].strip() if len(row) > 3 else ''
            }
            
            accounts.append(account_data)
            display_order += 1
        
        logger.info(f"Fetched {len(accounts)} accounts from Google Sheets")
        return accounts
    
    except Exception as e:
        logger.error(f"Failed to fetch from Google Sheets: {e}", exc_info=True)
        raise


def get_current_database_accounts() -> List[Account]:
    """データベースから現在のアカウントを取得"""
    logger.info("Fetching current accounts from database...")
    
    try:
        with get_session() as session:
            accounts = session.query(Account).all()
            logger.info(f"Found {len(accounts)} accounts in database")
            return accounts
    
    except Exception as e:
        logger.error(f"Failed to fetch accounts from database: {e}", exc_info=True)
        raise


def encrypt_password(password: str) -> str:
    """パスワードを暗号化"""
    cipher = Fernet(settings.ENCRYPTION_KEY.encode())
    encrypted = cipher.encrypt(password.encode())
    return encrypted.decode()


def reorder_accounts(sheet_accounts: List[Dict[str, Any]], db_accounts: List[Account]):
    """データベースのアカウントをGoogle Sheetsの順序に合わせて整理"""
    logger.info("Reordering accounts...")
    
    sheet_usernames_ordered = [acc['username'] for acc in sheet_accounts]
    db_accounts_dict = {acc.username: acc for acc in db_accounts}
    
    sheet_usernames_set = set(sheet_usernames_ordered)
    db_usernames_set = set(db_accounts_dict.keys())
    
    missing_in_db = sheet_usernames_set - db_usernames_set
    extra_in_db = db_usernames_set - sheet_usernames_set
    
    if missing_in_db:
        logger.info(f"Accounts in Sheets but not in DB: {missing_in_db}")
    if extra_in_db:
        logger.warning(f"Accounts in DB but not in Sheets (will be deleted): {extra_in_db}")
    
    try:
        with get_session() as session:
            # Delete extra accounts
            deleted_count = 0
            for username in extra_in_db:
                account = db_accounts_dict[username]
                session.delete(account)
                deleted_count += 1
                logger.info(f"Deleted account: {username}")
            
            if deleted_count > 0:
                session.commit()
                logger.info(f"Deleted {deleted_count} extra accounts")
            
            # Update or create accounts
            for sheet_account in sheet_accounts:
                username = sheet_account['username']
                display_order = sheet_account['display_order']
                
                if username in db_accounts_dict:
                    # Update existing account
                    account = session.query(Account).filter_by(username=username).first()
                    
                    import json
                    metadata = {}
                    if account.metadata_json:
                        try:
                            metadata = json.loads(account.metadata_json)
                        except:
                            metadata = {}
                    
                    metadata['sheet_row'] = sheet_account['sheet_row']
                    metadata['display_order'] = display_order
                    metadata['note'] = sheet_account['note']
                    
                    account.metadata_json = json.dumps(metadata, ensure_ascii=False)
                    
                    logger.info(f"Updated order for: {username} (order: {display_order})")
                
                else:
                    # Create new account
                    encrypted_password = encrypt_password(sheet_account['password'])
                    
                    metadata = {
                        'sheet_row': sheet_account['sheet_row'],
                        'display_order': display_order,
                        'note': sheet_account['note']
                    }
                    
                    new_account = Account(
                        username=username,
                        password_encrypted=encrypted_password,
                        store_name=username,
                        login_url="https://doors1.shinchakun.info/dokodemo/#/",
                        is_active=True,
                        status=AccountStatus.IDLE.value,
                        error_count=0,
                        metadata_json=json.dumps(metadata, ensure_ascii=False)
                    )
                    
                    session.add(new_account)
                    logger.info(f"Created new account: {username} (order: {display_order})")
            
            session.commit()
            logger.info("Account reordering completed")
            
            final_count = session.query(Account).count()
            logger.info(f"Final account count: {final_count}")
            
            return {
                'deleted': deleted_count,
                'updated': len(sheet_usernames_set & db_usernames_set),
                'created': len(missing_in_db),
                'final_count': final_count
            }
    
    except Exception as e:
        logger.error(f"Failed to reorder accounts: {e}", exc_info=True)
        raise


def main():
    """メイン処理"""
    logger.info("=" * 60)
    logger.info("AUTOMATIC ACCOUNT REORDERING")
    logger.info("=" * 60)
    
    try:
        # Fetch from Google Sheets
        sheet_accounts = fetch_accounts_from_google_sheets()
        logger.info(f"Sheets: {len(sheet_accounts)} accounts")
        
        # Fetch from database
        db_accounts = get_current_database_accounts()
        logger.info(f"Database: {len(db_accounts)} accounts")
        
        # Calculate differences
        sheet_usernames = set(acc['username'] for acc in sheet_accounts)
        db_usernames = set(acc.username for acc in db_accounts)
        
        missing = sheet_usernames - db_usernames
        extra = db_usernames - sheet_usernames
        
        logger.info(f"To delete: {len(extra)} accounts")
        logger.info(f"To create: {len(missing)} accounts")
        
        # Reorder
        result = reorder_accounts(sheet_accounts, db_accounts)
        
        # Results
        print("\n" + "=" * 80)
        print("REORDERING COMPLETED")
        print("=" * 80)
        print(f"  Deleted:  {result['deleted']} accounts")
        print(f"  Updated:  {result['updated']} accounts")
        print(f"  Created:  {result['created']} accounts")
        print(f"  Final:    {result['final_count']} accounts")
        print("=" * 80)
        
        logger.info("Account reordering completed successfully")
    
    except Exception as e:
        logger.error(f"Reordering failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()

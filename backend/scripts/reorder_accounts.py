"""
Reorder Database Accounts to Match Google Sheets Order

現在のデータベース（127アカウント）を整理し、
Google Sheetsの順序（126アカウント）に合わせて並び替え
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
        display_order = 1  # 表示順序用のカウンター
        
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


def decrypt_password(encrypted_password: str) -> str:
    """パスワードを復号化"""
    try:
        cipher = Fernet(settings.ENCRYPTION_KEY.encode())
        decrypted = cipher.decrypt(encrypted_password.encode())
        return decrypted.decode()
    except Exception as e:
        logger.error(f"Failed to decrypt password: {e}")
        return ""


def reorder_accounts(sheet_accounts: List[Dict[str, Any]], db_accounts: List[Account]):
    """
    データベースのアカウントをGoogle Sheetsの順序に合わせて整理
    
    処理内容:
    1. Sheetsに存在するアカウントは保持して順序を更新
    2. Sheetsに存在しないアカウントは削除（127→126）
    3. Sheetsに存在するがDBにないアカウントは新規作成
    """
    logger.info("Reordering accounts...")
    
    # Google Sheetsのユーザー名リスト（順序付き）
    sheet_usernames_ordered = [acc['username'] for acc in sheet_accounts]
    
    # データベースのアカウントを辞書化（username → Account）
    db_accounts_dict = {acc.username: acc for acc in db_accounts}
    
    logger.info(f"Sheets accounts: {len(sheet_usernames_ordered)}")
    logger.info(f"Database accounts: {len(db_accounts_dict)}")
    
    # アカウントの差分を確認
    sheet_usernames_set = set(sheet_usernames_ordered)
    db_usernames_set = set(db_accounts_dict.keys())
    
    # Sheetsにはあるが、DBにないアカウント
    missing_in_db = sheet_usernames_set - db_usernames_set
    if missing_in_db:
        logger.info(f"Accounts in Sheets but not in DB: {missing_in_db}")
    
    # DBにはあるが、Sheetsにないアカウント（削除対象）
    extra_in_db = db_usernames_set - sheet_usernames_set
    if extra_in_db:
        logger.warning(f"Accounts in DB but not in Sheets (will be deleted): {extra_in_db}")
    
    try:
        with get_session() as session:
            # Step 1: DBにあるがSheetsにないアカウントを削除
            deleted_count = 0
            for username in extra_in_db:
                account = db_accounts_dict[username]
                session.delete(account)
                deleted_count += 1
                logger.info(f"Deleted account: {username}")
            
            if deleted_count > 0:
                session.commit()
                logger.info(f"Deleted {deleted_count} extra accounts")
            
            # Step 2: アカウントを順序に従って更新または作成
            for sheet_account in sheet_accounts:
                username = sheet_account['username']
                display_order = sheet_account['display_order']
                
                if username in db_accounts_dict:
                    # 既存アカウントの更新（順序情報などを追加）
                    account = session.query(Account).filter_by(username=username).first()
                    
                    # メタデータに順序情報を追加
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
                    # 新規アカウントの作成
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
            
            # コミット
            session.commit()
            logger.info("Account reordering completed")
            
            # 確認
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


def print_comparison(sheet_accounts: List[Dict[str, Any]], db_accounts: List[Account]):
    """比較結果を表示"""
    print("\n" + "=" * 80)
    print("ACCOUNT COMPARISON")
    print("=" * 80)
    
    sheet_usernames = set(acc['username'] for acc in sheet_accounts)
    db_usernames = set(acc.username for acc in db_accounts)
    
    print(f"\nCounts:")
    print(f"  Google Sheets: {len(sheet_usernames)} accounts")
    print(f"  Database:      {len(db_usernames)} accounts")
    
    # 差分
    missing_in_db = sheet_usernames - db_usernames
    extra_in_db = db_usernames - sheet_usernames
    common = sheet_usernames & db_usernames
    
    print(f"\nDifferences:")
    print(f"  In both:       {len(common)} accounts")
    print(f"  Only in Sheets: {len(missing_in_db)} accounts")
    print(f"  Only in DB:     {len(extra_in_db)} accounts")
    
    if missing_in_db:
        print(f"\nMissing in DB (will be created):")
        for username in sorted(missing_in_db)[:10]:
            print(f"    - {username}")
        if len(missing_in_db) > 10:
            print(f"    ... and {len(missing_in_db) - 10} more")
    
    if extra_in_db:
        print(f"\nExtra in DB (will be deleted):")
        for username in sorted(extra_in_db):
            print(f"    - {username}")
    
    print("\n" + "=" * 80)


def verify_order(sheet_accounts: List[Dict[str, Any]]):
    """順序が正しく設定されたか確認"""
    logger.info("\nVerifying account order...")
    
    try:
        with get_session() as session:
            import json
            
            # メタデータに順序情報があるアカウントを取得
            accounts = session.query(Account).all()
            
            ordered_accounts = []
            for account in accounts:
                if account.metadata_json:
                    try:
                        metadata = json.loads(account.metadata_json)
                        if 'display_order' in metadata:
                            ordered_accounts.append({
                                'username': account.username,
                                'display_order': metadata['display_order'],
                                'sheet_row': metadata.get('sheet_row', 'N/A')
                            })
                    except:
                        pass
            
            # 順序でソート
            ordered_accounts.sort(key=lambda x: x['display_order'])
            
            print("\n" + "=" * 80)
            print("ACCOUNT ORDER VERIFICATION")
            print("=" * 80)
            print(f"\nFirst 10 accounts (in order):")
            for i, acc in enumerate(ordered_accounts[:10], 1):
                print(f"  {i}. {acc['username']} (order: {acc['display_order']}, row: {acc['sheet_row']})")
            
            print(f"\nLast 10 accounts (in order):")
            for i, acc in enumerate(ordered_accounts[-10:], len(ordered_accounts) - 9):
                print(f"  {i}. {acc['username']} (order: {acc['display_order']}, row: {acc['sheet_row']})")
            
            print("\n" + "=" * 80)
            
    except Exception as e:
        logger.error(f"Verification failed: {e}", exc_info=True)


def main():
    """メイン処理"""
    logger.info("=" * 60)
    logger.info("ACCOUNT REORDERING SCRIPT")
    logger.info("=" * 60)
    logger.info("This script will:")
    logger.info("1. Fetch 126 accounts from Google Sheets (in order)")
    logger.info("2. Compare with current database (127 accounts)")
    logger.info("3. Delete extra accounts not in Sheets")
    logger.info("4. Reorder remaining accounts to match Sheets")
    logger.info("=" * 60)
    
    try:
        # Step 1: Google Sheetsから取得
        logger.info("\nStep 1: Fetching accounts from Google Sheets...")
        sheet_accounts = fetch_accounts_from_google_sheets()
        logger.info(f"Fetched {len(sheet_accounts)} accounts from Sheets")
        
        # Step 2: データベースから取得
        logger.info("\nStep 2: Fetching accounts from database...")
        db_accounts = get_current_database_accounts()
        logger.info(f"Fetched {len(db_accounts)} accounts from database")
        
        # Step 3: 比較を表示
        logger.info("\nStep 3: Comparing accounts...")
        print_comparison(sheet_accounts, db_accounts)
        
        # Step 4: 確認
        print("\n" + "=" * 80)
        print("WARNING: This operation will:")
        print("  - Delete accounts that are NOT in the Google Sheets")
        print("  - Update account order to match Google Sheets")
        print("  - Create any missing accounts from Google Sheets")
        print("=" * 80)
        
        confirm = input("\nProceed with reordering? (type 'yes' to confirm): ").strip().lower()
        
        if confirm != 'yes':
            logger.info("Operation cancelled by user")
            return
        
        # Step 5: 並び替え実行
        logger.info("\nStep 4: Reordering accounts...")
        result = reorder_accounts(sheet_accounts, db_accounts)
        
        # Step 6: 結果表示
        print("\n" + "=" * 80)
        print("REORDERING COMPLETED")
        print("=" * 80)
        print(f"  Deleted:  {result['deleted']} accounts")
        print(f"  Updated:  {result['updated']} accounts")
        print(f"  Created:  {result['created']} accounts")
        print(f"  Final:    {result['final_count']} accounts")
        print("=" * 80)
        
        # Step 7: 順序確認
        verify_order(sheet_accounts)
        
        logger.info("\nAccount reordering completed successfully")
    
    except Exception as e:
        logger.error(f"Reordering failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()

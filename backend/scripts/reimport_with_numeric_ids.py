"""
Reimport Accounts with Numeric IDs and Inactive State

WARNING: This script stores passwords in PLAIN TEXT in the database
This is a MAJOR SECURITY RISK. Use only if absolutely necessary.

Changes:
- Numeric ID: 1-126 (stored in metadata)
- is_active: False (0) - users not logged in initially
- Session fields: Empty initially, auto-filled on login
- Passwords: PLAIN TEXT (as requested, but NOT RECOMMENDED)
- Order: Matches Google Sheets exactly
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
import json


# Google Sheets の公開CSV URL
GOOGLE_SHEET_ID = "1-2ydkZ1K08HxB73EkJ5kZ3a3_Gp_Av54X4j5RcGOCso"
GID = "556373435"
SHEET_CSV_URL = f"https://docs.google.com/spreadsheets/d/{GOOGLE_SHEET_ID}/export?format=csv&gid={GID}"

# 除外する行番号（Sheet rows）
EXCLUDED_ROWS = [2, 12, 102, 106]  # Data rows 1, 11, 101, 105

# セキュリティ設定
STORE_PLAIN_TEXT_PASSWORD = False  # ✓ SECURE: Using encryption (can be decrypted when needed)


def fetch_accounts_from_google_sheets() -> List[Dict[str, Any]]:
    """Google Sheetsからアカウント情報を取得"""
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
        numeric_id = 1  # 1から始まる連番ID
        
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
                'numeric_id': numeric_id,  # 連番ID: 1-126
                'sheet_row': row_num,
                'no': row[0].strip() if row[0] else '',
                'username': row[1].strip(),
                'password': row[2].strip(),  # そのままの形式で保存
                'note': row[3].strip() if len(row) > 3 else ''
            }
            
            accounts.append(account_data)
            numeric_id += 1
        
        logger.info(f"Fetched {len(accounts)} accounts from Google Sheets")
        return accounts
    
    except Exception as e:
        logger.error(f"Failed to fetch from Google Sheets: {e}", exc_info=True)
        raise


def delete_all_accounts() -> int:
    """既存のすべてのアカウントを削除"""
    logger.info("Deleting all existing accounts...")
    
    try:
        with get_session() as session:
            count = session.query(Account).count()
            logger.info(f"Found {count} existing accounts")
            
            deleted = session.query(Account).delete()
            session.commit()
            
            logger.info(f"Deleted {deleted} accounts")
            return deleted
    
    except Exception as e:
        logger.error(f"Failed to delete accounts: {e}", exc_info=True)
        raise


def import_accounts_with_numeric_ids(accounts_data: List[Dict[str, Any]]):
    """
    アカウントをインポート（数値ID付き）
    
    - numeric_id: 1-126の連番
    - is_active: False (0) - 未ログイン状態
    - session_token: None (空) - ログイン時に自動設定
    - last_login_at: None (空)
    - password: Plain text (⚠️ セキュリティリスク)
    """
    logger.info(f"Importing {len(accounts_data)} accounts...")
    
    if STORE_PLAIN_TEXT_PASSWORD:
        logger.warning("=" * 80)
        logger.warning("WARNING: Storing passwords in PLAIN TEXT")
        logger.warning("This is a MAJOR SECURITY RISK")
        logger.warning("Passwords will be visible to anyone with database access")
        logger.warning("=" * 80)
    
    success_count = 0
    failed_count = 0
    
    try:
        with get_session() as session:
            for account_data in accounts_data:
                username = account_data['username']
                password = account_data['password']
                numeric_id = account_data['numeric_id']
                
                try:
                    # メタデータ（数値IDと順序情報）
                    metadata = {
                        'numeric_id': numeric_id,
                        'sheet_row': account_data['sheet_row'],
                        'note': account_data['note']
                    }
                    
                    # パスワードの処理
                    if STORE_PLAIN_TEXT_PASSWORD:
                        # ⚠️ プレーンテキストで保存（セキュリティリスク）
                        password_to_store = password
                    else:
                        # 暗号化して保存（推奨）
                        from cryptography.fernet import Fernet
                        cipher = Fernet(settings.ENCRYPTION_KEY.encode())
                        password_to_store = cipher.encrypt(password.encode()).decode()
                    
                    # アカウントを作成
                    account = Account(
                        username=username,
                        password_encrypted=password_to_store,  # プレーンテキストまたは暗号化
                        store_name='',           # 空白
                        login_url='',            # 空白
                        is_active=False,         # 未ログイン状態 (0)
                        status=AccountStatus.IDLE.value,
                        error_count=0,
                        session_token=None,      # 空 - ログイン時に設定
                        last_login_at=None,      # 空 - ログイン時に設定
                        last_success_at=None,    # 空
                        metadata_json=json.dumps(metadata, ensure_ascii=False)
                    )
                    
                    session.add(account)
                    success_count += 1
                    
                    if numeric_id % 10 == 0:
                        logger.info(f"Progress: {numeric_id}/{len(accounts_data)} accounts")
                
                except Exception as e:
                    failed_count += 1
                    logger.error(f"Failed to add account {username}: {e}")
            
            # コミット
            session.commit()
            logger.info(f"Import completed: {success_count} success, {failed_count} failed")
            
            return success_count, failed_count
    
    except Exception as e:
        logger.error(f"Failed to import accounts: {e}", exc_info=True)
        raise


def verify_import():
    """インポート結果を確認"""
    logger.info("\nVerifying import...")
    
    try:
        with get_session() as session:
            accounts = session.query(Account).all()
            
            # メタデータから数値IDを取得してソート
            ordered = []
            for account in accounts:
                if account.metadata_json:
                    try:
                        metadata = json.loads(account.metadata_json)
                        ordered.append({
                            'numeric_id': metadata.get('numeric_id', 0),
                            'username': account.username,
                            'password': account.password_encrypted[:10] + '...' if len(account.password_encrypted) > 10 else account.password_encrypted,
                            'is_active': account.is_active,
                            'session_token': account.session_token,
                            'store_name': account.store_name,
                            'login_url': account.login_url
                        })
                    except:
                        pass
            
            ordered.sort(key=lambda x: x['numeric_id'])
            
            print("\n" + "=" * 80)
            print("IMPORT VERIFICATION")
            print("=" * 80)
            print(f"\nTotal accounts: {len(ordered)}")
            
            print(f"\nFirst 5 accounts:")
            for acc in ordered[:5]:
                active = "Active (1)" if acc['is_active'] else "Inactive (0)"
                session = "Yes" if acc['session_token'] else "No"
                print(f"  ID {acc['numeric_id']:3d}. {acc['username']:20s} | Password: {acc['password']:15s} | {active} | Session: {session}")
            
            print(f"\nLast 5 accounts:")
            for acc in ordered[-5:]:
                active = "Active (1)" if acc['is_active'] else "Inactive (0)"
                session = "Yes" if acc['session_token'] else "No"
                print(f"  ID {acc['numeric_id']:3d}. {acc['username']:20s} | Password: {acc['password']:15s} | {active} | Session: {session}")
            
            # 統計
            active_count = sum(1 for a in ordered if a['is_active'])
            session_count = sum(1 for a in ordered if a['session_token'])
            blank_stores = sum(1 for a in ordered if not a['store_name'])
            blank_urls = sum(1 for a in ordered if not a['login_url'])
            
            print(f"\nStatistics:")
            print(f"  Total accounts: {len(ordered)}")
            print(f"  Active accounts: {active_count} (should be 0)")
            print(f"  Accounts with session: {session_count} (should be 0)")
            print(f"  Blank store names: {blank_stores}/{len(ordered)}")
            print(f"  Blank login URLs: {blank_urls}/{len(ordered)}")
            print(f"  Numeric IDs: 1 to {len(ordered)}")
            
            if STORE_PLAIN_TEXT_PASSWORD:
                print(f"\nPassword Storage: PLAIN TEXT (SECURITY RISK)")
            else:
                print(f"\nPassword Storage: ENCRYPTED (SECURE)")
                print(f"Note: Passwords can be decrypted when needed using decrypt_password_helper.py")
            
            print("\n" + "=" * 80)
            
            # 検証
            is_valid = (
                len(ordered) == 126 and
                active_count == 0 and
                session_count == 0 and
                blank_stores == 126 and
                blank_urls == 126
            )
            
            return is_valid
    
    except Exception as e:
        logger.error(f"Verification failed: {e}", exc_info=True)
        return False


def main():
    """メイン処理"""
    print("=" * 80)
    print("REIMPORT WITH NUMERIC IDs AND INACTIVE STATE")
    print("=" * 80)
    
    if STORE_PLAIN_TEXT_PASSWORD:
        print("\nSECURITY WARNING")
        print("This script will store passwords in PLAIN TEXT!")
        print("This is NOT RECOMMENDED for production use.")
        print("Anyone with database access can see all passwords.")
        print("=" * 80)
        confirm = input("\nType 'I UNDERSTAND THE RISK' to proceed: ").strip()
        if confirm != "I UNDERSTAND THE RISK":
            print("Operation cancelled for security reasons.")
            return
    else:
        print("\nUsing ENCRYPTED password storage (recommended)")
        print("Passwords will be securely encrypted in the database.")
        print("They can be decrypted when needed for login operations.")
        print("=" * 80)
    
    print("\nThis script will:")
    print("  1. Delete ALL existing accounts")
    print("  2. Import 126 accounts from Google Sheets")
    print("  3. Assign numeric IDs: 1 to 126")
    print("  4. Set is_active: False (0) - not logged in")
    print("  5. Session fields: Empty (auto-filled on login)")
    print("  6. Store name: Blank")
    print("  7. Login URL: Blank")
    if STORE_PLAIN_TEXT_PASSWORD:
        print("  8. Password: PLAIN TEXT (INSECURE)")
    else:
        print("  8. Password: ENCRYPTED (SECURE)")
    print("=" * 80)
    
    try:
        # Step 1: Google Sheetsから取得
        logger.info("\nStep 1: Fetching from Google Sheets...")
        accounts_data = fetch_accounts_from_google_sheets()
        print(f"  Fetched: {len(accounts_data)} accounts")
        
        # Step 2: 既存削除
        logger.info("\nStep 2: Deleting existing accounts...")
        deleted_count = delete_all_accounts()
        print(f"  Deleted: {deleted_count} accounts")
        
        # Step 3: インポート
        logger.info("\nStep 3: Importing accounts with numeric IDs...")
        success, failed = import_accounts_with_numeric_ids(accounts_data)
        print(f"  Imported: {success} success, {failed} failed")
        
        # Step 4: 検証
        logger.info("\nStep 4: Verifying import...")
        is_valid = verify_import()
        
        if is_valid:
            print("\n" + "=" * 80)
            print("SUCCESS: IMPORT COMPLETED")
            print("=" * 80)
            print(f"  Total accounts: 126")
            print(f"  Numeric IDs: 1-126")
            print(f"  Active state: All inactive (0)")
            print(f"  Session fields: All empty")
            print(f"  Order: Matches Google Sheets")
            if STORE_PLAIN_TEXT_PASSWORD:
                print(f"  WARNING: Passwords: PLAIN TEXT (SECURITY RISK)")
            else:
                print(f"  Passwords: ENCRYPTED (SECURE)")
            print("=" * 80)
        else:
            print("\nWARNING: Import completed but verification failed")
    
    except Exception as e:
        logger.error(f"Import failed: {e}", exc_info=True)
        print(f"\nERROR: {e}")
        raise


if __name__ == "__main__":
    main()

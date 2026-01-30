"""
Clean Reimport of 126 Accounts

Delete all existing accounts and reimport fresh from Google Sheets
- Store name: Blank
- Login URL: Blank
- Strict sequential order maintained
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
import json


# Google Sheets の公開CSV URL
GOOGLE_SHEET_ID = "1-2ydkZ1K08HxB73EkJ5kZ3a3_Gp_Av54X4j5RcGOCso"
GID = "556373435"
SHEET_CSV_URL = f"https://docs.google.com/spreadsheets/d/{GOOGLE_SHEET_ID}/export?format=csv&gid={GID}"

# 除外する行番号（Sheet rows）
EXCLUDED_ROWS = [2, 12, 102, 106]  # Data rows 1, 11, 101, 105


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


def encrypt_password(password: str) -> str:
    """パスワードを暗号化"""
    cipher = Fernet(settings.ENCRYPTION_KEY.encode())
    encrypted = cipher.encrypt(password.encode())
    return encrypted.decode()


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


def import_accounts_clean(accounts_data: List[Dict[str, Any]]):
    """
    アカウントをクリーンインポート
    - Store name: 空白
    - Login URL: 空白
    - 順序情報のみメタデータに保存
    """
    logger.info(f"Importing {len(accounts_data)} accounts (clean mode)...")
    
    success_count = 0
    failed_count = 0
    
    try:
        with get_session() as session:
            for account_data in accounts_data:
                username = account_data['username']
                password = account_data['password']
                display_order = account_data['display_order']
                
                try:
                    # パスワードを暗号化
                    encrypted_password = encrypt_password(password)
                    
                    # メタデータ（順序情報のみ）
                    metadata = {
                        'sheet_row': account_data['sheet_row'],
                        'display_order': display_order,
                        'note': account_data['note']
                    }
                    
                    # アカウントを作成
                    account = Account(
                        username=username,
                        password_encrypted=encrypted_password,
                        store_name='',  # 空白
                        login_url='',   # 空白
                        is_active=True,
                        status=AccountStatus.IDLE.value,
                        error_count=0,
                        metadata_json=json.dumps(metadata, ensure_ascii=False)
                    )
                    
                    session.add(account)
                    success_count += 1
                    
                    if display_order % 10 == 0:
                        logger.info(f"Progress: {display_order}/{len(accounts_data)} accounts")
                
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
            # 総数
            total = session.query(Account).count()
            
            # メタデータ付きアカウント
            accounts = session.query(Account).all()
            
            ordered = []
            no_metadata = 0
            
            for account in accounts:
                if account.metadata_json:
                    try:
                        metadata = json.loads(account.metadata_json)
                        ordered.append({
                            'username': account.username,
                            'order': metadata.get('display_order', 0),
                            'store_name': account.store_name,
                            'login_url': account.login_url
                        })
                    except:
                        no_metadata += 1
                else:
                    no_metadata += 1
            
            ordered.sort(key=lambda x: x['order'])
            
            print("\n" + "=" * 80)
            print("IMPORT VERIFICATION")
            print("=" * 80)
            print(f"\nTotal accounts: {total}")
            print(f"Accounts with order: {len(ordered)}")
            print(f"Accounts without order: {no_metadata}")
            
            print(f"\nFirst 5 accounts:")
            for i, acc in enumerate(ordered[:5], 1):
                store = f"'{acc['store_name']}'" if acc['store_name'] else '(blank)'
                url = f"'{acc['login_url']}'" if acc['login_url'] else '(blank)'
                print(f"  {i}. {acc['username']} | Store: {store} | URL: {url}")
            
            print(f"\nLast 5 accounts:")
            for i, acc in enumerate(ordered[-5:], len(ordered)-4):
                store = f"'{acc['store_name']}'" if acc['store_name'] else '(blank)'
                url = f"'{acc['login_url']}'" if acc['login_url'] else '(blank)'
                print(f"  {i}. {acc['username']} | Store: {store} | URL: {url}")
            
            # 空白チェック
            blank_stores = sum(1 for a in ordered if not a['store_name'])
            blank_urls = sum(1 for a in ordered if not a['login_url'])
            
            print(f"\nBlank fields:")
            print(f"  Store names: {blank_stores}/{len(ordered)} are blank")
            print(f"  Login URLs: {blank_urls}/{len(ordered)} are blank")
            
            print("\n" + "=" * 80)
            
            return total == 126 and blank_stores == 126 and blank_urls == 126
    
    except Exception as e:
        logger.error(f"Verification failed: {e}", exc_info=True)
        return False


def main():
    """メイン処理"""
    print("=" * 80)
    print("CLEAN REIMPORT OF 126 ACCOUNTS")
    print("=" * 80)
    print("\nThis script will:")
    print("  1. Delete ALL existing accounts (126)")
    print("  2. Import 126 accounts from Google Sheets")
    print("  3. Store name: BLANK")
    print("  4. Login URL: BLANK")
    print("  5. Maintain strict sequential order")
    print("=" * 80)
    
    try:
        # Step 1: Google Sheetsから取得
        logger.info("\nStep 1: Fetching from Google Sheets...")
        accounts_data = fetch_accounts_from_google_sheets()
        print(f"  Fetched: {len(accounts_data)} accounts")
        
        if len(accounts_data) != 126:
            logger.warning(f"Expected 126 accounts, got {len(accounts_data)}")
        
        # Step 2: 既存削除
        logger.info("\nStep 2: Deleting existing accounts...")
        deleted_count = delete_all_accounts()
        print(f"  Deleted: {deleted_count} accounts")
        
        # Step 3: クリーンインポート
        logger.info("\nStep 3: Clean importing accounts...")
        success, failed = import_accounts_clean(accounts_data)
        print(f"  Imported: {success} success, {failed} failed")
        
        # Step 4: 検証
        logger.info("\nStep 4: Verifying import...")
        is_valid = verify_import()
        
        if is_valid:
            print("\n" + "=" * 80)
            print("SUCCESS: CLEAN IMPORT COMPLETED")
            print("=" * 80)
            print(f"  Total accounts: 126")
            print(f"  Store names: All blank")
            print(f"  Login URLs: All blank")
            print(f"  Order: Sequential (1-126)")
            print("=" * 80)
        else:
            print("\nWARNING: Import completed but verification failed")
    
    except Exception as e:
        logger.error(f"Clean import failed: {e}", exc_info=True)
        print(f"\nERROR: {e}")
        raise


if __name__ == "__main__":
    main()

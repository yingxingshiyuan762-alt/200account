"""
Load Accounts from Google Sheets

Google Sheetsから126アカウントを読み込み、データベースに登録
- Playwrightで実際にログインして店舗名を取得
- 登録URLをデータベースに保存
"""
import sys
import os
import re
import time
import requests
from typing import List, Dict, Any, Optional, Tuple
from playwright.sync_api import sync_playwright, Page, BrowserContext
from pathlib import Path

# プロジェクトルートをPythonパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.config import settings
from src.database.connection import get_session, db
from src.database.models import Account, AccountStatus
from src.core.logger import logger
from cryptography.fernet import Fernet


# Google Sheets の公開CSV URL
# 公開されているシートの場合は以下のような形式でCSVとして取得可能
# https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={GID}
GOOGLE_SHEET_ID = "1-2ydkZ1K08HxB73EkJ5kZ3a3_Gp_Av54X4j5RcGOCso"
GID = "556373435"  # シートのGID
SHEET_CSV_URL = f"https://docs.google.com/spreadsheets/d/{GOOGLE_SHEET_ID}/export?format=csv&gid={GID}"

# 除外する行番号（1-indexed）
EXCLUDED_ROWS = [1, 11, 101, 105]  # ヘッダー行 + 除外アカウント

# ログインURL
LOGIN_URLS = [
    "https://doors1.shinchakun.info/dokodemo/#/",
    "https://doors2.shinchakun.info/dokodemo/#/"
]


def fetch_accounts_from_google_sheets() -> List[Dict[str, str]]:
    """
    Google Sheetsからアカウント情報を取得
    
    Returns:
        List[Dict[str, str]]: アカウントリスト
    """
    logger.info("Fetching accounts from Google Sheets...")
    logger.info(f"Sheet URL: {SHEET_CSV_URL}")
    
    try:
        # CSVデータを取得
        response = requests.get(SHEET_CSV_URL, timeout=30)
        response.raise_for_status()
        
        # CSVをパース
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
            
            # ヘッダー行をスキップ（NO, ID, PASS, 備考）
            if row_num == 1:
                continue
            
            # データがない行をスキップ
            if len(row) < 3 or not row[1] or not row[2]:
                continue
            
            # アカウント情報を抽出
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


def get_store_name_from_login(
    username: str,
    password: str,
    playwright_instance,
    browser
) -> Tuple[Optional[str], Optional[str]]:
    """
    Playwrightでログインして店舗名を取得
    
    Args:
        username: ユーザー名
        password: パスワード
        playwright_instance: Playwright インスタンス
        browser: ブラウザインスタンス
    
    Returns:
        Tuple[Optional[str], Optional[str]]: (店舗名, 使用したログインURL)
    """
    logger.info(f"Getting store name for: {username}")
    
    context = None
    page = None
    
    try:
        # ブラウザコンテキストを作成
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        page = context.new_page()
        
        # 各ログインURLを試行
        for login_url in LOGIN_URLS:
            logger.info(f"[{username}] Trying login URL: {login_url}")
            
            try:
                # ページを開く
                page.goto(login_url, wait_until="domcontentloaded", timeout=30000)
                time.sleep(2)
                
                # ログインフォームを探す
                # 一般的なログインフォームセレクター
                username_selectors = [
                    'input[name="username"]',
                    'input[name="id"]',
                    'input[type="text"]',
                    '#username',
                    '#id',
                    'input[placeholder*="ID"]',
                    'input[placeholder*="ユーザー"]'
                ]
                
                password_selectors = [
                    'input[name="password"]',
                    'input[type="password"]',
                    '#password'
                ]
                
                login_button_selectors = [
                    'button[type="submit"]',
                    'input[type="submit"]',
                    'button:has-text("ログイン")',
                    'button:has-text("Login")',
                    '.login-button',
                    '#login-button'
                ]
                
                # ユーザー名入力
                username_input = None
                for selector in username_selectors:
                    try:
                        username_input = page.wait_for_selector(selector, timeout=3000)
                        if username_input and username_input.is_visible():
                            break
                    except:
                        continue
                
                if not username_input:
                    logger.warning(f"[{username}] Username input not found at {login_url}")
                    continue
                
                # パスワード入力
                password_input = None
                for selector in password_selectors:
                    try:
                        password_input = page.wait_for_selector(selector, timeout=3000)
                        if password_input and password_input.is_visible():
                            break
                    except:
                        continue
                
                if not password_input:
                    logger.warning(f"[{username}] Password input not found at {login_url}")
                    continue
                
                # ログイン実行
                logger.info(f"[{username}] Logging in...")
                username_input.fill(username)
                time.sleep(0.5)
                password_input.fill(password)
                time.sleep(0.5)
                
                # ログインボタンをクリック
                login_button = None
                for selector in login_button_selectors:
                    try:
                        login_button = page.wait_for_selector(selector, timeout=3000)
                        if login_button and login_button.is_visible():
                            break
                    except:
                        continue
                
                if login_button:
                    login_button.click()
                else:
                    # Enterキーで送信
                    password_input.press('Enter')
                
                # ページ遷移を待つ
                time.sleep(3)
                page.wait_for_load_state("networkidle", timeout=15000)
                
                # ログイン成功確認（URLが変わる、またはログインフォームが消える）
                current_url = page.url
                if "login" in current_url.lower() and "dokodemo" not in current_url:
                    logger.warning(f"[{username}] Still on login page, login may have failed")
                    continue
                
                # 店舗名を取得
                store_name = extract_store_name(page, username)
                
                if store_name:
                    logger.info(f"[{username}] Store name found: {store_name}")
                    return store_name, login_url
                else:
                    logger.warning(f"[{username}] Could not extract store name")
                    # 店舗名が取得できなくてもログインできた場合はユーザー名を使用
                    return username, login_url
            
            except Exception as e:
                logger.warning(f"[{username}] Error with URL {login_url}: {e}")
                continue
        
        # すべてのURLで失敗
        logger.error(f"[{username}] Failed to login with all URLs")
        return None, None
    
    except Exception as e:
        logger.error(f"[{username}] Unexpected error: {e}", exc_info=True)
        return None, None
    
    finally:
        if context:
            try:
                context.close()
            except:
                pass


def extract_store_name(page: Page, username: str) -> Optional[str]:
    """
    ページから店舗名を抽出
    
    Args:
        page: Playwrightページ
        username: ユーザー名（フォールバック用）
    
    Returns:
        Optional[str]: 店舗名
    """
    try:
        # 店舗名を表示している要素を探す
        # 一般的なセレクター
        store_name_selectors = [
            '.store-name',
            '#store-name',
            '[data-store-name]',
            '.shop-name',
            '#shop-name',
            'h1',
            'h2',
            '.header-title',
            '.user-info .name',
            '.profile .name'
        ]
        
        for selector in store_name_selectors:
            try:
                elements = page.query_selector_all(selector)
                for element in elements:
                    text = element.inner_text().strip()
                    if text and len(text) > 0 and len(text) < 100:
                        # IDやパスワードでなさそうな文字列
                        if not re.match(r'^[a-z0-9_]+$', text):
                            logger.debug(f"Found potential store name: {text}")
                            return text
            except:
                continue
        
        # メタタグから取得を試行
        try:
            title = page.title()
            if title and title != "Shinchakun" and len(title) < 100:
                logger.debug(f"Using page title as store name: {title}")
                return title
        except:
            pass
        
        # 取得できない場合はユーザー名を使用
        logger.warning(f"Could not extract store name, using username: {username}")
        return username
    
    except Exception as e:
        logger.error(f"Error extracting store name: {e}")
        return username


def encrypt_password(password: str) -> str:
    """
    パスワードを暗号化
    
    Args:
        password: 平文パスワード
    
    Returns:
        str: 暗号化されたパスワード
    """
    cipher = Fernet(settings.ENCRYPTION_KEY.encode())
    encrypted = cipher.encrypt(password.encode())
    return encrypted.decode()


def delete_all_accounts():
    """既存のすべてのアカウントを削除"""
    logger.info("Deleting all existing accounts...")
    
    try:
        with get_session() as session:
            from src.database.repositories.account import AccountRepository
            account_repo = AccountRepository(session)
            
            # すべてのアカウントを取得
            all_accounts = account_repo.get_all()
            count = len(all_accounts)
            
            # 削除
            for account in all_accounts:
                session.delete(account)
            
            session.commit()
            logger.info(f"Deleted {count} existing accounts")
            return count
    
    except Exception as e:
        logger.error(f"Failed to delete accounts: {e}", exc_info=True)
        raise


def load_accounts_to_database(accounts_data: List[Dict[str, str]], validated_accounts: Dict[str, Tuple[str, str]]):
    """
    アカウント情報をデータベースに登録
    
    Args:
        accounts_data: Google Sheetsから取得したアカウントデータ
        validated_accounts: {username: (store_name, login_url)} の辞書
    """
    logger.info(f"Loading {len(accounts_data)} accounts to database...")
    
    success_count = 0
    failed_count = 0
    
    try:
        with get_session() as session:
            for account_data in accounts_data:
                username = account_data['username']
                password = account_data['password']
                
                # 検証済み情報を取得
                store_name = username  # デフォルト
                login_url = LOGIN_URLS[0]  # デフォルト
                
                if username in validated_accounts:
                    store_name, login_url = validated_accounts[username]
                
                try:
                    # パスワードを暗号化
                    encrypted_password = encrypt_password(password)
                    
                    # アカウントを作成
                    account = Account(
                        username=username,
                        password_encrypted=encrypted_password,
                        store_name=store_name,
                        login_url=login_url,
                        is_active=True,
                        status=AccountStatus.IDLE.value,
                        error_count=0
                    )
                    
                    session.add(account)
                    success_count += 1
                    logger.info(f"Added account: {username} (store: {store_name})")
                
                except Exception as e:
                    failed_count += 1
                    logger.error(f"Failed to add account {username}: {e}")
            
            # コミット
            session.commit()
            logger.info(f"Database load completed: {success_count} success, {failed_count} failed")
    
    except Exception as e:
        logger.error(f"Failed to load accounts to database: {e}", exc_info=True)
        raise


def validate_accounts_with_playwright(
    accounts_data: List[Dict[str, str]],
    max_accounts: int = 10,
    headless: bool = True
) -> Dict[str, Tuple[str, str]]:
    """
    Playwrightで実際にログインして店舗名を検証
    
    Args:
        accounts_data: アカウントデータ
        max_accounts: 検証する最大アカウント数（全てを検証すると時間がかかるため）
        headless: ヘッドレスモード
    
    Returns:
        Dict[str, Tuple[str, str]]: {username: (store_name, login_url)}
    """
    logger.info(f"Validating accounts with Playwright (max {max_accounts} accounts)...")
    
    validated = {}
    
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox'
                ]
            )
            
            # 最初のN件のアカウントを検証
            accounts_to_validate = accounts_data[:max_accounts]
            
            for i, account_data in enumerate(accounts_to_validate, 1):
                username = account_data['username']
                password = account_data['password']
                
                logger.info(f"[{i}/{len(accounts_to_validate)}] Validating: {username}")
                
                store_name, login_url = get_store_name_from_login(
                    username, password, playwright, browser
                )
                
                if store_name and login_url:
                    validated[username] = (store_name, login_url)
                    logger.info(f"[{username}] Validated: store={store_name}, url={login_url}")
                else:
                    logger.warning(f"[{username}] Validation failed, will use default values")
                
                # 少し待機（レート制限対策）
                time.sleep(2)
            
            browser.close()
        
        logger.info(f"Validation completed: {len(validated)} accounts validated")
        return validated
    
    except Exception as e:
        logger.error(f"Playwright validation failed: {e}", exc_info=True)
        return validated


def main():
    """メイン処理"""
    logger.info("=" * 60)
    logger.info("ACCOUNT LOADING SCRIPT")
    logger.info("=" * 60)
    logger.info(f"Source: Google Sheets")
    logger.info(f"Excluded rows: {EXCLUDED_ROWS}")
    logger.info(f"Expected total: 126 accounts")
    logger.info("=" * 60)
    
    try:
        # Step 1: Google Sheetsからアカウント情報を取得
        logger.info("\nStep 1: Fetching accounts from Google Sheets...")
        accounts_data = fetch_accounts_from_google_sheets()
        
        if not accounts_data:
            logger.error("No accounts fetched from Google Sheets")
            return
        
        logger.info(f"Fetched {len(accounts_data)} accounts")
        
        # Step 2: 既存のアカウントを削除
        logger.info("\nStep 2: Deleting existing accounts...")
        deleted_count = delete_all_accounts()
        logger.info(f"Deleted {deleted_count} existing accounts")
        
        # Step 3: Playwrightで一部のアカウントを検証（全てを検証すると時間がかかる）
        logger.info("\nStep 3: Validating accounts with Playwright...")
        print("\n⚠️  Playwright validation will take time. Validating first 10 accounts...")
        print("⚠️  To validate all accounts, press 'y'. To skip validation and use defaults, press 'n'.")
        
        choice = input("Validate accounts? (y/n): ").strip().lower()
        
        validated_accounts = {}
        if choice == 'y':
            # 全アカウントを検証
            validated_accounts = validate_accounts_with_playwright(
                accounts_data,
                max_accounts=len(accounts_data),  # 全て
                headless=False  # GUIで確認できるように
            )
        elif choice == '10':
            # 最初の10件のみ検証
            validated_accounts = validate_accounts_with_playwright(
                accounts_data,
                max_accounts=10,
                headless=False
            )
        else:
            logger.info("Skipping Playwright validation, using default values")
        
        # Step 4: データベースに登録
        logger.info("\nStep 4: Loading accounts to database...")
        load_accounts_to_database(accounts_data, validated_accounts)
        
        # Step 5: 確認
        logger.info("\nStep 5: Verification...")
        with get_session() as session:
            from src.database.repositories.account import AccountRepository
            account_repo = AccountRepository(session)
            
            all_accounts = account_repo.get_all()
            active_accounts = account_repo.get_active_accounts()
            
            logger.info(f"Total accounts in database: {len(all_accounts)}")
            logger.info(f"Active accounts: {len(active_accounts)}")
        
        logger.info("=" * 60)
        logger.info("ACCOUNT LOADING COMPLETED SUCCESSFULLY")
        logger.info("=" * 60)
        logger.info(f"✓ Fetched: {len(accounts_data)} accounts")
        logger.info(f"✓ Validated: {len(validated_accounts)} accounts")
        logger.info(f"✓ Loaded: {len(all_accounts)} accounts")
        logger.info("=" * 60)
    
    except Exception as e:
        logger.error(f"Account loading failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()

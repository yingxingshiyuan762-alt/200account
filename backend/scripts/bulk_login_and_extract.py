"""
Bulk Login and Information Extraction

Login to all 126 accounts using Playwright:
- Try both login URLs (doors1 and doors2)
- Extract store name from the page
- Extract session information
- Update database with:
  - login_url: The URL that worked
  - store_name: Extracted from page
  - session_token: Session information
  - is_active: Set to True (1)
  - last_login_at: Current timestamp
"""
import sys
import os
import time
import re
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from datetime import datetime

# プロジェクトルートをPythonパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.config import settings
from src.database.connection import get_session
from src.database.models import Account
from src.core.logger import logger
from cryptography.fernet import Fernet
from playwright.sync_api import sync_playwright, Page, BrowserContext, TimeoutError as PlaywrightTimeout
import json


# Login URLs to try
LOGIN_URLS = [
    "https://doors1.shinchakun.info/dokodemo/#/",
    "https://doors2.shinchakun.info/dokodemo/#/"
]


def decrypt_password(encrypted_password: str) -> str:
    """パスワードを復号化"""
    cipher = Fernet(settings.ENCRYPTION_KEY.encode())
    decrypted = cipher.decrypt(encrypted_password.encode())
    return decrypted.decode()


def get_accounts_ordered() -> List[Account]:
    """数値IDの順序でアカウントを取得"""
    logger.info("Fetching accounts from database...")
    
    with get_session() as session:
        accounts = session.query(Account).all()
        
        # 数値IDでソート
        ordered = []
        for account in accounts:
            numeric_id = 0
            if account.metadata_json:
                try:
                    metadata = json.loads(account.metadata_json)
                    numeric_id = metadata.get('numeric_id', 0)
                except:
                    pass
            ordered.append((numeric_id, account))
        
        ordered.sort(key=lambda x: x[0])
        sorted_accounts = [acc for _, acc in ordered]
        
        logger.info(f"Loaded {len(sorted_accounts)} accounts")
        return sorted_accounts


def try_login(page: Page, url: str, username: str, password: str) -> Tuple[bool, Optional[str]]:
    """
    ログインを試行
    
    Returns:
        Tuple[bool, Optional[str]]: (成功/失敗, エラーメッセージ)
    """
    try:
        logger.info(f"[{username}] Trying login at: {url}")
        
        # ページを開く
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(2)
        
        # ログインフォームを探す
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
        
        # ユーザー名入力欄を探す
        username_input = None
        for selector in username_selectors:
            try:
                username_input = page.wait_for_selector(selector, timeout=3000)
                if username_input and username_input.is_visible():
                    logger.info(f"[{username}] Found username input: {selector}")
                    break
            except:
                continue
        
        if not username_input:
            return False, "Username input not found"
        
        # パスワード入力欄を探す
        password_input = None
        for selector in password_selectors:
            try:
                password_input = page.wait_for_selector(selector, timeout=3000)
                if password_input and password_input.is_visible():
                    logger.info(f"[{username}] Found password input: {selector}")
                    break
            except:
                continue
        
        if not password_input:
            return False, "Password input not found"
        
        # ログイン実行
        logger.info(f"[{username}] Entering credentials...")
        username_input.fill(username)
        time.sleep(0.5)
        password_input.fill(password)
        time.sleep(0.5)
        
        # ログインボタンを探してクリック
        login_button_selectors = [
            'button[type="submit"]',
            'input[type="submit"]',
            'button:has-text("ログイン")',
            'button:has-text("Login")',
            '.login-button',
            '#login-button'
        ]
        
        login_button = None
        for selector in login_button_selectors:
            try:
                login_button = page.wait_for_selector(selector, timeout=3000)
                if login_button and login_button.is_visible():
                    logger.info(f"[{username}] Found login button: {selector}")
                    break
            except:
                continue
        
        if login_button:
            login_button.click()
        else:
            # Enterキーで送信
            logger.info(f"[{username}] No button found, pressing Enter")
            password_input.press('Enter')
        
        # ページ遷移を待つ
        time.sleep(3)
        page.wait_for_load_state("networkidle", timeout=15000)
        
        # ログイン成功確認
        current_url = page.url
        
        # エラーメッセージをチェック
        error_indicators = [
            '.error', '.alert-danger', '.error-message',
            '[class*="error"]', '[class*="invalid"]'
        ]
        
        for selector in error_indicators:
            try:
                error_elem = page.query_selector(selector)
                if error_elem and error_elem.is_visible():
                    error_text = error_elem.inner_text()
                    logger.warning(f"[{username}] Error found: {error_text}")
                    return False, f"Login error: {error_text}"
            except:
                pass
        
        # ログインフォームがまだ表示されているかチェック
        if page.query_selector('input[type="password"]'):
            logger.warning(f"[{username}] Still on login page")
            return False, "Still on login page after submission"
        
        logger.info(f"[{username}] Login successful!")
        return True, None
    
    except PlaywrightTimeout as e:
        logger.error(f"[{username}] Timeout: {e}")
        return False, f"Timeout: {str(e)}"
    except Exception as e:
        logger.error(f"[{username}] Login error: {e}")
        return False, f"Error: {str(e)}"


def extract_store_name(page: Page, username: str) -> str:
    """
    ページから店舗名を抽出
    
    Args:
        page: Playwrightページ
        username: ユーザー名（フォールバック用）
    
    Returns:
        str: 店舗名
    """
    try:
        logger.info(f"[{username}] Extracting store name...")
        
        # 店舗名を表示している要素を探す
        store_name_selectors = [
            '.store-name',
            '#store-name',
            '[data-store-name]',
            '.shop-name',
            '#shop-name',
            'h1',
            'h2',
            '.header-title',
            '.navbar-brand',
            '.user-info .name',
            '.profile .name',
            '[class*="store"]',
            '[class*="shop"]'
        ]
        
        for selector in store_name_selectors:
            try:
                elements = page.query_selector_all(selector)
                for element in elements:
                    text = element.inner_text().strip()
                    # 有効な店舗名かチェック
                    if text and 3 <= len(text) <= 100:
                        # IDやユーザー名っぽくない
                        if not re.match(r'^[a-z0-9_]+$', text):
                            logger.info(f"[{username}] Found store name: {text}")
                            return text
            except:
                continue
        
        # メタタグから取得を試行
        try:
            title = page.title()
            if title and title != "Shinchakun" and len(title) < 100:
                logger.info(f"[{username}] Using page title: {title}")
                return title
        except:
            pass
        
        # 取得できない場合はユーザー名を使用
        logger.warning(f"[{username}] Could not extract store name, using username")
        return username
    
    except Exception as e:
        logger.error(f"[{username}] Error extracting store name: {e}")
        return username


def extract_session_token(page: Page, context: BrowserContext, username: str) -> Optional[str]:
    """
    セッショントークンを抽出
    
    Args:
        page: Playwrightページ
        context: ブラウザコンテキスト
        username: ユーザー名
    
    Returns:
        Optional[str]: セッショントークン
    """
    try:
        logger.info(f"[{username}] Extracting session token...")
        
        # Cookieからセッション情報を取得
        cookies = context.cookies()
        
        # 一般的なセッションCookie名
        session_cookie_names = [
            'session',
            'sessionid',
            'PHPSESSID',
            'JSESSIONID',
            'connect.sid',
            'token',
            'auth_token',
            'access_token'
        ]
        
        for cookie in cookies:
            if cookie['name'].lower() in [name.lower() for name in session_cookie_names]:
                logger.info(f"[{username}] Found session cookie: {cookie['name']}")
                return cookie['value']
        
        # localStorageからトークンを取得
        try:
            storage = page.evaluate('''() => {
                let data = {};
                for (let i = 0; i < localStorage.length; i++) {
                    let key = localStorage.key(i);
                    data[key] = localStorage.getItem(key);
                }
                return data;
            }''')
            
            token_keys = ['token', 'auth_token', 'session', 'access_token', 'sessionToken']
            for key in token_keys:
                if key in storage:
                    logger.info(f"[{username}] Found token in localStorage: {key}")
                    return storage[key]
        except:
            pass
        
        # すべてのCookieを結合（フォールバック）
        if cookies:
            all_cookies = '; '.join([f"{c['name']}={c['value']}" for c in cookies])
            logger.info(f"[{username}] Using all cookies as session")
            return all_cookies
        
        logger.warning(f"[{username}] No session token found")
        return None
    
    except Exception as e:
        logger.error(f"[{username}] Error extracting session: {e}")
        return None


def logout(page: Page, username: str):
    """ログアウト"""
    try:
        logger.info(f"[{username}] Logging out...")
        
        logout_selectors = [
            'a:has-text("ログアウト")',
            'button:has-text("ログアウト")',
            'a:has-text("Logout")',
            'button:has-text("Logout")',
            '.logout',
            '#logout',
            '[href*="logout"]'
        ]
        
        for selector in logout_selectors:
            try:
                logout_elem = page.wait_for_selector(selector, timeout=3000)
                if logout_elem and logout_elem.is_visible():
                    logout_elem.click()
                    time.sleep(2)
                    logger.info(f"[{username}] Logged out successfully")
                    return
            except:
                continue
        
        logger.warning(f"[{username}] Logout button not found, clearing cookies instead")
        # Cookieをクリアしてログアウトの代わりとする
        
    except Exception as e:
        logger.warning(f"[{username}] Logout error (non-critical): {e}")


def update_account_in_db(account_id: str, login_url: str, store_name: str, session_token: Optional[str]):
    """データベースのアカウント情報を更新"""
    try:
        with get_session() as session:
            account = session.query(Account).filter_by(id=account_id).first()
            
            if account:
                account.login_url = login_url
                account.store_name = store_name
                account.session_token = session_token
                account.is_active = True  # ログイン成功なので有効化
                account.last_login_at = datetime.now()
                account.last_success_at = datetime.now()
                
                session.commit()
                logger.info(f"Updated account in database: {account.username}")
            else:
                logger.error(f"Account not found in database: {account_id}")
    
    except Exception as e:
        logger.error(f"Failed to update account in database: {e}")


def process_account(account: Account, playwright_instance, browser, stats: Dict) -> bool:
    """
    1つのアカウントを処理
    
    Returns:
        bool: 成功/失敗
    """
    username = account.username
    numeric_id = 0
    
    if account.metadata_json:
        try:
            metadata = json.loads(account.metadata_json)
            numeric_id = metadata.get('numeric_id', 0)
        except:
            pass
    
    logger.info("=" * 80)
    logger.info(f"Processing Account ID {numeric_id}: {username}")
    logger.info("=" * 80)
    
    context = None
    page = None
    
    try:
        # パスワードを復号化
        plain_password = decrypt_password(account.password_encrypted)
        logger.info(f"[{username}] Password decrypted")
        
        # ブラウザコンテキストを作成
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        page = context.new_page()
        
        # 各ログインURLを試行
        login_success = False
        working_url = None
        
        for url in LOGIN_URLS:
            success, error = try_login(page, url, username, plain_password)
            
            if success:
                login_success = True
                working_url = url
                logger.info(f"[{username}] Login successful with: {url}")
                break
            else:
                logger.warning(f"[{username}] Login failed with {url}: {error}")
        
        if not login_success:
            logger.error(f"[{username}] Failed to login with all URLs")
            stats['failed'] += 1
            return False
        
        # 店舗名を抽出
        store_name = extract_store_name(page, username)
        
        # セッショントークンを抽出
        session_token = extract_session_token(page, context, username)
        
        # データベースを更新
        update_account_in_db(
            account_id=account.id,
            login_url=working_url,
            store_name=store_name,
            session_token=session_token
        )
        
        logger.info(f"[{username}] Successfully processed:")
        logger.info(f"  - Login URL: {working_url}")
        logger.info(f"  - Store Name: {store_name}")
        logger.info(f"  - Session Token: {'Yes' if session_token else 'No'}")
        
        # ログアウト
        logout(page, username)
        
        stats['success'] += 1
        return True
    
    except Exception as e:
        logger.error(f"[{username}] Processing error: {e}", exc_info=True)
        stats['failed'] += 1
        return False
    
    finally:
        if context:
            try:
                context.close()
            except:
                pass


def main():
    """メイン処理"""
    logger.info("=" * 80)
    logger.info("BULK LOGIN AND INFORMATION EXTRACTION")
    logger.info("=" * 80)
    logger.info("This script will:")
    logger.info("  1. Login to all 126 accounts")
    logger.info("  2. Try both doors1 and doors2 URLs")
    logger.info("  3. Extract store name from page")
    logger.info("  4. Extract session information")
    logger.info("  5. Update database with:")
    logger.info("     - login_url (the one that worked)")
    logger.info("     - store_name (extracted)")
    logger.info("     - session_token (extracted)")
    logger.info("     - is_active = True (1)")
    logger.info("     - last_login_at (timestamp)")
    logger.info("  6. Logout from each account")
    logger.info("=" * 80)
    
    print("\nThis will take approximately 10-20 minutes for 126 accounts.")
    print("The browser will run in visible mode so you can monitor progress.")
    
    # Auto-proceed (no confirmation needed for automation)
    print("\nAuto-proceeding with bulk login...")
    logger.info("Starting bulk login in automated mode")
    
    stats = {
        'success': 0,
        'failed': 0,
        'total': 0
    }
    
    try:
        # アカウントを取得
        accounts = get_accounts_ordered()
        stats['total'] = len(accounts)
        
        logger.info(f"\nProcessing {len(accounts)} accounts...")
        
        # Playwrightを起動
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=False,  # 可視モードで実行
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox'
                ]
            )
            
            start_time = time.time()
            
            # 各アカウントを処理
            for i, account in enumerate(accounts, 1):
                logger.info(f"\n[Progress: {i}/{len(accounts)}]")
                process_account(account, playwright, browser, stats)
                
                # 進捗表示
                if i % 10 == 0:
                    elapsed = time.time() - start_time
                    avg_time = elapsed / i
                    remaining = (len(accounts) - i) * avg_time
                    logger.info(f"Progress: {i}/{len(accounts)} | "
                              f"Success: {stats['success']} | "
                              f"Failed: {stats['failed']} | "
                              f"Est. remaining: {remaining/60:.1f} min")
                
                # レート制限対策
                time.sleep(2)
            
            browser.close()
        
        # 最終結果
        total_time = time.time() - start_time
        
        print("\n" + "=" * 80)
        print("BULK LOGIN COMPLETED")
        print("=" * 80)
        print(f"Total accounts: {stats['total']}")
        print(f"Successful:     {stats['success']}")
        print(f"Failed:         {stats['failed']}")
        print(f"Success rate:   {stats['success']/stats['total']*100:.1f}%")
        print(f"Total time:     {total_time/60:.1f} minutes")
        print("=" * 80)
        
        logger.info("Bulk login process completed")
    
    except Exception as e:
        logger.error(f"Bulk login failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()

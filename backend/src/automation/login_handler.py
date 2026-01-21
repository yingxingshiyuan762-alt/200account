"""
Login Handler Module

ログイン処理の実装
"""
from typing import Optional
from playwright.sync_api import Page

from src.core.logger import logger
from src.core.exceptions import LoginError, AutomationError
from src.database.models import Account
from src.database.encryption import decrypt_password


def login(page: Page, account: Account) -> str:
    """
    ログイン処理を実行
    
    Args:
        page: Playwrightページオブジェクト
        account: アカウントモデル
    
    Returns:
        str: セッショントークン
    
    Raises:
        LoginError: ログイン失敗時
    """
    account_id = str(account.id)
    logger.info(f"[{account_id}] Starting login process...")
    
    try:
        # パスワード復号化
        password = decrypt_password(account.password_encrypted)
        if not password:
            raise LoginError("Failed to decrypt password")
        
        # ログインID入力
        login_id_input = page.locator("input[name='login_id']")
        if not login_id_input.is_visible(timeout=5000):
            raise LoginError("Login ID input field not found")
        
        logger.debug(f"[{account_id}] Filling login ID: {account.username}")
        login_id_input.fill(account.username)
        
        # パスワード入力
        password_input = page.locator("input[type='password']")
        if not password_input.is_visible(timeout=5000):
            raise LoginError("Password input field not found")
        
        logger.debug(f"[{account_id}] Filling password")
        password_input.fill(password)
        
        # ログインボタンクリック
        submit_button = page.locator("button[type='submit']")
        if not submit_button.is_visible(timeout=5000):
            # 代替セレクタを試行
            submit_button = page.locator("button:has-text('ログイン')")
            if not submit_button.is_visible(timeout=2000):
                submit_button = page.locator("input[type='submit']")
        
        logger.debug(f"[{account_id}] Clicking submit button")
        submit_button.click()
        
        # ネットワークアイドルを待機
        logger.debug(f"[{account_id}] Waiting for navigation...")
        page.wait_for_load_state("networkidle", timeout=15000)
        
        # ログイン成功確認（トークン取得を試行）
        token = get_token(page)
        if not token:
            # トークンがない場合でも、ログインページから遷移していれば成功とみなす
            current_url = page.url
            if "login" not in current_url.lower() and "dokodemo" in current_url:
                logger.info(f"[{account_id}] Login successful (no token, but navigated)")
                return ""
            raise LoginError("Login failed: No token and still on login page")
        
        logger.info(f"[{account_id}] Login successful")
        return token
        
    except LoginError:
        raise
    except Exception as e:
        logger.error(f"[{account_id}] Login error: {e}", exc_info=True)
        raise LoginError(f"Login failed: {str(e)}") from e


def get_token(page: Page) -> Optional[str]:
    """
    セッショントークンを取得
    
    Args:
        page: Playwrightページオブジェクト
    
    Returns:
        Optional[str]: トークン（存在しない場合はNone）
    """
    try:
        token = page.evaluate("() => localStorage.getItem('token')")
        return token if token else None
    except Exception as e:
        logger.debug(f"Failed to get token: {e}")
        return None


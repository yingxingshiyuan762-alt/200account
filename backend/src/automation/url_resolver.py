"""
URL Resolver Module

ログインURL自動判別機能
"""
from typing import Optional
from playwright.sync_api import Page

from config.config import settings
from src.core.logger import logger
from src.core.exceptions import AutomationError


def resolve_base_url(page: Page, account_id: str) -> str:
    """
    ログインURLを自動判別
    
    複数のURLを試行し、パスワード入力欄が表示されるURLを返す
    
    Args:
        page: Playwrightページオブジェクト
        account_id: アカウントID（ログ用）
    
    Returns:
        str: 有効なログインURL
    
    Raises:
        AutomationError: 有効なURLが見つからない場合
    """
    logger.info(f"[{account_id}] Resolving login URL...")
    
    for url in settings.LOGIN_URLS:
        try:
            logger.debug(f"[{account_id}] Trying URL: {url}")
            page.goto(url, timeout=5000, wait_until="domcontentloaded")
            
            # パスワード入力欄の存在確認
            password_input = page.locator("input[type='password']")
            if password_input.is_visible(timeout=2000):
                logger.info(f"[{account_id}] Login URL resolved: {url}")
                return url
        except Exception as e:
            logger.debug(f"[{account_id}] URL {url} failed: {e}")
            continue
    
    # すべてのURLが失敗
    error_msg = f"Login URL not found. Tried: {settings.LOGIN_URLS}"
    logger.error(f"[{account_id}] {error_msg}")
    raise AutomationError(error_msg)


def get_cached_url(account) -> Optional[str]:
    """
    アカウントに保存されているURLを取得
    
    Args:
        account: Accountモデルインスタンス
    
    Returns:
        Optional[str]: 保存されているURL（存在しない場合はNone）
    """
    if account and account.login_url:
        logger.debug(f"[{account.id}] Using cached URL: {account.login_url}")
        return account.login_url
    return None


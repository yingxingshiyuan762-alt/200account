"""
App Crash Detector Module

アプリ停止（赤い×）検知と再起動機能
"""
from typing import Optional, TYPE_CHECKING, Any
from playwright.sync_api import Page, BrowserContext

from src.core.logger import logger
from src.core.exceptions import AppCrashError

if TYPE_CHECKING:
    from src.automation.browser_manager import BrowserManager
    from src.database.models import Account


def detect_app_crash(page: Page) -> bool:
    """
    アプリ停止（赤い×）を検知
    
    Args:
        page: Playwrightページオブジェクト
    
    Returns:
        bool: クラッシュが検知された場合True
    """
    try:
        # 赤い×のセレクタ（実際のDOMに合わせて調整が必要）
        red_x_selectors = [
            ".red-x",
            "[class*='red-x']",
            "[class*='error-x']",
            "[class*='crash']",
            "div:has-text('×')",
            ".app-crash",
            ".error-indicator"
        ]
        
        for selector in red_x_selectors:
            try:
                element = page.locator(selector)
                if element.is_visible(timeout=1000):
                    logger.warning(f"App crash detected with selector: {selector}")
                    return True
            except Exception:
                continue
        
        return False
    except Exception as e:
        logger.debug(f"Error detecting app crash: {e}")
        return False


def handle_app_crash(
    page: Page,
    context: BrowserContext,
    account_id: str,
    browser_manager: 'BrowserManager',
    account: 'Account'
) -> Page:
    """
    アプリクラッシュを処理（再起動）
    
    Args:
        page: 現在のページオブジェクト
        context: 現在のブラウザコンテキスト
        account_id: アカウントID
        browser_manager: ブラウザマネージャー
        account: アカウントモデル
    
    Returns:
        Page: 新しいページオブジェクト
    """
    logger.critical(f"[{account_id}] App crash detected, restarting...")
    
    try:
        # 古いコンテキストを閉じる
        context.close()
        logger.info(f"[{account_id}] Old context closed")
        
        # 新しいコンテキストを作成
        new_context = browser_manager.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        new_context.set_default_timeout(10000)
        new_context.set_default_navigation_timeout(30000)
        
        # 新しいページを作成
        new_page = new_context.new_page()
        
        logger.info(f"[{account_id}] App restarted successfully")
        return new_page
        
    except Exception as e:
        logger.error(f"[{account_id}] Failed to restart app: {e}", exc_info=True)
        raise AppCrashError(f"App restart failed: {e}") from e


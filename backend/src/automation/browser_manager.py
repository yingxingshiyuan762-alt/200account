"""
Browser Manager Module

Playwrightブラウザ管理とコンテキスト分離
"""
from typing import Optional, Dict, Any
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page, Playwright
from contextlib import contextmanager

from config.config import settings
from src.core.logger import logger
from src.core.exceptions import AutomationError, AppCrashError


class BrowserManager:
    """
    Playwrightブラウザマネージャー
    
    原則:
    - 1アカウント = 1 Browser Context
    - ブラウザは共有、コンテキストは分離
    """
    
    def __init__(self, headless: Optional[bool] = None):
        """
        初期化
        
        Args:
            headless: ヘッドレスモード（Noneの場合は設定から取得）
        """
        self.headless = headless if headless is not None else settings.BROWSER_HEADLESS
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self._is_running = False
    
    def start(self):
        """ブラウザを起動"""
        if self._is_running:
            logger.warning("Browser is already running")
            return
        
        try:
            logger.info("Starting Playwright browser...")
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(
                headless=self.headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox'
                ]
            )
            self._is_running = True
            logger.info("Browser started successfully")
        except Exception as e:
            logger.error(f"Failed to start browser: {e}", exc_info=True)
            raise AutomationError(f"Browser startup failed: {e}") from e
    
    def stop(self):
        """ブラウザを停止"""
        if not self._is_running:
            return
        
        try:
            logger.info("Stopping browser...")
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
            self._is_running = False
            logger.info("Browser stopped")
        except Exception as e:
            logger.error(f"Error stopping browser: {e}", exc_info=True)
    
    @contextmanager
    def create_context(self, account_id: str, **kwargs) -> BrowserContext:
        """
        アカウント用のブラウザコンテキストを作成
        
        原則: 1アカウント = 1 Context
        
        Args:
            account_id: アカウントID（ログ用）
            **kwargs: コンテキスト作成時の追加オプション
        
        Yields:
            BrowserContext: ブラウザコンテキスト
        """
        if not self._is_running:
            raise AutomationError("Browser is not running. Call start() first.")
        
        context: Optional[BrowserContext] = None
        try:
            logger.info(f"[{account_id}] Creating browser context")
            
            # コンテキスト作成（Cookie/localStorage/session完全分離）
            context = self.browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                **kwargs
            )
            
            # デフォルトタイムアウト設定
            context.set_default_timeout(settings.BROWSER_WAIT_TIMEOUT)
            context.set_default_navigation_timeout(settings.BROWSER_TIMEOUT)
            
            logger.info(f"[{account_id}] Browser context created")
            yield context
            
        except Exception as e:
            logger.error(f"[{account_id}] Error in browser context: {e}", exc_info=True)
            raise
        finally:
            if context:
                try:
                    logger.info(f"[{account_id}] Closing browser context")
                    context.close()
                except Exception as e:
                    logger.error(f"[{account_id}] Error closing context: {e}", exc_info=True)
    
    def __enter__(self):
        """コンテキストマネージャー: 開始"""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """コンテキストマネージャー: 終了"""
        self.stop()
    
    def is_running(self) -> bool:
        """ブラウザが起動中か確認"""
        return self._is_running


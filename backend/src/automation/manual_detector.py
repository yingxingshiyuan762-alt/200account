"""
Manual Operation Detector Module

手動操作検知機能
"""
from typing import Optional, Dict, Any
from playwright.sync_api import Page
import hashlib
import base64

from src.core.logger import logger
from src.core.exceptions import ManualOperationDetectedError
from src.database.models import DetectionType


class ManualOperationDetector:
    """
    手動操作検知器
    
    トークン変化とDOM変化を監視して手動操作を検知
    """
    
    def __init__(self, account_id: str):
        """
        初期化
        
        Args:
            account_id: アカウントID
        """
        self.account_id = account_id
        self.last_token: Optional[str] = None
        self.last_dom_fingerprint: Optional[str] = None
        self._initialized = False
    
    def initialize(self, page: Page):
        """
        初期状態を記録
        
        Args:
            page: Playwrightページオブジェクト
        """
        try:
            self.last_token = self._get_token(page)
            self.last_dom_fingerprint = self._get_dom_fingerprint(page)
            self._initialized = True
            logger.debug(f"[{self.account_id}] Manual detector initialized")
        except Exception as e:
            logger.warning(f"[{self.account_id}] Failed to initialize detector: {e}")
    
    def check(self, page: Page) -> Dict[str, Any]:
        """
        手動操作をチェック
        
        Args:
            page: Playwrightページオブジェクト
        
        Returns:
            Dict[str, Any]: 検知結果
        
        Raises:
            ManualOperationDetectedError: 手動操作が検知された場合
        """
        if not self._initialized:
            self.initialize(page)
            return {'detected': False}
        
        try:
            current_token = self._get_token(page)
            current_dom = self._get_dom_fingerprint(page)
            
            token_changed = (current_token != self.last_token and 
                           self.last_token is not None and 
                           current_token is not None)
            
            dom_changed = (current_dom != self.last_dom_fingerprint and 
                          self.last_dom_fingerprint is not None)
            
            if token_changed or dom_changed:
                detection_type = DetectionType.TOKEN_CHANGE if token_changed else DetectionType.DOM_MUTATION
                
                logger.warning(
                    f"[{self.account_id}] Manual operation detected: "
                    f"token_changed={token_changed}, dom_changed={dom_changed}"
                )
                
                raise ManualOperationDetectedError(
                    f"Manual operation detected: {detection_type.value}"
                )
            
            return {
                'detected': False,
                'token_changed': False,
                'dom_changed': False
            }
            
        except ManualOperationDetectedError:
            raise
        except Exception as e:
            logger.error(f"[{self.account_id}] Error checking manual operation: {e}", exc_info=True)
            return {'detected': False, 'error': str(e)}
    
    def _get_token(self, page: Page) -> Optional[str]:
        """トークンを取得"""
        try:
            return page.evaluate("() => localStorage.getItem('token')")
        except Exception:
            return None
    
    def _get_dom_fingerprint(self, page: Page) -> Optional[str]:
        """
        DOMフィンガープリントを取得
        
        最初の1500文字をBase64エンコードして返す
        """
        try:
            fingerprint = page.evaluate("""
                () => {
                    const html = document.body.innerHTML.slice(0, 1500);
                    return btoa(unescape(encodeURIComponent(html)));
                }
            """)
            return fingerprint
        except Exception:
            return None
    
    def update_state(self, page: Page):
        """
        状態を更新（正常な操作後）
        
        Args:
            page: Playwrightページオブジェクト
        """
        try:
            self.last_token = self._get_token(page)
            self.last_dom_fingerprint = self._get_dom_fingerprint(page)
        except Exception as e:
            logger.debug(f"[{self.account_id}] Failed to update detector state: {e}")


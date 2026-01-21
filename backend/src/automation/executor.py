"""
Parallel Executor Module

並列実行エンジン（安全な上限付き）
"""
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from config.config import settings
from src.core.logger import logger
from src.database.models import Account
from src.automation.browser_manager import BrowserManager
from src.automation.worker import run_account_job


class ParallelExecutor:
    """
    並列実行エンジン
    
    原則:
    - 5〜10並列が現実的
    - 200並列は禁止
    """
    
    def __init__(self, max_workers: Optional[int] = None):
        """
        初期化
        
        Args:
            max_workers: 最大並列数（Noneの場合は設定から取得）
        """
        self.max_workers = max_workers or settings.MAX_CONCURRENT_ACCOUNTS
        if self.max_workers > 10:
            logger.warning(f"max_workers ({self.max_workers}) is too high. Capping at 10.")
            self.max_workers = 10
        
        self.browser_manager: Optional[BrowserManager] = None
        self._lock = threading.Lock()
    
    def execute_accounts(
        self,
        accounts: List[Account],
        task_type: str = "schedule_update"
    ) -> Dict[str, Any]:
        """
        複数アカウントを並列実行
        
        Args:
            accounts: アカウントリスト
            task_type: タスク種別
        
        Returns:
            Dict[str, Any]: 実行結果サマリー
        """
        if not accounts:
            logger.warning("No accounts to process")
            return {
                'total': 0,
                'success': 0,
                'failed': 0,
                'skipped': 0,
                'results': []
            }
        
        logger.info(
            f"Starting parallel execution: {len(accounts)} accounts, "
            f"max_workers={self.max_workers}, task_type={task_type}"
        )
        
        # スケジュール更新の場合はロックされていないアカウントのみをフィルタ
        if task_type == "schedule_update":
            from src.database.connection import get_session
            from src.database.repositories.account import AccountRepository
            with get_session() as session:
                account_repo = AccountRepository(session)
                # ロックされていないアカウントのみ
                accounts = [acc for acc in accounts if not account_repo.is_locked(str(acc.id))]
                logger.info(f"After lock check: {len(accounts)} accounts available for schedule update")
        
        # ブラウザマネージャーを起動
        self.browser_manager = BrowserManager()
        self.browser_manager.start()
        
        summary = {
            'total': len(accounts),
            'success': 0,
            'failed': 0,
            'skipped': 0,
            'results': []
        }
        
        try:
            # 並列実行
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # タスクを送信
                future_to_account = {
                    executor.submit(run_account_job, self.browser_manager, account, task_type): account
                    for account in accounts
                }
                
                # 完了を待機
                for future in as_completed(future_to_account):
                    account = future_to_account[future]
                    account_id = str(account.id)
                    
                    try:
                        result = future.result()
                        summary['results'].append(result)
                        
                        if result.get('success'):
                            summary['success'] += 1
                            logger.info(f"[{account_id}] Completed successfully")
                        elif result.get('error') == "Manual operation detected":
                            summary['skipped'] += 1
                            logger.info(f"[{account_id}] Skipped (manual operation)")
                        else:
                            summary['failed'] += 1
                            logger.warning(f"[{account_id}] Failed: {result.get('error')}")
                    
                    except Exception as e:
                        logger.error(f"[{account_id}] Unexpected error in executor: {e}", exc_info=True)
                        summary['failed'] += 1
                        summary['results'].append({
                            'account_id': account_id,
                            'username': account.username,
                            'success': False,
                            'error': str(e),
                            'task_type': task_type
                        })
        
        finally:
            # ブラウザマネージャーを停止
            if self.browser_manager:
                self.browser_manager.stop()
                self.browser_manager = None
        
        logger.info(
            f"Parallel execution completed: "
            f"success={summary['success']}, "
            f"failed={summary['failed']}, "
            f"skipped={summary['skipped']}, "
            f"total={summary['total']}"
        )
        
        return summary
    
    def execute_single_account(
        self,
        account: Account,
        task_type: str = "schedule_update"
    ) -> Dict[str, Any]:
        """
        単一アカウントを実行
        
        Args:
            account: アカウントモデル
            task_type: タスク種別
        
        Returns:
            Dict[str, Any]: 実行結果
        """
        logger.info(f"Executing single account: {account.username}, task_type={task_type}")
        
        # ブラウザマネージャーを起動
        self.browser_manager = BrowserManager()
        self.browser_manager.start()
        
        try:
            result = run_account_job(self.browser_manager, account, task_type)
            return result
        finally:
            # ブラウザマネージャーを停止
            if self.browser_manager:
                self.browser_manager.stop()
                self.browser_manager = None


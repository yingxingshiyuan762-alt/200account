"""
Task Scheduler Module

自動スケジュール更新と待機接客配信のスケジューリング
"""
import asyncio
from datetime import datetime, timedelta, date
from typing import Optional, Dict, Any, Set
import random
import threading

from config.config import settings
from src.core.logger import logger
from src.database.connection import get_session
from src.database.repositories.account import AccountRepository
from src.automation.executor import ParallelExecutor
from src.database.models import Account, AccountStatus
from src.database.repositories.log import AccountLogRepository
from src.database.models import ActionType

class TaskScheduler:
    """
    タスクスケジューラー
    
    機能:
    - 毎日7:00-10:00にスケジュール更新を自動実行
    - 60-90分間隔で待機接客配信を自動実行
    """
    
    def __init__(self):
        self.running = False
        self.schedule_update_task: Optional[asyncio.Task] = None
        self.wait_reception_task: Optional[asyncio.Task] = None
        self.last_schedule_update_date: Optional[date] = None
        self._lock = threading.Lock()
        
    async def start(self):
        """スケジューラーを開始"""
        self.running = True
        logger.info("=" * 60)
        logger.info("Task Scheduler Starting")
        logger.info("=" * 60)
        logger.info(f"Schedule Update: Daily at {settings.SCHEDULE_UPDATE_START_HOUR}:00-{settings.SCHEDULE_UPDATE_END_HOUR}:00")
        logger.info(f"Wait Reception: Every {settings.WAIT_RECEPTION_INTERVAL_MIN}-{settings.WAIT_RECEPTION_INTERVAL_MAX} minutes")
        logger.info("=" * 60)
        
        # スケジュール更新タスクを開始
        self.schedule_update_task = asyncio.create_task(
            self._schedule_update_loop()
        )
        
        # 待機接客配信タスクを開始
        self.wait_reception_task = asyncio.create_task(
            self._wait_reception_loop()
        )
        
        logger.info("Task scheduler started successfully")
    
    async def stop(self):
        """スケジューラーを停止"""
        self.running = False
        logger.info("Stopping task scheduler...")
        
        if self.schedule_update_task:
            self.schedule_update_task.cancel()
            try:
                await self.schedule_update_task
            except asyncio.CancelledError:
                pass
        
        if self.wait_reception_task:
            self.wait_reception_task.cancel()
            try:
                await self.wait_reception_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Task scheduler stopped")
    
    async def _schedule_update_loop(self):
        """
        スケジュール更新ループ
        
        毎日7:00-10:00の時間帯に1回実行
        """
        while self.running:
            try:
                now = datetime.now()
                current_hour = now.hour
                current_date = now.date()
                
                # 実行時間帯チェック（7:00-10:00）
                if settings.SCHEDULE_UPDATE_START_HOUR <= current_hour < settings.SCHEDULE_UPDATE_END_HOUR:
                    # 今日すでに実行済みかチェック
                    with self._lock:
                        if self.last_schedule_update_date == current_date:
                            # 今日は実行済み：次の実行時刻まで待機
                            next_run = self._get_next_schedule_update_time()
                            wait_seconds = (next_run - now).total_seconds()
                            logger.info(f"Schedule update already executed today. Next run: {next_run}")
                            await asyncio.sleep(min(wait_seconds, 3600))  # 最大1時間ごとにチェック
                            continue
                    
                    # 実行条件チェック（システム設定で有効になっているか）
                    if not await self._is_schedule_update_enabled():
                        logger.info("Schedule update is disabled in system config")
                        await asyncio.sleep(3600)  # 1時間待機
                        continue
                    
                    # スケジュール更新を実行
                    logger.info("=" * 60)
                    logger.info("Starting scheduled schedule update task...")
                    logger.info(f"Time: {now.strftime('%Y-%m-%d %H:%M:%S')}")
                    logger.info("=" * 60)
                    
                    success = await self._execute_schedule_update()
                    
                    if success:
                        with self._lock:
                            self.last_schedule_update_date = current_date
                        logger.info("Schedule update task completed successfully")
                    else:
                        logger.error("Schedule update task failed")
                    
                    # 今日はもう実行しない（明日まで待機）
                    next_run = self._get_next_schedule_update_time()
                    wait_seconds = (next_run - now).total_seconds()
                    logger.info(f"Next schedule update: {next_run} (in {wait_seconds/3600:.1f} hours)")
                    await asyncio.sleep(min(wait_seconds, 3600))
                    
                else:
                    # 実行時間外：次の実行時刻まで待機
                    next_run = self._get_next_schedule_update_time()
                    wait_seconds = (next_run - now).total_seconds()
                    
                    if wait_seconds > 3600:
                        # 1時間以上待つ場合は、1時間ごとにチェック
                        logger.debug(f"Schedule update: Next run at {next_run}, waiting {wait_seconds/3600:.1f} hours")
                        await asyncio.sleep(3600)
                    else:
                        # 1時間以内の場合はそのまま待機
                        logger.debug(f"Schedule update: Next run at {next_run}, waiting {wait_seconds/60:.1f} minutes")
                        await asyncio.sleep(wait_seconds)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in schedule update loop: {e}", exc_info=True)
                await asyncio.sleep(60)  # エラー時は1分待機
    
    async def _execute_schedule_update(self) -> bool:
        """
        スケジュール更新を実行
        
        Returns:
            bool: 実行成功時True
        """
        try:
            def _run_sync():
                """同期関数で実行（データベース操作のため）"""
                with get_session() as session:
                    account_repo = AccountRepository(session)
                    
                    # アクティブなアカウントを取得
                    accounts = account_repo.get_active_accounts()
                    
                    if not accounts:
                        logger.warning("No active accounts found for schedule update")
                        return {
                            'success': False,
                            'total': 0,
                            'message': 'No active accounts'
                        }
                    
                    logger.info(f"Found {len(accounts)} active accounts for schedule update")
                    
                    # 並列実行
                    executor = ParallelExecutor()
                    summary = executor.execute_accounts(accounts, task_type="schedule_update")
                    
                    return summary
            
            # 非同期スレッドで実行（ブロッキングを回避）
            summary = await asyncio.to_thread(_run_sync)
            
            logger.info(
                f"Schedule update completed: "
                f"total={summary.get('total', 0)}, "
                f"success={summary.get('success', 0)}, "
                f"failed={summary.get('failed', 0)}, "
                f"skipped={summary.get('skipped', 0)}"
            )
            
            return summary.get('success', 0) > 0 or summary.get('total', 0) == 0
            
        except Exception as e:
            logger.error(f"Error executing schedule update: {e}", exc_info=True)
            return False
    
    def _get_next_schedule_update_time(self) -> datetime:
        """
        次回スケジュール更新時刻を計算
        
        Returns:
            datetime: 次回実行時刻
        """
        now = datetime.now()
        today_7am = now.replace(
            hour=settings.SCHEDULE_UPDATE_START_HOUR,
            minute=0,
            second=0,
            microsecond=0
        )
        
        if now < today_7am:
            # 今日の7:00がまだ来ていない
            return today_7am
        else:
            # 今日の7:00は過ぎたので、明日の7:00
            return today_7am + timedelta(days=1)
    
    async def _is_schedule_update_enabled(self) -> bool:
        """
        スケジュール更新が有効かチェック
        
        Returns:
            bool: 有効な場合True
        """
        def _check_sync():
            with get_session() as session:
                from src.database.models import SystemConfig
                config = session.query(SystemConfig).filter_by(
                    key='schedule_update_enabled'
                ).first()
                
                if config and isinstance(config.value, dict):
                    return config.value.get('value', True)
                return True  # デフォルトは有効
        
        return await asyncio.to_thread(_check_sync)
    
    async def _wait_reception_loop(self):
        """
        待機接客配信ループ（60-90分間隔で実行）
        
        各サイクルは独立して実行され、安全に再実行可能
        """
        while self.running:
            try:
                # ランダム間隔（60-90分）を秒単位で計算
                interval_seconds = random.randint(
                    settings.WAIT_RECEPTION_INTERVAL_MIN * 60,
                    settings.WAIT_RECEPTION_INTERVAL_MAX * 60
                )
                
                logger.debug(f"Wait reception: Next run in {interval_seconds/60:.1f} minutes ({interval_seconds} seconds)")
                await asyncio.sleep(interval_seconds)
                
                if self.running:
                    # 実行条件チェック
                    if not await self._is_wait_reception_enabled():
                        logger.info("Wait reception is disabled in system config")
                        continue
                    
                    logger.info("=" * 60)
                    logger.info("Starting scheduled wait reception task...")
                    logger.info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                    logger.info("=" * 60)
                    
                    success = await self._execute_wait_reception()
                    
                    if success:
                        logger.info("Wait reception task completed successfully")
                    else:
                        logger.warning("Wait reception task completed with warnings or aborted")
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in wait reception loop: {e}", exc_info=True)
                await asyncio.sleep(60)  # エラー時は1分待機
    
    async def _execute_wait_reception(self) -> bool:
        """
        待機接客配信を実行
        
        グローバル事前チェックを実行後、対象アカウントを処理
        
        Returns:
            bool: 実行成功時True（中止時もTrueとして扱う）
        """
        try:
            def _run_sync():
                """同期関数で実行（データベース操作とブラウザ操作のため）"""
                from src.automation.browser_manager import BrowserManager
                from src.automation.worker import check_global_preconditions
                
                with get_session() as session:
                    account_repo = AccountRepository(session)
                    accounts = account_repo.get_active_accounts()
                    
                    if not accounts:
                        logger.warning("No active accounts found for wait reception")
                        return {
                            'success': False,
                            'total': 0,
                            'message': 'No active accounts',
                            'aborted': False
                        }
                    
                    logger.info(f"Found {len(accounts)} active accounts for wait reception")
                    
                    # グローバル事前チェック
                    browser_manager = BrowserManager()
                    browser_manager.start()
                    
                    try:
                        precheck_result = check_global_preconditions(
                            browser_manager,
                            accounts[0] if accounts else None  # 代表アカウントでチェック
                        )
                        
                        if not precheck_result['can_proceed']:
                            logger.warning(
                                f"Wait reception cycle aborted: {precheck_result['reason']}"
                            )
                            return {
                                'success': True,  # 中止は正常な動作
                                'total': 0,
                                'aborted': True,
                                'reason': precheck_result['reason']
                            }
                        
                        logger.info(
                            f"Global pre-check passed: "
                            f"active_casts={precheck_result.get('active_cast_count', 'N/A')}, "
                            f"eligible_accounts={precheck_result.get('eligible_account_count', 'N/A')}"
                        )
                        
                        # 対象アカウントをフィルタ（時間制約チェック済み）
                        eligible_accounts = precheck_result.get('eligible_accounts', accounts)
                        
                        if not eligible_accounts:
                            logger.info("No eligible accounts after time constraint check")
                            return {
                                'success': True,
                                'total': 0,
                                'aborted': False,
                                'message': 'No eligible accounts'
                            }
                        
                        logger.info(f"Processing {len(eligible_accounts)} eligible accounts")
                        
                        # 並列実行
                        executor = ParallelExecutor()
                        summary = executor.execute_accounts(eligible_accounts, task_type="wait_reception")
                        summary['aborted'] = False
                        return summary
                    
                    finally:
                        browser_manager.stop()
            
            summary = await asyncio.to_thread(_run_sync)
            
            logger.info(
                f"Wait reception completed: "
                f"total={summary.get('total', 0)}, "
                f"success={summary.get('success', 0)}, "
                f"failed={summary.get('failed', 0)}, "
                f"skipped={summary.get('skipped', 0)}, "
                f"aborted={summary.get('aborted', False)}"
            )
            
            # 中止時も成功として扱う（正常な動作）
            return True
            
        except Exception as e:
            logger.error(f"Error executing wait reception: {e}", exc_info=True)
            return False
    
    async def _is_wait_reception_enabled(self) -> bool:
        """待機接客配信が有効かチェック"""
        def _check_sync():
            with get_session() as session:
                from src.database.models import SystemConfig
                config = session.query(SystemConfig).filter_by(
                    key='wait_reception_enabled'
                ).first()
                
                if config and isinstance(config.value, dict):
                    return config.value.get('value', True)
                return True
        
        return await asyncio.to_thread(_check_sync)
    
    def get_next_schedule_update_time(self) -> datetime:
        """次回スケジュール更新時刻を取得（API用）"""
        return self._get_next_schedule_update_time()
    
    def get_last_schedule_update_date(self) -> Optional[date]:
        """最後のスケジュール更新日時を取得"""
        return self.last_schedule_update_date

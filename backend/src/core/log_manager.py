"""
統合ログマネージャーモジュール

200アカウントのシステムイベントログを一元管理
ログベースの復旧システムの中核コンポーネント
"""
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from contextlib import contextmanager
import uuid
import time
import inspect
import os
from pathlib import Path

from src.core.logger import logger
from src.core.event_system import EventType, EventSeverity, event_logger, SystemEvent
from src.database.repositories.account import AccountRepository
from src.database.repositories.log import AccountLogRepository
from src.database.models import Account, AccountStatus, ActionType, LogStatus

# Lazy import get_session to avoid circular dependency
# from src.database.connection import get_session

# Lazy imports to avoid circular dependency
# from src.core.recovery_manager import RecoveryManager, RecoveryStrategy, recovery_manager
# from src.core.account_state_recovery import AccountStateRecovery, account_state_recovery


def _get_code_location() -> Dict[str, Optional[Any]]:
    """
    現在のコード位置を取得
    
    呼び出し元のコード（log_success/log_error/log_skippedを呼び出したコード）を取得
    
    Returns:
        Dict with file_path, function_name, line_number
    """
    try:
        # 呼び出し元のフレームを取得
        # フレーム構造:
        # 0: _get_code_location() (現在)
        # 1: LogContext.log_success/log_error/log_skipped()
        # 2: 実際のユーザーコード（log_ctx.log_success()を呼び出した場所）
        frame = inspect.currentframe()
        if frame:
            # 1つ前のフレーム（LogContextのメソッド）
            caller_frame = frame.f_back
            if caller_frame:
                # さらに1つ前のフレーム（実際のユーザーコード）
                caller_frame = caller_frame.f_back
                if caller_frame:
                    # ファイルパスを取得
                    file_path = caller_frame.f_code.co_filename
                    
                    # プロジェクトルートからの相対パスに変換
                    project_root = Path(__file__).parent.parent.parent
                    try:
                        relative_path = os.path.relpath(file_path, project_root)
                    except ValueError:
                        # Windowsで異なるドライブの場合など
                        relative_path = file_path
                    
                    return {
                        'file_path': relative_path.replace('\\', '/'),  # 統一されたパス区切り
                        'function_name': caller_frame.f_code.co_name,
                        'line_number': caller_frame.f_lineno
                    }
    except Exception as e:
        logger.debug(f"Failed to get code location: {e}")
    
    return {
        'file_path': None,
        'function_name': None,
        'line_number': None
    }


class LogManager:
    """
    統合ログマネージャー
    
    200アカウントのシステムイベントログを一元管理し、
    ログベースの復旧を提供する
    """
    
    def __init__(self):
        # Lazy imports to avoid circular dependency
        from src.core.recovery_manager import recovery_manager
        from src.core.account_state_recovery import account_state_recovery
        
        self.recovery_manager = recovery_manager
        self.account_state_recovery = account_state_recovery
        self.event_logger = event_logger
    
    @contextmanager
    def log_operation(
        self,
        account_id: Optional[str],
        action_type: ActionType,
        request_id: Optional[str] = None,
        **extra_data
    ):
        """
        操作をログ記録するコンテキストマネージャー
        
        使用例:
            with log_manager.log_operation(account_id, ActionType.LOGIN) as log_ctx:
                # 操作を実行
                log_ctx.log_success("Login successful")
                # または
                log_ctx.log_error("Login failed", error_detail={...})
        
        Args:
            account_id: アカウントID
            action_type: 操作種別
            request_id: リクエストID（未指定時は自動生成）
            **extra_data: 追加データ
        
        Yields:
            LogContext: ログコンテキスト
        """
        start_time = time.time()
        operation_request_id = request_id or str(uuid.uuid4())
        
        # 操作開始イベント
        event_logger.log_event(
            event_type=self._get_start_event_type(action_type),
            severity=EventSeverity.INFO,
            account_id=account_id,
            message=f"{action_type.value} operation started",
            request_id=operation_request_id,
            data=extra_data
        )
        
        log_context = LogContext(
            account_id=account_id,
            action_type=action_type,
            request_id=operation_request_id,
            start_time=start_time
        )
        
        try:
            yield log_context
        except Exception as e:
            execution_time = time.time() - start_time
            
            # エラーをログ記録
            log_context.log_error(
                message=str(e),
                error_detail={
                    'exception_type': type(e).__name__,
                    'traceback': str(e),
                    **extra_data
                },
                execution_time=execution_time
            )
            
            # イベントログ
            event_logger.log_event(
                event_type=self._get_fail_event_type(action_type),
                severity=EventSeverity.ERROR,
                account_id=account_id,
                message=f"{action_type.value} operation failed: {str(e)}",
                request_id=operation_request_id,
                data={'execution_time': execution_time, **extra_data}
            )
            raise
        finally:
            if not log_context.completed:
                execution_time = time.time() - start_time
                log_context.log_skipped(
                    message="Operation was not completed",
                    execution_time=execution_time
                )
    
    def _get_start_event_type(self, action_type: ActionType) -> EventType:
        """操作種別から開始イベントタイプを取得"""
        mapping = {
            ActionType.LOGIN: EventType.LOGIN_STARTED,
            ActionType.SCHEDULE_UPDATE: EventType.SCHEDULE_UPDATE_STARTED,
            ActionType.WAIT_RECEPTION: EventType.WAIT_RECEPTION_STARTED,
        }
        return mapping.get(action_type, EventType.SYSTEM_STARTED)
    
    def _get_success_event_type(self, action_type: ActionType) -> EventType:
        """操作種別から成功イベントタイプを取得"""
        mapping = {
            ActionType.LOGIN: EventType.LOGIN_SUCCESS,
            ActionType.SCHEDULE_UPDATE: EventType.SCHEDULE_UPDATE_COMPLETED,
            ActionType.WAIT_RECEPTION: EventType.WAIT_RECEPTION_COMPLETED,
        }
        return mapping.get(action_type, EventType.SYSTEM_STARTED)
    
    def _get_fail_event_type(self, action_type: ActionType) -> EventType:
        """操作種別から失敗イベントタイプを取得"""
        mapping = {
            ActionType.LOGIN: EventType.LOGIN_FAILED,
            ActionType.SCHEDULE_UPDATE: EventType.SCHEDULE_UPDATE_FAILED,
            ActionType.WAIT_RECEPTION: EventType.WAIT_RECEPTION_FAILED,
        }
        return mapping.get(action_type, EventType.ERROR_OCCURRED)
    
    def batch_recover_all_accounts(
        self,
        strategy=None,
        filter_status: Optional[AccountStatus] = AccountStatus.ERROR,
        max_workers: int = 10
    ) -> Dict[str, Any]:
        """
        全アカウント（最大200）を一括復旧
        
        Args:
            strategy: 復旧戦略
            filter_status: 復旧対象のステータス（Noneの場合は全アカウント）
            max_workers: 最大並列処理数
        
        Returns:
            Dict[str, Any]: 復旧結果サマリー
        """
        # Lazy import to avoid circular dependency
        from src.core.recovery_manager import RecoveryStrategy
        
        if strategy is None:
            strategy = RecoveryStrategy.LAST_SUCCESS_RECOVERY
        
        logger.info(
            f"Starting batch recovery for all accounts "
            f"(strategy: {strategy.value}, filter: {filter_status}, workers: {max_workers})"
        )
        
        start_time = time.time()
        
        # イベントログ
        event_logger.log_event(
            event_type=EventType.SYSTEM_STARTED,
            severity=EventSeverity.INFO,
            message=f"Batch recovery started (strategy: {strategy.value})",
            data={
                'filter_status': filter_status.value if filter_status else 'ALL',
                'max_workers': max_workers
            }
        )
        
        # 復旧実行
        summary = self.recovery_manager.recover_all_accounts(
            strategy=strategy,
            filter_status=filter_status
        )
        
        execution_time = time.time() - start_time
        summary['execution_time'] = execution_time
        summary['strategy'] = strategy.value
        
        # イベントログ
        event_logger.log_event(
            event_type=EventType.SYSTEM_STOPPED,
            severity=EventSeverity.INFO if summary['success'] > 0 else EventSeverity.WARNING,
            message=f"Batch recovery completed: {summary['success']}/{summary['total']} succeeded",
            data=summary
        )
        
        logger.info(
            f"Batch recovery completed in {execution_time:.2f}s: "
            f"{summary['success']}/{summary['total']} succeeded"
        )
        
        return summary
    
    def recover_account_state(
        self,
        account_id: str,
        recovery_point: Optional[datetime] = None,
        restore: bool = True
    ) -> Dict[str, Any]:
        """
        アカウントの状態をログから復旧
        
        Args:
            account_id: アカウントID
            recovery_point: 復旧時点（Noneの場合は最新状態）
            restore: 復旧後にデータベースに反映するか
        
        Returns:
            Dict[str, Any]: 復旧結果
        """
        logger.info(f"Recovering account state for {account_id}")
        
        result = {
            'account_id': account_id,
            'success': False,
            'recovered_state': None,
            'restored': False,
            'errors': []
        }
        
        try:
            # 状態を復旧
            state = self.account_state_recovery.recover_account_state(
                account_id=account_id,
                recovery_point=recovery_point
            )
            
            if not state:
                result['errors'].append("Failed to recover account state from logs")
                return result
            
            result['recovered_state'] = {
                'account_id': state.account_id,
                'username': state.username,
                'status': state.status.value,
                'last_login_at': state.last_login_at.isoformat() if state.last_login_at else None,
                'last_success_at': state.last_success_at.isoformat() if state.last_success_at else None,
                'error_count': state.error_count,
                'has_session_token': bool(state.session_token),
                'has_login_url': bool(state.login_url)
            }
            
            # データベースに反映
            if restore:
                restored = self.account_state_recovery.restore_account_from_state(
                    state=state,
                    force=False
                )
                result['restored'] = restored
                if not restored:
                    result['errors'].append("Failed to restore account state to database")
            
            result['success'] = True
            
            # イベントログ
            event_logger.log_event(
                event_type=EventType.ERROR_RECOVERED,
                severity=EventSeverity.INFO,
                account_id=account_id,
                message="Account state recovered from logs",
                data=result['recovered_state']
            )
            
        except Exception as e:
            logger.error(f"Failed to recover account state: {e}", exc_info=True)
            result['errors'].append(str(e))
        
        return result
    
    def batch_recover_account_states(
        self,
        account_ids: List[str],
        recovery_point: Optional[datetime] = None,
        restore: bool = True
    ) -> Dict[str, Any]:
        """
        複数アカウントの状態を一括復旧
        
        Args:
            account_ids: アカウントIDリスト
            recovery_point: 復旧時点
            restore: 復旧後にデータベースに反映するか
        
        Returns:
            Dict[str, Any]: 一括復旧結果
        """
        logger.info(f"Starting batch state recovery for {len(account_ids)} accounts")
        
        start_time = time.time()
        
        summary = {
            'total': len(account_ids),
            'success': 0,
            'failed': 0,
            'restored': 0,
            'results': []
        }
        
        for account_id in account_ids:
            result = self.recover_account_state(
                account_id=account_id,
                recovery_point=recovery_point,
                restore=restore
            )
            
            summary['results'].append(result)
            
            if result['success']:
                summary['success'] += 1
                if result.get('restored'):
                    summary['restored'] += 1
            else:
                summary['failed'] += 1
        
        execution_time = time.time() - start_time
        summary['execution_time'] = execution_time
        
        logger.info(
            f"Batch state recovery completed in {execution_time:.2f}s: "
            f"{summary['success']}/{summary['total']} succeeded, "
            f"{summary['restored']} restored"
        )
        
        return summary
    
    def get_account_log_summary(
        self,
        account_id: str,
        days: int = 7
    ) -> Dict[str, Any]:
        """
        アカウントのログサマリーを取得
        
        Args:
            account_id: アカウントID
            days: 取得期間（日数）
        
        Returns:
            Dict[str, Any]: ログサマリー
        """
        try:
            from src.database.connection import get_session
            with get_session() as session:
                log_repo = AccountLogRepository(session)
                
                end_date = datetime.utcnow()
                start_date = end_date - timedelta(days=days)
                
                logs = log_repo.get_logs_by_date_range(
                    start_date=start_date,
                    end_date=end_date,
                    account_id=account_id
                )
                
                # 統計情報
                total_logs = len(logs)
                success_count = sum(1 for log in logs if log.status == LogStatus.SUCCESS.value)
                failure_count = sum(1 for log in logs if log.status == LogStatus.FAILURE.value)
                
                # 操作種別別カウント
                action_counts = {}
                for action_type in ActionType:
                    count = sum(1 for log in logs if log.action_type == action_type.value)
                    if count > 0:
                        action_counts[action_type.value] = count
                
                # 最新のログイン成功
                last_success_login = None
                for log in logs:
                    if (log.action_type == ActionType.LOGIN.value and 
                        log.status == LogStatus.SUCCESS.value):
                        last_success_login = {
                            'created_at': log.created_at.isoformat(),
                            'execution_time': log.execution_time,
                            'message': log.message
                        }
                        break
                
                return {
                    'account_id': account_id,
                    'period': {
                        'start': start_date.isoformat(),
                        'end': end_date.isoformat(),
                        'days': days
                    },
                    'statistics': {
                        'total_logs': total_logs,
                        'success_count': success_count,
                        'failure_count': failure_count,
                        'success_rate': success_count / total_logs if total_logs > 0 else 0,
                        'action_counts': action_counts
                    },
                    'last_success_login': last_success_login
                }
                
        except Exception as e:
            logger.error(f"Failed to get account log summary: {e}", exc_info=True)
            return {
                'account_id': account_id,
                'error': str(e)
            }
    
    def get_system_statistics(
        self,
        days: int = 7
    ) -> Dict[str, Any]:
        """
        システム全体のログ統計を取得
        
        Args:
            days: 取得期間（日数）
        
        Returns:
            Dict[str, Any]: システム統計
        """
        try:
            from src.database.connection import get_session
            with get_session() as session:
                log_repo = AccountLogRepository(session)
                account_repo = AccountRepository(session)
                
                end_date = datetime.utcnow()
                start_date = end_date - timedelta(days=days)
                
                # 全ログ取得
                logs = log_repo.get_logs_by_date_range(
                    start_date=start_date,
                    end_date=end_date
                )
                
                # 全アカウント数
                total_accounts = account_repo.count()
                active_accounts_list = account_repo.get_active_accounts()
                active_accounts = len(active_accounts_list)
                
                # 統計情報
                total_logs = len(logs)
                success_count = sum(1 for log in logs if log.status == LogStatus.SUCCESS.value)
                failure_count = sum(1 for log in logs if log.status == LogStatus.FAILURE.value)
                
                # アカウント別統計
                account_stats = {}
                for log in logs:
                    account_id = str(log.account_id)
                    if account_id not in account_stats:
                        account_stats[account_id] = {
                            'total': 0,
                            'success': 0,
                            'failure': 0
                        }
                    account_stats[account_id]['total'] += 1
                    if log.status == LogStatus.SUCCESS.value:
                        account_stats[account_id]['success'] += 1
                    elif log.status == LogStatus.FAILURE.value:
                        account_stats[account_id]['failure'] += 1
                
                # エラー率が高いアカウント
                high_error_accounts = []
                for account_id, stats in account_stats.items():
                    if stats['total'] >= 5:
                        error_rate = stats['failure'] / stats['total']
                        if error_rate >= 0.5:
                            high_error_accounts.append({
                                'account_id': account_id,
                                'error_rate': error_rate,
                                'total_logs': stats['total'],
                                'failure_count': stats['failure']
                            })
                
                return {
                    'period': {
                        'start': start_date.isoformat(),
                        'end': end_date.isoformat(),
                        'days': days
                    },
                    'accounts': {
                        'total': total_accounts,
                        'active': active_accounts,
                        'inactive': total_accounts - active_accounts
                    },
                    'statistics': {
                        'total_logs': total_logs,
                        'success_count': success_count,
                        'failure_count': failure_count,
                        'success_rate': success_count / total_logs if total_logs > 0 else 0,
                        'accounts_with_logs': len(account_stats)
                    },
                    'high_error_accounts': high_error_accounts[:10]  # Top 10
                }
                
        except Exception as e:
            logger.error(f"Failed to get system statistics: {e}", exc_info=True)
            return {'error': str(e)}


class LogContext:
    """ログコンテキスト（操作ログ記録用）"""
    
    def __init__(
        self,
        account_id: Optional[str],
        action_type: ActionType,
        request_id: str,
        start_time: float
    ):
        self.account_id = account_id
        self.action_type = action_type
        self.request_id = request_id
        self.start_time = start_time
        self.completed = False
    
    def log_success(
        self,
        message: str = "",
        execution_time: Optional[float] = None,
        **extra_data
    ):
        """成功ログを記録"""
        if execution_time is None:
            execution_time = time.time() - self.start_time
        
        # コード位置を取得
        code_location = _get_code_location()
        
        try:
            from src.database.connection import get_session
            with get_session() as session:
                log_repo = AccountLogRepository(session)
                
                log_repo.create_log(
                    account_id=self.account_id,
                    action_type=self.action_type,
                    status=LogStatus.SUCCESS,
                    message=message,
                    execution_time=execution_time,
                    request_id=self.request_id,
                    error_detail=extra_data if extra_data else None,
                    file_path=code_location.get('file_path'),
                    function_name=code_location.get('function_name'),
                    line_number=code_location.get('line_number')
                )
            
            self.completed = True
            
        except Exception as e:
            logger.error(f"Failed to log success: {e}", exc_info=True)
    
    def log_error(
        self,
        message: str,
        error_detail: Optional[Dict[str, Any]] = None,
        execution_time: Optional[float] = None
    ):
        """エラーログを記録"""
        if execution_time is None:
            execution_time = time.time() - self.start_time
        
        # コード位置を取得
        code_location = _get_code_location()
        
        try:
            from src.database.connection import get_session
            with get_session() as session:
                log_repo = AccountLogRepository(session)
                
                log_repo.create_log(
                    account_id=self.account_id,
                    action_type=self.action_type,
                    status=LogStatus.FAILURE,
                    message=message,
                    error_detail=error_detail,
                    execution_time=execution_time,
                    request_id=self.request_id,
                    file_path=code_location.get('file_path'),
                    function_name=code_location.get('function_name'),
                    line_number=code_location.get('line_number')
                )
            
            self.completed = True
            
        except Exception as e:
            logger.error(f"Failed to log error: {e}", exc_info=True)
    
    def log_skipped(
        self,
        message: str = "",
        execution_time: Optional[float] = None
    ):
        """スキップログを記録"""
        if execution_time is None:
            execution_time = time.time() - self.start_time
        
        # コード位置を取得
        code_location = _get_code_location()
        
        try:
            from src.database.connection import get_session
            with get_session() as session:
                log_repo = AccountLogRepository(session)
                
                log_repo.create_log(
                    account_id=self.account_id,
                    action_type=self.action_type,
                    status=LogStatus.SKIPPED,
                    message=message,
                    execution_time=execution_time,
                    request_id=self.request_id,
                    file_path=code_location.get('file_path'),
                    function_name=code_location.get('function_name'),
                    line_number=code_location.get('line_number')
                )
            
            self.completed = True
            
        except Exception as e:
            logger.error(f"Failed to log skipped: {e}", exc_info=True)


# グローバルログマネージャー
log_manager = LogManager()


"""
Recovery Manager Module

ログベースの復旧システム
200アカウントの状態をログから復旧
"""
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from enum import Enum

from src.core.logger import logger
from src.core.event_system import EventType, EventSeverity, event_logger, SystemEvent
from src.database.connection import get_session
from src.database.repositories.account import AccountRepository
from src.database.repositories.log import AccountLogRepository
from src.database.models import Account, AccountStatus, ActionType, LogStatus


class RecoveryStrategy(str, Enum):
    """復旧戦略"""
    FULL_RECOVERY = 'FULL_RECOVERY'  # 完全復旧
    PARTIAL_RECOVERY = 'PARTIAL_RECOVERY'  # 部分復旧
    STATUS_RECOVERY = 'STATUS_RECOVERY'  # ステータスのみ復旧
    LAST_SUCCESS_RECOVERY = 'LAST_SUCCESS_RECOVERY'  # 最後の成功状態に復旧


class RecoveryManager:
    """
    復旧マネージャー
    
    ログからアカウントの状態を復旧する
    """
    
    def __init__(self):
        self.recovery_history: List[Dict[str, Any]] = []
    
    def recover_account_from_logs(
        self,
        account_id: str,
        strategy: RecoveryStrategy = RecoveryStrategy.LAST_SUCCESS_RECOVERY
    ) -> Dict[str, Any]:
        """
        ログからアカウントの状態を復旧
        
        Args:
            account_id: アカウントID
            strategy: 復旧戦略
        
        Returns:
            Dict[str, Any]: 復旧結果
        """
        logger.info(f"Starting recovery for account {account_id} using strategy: {strategy.value}")
        
        recovery_result = {
            'account_id': account_id,
            'strategy': strategy.value,
            'success': False,
            'recovered_fields': [],
            'errors': [],
            'timestamp': datetime.utcnow().isoformat()
        }
        
        try:
            with get_session() as session:
                account_repo = AccountRepository(session)
                log_repo = AccountLogRepository(session)
                
                # アカウント取得
                account = account_repo.get_by_id(account_id)
                if not account:
                    recovery_result['errors'].append("Account not found")
                    return recovery_result
                
                # ログから復旧情報を取得
                if strategy == RecoveryStrategy.LAST_SUCCESS_RECOVERY:
                    result = self._recover_from_last_success(
                        account, account_repo, log_repo
                    )
                elif strategy == RecoveryStrategy.STATUS_RECOVERY:
                    result = self._recover_status(
                        account, account_repo, log_repo
                    )
                elif strategy == RecoveryStrategy.FULL_RECOVERY:
                    result = self._full_recovery(
                        account, account_repo, log_repo
                    )
                else:
                    result = self._partial_recovery(
                        account, account_repo, log_repo
                    )
                
                recovery_result.update(result)
                recovery_result['success'] = len(recovery_result['errors']) == 0
                
                # 復旧履歴に記録
                self.recovery_history.append(recovery_result)
                
                # イベントログ
                event_logger.log_event(
                    event_type=EventType.ERROR_RECOVERED,
                    severity=EventSeverity.INFO if recovery_result['success'] else EventSeverity.WARNING,
                    account_id=account_id,
                    message=f"Account recovered using {strategy.value}",
                    data=recovery_result
                )
                
                logger.info(f"Recovery completed for account {account_id}: {recovery_result['success']}")
                
        except Exception as e:
            logger.error(f"Recovery failed for account {account_id}: {e}", exc_info=True)
            recovery_result['errors'].append(str(e))
            recovery_result['success'] = False
        
        return recovery_result
    
    def _recover_from_last_success(
        self,
        account: Account,
        account_repo: AccountRepository,
        log_repo: AccountLogRepository
    ) -> Dict[str, Any]:
        """
        最後の成功状態から復旧
        
        最後の成功したログインまたは操作の状態に復旧
        """
        result = {
            'recovered_fields': [],
            'errors': []
        }
        
        try:
            # 最後の成功ログを取得
            success_logs = log_repo.get_account_logs(
                account_id=account.id,
                limit=100
            )
            
            # 成功したログインを探す
            last_success_login = None
            for log in success_logs:
                if (log.action_type == ActionType.LOGIN.value and 
                    log.status == LogStatus.SUCCESS.value):
                    last_success_login = log
                    break
            
            if last_success_login:
                # ログイン情報を復旧
                if last_success_login.error_detail:
                    login_url = last_success_login.error_detail.get('login_url')
                    if login_url:
                        account_repo.update(
                            account.id,
                            login_url=login_url,
                            status=AccountStatus.IDLE.value
                        )
                        result['recovered_fields'].append('login_url')
                        result['recovered_fields'].append('status')
                    
                    session_token = last_success_login.error_detail.get('session_token')
                    if session_token:
                        account_repo.update(account.id, session_token=session_token)
                        result['recovered_fields'].append('session_token')
                
                # 最終成功時刻を更新
                account_repo.update_last_success(account.id)
                result['recovered_fields'].append('last_success_at')
                
                logger.info(f"Recovered account {account.username} from last success login")
            
            # エラーカウントをリセット
            account_repo.reset_error_count(account.id)
            result['recovered_fields'].append('error_count')
            
        except Exception as e:
            result['errors'].append(f"Error in last success recovery: {e}")
        
        return result
    
    def _recover_status(
        self,
        account: Account,
        account_repo: AccountRepository,
        log_repo: AccountLogRepository
    ) -> Dict[str, Any]:
        """
        ステータスのみ復旧
        
        最新のログから適切なステータスを推測
        """
        result = {
            'recovered_fields': [],
            'errors': []
        }
        
        try:
            # 最新のログを取得
            recent_logs = log_repo.get_account_logs(account_id=account.id, limit=10)
            
            if recent_logs:
                latest_log = recent_logs[0]
                
                # ログからステータスを推測
                if latest_log.status == LogStatus.SUCCESS.value:
                    new_status = AccountStatus.IDLE.value
                elif latest_log.status == LogStatus.FAILURE.value:
                    # 連続エラーをチェック
                    error_count = sum(
                        1 for log in recent_logs[:5]
                        if log.status == LogStatus.FAILURE.value
                    )
                    
                    if error_count >= 5:
                        new_status = AccountStatus.DISABLED.value
                    else:
                        new_status = AccountStatus.ERROR.value
                else:
                    new_status = AccountStatus.IDLE.value
                
                account_repo.update_status(account.id, AccountStatus(new_status))
                result['recovered_fields'].append('status')
                
                logger.info(f"Recovered status for account {account.username}: {new_status}")
        
        except Exception as e:
            result['errors'].append(f"Error in status recovery: {e}")
        
        return result
    
    def _full_recovery(
        self,
        account: Account,
        account_repo: AccountRepository,
        log_repo: AccountLogRepository
    ) -> Dict[str, Any]:
        """
        完全復旧
        
        全ての復旧可能な情報を復旧
        """
        result = {
            'recovered_fields': [],
            'errors': []
        }
        
        # 最後の成功状態から復旧
        last_success_result = self._recover_from_last_success(account, account_repo, log_repo)
        result['recovered_fields'].extend(last_success_result['recovered_fields'])
        result['errors'].extend(last_success_result['errors'])
        
        # ステータス復旧
        status_result = self._recover_status(account, account_repo, log_repo)
        result['recovered_fields'].extend(status_result['recovered_fields'])
        result['errors'].extend(status_result['errors'])
        
        return result
    
    def _partial_recovery(
        self,
        account: Account,
        account_repo: AccountRepository,
        log_repo: AccountLogRepository
    ) -> Dict[str, Any]:
        """
        部分復旧
        
        重要なフィールドのみ復旧
        """
        result = {
            'recovered_fields': [],
            'errors': []
        }
        
        # ステータスのみ復旧
        status_result = self._recover_status(account, account_repo, log_repo)
        result['recovered_fields'].extend(status_result['recovered_fields'])
        result['errors'].extend(status_result['errors'])
        
        return result
    
    def recover_all_accounts(
        self,
        strategy: RecoveryStrategy = RecoveryStrategy.LAST_SUCCESS_RECOVERY,
        filter_status: Optional[AccountStatus] = AccountStatus.ERROR
    ) -> Dict[str, Any]:
        """
        全アカウントの復旧
        
        Args:
            strategy: 復旧戦略
            filter_status: 復旧対象のステータス（Noneの場合は全アカウント）
        
        Returns:
            Dict[str, Any]: 復旧結果サマリー
        """
        logger.info(f"Starting bulk recovery for all accounts (strategy: {strategy.value})")
        
        summary = {
            'total': 0,
            'success': 0,
            'failed': 0,
            'recovered_accounts': [],
            'failed_accounts': [],
            'timestamp': datetime.utcnow().isoformat()
        }
        
        try:
            with get_session() as session:
                account_repo = AccountRepository(session)
                
                # アカウント取得
                if filter_status:
                    # 特定ステータスのアカウントのみ
                    accounts = session.query(Account).filter_by(
                        status=filter_status.value,
                        is_active=True
                    ).all()
                else:
                    # 全アカウント
                    accounts = account_repo.get_active_accounts()
                
                summary['total'] = len(accounts)
                
                # 各アカウントを復旧
                for account in accounts:
                    result = self.recover_account_from_logs(
                        account_id=str(account.id),
                        strategy=strategy
                    )
                    
                    if result['success']:
                        summary['success'] += 1
                        summary['recovered_accounts'].append({
                            'account_id': str(account.id),
                            'username': account.username,
                            'recovered_fields': result['recovered_fields']
                        })
                    else:
                        summary['failed'] += 1
                        summary['failed_accounts'].append({
                            'account_id': str(account.id),
                            'username': account.username,
                            'errors': result['errors']
                        })
                
                logger.info(
                    f"Bulk recovery completed: {summary['success']}/{summary['total']} succeeded"
                )
                
        except Exception as e:
            logger.error(f"Bulk recovery failed: {e}", exc_info=True)
            summary['errors'] = [str(e)]
        
        return summary
    
    def get_recovery_history(
        self,
        account_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        復旧履歴を取得
        
        Args:
            account_id: アカウントID（フィルタ）
            limit: 取得件数制限
        
        Returns:
            List[Dict[str, Any]]: 復旧履歴
        """
        history = self.recovery_history.copy()
        
        if account_id:
            history = [h for h in history if h['account_id'] == account_id]
        
        # 新しい順にソート
        history.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return history[:limit]


# グローバル復旧マネージャー
recovery_manager = RecoveryManager()


"""
Account State Recovery Module

アカウント状態の復旧システム
ログからアカウントの完全な状態を復旧
"""
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass

from src.core.logger import logger
from src.database.connection import get_session
from src.database.repositories.account import AccountRepository
from src.database.repositories.log import AccountLogRepository
from src.database.models import Account, AccountStatus, ActionType, LogStatus
from src.core.event_system import event_logger, EventType, EventSeverity


@dataclass
class AccountState:
    """
    アカウントの状態スナップショット
    
    復旧に必要な全ての情報を含む
    """
    account_id: str
    username: str
    status: AccountStatus
    last_login_at: Optional[datetime] = None
    last_success_at: Optional[datetime] = None
    session_token: Optional[str] = None
    login_url: Optional[str] = None
    error_count: int = 0
    last_error: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class AccountStateRecovery:
    """
    アカウント状態復旧クラス
    
    ログからアカウントの完全な状態を復旧する
    """
    
    def recover_account_state(
        self,
        account_id: str,
        recovery_point: Optional[datetime] = None
    ) -> Optional[AccountState]:
        """
        ログからアカウントの状態を復旧
        
        Args:
            account_id: アカウントID
            recovery_point: 復旧時点（Noneの場合は最新状態）
        
        Returns:
            Optional[AccountState]: 復旧された状態
        """
        logger.info(f"Recovering account state for {account_id}")
        
        try:
            with get_session() as session:
                account_repo = AccountRepository(session)
                log_repo = AccountLogRepository(session)
                
                # アカウント取得
                account = account_repo.get_by_id(account_id)
                if not account:
                    logger.error(f"Account not found: {account_id}")
                    return None
                
                # ログから状態を構築
                state = AccountState(
                    account_id=str(account.id),
                    username=account.username,
                    status=AccountStatus(account.status),
                    error_count=account.error_count,
                    last_error=account.last_error
                )
                
                # ログを取得
                if recovery_point:
                    logs = log_repo.get_logs_by_date_range(
                        start_date=recovery_point - timedelta(days=30),
                        end_date=recovery_point,
                        account_id=account_id
                    )
                else:
                    logs = log_repo.get_account_logs(account_id=account_id, limit=200)
                
                # ログを時系列で処理（古い順）
                logs.sort(key=lambda x: x.created_at)
                
                # 各ログから状態を復元
                for log in logs:
                    if recovery_point and log.created_at > recovery_point:
                        break
                    
                    self._apply_log_to_state(state, log)
                
                logger.info(f"Account state recovered for {account.username}")
                return state
                
        except Exception as e:
            logger.error(f"Failed to recover account state: {e}", exc_info=True)
            return None
    
    def _apply_log_to_state(self, state: AccountState, log):
        """ログを状態に適用"""
        # ログイン成功
        if (log.action_type == ActionType.LOGIN.value and 
            log.status == LogStatus.SUCCESS.value):
            
            state.last_login_at = log.created_at
            state.last_success_at = log.created_at
            
            if log.error_detail:
                state.session_token = log.error_detail.get('session_token')
                state.login_url = log.error_detail.get('login_url')
                if state.login_url:
                    state.metadata['last_successful_login_url'] = state.login_url
        
        # ログイン失敗
        elif (log.action_type == ActionType.LOGIN.value and 
              log.status == LogStatus.FAILURE.value):
            
            state.error_count += 1
            state.last_error = log.message
            
            if state.error_count >= 5:
                state.status = AccountStatus.DISABLED
        
        # スケジュール更新成功
        elif (log.action_type == ActionType.SCHEDULE_UPDATE.value and 
              log.status == LogStatus.SUCCESS.value):
            
            state.last_success_at = log.created_at
            if state.status == AccountStatus.ERROR:
                state.status = AccountStatus.IDLE
                state.error_count = 0
        
        # エラー
        elif log.status == LogStatus.FAILURE.value:
            state.error_count += 1
            state.last_error = log.message
    
    def restore_account_from_state(
        self,
        state: AccountState,
        force: bool = False
    ) -> bool:
        """
        復旧した状態をアカウントに適用
        
        Args:
            state: 復旧された状態
            force: 強制的に適用（既存データを上書き）
        
        Returns:
            bool: 復旧成功時True
        """
        logger.info(f"Restoring account {state.username} from recovered state")
        
        try:
            with get_session() as session:
                account_repo = AccountRepository(session)
                
                update_data = {}
                
                if force or state.last_success_at:
                    if state.last_success_at:
                        update_data['last_success_at'] = state.last_success_at
                
                if force or state.last_login_at:
                    if state.last_login_at:
                        update_data['last_login_at'] = state.last_login_at
                
                if force or state.session_token:
                    if state.session_token:
                        update_data['session_token'] = state.session_token
                
                if force or state.login_url:
                    if state.login_url:
                        update_data['login_url'] = state.login_url
                
                if force or state.status:
                    update_data['status'] = state.status.value
                
                if update_data:
                    account_repo.update(state.account_id, **update_data)
                    
                    # エラーカウントのリセット
                    if state.error_count == 0:
                        account_repo.reset_error_count(state.account_id)
                    
                    logger.info(f"Account {state.username} restored successfully")
                    
                    # イベントログ
                    event_logger.log_event(
                        event_type=EventType.ACCOUNT_UPDATED,
                        severity=EventSeverity.INFO,
                        account_id=state.account_id,
                        message=f"Account restored from recovered state",
                        data={'recovered_fields': list(update_data.keys())}
                    )
                    
                    return True
                else:
                    logger.warning(f"No data to restore for account {state.username}")
                    return False
                    
        except Exception as e:
            logger.error(f"Failed to restore account from state: {e}", exc_info=True)
            return False
    
    def recover_and_restore_account(
        self,
        account_id: str,
        recovery_point: Optional[datetime] = None,
        force: bool = False
    ) -> Dict[str, Any]:
        """
        アカウントの状態を復旧して適用
        
        Args:
            account_id: アカウントID
            recovery_point: 復旧時点
            force: 強制適用
        
        Returns:
            Dict[str, Any]: 復旧結果
        """
        result = {
            'account_id': account_id,
            'success': False,
            'recovered_fields': [],
            'errors': []
        }
        
        try:
            # 状態を復旧
            state = self.recover_account_state(account_id, recovery_point)
            
            if not state:
                result['errors'].append("Failed to recover account state")
                return result
            
            # 状態を適用
            if self.restore_account_from_state(state, force):
                result['success'] = True
                result['recovered_fields'] = [
                    'last_success_at',
                    'last_login_at',
                    'session_token',
                    'login_url',
                    'status'
                ]
            else:
                result['errors'].append("Failed to restore account state")
        
        except Exception as e:
            logger.error(f"Recover and restore failed: {e}", exc_info=True)
            result['errors'].append(str(e))
        
        return result
    
    def batch_recover_accounts(
        self,
        account_ids: List[str],
        recovery_point: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        複数アカウントを一括復旧
        
        Args:
            account_ids: アカウントIDリスト
            recovery_point: 復旧時点
        
        Returns:
            Dict[str, Any]: 一括復旧結果
        """
        logger.info(f"Starting batch recovery for {len(account_ids)} accounts")
        
        summary = {
            'total': len(account_ids),
            'success': 0,
            'failed': 0,
            'results': []
        }
        
        for account_id in account_ids:
            result = self.recover_and_restore_account(account_id, recovery_point)
            summary['results'].append(result)
            
            if result['success']:
                summary['success'] += 1
            else:
                summary['failed'] += 1
        
        logger.info(
            f"Batch recovery completed: {summary['success']}/{summary['total']} succeeded"
        )
        
        return summary


# グローバルインスタンス
account_state_recovery = AccountStateRecovery()


"""
Account Repository

アカウント専用のリポジトリ
"""
from typing import Optional, List
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_
from src.database.models import Account, AccountStatus
from src.database.repositories.base import BaseRepository
from src.database.encryption import encrypt_password, decrypt_password
from src.core.logger import logger


class AccountRepository(BaseRepository[Account]):
    """
    アカウントリポジトリ
    
    アカウント専用の高レベル操作を提供
    """
    
    def __init__(self, session: Session):
        """初期化"""
        super().__init__(session, Account)
    
    def get_by_username(self, username: str) -> Optional[Account]:
        """
        ユーザー名でアカウントを取得
        
        Args:
            username: ユーザー名
        
        Returns:
            Optional[Account]: アカウント（存在しない場合はNone）
        """
        try:
            return self.session.query(Account).filter_by(username=username).first()
        except Exception as e:
            logger.error(f"Error getting account by username {username}: {e}")
            raise
    
    def get_idle_accounts(self, limit: Optional[int] = None) -> List[Account]:
        """
        処理可能なIDLEアカウントを取得
        
        条件:
        - is_active = True
        - status = 'IDLE'
        
        Args:
            limit: 取得件数制限
        
        Returns:
            List[Account]: IDLEアカウントリスト
        """
        query = self.session.query(Account).filter(
            and_(
                Account.status == AccountStatus.IDLE,
                Account.is_active == True
            )
        )
        
        if limit:
            query = query.limit(limit)
        
        return query.all()
    
    def get_active_accounts(self, limit: Optional[int] = None) -> List[Account]:
        """
        有効なアカウントを取得
        
        Args:
            limit: 取得件数制限
        
        Returns:
            List[Account]: 有効アカウントリスト
        """
        query = self.session.query(Account).filter_by(is_active=True)
        
        if limit:
            query = query.limit(limit)
        
        return query.all()
    
    def create_account(
        self,
        username: str,
        password: str,
        store_name: str,
        login_url: Optional[str] = None,
        is_active: bool = True
    ) -> Account:
        """
        アカウントを作成（パスワード自動暗号化）
        
        Args:
            username: ユーザー名
            password: 平文パスワード
            store_name: 店舗名
            login_url: ログインURL
            is_active: 有効フラグ
        
        Returns:
            Account: 作成されたアカウント
        """
        encrypted_password = encrypt_password(password)
        
        return self.create(
            username=username,
            password_encrypted=encrypted_password,
            store_name=store_name,
            login_url=login_url,
            is_active=is_active,
            status=AccountStatus.IDLE
        )
    
    def update_login_info(
        self,
        account_id: str,
        session_token: str,
        login_url: Optional[str] = None
    ) -> bool:
        """
        ログイン成功時の情報更新
        
        自動的に:
        - ステータスをIDLEに
        - エラーカウントをリセット
        - 最終ログイン時刻を記録
        
        Args:
            account_id: アカウントID
            session_token: セッショントークン
            login_url: ログインURL
        
        Returns:
            bool: 更新成功時True
        """
        update_data = {
            'session_token': session_token,
            'last_login_at': datetime.utcnow(),
            'status': AccountStatus.IDLE,
            'error_count': 0,
            'last_error': None,
            'updated_at': datetime.utcnow()
        }
        
        if login_url:
            update_data['login_url'] = login_url
        
        account = self.update(account_id, **update_data)
        return account is not None
    
    def update_last_success(self, account_id: str) -> bool:
        """
        最終成功時刻を更新
        
        Args:
            account_id: アカウントID
        
        Returns:
            bool: 更新成功時True
        """
        account = self.update(
            account_id,
            last_success_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        return account is not None
    
    def increment_error_count(self, account_id: str, error_message: str = None) -> bool:
        """
        エラーカウントを増加
        
        Args:
            account_id: アカウントID
            error_message: エラーメッセージ
        
        Returns:
            bool: 更新成功時True
        """
        account = self.get_by_id(account_id)
        if account:
            account.increment_error_count(error_message)
            self.session.flush()
            return True
        return False
    
    def reset_error_count(self, account_id: str) -> bool:
        """
        エラーカウントをリセット
        
        Args:
            account_id: アカウントID
        
        Returns:
            bool: 更新成功時True
        """
        account = self.get_by_id(account_id)
        if account:
            account.reset_error_count()
            self.session.flush()
            return True
        return False
    
    def get_password(self, account_id: str) -> Optional[str]:
        """
        パスワードを取得（復号化）
        
        Args:
            account_id: アカウントID
        
        Returns:
            Optional[str]: 平文パスワード（存在しない場合はNone）
        """
        account = self.get_by_id(account_id)
        if account:
            try:
                return decrypt_password(account.password_encrypted)
            except Exception as e:
                logger.error(f"Failed to decrypt password for account {account_id}: {e}")
                return None
        return None
    
    def update_status(self, account_id: str, status: AccountStatus) -> bool:
        """
        ステータスを更新
        
        Args:
            account_id: アカウントID
            status: 新しいステータス
        
        Returns:
            bool: 更新成功時True
        """
        account = self.update(account_id, status=status.value)
        return account is not None
    
    def acquire_lock(self, account_id: str, task_type: str = "schedule_update") -> bool:
        """
        アカウントの自動化ロックを取得
        
        Args:
            account_id: アカウントID
            task_type: タスク種別
        
        Returns:
            bool: ロック取得成功時True（既にロックされている場合はFalse）
        """
        account = self.get_by_id(account_id)
        if not account:
            return False
        
        # 既にPROCESSING状態の場合はロック済み
        if account.status == AccountStatus.PROCESSING:
            # ロック情報を確認
            if account.metadata_json and isinstance(account.metadata_json, dict):
                lock_info = account.metadata_json.get('automation_lock')
                if lock_info and lock_info.get('locked'):
                    logger.warning(f"[{account_id}] Account is already locked by {lock_info.get('task_type')}")
                    return False
        
        # ロックを設定
        lock_metadata = account.metadata_json or {}
        if not isinstance(lock_metadata, dict):
            lock_metadata = {}
        
        lock_metadata['automation_lock'] = {
            'locked': True,
            'task_type': task_type,
            'locked_at': datetime.utcnow().isoformat()
        }
        
        self.update(account_id, 
                   status=AccountStatus.PROCESSING,
                   metadata_json=lock_metadata)
        logger.debug(f"[{account_id}] Automation lock acquired for {task_type}")
        return True
    
    def release_lock(self, account_id: str) -> bool:
        """
        アカウントの自動化ロックを解放
        
        Args:
            account_id: アカウントID
        
        Returns:
            bool: ロック解放成功時True
        """
        account = self.get_by_id(account_id)
        if not account:
            return False
        
        # ロック情報をクリア
        lock_metadata = account.metadata_json or {}
        if isinstance(lock_metadata, dict):
            lock_metadata.pop('automation_lock', None)
        
        # ステータスをIDLEに戻す（エラー時は既に更新済みの可能性がある）
        if account.status == AccountStatus.PROCESSING:
            self.update(account_id,
                       status=AccountStatus.IDLE,
                       metadata_json=lock_metadata)
        
        logger.debug(f"[{account_id}] Automation lock released")
        return True
    
    def is_locked(self, account_id: str) -> bool:
        """
        アカウントがロックされているかチェック
        
        Args:
            account_id: アカウントID
        
        Returns:
            bool: ロックされている場合True
        """
        account = self.get_by_id(account_id)
        if not account:
            return False
        
        if account.status == AccountStatus.PROCESSING:
            if account.metadata_json and isinstance(account.metadata_json, dict):
                lock_info = account.metadata_json.get('automation_lock')
                if lock_info and lock_info.get('locked'):
                    return True
        
        return False
    
    def get_eligible_accounts_for_schedule_update(self) -> List[Account]:
        """
        スケジュール更新の対象アカウントを取得
        
        条件:
        - is_active = True
        - status = IDLE（ロックされていない）
        - 週間スケジュールに少なくとも1日の「出勤設定」がある
        
        Note: 週間スケジュールのチェックは実際のUI操作時に実施
        
        Returns:
            List[Account]: 対象アカウントリスト
        """
        # 基本的にはアクティブでIDLE状態のアカウントを取得
        # 週間スケジュールのチェックはexecute_schedule_update内で実施
        return self.get_idle_accounts()


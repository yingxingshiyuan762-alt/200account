"""
Account Log Repository

アカウントログ専用のリポジトリ
"""
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc
from src.database.models import AccountLog, ActionType, LogStatus
from src.database.repositories.base import BaseRepository
from src.core.logger import logger


class AccountLogRepository(BaseRepository[AccountLog]):
    """
    アカウントログリポジトリ
    """
    
    def __init__(self, session: Session):
        """初期化"""
        super().__init__(session, AccountLog)
    
    def create_log(
        self,
        account_id: str,
        action_type: ActionType,
        status: LogStatus,
        message: Optional[str] = None,
        error_detail: Optional[Dict[str, Any]] = None,
        execution_time: Optional[float] = None,
        request_id: Optional[str] = None,
        file_path: Optional[str] = None,
        function_name: Optional[str] = None,
        line_number: Optional[int] = None
    ) -> AccountLog:
        """
        ログを作成
        
        Args:
            account_id: アカウントID
            action_type: 操作種別
            status: ステータス
            message: メッセージ
            error_detail: エラー詳細
            execution_time: 実行時間（秒）
            request_id: リクエストID
            file_path: コードファイルパス（相対パス）
            function_name: 関数名
            line_number: 行番号
        
        Returns:
            AccountLog: 作成されたログ
        """
        return self.create(
            account_id=account_id,
            action_type=action_type.value,
            status=status.value,
            message=message,
            error_detail=error_detail,
            execution_time=execution_time,
            request_id=request_id,
            file_path=file_path,
            function_name=function_name,
            line_number=line_number
        )
    
    def get_account_logs(
        self,
        account_id: str,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[AccountLog]:
        """
        アカウントのログを取得
        
        Args:
            account_id: アカウントID
            limit: 取得件数制限
            offset: オフセット
        
        Returns:
            List[AccountLog]: ログリスト
        """
        query = self.session.query(AccountLog).filter_by(
            account_id=account_id
        ).order_by(desc(AccountLog.created_at))
        
        if limit:
            query = query.limit(limit).offset(offset)
        
        return query.all()
    
    def get_recent_logs(
        self,
        limit: int = 100,
        account_id: Optional[str] = None
    ) -> List[AccountLog]:
        """
        最近のログを取得
        
        Args:
            limit: 取得件数
            account_id: アカウントID（指定時はそのアカウントのみ）
        
        Returns:
            List[AccountLog]: ログリスト
        """
        query = self.session.query(AccountLog)
        
        if account_id:
            query = query.filter_by(account_id=account_id)
        
        return query.order_by(desc(AccountLog.created_at)).limit(limit).all()
    
    def get_logs_by_action_type(
        self,
        action_type: ActionType,
        limit: Optional[int] = None
    ) -> List[AccountLog]:
        """
        操作種別でログを取得
        
        Args:
            action_type: 操作種別
            limit: 取得件数制限
        
        Returns:
            List[AccountLog]: ログリスト
        """
        query = self.session.query(AccountLog).filter_by(
            action_type=action_type.value
        ).order_by(desc(AccountLog.created_at))
        
        if limit:
            query = query.limit(limit)
        
        return query.all()
    
    def get_error_logs(
        self,
        account_id: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[AccountLog]:
        """
        エラーログを取得
        
        Args:
            account_id: アカウントID（指定時はそのアカウントのみ）
            limit: 取得件数制限
        
        Returns:
            List[AccountLog]: エラーログリスト
        """
        query = self.session.query(AccountLog).filter_by(
            status=LogStatus.FAILURE.value
        )
        
        if account_id:
            query = query.filter_by(account_id=account_id)
        
        query = query.order_by(desc(AccountLog.created_at))
        
        if limit:
            query = query.limit(limit)
        
        return query.all()
    
    def get_logs_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        account_id: Optional[str] = None
    ) -> List[AccountLog]:
        """
        日付範囲でログを取得
        
        Args:
            start_date: 開始日時
            end_date: 終了日時
            account_id: アカウントID（指定時はそのアカウントのみ）
        
        Returns:
            List[AccountLog]: ログリスト
        """
        query = self.session.query(AccountLog).filter(
            and_(
                AccountLog.created_at >= start_date,
                AccountLog.created_at <= end_date
            )
        )
        
        if account_id:
            query = query.filter_by(account_id=account_id)
        
        return query.order_by(desc(AccountLog.created_at)).all()
    
    def get_statistics(
        self,
        account_id: Optional[str] = None,
        days: int = 7
    ) -> Dict[str, Any]:
        """
        ログ統計を取得
        
        Args:
            account_id: アカウントID（指定時はそのアカウントのみ）
            days: 統計期間（日数）
        
        Returns:
            Dict[str, Any]: 統計情報
        """
        start_date = datetime.utcnow() - timedelta(days=days)
        
        query = self.session.query(AccountLog).filter(
            AccountLog.created_at >= start_date
        )
        
        if account_id:
            query = query.filter_by(account_id=account_id)
        
        logs = query.all()
        
        total = len(logs)
        success = sum(1 for log in logs if log.status == LogStatus.SUCCESS.value)
        failure = sum(1 for log in logs if log.status == LogStatus.FAILURE.value)
        skipped = sum(1 for log in logs if log.status == LogStatus.SKIPPED.value)
        
        return {
            'total': total,
            'success': success,
            'failure': failure,
            'skipped': skipped,
            'success_rate': (success / total * 100) if total > 0 else 0,
            'period_days': days
        }


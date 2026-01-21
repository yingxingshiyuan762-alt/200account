"""
Session History Repository

セッション履歴専用のリポジトリ
"""
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc
from src.database.models import SessionHistory, DetectionType
from src.database.repositories.base import BaseRepository
from src.core.logger import logger


class SessionHistoryRepository(BaseRepository[SessionHistory]):
    """
    セッション履歴リポジトリ
    """
    
    def __init__(self, session: Session):
        """初期化"""
        super().__init__(session, SessionHistory)
    
    def create_history(
        self,
        account_id: str,
        detection_type: DetectionType,
        is_manual_operation: bool = False,
        conflict_detected: bool = False,
        action_taken: Optional[str] = None,
        session_token: Optional[str] = None,
        detection_data: Optional[Dict[str, Any]] = None
    ) -> SessionHistory:
        """
        セッション履歴を作成
        
        Args:
            account_id: アカウントID
            detection_type: 検知タイプ
            is_manual_operation: 手動操作フラグ
            conflict_detected: 競合検知フラグ
            action_taken: 実行アクション
            session_token: セッショントークン
            detection_data: 検知データ
        
        Returns:
            SessionHistory: 作成された履歴
        """
        return self.create(
            account_id=account_id,
            detection_type=detection_type.value,
            is_manual_operation=is_manual_operation,
            conflict_detected=conflict_detected,
            action_taken=action_taken,
            session_token=session_token,
            detection_data=detection_data
        )
    
    def get_account_histories(
        self,
        account_id: str,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[SessionHistory]:
        """
        アカウントのセッション履歴を取得
        
        Args:
            account_id: アカウントID
            limit: 取得件数制限
            offset: オフセット
        
        Returns:
            List[SessionHistory]: 履歴リスト
        """
        query = self.session.query(SessionHistory).filter_by(
            account_id=account_id
        ).order_by(desc(SessionHistory.created_at))
        
        if limit:
            query = query.limit(limit).offset(offset)
        
        return query.all()
    
    def get_conflict_histories(
        self,
        account_id: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[SessionHistory]:
        """
        競合検知履歴を取得
        
        Args:
            account_id: アカウントID（指定時はそのアカウントのみ）
            limit: 取得件数制限
        
        Returns:
            List[SessionHistory]: 競合履歴リスト
        """
        query = self.session.query(SessionHistory).filter_by(
            conflict_detected=True
        )
        
        if account_id:
            query = query.filter_by(account_id=account_id)
        
        query = query.order_by(desc(SessionHistory.created_at))
        
        if limit:
            query = query.limit(limit)
        
        return query.all()
    
    def get_manual_operation_histories(
        self,
        account_id: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[SessionHistory]:
        """
        手動操作履歴を取得
        
        Args:
            account_id: アカウントID（指定時はそのアカウントのみ）
            limit: 取得件数制限
        
        Returns:
            List[SessionHistory]: 手動操作履歴リスト
        """
        query = self.session.query(SessionHistory).filter_by(
            is_manual_operation=True
        )
        
        if account_id:
            query = query.filter_by(account_id=account_id)
        
        query = query.order_by(desc(SessionHistory.created_at))
        
        if limit:
            query = query.limit(limit)
        
        return query.all()
    
    def get_recent_conflicts(
        self,
        hours: int = 24,
        account_id: Optional[str] = None
    ) -> List[SessionHistory]:
        """
        最近の競合を取得
        
        Args:
            hours: 時間範囲
            account_id: アカウントID（指定時はそのアカウントのみ）
        
        Returns:
            List[SessionHistory]: 競合履歴リスト
        """
        start_date = datetime.utcnow() - timedelta(hours=hours)
        
        query = self.session.query(SessionHistory).filter(
            and_(
                SessionHistory.conflict_detected == True,
                SessionHistory.created_at >= start_date
            )
        )
        
        if account_id:
            query = query.filter_by(account_id=account_id)
        
        return query.order_by(desc(SessionHistory.created_at)).all()
    
    def get_statistics(
        self,
        account_id: Optional[str] = None,
        days: int = 7
    ) -> Dict[str, Any]:
        """
        セッション履歴統計を取得
        
        Args:
            account_id: アカウントID（指定時はそのアカウントのみ）
            days: 統計期間（日数）
        
        Returns:
            Dict[str, Any]: 統計情報
        """
        start_date = datetime.utcnow() - timedelta(days=days)
        
        query = self.session.query(SessionHistory).filter(
            SessionHistory.created_at >= start_date
        )
        
        if account_id:
            query = query.filter_by(account_id=account_id)
        
        histories = query.all()
        
        total = len(histories)
        conflicts = sum(1 for h in histories if h.conflict_detected)
        manual_ops = sum(1 for h in histories if h.is_manual_operation)
        
        # 検知タイプ別カウント
        detection_counts = {}
        for history in histories:
            det_type = history.detection_type
            detection_counts[det_type] = detection_counts.get(det_type, 0) + 1
        
        return {
            'total': total,
            'conflicts': conflicts,
            'manual_operations': manual_ops,
            'conflict_rate': (conflicts / total * 100) if total > 0 else 0,
            'detection_types': detection_counts,
            'period_days': days
        }


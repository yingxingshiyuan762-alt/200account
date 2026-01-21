"""
Event System Module

システムイベントの記録と管理
ログベースの復旧システムの中核
"""
from enum import Enum
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass, asdict
import json

from src.core.logger import logger


class EventType(str, Enum):
    """イベントタイプ"""
    # アカウント操作
    ACCOUNT_CREATED = 'ACCOUNT_CREATED'
    ACCOUNT_UPDATED = 'ACCOUNT_UPDATED'
    ACCOUNT_DELETED = 'ACCOUNT_DELETED'
    ACCOUNT_STATUS_CHANGED = 'ACCOUNT_STATUS_CHANGED'
    
    # ログイン操作
    LOGIN_STARTED = 'LOGIN_STARTED'
    LOGIN_SUCCESS = 'LOGIN_SUCCESS'
    LOGIN_FAILED = 'LOGIN_FAILED'
    
    # スケジュール操作
    SCHEDULE_UPDATE_STARTED = 'SCHEDULE_UPDATE_STARTED'
    SCHEDULE_UPDATE_COMPLETED = 'SCHEDULE_UPDATE_COMPLETED'
    SCHEDULE_UPDATE_FAILED = 'SCHEDULE_UPDATE_FAILED'
    
    # 待機接客操作
    WAIT_RECEPTION_STARTED = 'WAIT_RECEPTION_STARTED'
    WAIT_RECEPTION_COMPLETED = 'WAIT_RECEPTION_COMPLETED'
    WAIT_RECEPTION_FAILED = 'WAIT_RECEPTION_FAILED'
    
    # エラー
    ERROR_OCCURRED = 'ERROR_OCCURRED'
    ERROR_RECOVERED = 'ERROR_RECOVERED'
    
    # セッション
    SESSION_CONFLICT_DETECTED = 'SESSION_CONFLICT_DETECTED'
    SESSION_RESTORED = 'SESSION_RESTORED'
    
    # システム
    SYSTEM_STARTED = 'SYSTEM_STARTED'
    SYSTEM_STOPPED = 'SYSTEM_STOPPED'
    SYSTEM_ERROR = 'SYSTEM_ERROR'
    
    # 通知対象イベント
    APP_STOP_DETECTED = 'APP_STOP_DETECTED'  # アプリ停止検知（赤い×）
    RECOVERY_FAILED = 'RECOVERY_FAILED'  # 復旧失敗（最大リトライ後）
    SESSION_CORRUPTION_DETECTED = 'SESSION_CORRUPTION_DETECTED'  # セッション破損検知
    AUTOMATION_PROCESS_CRASH = 'AUTOMATION_PROCESS_CRASH'  # 自動化プロセスクラッシュ
    UNSTABLE_SESSION_SKIPPED = 'UNSTABLE_SESSION_SKIPPED'  # 不安定セッションでスキップ
    MANUAL_OPERATION_DETECTED = 'MANUAL_OPERATION_DETECTED'  # 手動操作検知
    REPEATED_UI_FAILURES = 'REPEATED_UI_FAILURES'  # 繰り返しUI操作失敗


class EventSeverity(str, Enum):
    """イベント重要度"""
    INFO = 'INFO'
    WARNING = 'WARNING'
    ERROR = 'ERROR'
    CRITICAL = 'CRITICAL'


@dataclass
class SystemEvent:
    """
    システムイベント
    
    全操作をイベントとして記録し、ログベース復旧の基盤とする
    """
    event_id: str
    event_type: EventType
    severity: EventSeverity
    account_id: Optional[str] = None
    timestamp: datetime = None
    message: str = ""
    data: Dict[str, Any] = None
    request_id: Optional[str] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
        if self.data is None:
            self.data = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        result = asdict(self)
        result['event_type'] = self.event_type.value
        result['severity'] = self.severity.value
        result['timestamp'] = self.timestamp.isoformat()
        return result
    
    def to_json(self) -> str:
        """JSON形式に変換"""
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SystemEvent':
        """辞書から作成"""
        data = data.copy()
        data['event_type'] = EventType(data['event_type'])
        data['severity'] = EventSeverity(data['severity'])
        if isinstance(data['timestamp'], str):
            data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)


class EventLogger:
    """
    イベントロガー
    
    システムイベントを記録し、ログとデータベースの両方に保存
    """
    
    def __init__(self):
        self.events: List[SystemEvent] = []
        self.max_memory_events = 1000  # メモリに保持する最大イベント数
    
    def log_event(
        self,
        event_type: EventType,
        severity: EventSeverity,
        account_id: Optional[str] = None,
        message: str = "",
        data: Optional[Dict[str, Any]] = None,
        request_id: Optional[str] = None
    ) -> SystemEvent:
        """
        イベントを記録
        
        Args:
            event_type: イベントタイプ
            severity: 重要度
            account_id: アカウントID
            message: メッセージ
            data: 追加データ
            request_id: リクエストID
        
        Returns:
            SystemEvent: 作成されたイベント
        """
        import uuid
        
        event = SystemEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            severity=severity,
            account_id=account_id,
            message=message,
            data=data or {},
            request_id=request_id
        )
        
        # メモリに保存
        self.events.append(event)
        if len(self.events) > self.max_memory_events:
            self.events.pop(0)  # 古いイベントを削除
        
        # ログに記録
        log_level = {
            EventSeverity.INFO: logger.info,
            EventSeverity.WARNING: logger.warning,
            EventSeverity.ERROR: logger.error,
            EventSeverity.CRITICAL: logger.critical,
        }.get(severity, logger.info)
        
        log_message = f"[EVENT:{event_type.value}] {message}"
        log_level(log_message, extra={
            'event_type': event_type.value,
            'account_id': account_id,
            'request_id': request_id
        })
        
        # データベースに記録（オプション）
        self._save_to_database(event)
        
        return event
    
    def _save_to_database(self, event: SystemEvent):
        """データベースにイベントを保存"""
        try:
            from src.database import db
            from src.database.repositories.log import AccountLogRepository
            from src.database.models import ActionType, LogStatus
            
            # イベントタイプからActionTypeにマッピング
            action_type_map = {
                EventType.LOGIN_STARTED: ActionType.LOGIN,
                EventType.LOGIN_SUCCESS: ActionType.LOGIN,
                EventType.LOGIN_FAILED: ActionType.LOGIN,
                EventType.SCHEDULE_UPDATE_STARTED: ActionType.SCHEDULE_UPDATE,
                EventType.SCHEDULE_UPDATE_COMPLETED: ActionType.SCHEDULE_UPDATE,
                EventType.SCHEDULE_UPDATE_FAILED: ActionType.SCHEDULE_UPDATE,
                EventType.WAIT_RECEPTION_STARTED: ActionType.WAIT_RECEPTION,
                EventType.WAIT_RECEPTION_COMPLETED: ActionType.WAIT_RECEPTION,
                EventType.WAIT_RECEPTION_FAILED: ActionType.WAIT_RECEPTION,
            }
            
            action_type = action_type_map.get(event.event_type, ActionType.QUEUE_EXECUTION)
            
            # ステータスマッピング
            if 'SUCCESS' in event.event_type.value or 'COMPLETED' in event.event_type.value:
                status = LogStatus.SUCCESS
            elif 'FAILED' in event.event_type.value or event.severity == EventSeverity.ERROR:
                status = LogStatus.FAILURE
            else:
                status = LogStatus.SUCCESS
            
            if event.account_id:
                with db.get_session() as session:
                    log_repo = AccountLogRepository(session)
                    log_repo.create_log(
                        account_id=event.account_id,
                        action_type=action_type,
                        status=status,
                        message=event.message,
                        error_detail=event.data if event.severity == EventSeverity.ERROR else None,
                        request_id=event.request_id
                    )
        except Exception as e:
            logger.debug(f"Failed to save event to database: {e}")
    
    def get_events(
        self,
        account_id: Optional[str] = None,
        event_type: Optional[EventType] = None,
        limit: Optional[int] = None
    ) -> List[SystemEvent]:
        """
        イベントを取得
        
        Args:
            account_id: アカウントID（フィルタ）
            event_type: イベントタイプ（フィルタ）
            limit: 取得件数制限
        
        Returns:
            List[SystemEvent]: イベントリスト
        """
        events = self.events.copy()
        
        # フィルタリング
        if account_id:
            events = [e for e in events if e.account_id == account_id]
        
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        
        # 新しい順にソート
        events.sort(key=lambda x: x.timestamp, reverse=True)
        
        # 件数制限
        if limit:
            events = events[:limit]
        
        return events
    
    def get_account_events(self, account_id: str) -> List[SystemEvent]:
        """アカウントのイベントを取得"""
        return self.get_events(account_id=account_id)
    
    def get_recent_errors(self, limit: int = 50) -> List[SystemEvent]:
        """最近のエラーイベントを取得"""
        events = [
            e for e in self.events
            if e.severity in [EventSeverity.ERROR, EventSeverity.CRITICAL]
        ]
        events.sort(key=lambda x: x.timestamp, reverse=True)
        return events[:limit]


# グローバルイベントロガー
event_logger = EventLogger()


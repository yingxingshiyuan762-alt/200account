"""
Patch System Models

パッチシステムのデータモデル
"""
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List, Callable
import uuid


class PatchType(str, Enum):
    """パッチタイプ"""
    DATABASE = 'database'       # データベース修正
    CODE = 'code'               # コード修正
    CONFIG = 'config'           # 設定修正
    DATA = 'data'               # データ修正
    MIGRATION = 'migration'     # マイグレーション
    HOTFIX = 'hotfix'           # 緊急修正


class PatchStatus(str, Enum):
    """パッチステータス"""
    PENDING = 'pending'         # 未実行
    RUNNING = 'running'         # 実行中
    SUCCESS = 'success'         # 成功
    FAILED = 'failed'           # 失敗
    SKIPPED = 'skipped'         # スキップ
    ROLLBACK = 'rollback'       # ロールバック済み


@dataclass
class Patch:
    """
    パッチモデル
    
    パッチファイルの情報を保持
    """
    # 必須フィールド
    id: str                                 # パッチID（ファイル名から生成）
    name: str                               # パッチ名
    description: str                        # 説明
    version: str                            # バージョン
    patch_type: PatchType                   # パッチタイプ
    
    # 実行関連
    execute_func: Callable                  # 実行関数
    rollback_func: Optional[Callable] = None  # ロールバック関数
    validate_func: Optional[Callable] = None  # 検証関数
    
    # メタデータ
    author: str = 'System'                  # 作成者
    created_at: datetime = field(default_factory=datetime.utcnow)
    dependencies: List[str] = field(default_factory=list)  # 依存パッチID
    tags: List[str] = field(default_factory=list)
    
    # 実行状態
    status: PatchStatus = PatchStatus.PENDING
    executed_at: Optional[datetime] = None
    execution_time: float = 0.0             # 実行時間（秒）
    error_message: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    
    # フラグ
    is_critical: bool = False               # 緊急パッチかどうか
    require_confirmation: bool = False       # 実行前に確認が必要か
    can_rollback: bool = False              # ロールバック可能か
    auto_execute: bool = True               # 自動実行可能か
    
    def __post_init__(self):
        """初期化後処理"""
        if not self.id:
            self.id = str(uuid.uuid4())
        
        # ロールバック関数がある場合、ロールバック可能フラグを設定
        if self.rollback_func is not None:
            self.can_rollback = True
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'version': self.version,
            'patch_type': self.patch_type.value,
            'author': self.author,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'dependencies': self.dependencies,
            'tags': self.tags,
            'status': self.status.value,
            'executed_at': self.executed_at.isoformat() if self.executed_at else None,
            'execution_time': self.execution_time,
            'error_message': self.error_message,
            'result': self.result,
            'is_critical': self.is_critical,
            'require_confirmation': self.require_confirmation,
            'can_rollback': self.can_rollback,
            'auto_execute': self.auto_execute
        }


@dataclass
class PatchExecutionRecord:
    """パッチ実行記録"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    patch_id: str = ''
    status: PatchStatus = PatchStatus.PENDING
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    execution_time: float = 0.0
    error_message: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    rollback_available: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            'id': self.id,
            'patch_id': self.patch_id,
            'status': self.status.value,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'execution_time': self.execution_time,
            'error_message': self.error_message,
            'result': self.result,
            'rollback_available': self.rollback_available
        }

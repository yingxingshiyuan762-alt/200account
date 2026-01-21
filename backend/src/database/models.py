"""
Database Models

MySQL用のSQLAlchemyモデル定義
"""
import uuid
from datetime import datetime
from enum import Enum
from typing import Optional, List
from sqlalchemy import Column, String, Integer, Boolean, Text, DateTime, ForeignKey, Float, JSON
from sqlalchemy.orm import relationship, declarative_base
from src.core.logger import logger

Base = declarative_base()


# ═══════════════════════════════════════════════════════
# Enums
# ═══════════════════════════════════════════════════════

class AccountStatus(str, Enum):
    """アカウントステータス"""
    IDLE = 'IDLE'                       # 待機中
    PROCESSING = 'PROCESSING'           # 処理中
    ERROR = 'ERROR'                     # エラー
    MANUAL_OPERATION = 'MANUAL_OPERATION'  # 手動操作中
    DISABLED = 'DISABLED'               # 無効化


class LogStatus(str, Enum):
    """ログステータス"""
    SUCCESS = 'SUCCESS'     # 成功
    FAILURE = 'FAILURE'     # 失敗
    SKIPPED = 'SKIPPED'     # スキップ
    TIMEOUT = 'TIMEOUT'     # タイムアウト


class ActionType(str, Enum):
    """操作種別"""
    LOGIN = 'LOGIN'
    LOGOUT = 'LOGOUT'
    SCHEDULE_UPDATE = 'SCHEDULE_UPDATE'
    WAIT_RECEPTION = 'WAIT_RECEPTION'
    STATUS_CHECK = 'STATUS_CHECK'
    ERROR_RECOVERY = 'ERROR_RECOVERY'
    QUEUE_EXECUTION = 'QUEUE_EXECUTION'


class DetectionType(str, Enum):
    """競合検知タイプ"""
    TOKEN_CHANGE = 'TOKEN_CHANGE'
    DOM_MUTATION = 'DOM_MUTATION'
    NETWORK_ACTIVITY = 'NETWORK_ACTIVITY'
    USER_INPUT = 'USER_INPUT'


# ═══════════════════════════════════════════════════════
# Models
# ═══════════════════════════════════════════════════════

class Account(Base):
    """
    アカウントモデル
    
    200アカウントの情報を管理するメインモデル
    """
    __tablename__ = 'accounts'
    
    # Primary Key (MySQL uses CHAR(36) for UUID)
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Authentication
    username = Column(String(100), unique=True, nullable=False, index=True)
    password_encrypted = Column(Text, nullable=False)
    
    # Account Info
    store_name = Column(String(200), nullable=False)
    login_url = Column(String(255), nullable=True)
    
    # Status Management
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    status = Column(String(50), default=AccountStatus.IDLE, nullable=False, index=True)
    
    # Session Management
    session_token = Column(Text, nullable=True)
    last_login_at = Column(DateTime, nullable=True)
    last_success_at = Column(DateTime, nullable=True)
    
    # Error Tracking
    error_count = Column(Integer, default=0, nullable=False)
    last_error = Column(Text, nullable=True)
    
    # Metadata (MySQL uses JSON type)
    metadata_json = Column(JSON, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, 
                       onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    logs = relationship("AccountLog", back_populates="account", 
                       cascade="all, delete-orphan")
    session_histories = relationship("SessionHistory", back_populates="account",
                                    cascade="all, delete-orphan")
    
    def increment_error_count(self, error_message: str = None):
        """
        エラーカウントを増加
        
        5回連続エラーでアカウント無効化
        """
        self.error_count += 1
        self.last_error = error_message
        self.status = AccountStatus.ERROR
        self.updated_at = datetime.utcnow()
        
        if self.error_count >= 5:
            self.is_active = False
            self.status = AccountStatus.DISABLED
            logger.warning(f"Account {self.username} disabled after 5 errors")
    
    def reset_error_count(self):
        """エラーカウントをリセット（成功時）"""
        self.error_count = 0
        self.last_error = None
        self.status = AccountStatus.IDLE
        self.updated_at = datetime.utcnow()
    
    def __repr__(self):
        return f"<Account(username='{self.username}', status='{self.status}')>"


class AccountLog(Base):
    """
    アカウント操作ログモデル
    """
    __tablename__ = 'account_logs'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id = Column(String(36), ForeignKey('accounts.id'), 
                       nullable=False, index=True)
    
    # Action Details
    action_type = Column(String(50), nullable=False, index=True)
    status = Column(String(20), nullable=False, index=True)
    message = Column(Text, nullable=True)
    error_detail = Column(JSON, nullable=True)
    execution_time = Column(Float, nullable=True)
    
    # Tracing
    request_id = Column(String(100), nullable=True, index=True)
    
    # Code Location (for linking to source code)
    file_path = Column(String(500), nullable=True)  # Relative path from project root
    function_name = Column(String(200), nullable=True)  # Function name where log was created
    line_number = Column(Integer, nullable=True)  # Line number in the file
    
    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationships
    account = relationship("Account", back_populates="logs")
    
    def __repr__(self):
        return f"<AccountLog(account_id='{self.account_id}', action='{self.action_type}', status='{self.status}')>"


class SessionHistory(Base):
    """
    セッション競合検知履歴モデル
    """
    __tablename__ = 'session_histories'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    account_id = Column(String(36), ForeignKey('accounts.id'), 
                       nullable=False, index=True)
    
    # Detection Info
    detection_type = Column(String(50), nullable=False, index=True)
    is_manual_operation = Column(Boolean, default=False, nullable=False)
    conflict_detected = Column(Boolean, default=False, nullable=False, index=True)
    action_taken = Column(String(50), nullable=True)
    
    # Session Info
    session_token = Column(Text, nullable=True)
    detection_data = Column(JSON, nullable=True)
    
    # Timestamp
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationships
    account = relationship("Account", back_populates="session_histories")
    
    def __repr__(self):
        return f"<SessionHistory(account_id='{self.account_id}', detection='{self.detection_type}', conflict={self.conflict_detected})>"


class SystemConfig(Base):
    """
    システム設定モデル
    """
    __tablename__ = 'system_configs'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(JSON, nullable=False)
    description = Column(Text, nullable=True)
    is_system = Column(Boolean, default=False, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, 
                       onupdate=datetime.utcnow, nullable=False)
    
    def __repr__(self):
        return f"<SystemConfig(key='{self.key}', value={self.value})>"


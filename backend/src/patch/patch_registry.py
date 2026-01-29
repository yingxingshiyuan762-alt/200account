"""
Patch Registry Module

パッチ実行履歴の永続化
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Float, JSON, Boolean, Text

from src.core.logger import logger
from src.database.connection import get_session, db
from src.database.models import Base


class PatchRecord(Base):
    """パッチ実行記録テーブル"""
    __tablename__ = 'patch_records'
    
    patch_id = Column(String(255), primary_key=True)
    patch_name = Column(String(255), nullable=False)
    patch_type = Column(String(50), nullable=False)
    patch_version = Column(String(50), nullable=False)
    
    status = Column(String(50), nullable=False)  # success, failed, rollback
    executed_at = Column(DateTime, nullable=False)
    execution_time = Column(Float, default=0.0)
    
    result = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    
    rolled_back = Column(Boolean, default=False)
    rolled_back_at = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PatchRegistry:
    """
    パッチレジストリ
    
    実行済みパッチをデータベースで管理
    """
    
    def __init__(self):
        """初期化"""
        self._ensure_table_exists()
    
    def _ensure_table_exists(self):
        """テーブルが存在することを確認"""
        try:
            Base.metadata.create_all(db._engine, tables=[PatchRecord.__table__])
            logger.debug("Patch records table verified")
        except Exception as e:
            logger.error(f"Failed to create patch records table: {e}", exc_info=True)
    
    def mark_executed(
        self,
        patch_id: str,
        patch_name: str = '',
        patch_type: str = 'hotfix',
        patch_version: str = '1.0.0',
        execution_time: float = 0.0,
        result: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        パッチを実行済みとしてマーク
        
        Args:
            patch_id: パッチID
            patch_name: パッチ名
            patch_type: パッチタイプ
            patch_version: パッチバージョン
            execution_time: 実行時間（秒）
            result: 実行結果
        
        Returns:
            bool: 成功時True
        """
        try:
            with get_session() as session:
                # 既存レコードをチェック
                existing = session.query(PatchRecord).filter_by(patch_id=patch_id).first()
                
                if existing:
                    # 更新
                    existing.status = 'success'
                    existing.executed_at = datetime.utcnow()
                    existing.execution_time = execution_time
                    existing.result = result
                    existing.rolled_back = False
                    existing.rolled_back_at = None
                    existing.updated_at = datetime.utcnow()
                else:
                    # 新規作成
                    record = PatchRecord(
                        patch_id=patch_id,
                        patch_name=patch_name,
                        patch_type=patch_type,
                        patch_version=patch_version,
                        status='success',
                        executed_at=datetime.utcnow(),
                        execution_time=execution_time,
                        result=result,
                        rolled_back=False
                    )
                    session.add(record)
                
                session.commit()
                logger.info(f"Patch marked as executed: {patch_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to mark patch as executed: {e}", exc_info=True)
            return False
    
    def mark_failed(
        self,
        patch_id: str,
        error_message: str,
        patch_name: str = '',
        patch_type: str = 'hotfix',
        patch_version: str = '1.0.0',
        execution_time: float = 0.0
    ) -> bool:
        """
        パッチを失敗としてマーク
        
        Args:
            patch_id: パッチID
            error_message: エラーメッセージ
            patch_name: パッチ名
            patch_type: パッチタイプ
            patch_version: パッチバージョン
            execution_time: 実行時間（秒）
        
        Returns:
            bool: 成功時True
        """
        try:
            with get_session() as session:
                # 既存レコードをチェック
                existing = session.query(PatchRecord).filter_by(patch_id=patch_id).first()
                
                if existing:
                    # 更新
                    existing.status = 'failed'
                    existing.executed_at = datetime.utcnow()
                    existing.execution_time = execution_time
                    existing.error_message = error_message
                    existing.updated_at = datetime.utcnow()
                else:
                    # 新規作成
                    record = PatchRecord(
                        patch_id=patch_id,
                        patch_name=patch_name,
                        patch_type=patch_type,
                        patch_version=patch_version,
                        status='failed',
                        executed_at=datetime.utcnow(),
                        execution_time=execution_time,
                        error_message=error_message
                    )
                    session.add(record)
                
                session.commit()
                logger.info(f"Patch marked as failed: {patch_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to mark patch as failed: {e}", exc_info=True)
            return False
    
    def mark_rolled_back(self, patch_id: str) -> bool:
        """
        パッチをロールバック済みとしてマーク
        
        Args:
            patch_id: パッチID
        
        Returns:
            bool: 成功時True
        """
        try:
            with get_session() as session:
                record = session.query(PatchRecord).filter_by(patch_id=patch_id).first()
                
                if not record:
                    logger.warning(f"Patch record not found for rollback: {patch_id}")
                    return False
                
                record.status = 'rollback'
                record.rolled_back = True
                record.rolled_back_at = datetime.utcnow()
                record.updated_at = datetime.utcnow()
                
                session.commit()
                logger.info(f"Patch marked as rolled back: {patch_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to mark patch as rolled back: {e}", exc_info=True)
            return False
    
    def is_executed(self, patch_id: str) -> bool:
        """
        パッチが実行済みかチェック
        
        Args:
            patch_id: パッチID
        
        Returns:
            bool: 実行済みの場合True
        """
        try:
            with get_session() as session:
                record = session.query(PatchRecord).filter_by(
                    patch_id=patch_id,
                    status='success',
                    rolled_back=False
                ).first()
                
                return record is not None
                
        except Exception as e:
            logger.error(f"Failed to check patch execution status: {e}", exc_info=True)
            return False
    
    def get_record(self, patch_id: str) -> Optional[Dict[str, Any]]:
        """
        パッチ実行記録を取得
        
        Args:
            patch_id: パッチID
        
        Returns:
            Optional[Dict[str, Any]]: 実行記録
        """
        try:
            with get_session() as session:
                record = session.query(PatchRecord).filter_by(patch_id=patch_id).first()
                
                if not record:
                    return None
                
                return {
                    'patch_id': record.patch_id,
                    'patch_name': record.patch_name,
                    'patch_type': record.patch_type,
                    'patch_version': record.patch_version,
                    'status': record.status,
                    'executed_at': record.executed_at.isoformat() if record.executed_at else None,
                    'execution_time': record.execution_time,
                    'result': record.result,
                    'error_message': record.error_message,
                    'rolled_back': record.rolled_back,
                    'rolled_back_at': record.rolled_back_at.isoformat() if record.rolled_back_at else None
                }
                
        except Exception as e:
            logger.error(f"Failed to get patch record: {e}", exc_info=True)
            return None
    
    def get_all_executed(self) -> List[str]:
        """
        すべての実行済みパッチIDを取得
        
        Returns:
            List[str]: パッチIDリスト
        """
        try:
            with get_session() as session:
                records = session.query(PatchRecord).filter_by(
                    status='success',
                    rolled_back=False
                ).all()
                
                return [r.patch_id for r in records]
                
        except Exception as e:
            logger.error(f"Failed to get executed patches: {e}", exc_info=True)
            return []
    
    def get_all_records(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        すべての実行記録を取得
        
        Args:
            limit: 取得件数制限
        
        Returns:
            List[Dict[str, Any]]: 実行記録リスト
        """
        try:
            with get_session() as session:
                records = session.query(PatchRecord).order_by(
                    PatchRecord.executed_at.desc()
                ).limit(limit).all()
                
                return [
                    {
                        'patch_id': r.patch_id,
                        'patch_name': r.patch_name,
                        'patch_type': r.patch_type,
                        'status': r.status,
                        'executed_at': r.executed_at.isoformat() if r.executed_at else None,
                        'execution_time': r.execution_time,
                        'rolled_back': r.rolled_back
                    }
                    for r in records
                ]
                
        except Exception as e:
            logger.error(f"Failed to get all patch records: {e}", exc_info=True)
            return []
    
    def clear_all(self) -> bool:
        """
        すべての実行記録を削除（開発/テスト用）
        
        Returns:
            bool: 成功時True
        """
        try:
            with get_session() as session:
                session.query(PatchRecord).delete()
                session.commit()
                logger.warning("All patch records cleared")
                return True
                
        except Exception as e:
            logger.error(f"Failed to clear patch records: {e}", exc_info=True)
            return False

"""
Base Repository

全リポジトリの基底クラス
"""
from typing import Generic, TypeVar, Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from src.core.logger import logger

T = TypeVar('T')


class BaseRepository(Generic[T]):
    """
    ベースリポジトリクラス
    
    全リポジトリの基底となり、基本的なCRUD操作を提供
    """
    
    def __init__(self, session: Session, model_class: type):
        """
        初期化
        
        Args:
            session: SQLAlchemyセッション
            model_class: モデルクラス
        """
        self.session = session
        self.model_class = model_class
    
    def get_by_id(self, id: str) -> Optional[T]:
        """
        IDでレコードを取得
        
        Args:
            id: レコードID
        
        Returns:
            Optional[T]: レコード（存在しない場合はNone）
        """
        try:
            return self.session.query(self.model_class).filter_by(id=id).first()
        except SQLAlchemyError as e:
            logger.error(f"Error getting {self.model_class.__name__} by id {id}: {e}")
            raise
    
    def get_all(self, limit: Optional[int] = None, offset: int = 0) -> List[T]:
        """
        全レコードを取得
        
        Args:
            limit: 取得件数制限
            offset: オフセット
        
        Returns:
            List[T]: レコードリスト
        """
        try:
            query = self.session.query(self.model_class)
            if limit:
                query = query.limit(limit).offset(offset)
            return query.all()
        except SQLAlchemyError as e:
            logger.error(f"Error getting all {self.model_class.__name__}: {e}")
            raise
    
    def create(self, **kwargs) -> T:
        """
        レコードを作成
        
        Args:
            **kwargs: モデルの属性
        
        Returns:
            T: 作成されたレコード
        """
        try:
            instance = self.model_class(**kwargs)
            self.session.add(instance)
            self.session.flush()  # IDを即座に取得
            logger.debug(f"Created {self.model_class.__name__}: {instance.id}")
            return instance
        except SQLAlchemyError as e:
            logger.error(f"Error creating {self.model_class.__name__}: {e}")
            raise
    
    def update(self, id: str, **kwargs) -> Optional[T]:
        """
        レコードを更新
        
        Args:
            id: レコードID
            **kwargs: 更新する属性
        
        Returns:
            Optional[T]: 更新されたレコード（存在しない場合はNone）
        """
        try:
            instance = self.get_by_id(id)
            
            if instance is None:
                logger.warning(f"{self.model_class.__name__} not found: {id}")
                return None
            
            for key, value in kwargs.items():
                if hasattr(instance, key):
                    setattr(instance, key, value)
            
            self.session.flush()
            logger.debug(f"Updated {self.model_class.__name__}: {id}")
            return instance
        except SQLAlchemyError as e:
            logger.error(f"Error updating {self.model_class.__name__} {id}: {e}")
            raise
    
    def delete(self, id: str) -> bool:
        """
        レコードを削除
        
        Args:
            id: レコードID
        
        Returns:
            bool: 削除成功時True
        """
        try:
            instance = self.get_by_id(id)
            
            if instance is None:
                logger.warning(f"{self.model_class.__name__} not found: {id}")
                return False
            
            self.session.delete(instance)
            self.session.flush()
            logger.debug(f"Deleted {self.model_class.__name__}: {id}")
            return True
        except SQLAlchemyError as e:
            logger.error(f"Error deleting {self.model_class.__name__} {id}: {e}")
            raise
    
    def count(self) -> int:
        """
        レコード数を取得
        
        Returns:
            int: レコード数
        """
        try:
            return self.session.query(self.model_class).count()
        except SQLAlchemyError as e:
            logger.error(f"Error counting {self.model_class.__name__}: {e}")
            raise


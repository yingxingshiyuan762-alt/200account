"""
Patch Loader Module

パッチファイルの読み込みと検証
"""
import os
import importlib.util
import inspect
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

from config.config import settings
from src.core.logger import logger
from .models import Patch, PatchType, PatchStatus


class PatchLoader:
    """
    パッチローダー
    
    パッチディレクトリからパッチファイルを読み込む
    """
    
    def __init__(self, patch_dir: Optional[Path] = None):
        """
        初期化
        
        Args:
            patch_dir: パッチディレクトリ（デフォルト: settings.PATCH_DIR）
        """
        self.patch_dir = patch_dir or settings.PATCH_DIR
        self.patch_dir.mkdir(parents=True, exist_ok=True)
        
    def load_all_patches(self) -> List[Patch]:
        """
        すべてのパッチファイルを読み込む
        
        Returns:
            List[Patch]: パッチリスト
        """
        patches = []
        
        # パッチディレクトリをスキャン
        for patch_file in self.patch_dir.glob('*.py'):
            if patch_file.name.startswith('_'):
                continue  # プライベートファイルをスキップ
            
            try:
                patch = self.load_patch_from_file(patch_file)
                if patch:
                    patches.append(patch)
                    logger.info(f"Loaded patch: {patch.id} - {patch.name}")
            except Exception as e:
                logger.error(f"Failed to load patch from {patch_file}: {e}", exc_info=True)
        
        # 依存関係順にソート
        patches = self._sort_by_dependencies(patches)
        
        logger.info(f"Loaded {len(patches)} patches from {self.patch_dir}")
        return patches
    
    def load_patch_from_file(self, patch_file: Path) -> Optional[Patch]:
        """
        パッチファイルから Patch オブジェクトを生成
        
        Args:
            patch_file: パッチファイルパス
        
        Returns:
            Optional[Patch]: パッチオブジェクト
        """
        try:
            # モジュールを動的にインポート
            spec = importlib.util.spec_from_file_location(
                patch_file.stem,
                patch_file
            )
            if not spec or not spec.loader:
                logger.error(f"Cannot load spec from {patch_file}")
                return None
            
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # パッチ情報を取得
            patch_info = self._extract_patch_info(module, patch_file)
            
            if not patch_info:
                logger.warning(f"No valid patch info found in {patch_file}")
                return None
            
            # Patchオブジェクトを生成
            patch = Patch(**patch_info)
            
            # バリデーション
            if not self._validate_patch(patch):
                logger.error(f"Patch validation failed: {patch.id}")
                return None
            
            return patch
            
        except Exception as e:
            logger.error(f"Error loading patch from {patch_file}: {e}", exc_info=True)
            return None
    
    def _extract_patch_info(self, module: Any, patch_file: Path) -> Optional[Dict[str, Any]]:
        """
        モジュールからパッチ情報を抽出
        
        Args:
            module: インポートされたモジュール
            patch_file: パッチファイルパス
        
        Returns:
            Optional[Dict[str, Any]]: パッチ情報
        """
        try:
            # 必須属性の確認
            required_attrs = ['PATCH_ID', 'PATCH_NAME', 'PATCH_DESCRIPTION', 'execute']
            for attr in required_attrs:
                if not hasattr(module, attr):
                    logger.error(f"Missing required attribute: {attr} in {patch_file}")
                    return None
            
            # パッチ情報を構築
            patch_info = {
                'id': module.PATCH_ID,
                'name': module.PATCH_NAME,
                'description': module.PATCH_DESCRIPTION,
                'version': getattr(module, 'PATCH_VERSION', '1.0.0'),
                'patch_type': PatchType(getattr(module, 'PATCH_TYPE', 'hotfix')),
                'execute_func': module.execute,
                'rollback_func': getattr(module, 'rollback', None),
                'validate_func': getattr(module, 'validate', None),
                'author': getattr(module, 'AUTHOR', 'System'),
                'dependencies': getattr(module, 'DEPENDENCIES', []),
                'tags': getattr(module, 'TAGS', []),
                'is_critical': getattr(module, 'IS_CRITICAL', False),
                'require_confirmation': getattr(module, 'REQUIRE_CONFIRMATION', False),
                'auto_execute': getattr(module, 'AUTO_EXECUTE', True)
            }
            
            return patch_info
            
        except Exception as e:
            logger.error(f"Error extracting patch info: {e}", exc_info=True)
            return None
    
    def _validate_patch(self, patch: Patch) -> bool:
        """
        パッチを検証
        
        Args:
            patch: パッチオブジェクト
        
        Returns:
            bool: 検証結果
        """
        # IDの検証
        if not patch.id or len(patch.id) < 3:
            logger.error(f"Invalid patch ID: {patch.id}")
            return False
        
        # 実行関数の検証
        if not callable(patch.execute_func):
            logger.error(f"Execute function is not callable for patch: {patch.id}")
            return False
        
        # ロールバック関数の検証（存在する場合）
        if patch.rollback_func and not callable(patch.rollback_func):
            logger.error(f"Rollback function is not callable for patch: {patch.id}")
            return False
        
        # 検証関数の検証（存在する場合）
        if patch.validate_func and not callable(patch.validate_func):
            logger.error(f"Validate function is not callable for patch: {patch.id}")
            return False
        
        return True
    
    def _sort_by_dependencies(self, patches: List[Patch]) -> List[Patch]:
        """
        依存関係に基づいてパッチをソート
        
        Args:
            patches: パッチリスト
        
        Returns:
            List[Patch]: ソート済みパッチリスト
        """
        # パッチIDでマッピング
        patch_map = {p.id: p for p in patches}
        sorted_patches = []
        visited = set()
        
        def visit(patch_id: str):
            """深さ優先探索で依存関係を解決"""
            if patch_id in visited:
                return
            
            patch = patch_map.get(patch_id)
            if not patch:
                return
            
            # 依存パッチを先に訪問
            for dep_id in patch.dependencies:
                visit(dep_id)
            
            visited.add(patch_id)
            sorted_patches.append(patch)
        
        # すべてのパッチを訪問
        for patch in patches:
            visit(patch.id)
        
        return sorted_patches
    
    def get_patch_file_path(self, patch_id: str) -> Optional[Path]:
        """
        パッチIDからファイルパスを取得
        
        Args:
            patch_id: パッチID
        
        Returns:
            Optional[Path]: ファイルパス
        """
        for patch_file in self.patch_dir.glob('*.py'):
            if patch_file.stem == patch_id or patch_id in patch_file.stem:
                return patch_file
        return None

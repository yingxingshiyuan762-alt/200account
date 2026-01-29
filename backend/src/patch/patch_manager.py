"""
Patch Manager Module

パッチシステムの統合管理
"""
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime
import threading

from config.config import settings
from src.core.logger import logger
from src.database.connection import get_session
from .models import Patch, PatchStatus, PatchType, PatchExecutionRecord
from .patch_loader import PatchLoader
from .patch_executor import PatchExecutor
from .patch_registry import PatchRegistry


class PatchManager:
    """
    パッチマネージャー
    
    パッチシステムの中央管理クラス
    - パッチの読み込み
    - パッチの実行
    - パッチのトラッキング
    - パッチの状態管理
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """シングルトンパターン"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """初期化"""
        if not hasattr(self, '_initialized'):
            self.loader = PatchLoader(settings.PATCH_DIR)
            self.executor = PatchExecutor()
            self.registry = PatchRegistry()
            
            self.patches: Dict[str, Patch] = {}
            self.execution_history: List[PatchExecutionRecord] = []
            
            self._initialized = True
            logger.info("Patch Manager initialized")
    
    def load_patches(self) -> List[Patch]:
        """
        パッチを読み込む
        
        Returns:
            List[Patch]: 読み込まれたパッチリスト
        """
        logger.info("Loading patches...")
        
        # パッチファイルを読み込み
        patches = self.loader.load_all_patches()
        
        # 内部辞書に格納
        for patch in patches:
            self.patches[patch.id] = patch
        
        # レジストリと照合して実行済みパッチをマーク
        self._sync_with_registry()
        
        logger.info(f"Loaded {len(patches)} patches")
        return patches
    
    def get_patch(self, patch_id: str) -> Optional[Patch]:
        """
        パッチIDからパッチを取得
        
        Args:
            patch_id: パッチID
        
        Returns:
            Optional[Patch]: パッチオブジェクト
        """
        return self.patches.get(patch_id)
    
    def get_all_patches(self) -> List[Patch]:
        """
        すべてのパッチを取得
        
        Returns:
            List[Patch]: パッチリスト
        """
        return list(self.patches.values())
    
    def get_pending_patches(self) -> List[Patch]:
        """
        未実行のパッチを取得
        
        Returns:
            List[Patch]: 未実行パッチリスト
        """
        return [p for p in self.patches.values() if p.status == PatchStatus.PENDING]
    
    def get_critical_patches(self) -> List[Patch]:
        """
        緊急パッチを取得
        
        Returns:
            List[Patch]: 緊急パッチリスト
        """
        return [p for p in self.patches.values() if p.is_critical and p.status == PatchStatus.PENDING]
    
    def execute_patch(self, patch_id: str, force: bool = False) -> Dict[str, Any]:
        """
        パッチを実行
        
        Args:
            patch_id: パッチID
            force: 強制実行フラグ（既に実行済みでも再実行）
        
        Returns:
            Dict[str, Any]: 実行結果
        """
        patch = self.get_patch(patch_id)
        
        if not patch:
            return {
                'success': False,
                'error': f'Patch not found: {patch_id}'
            }
        
        # 実行済みチェック
        if patch.status == PatchStatus.SUCCESS and not force:
            return {
                'success': False,
                'error': f'Patch already executed: {patch_id}',
                'status': 'skipped'
            }
        
        # 依存関係チェック
        unmet_deps = self._check_dependencies(patch)
        if unmet_deps:
            return {
                'success': False,
                'error': f'Unmet dependencies: {", ".join(unmet_deps)}',
                'unmet_dependencies': unmet_deps
            }
        
        # パッチ実行
        logger.info(f"Executing patch: {patch_id}")
        record = self.executor.execute_patch(patch)
        
        # 実行履歴に追加
        self.execution_history.append(record)
        
        # レジストリに記録
        if record.status == PatchStatus.SUCCESS:
            self.registry.mark_executed(
                patch_id=patch.id,
                execution_time=record.execution_time,
                result=record.result
            )
        
        return {
            'success': record.status == PatchStatus.SUCCESS,
            'patch_id': patch.id,
            'status': record.status.value,
            'execution_time': record.execution_time,
            'result': record.result,
            'error': record.error_message
        }
    
    def execute_all_pending(self, auto_only: bool = True) -> Dict[str, Any]:
        """
        すべての未実行パッチを実行
        
        Args:
            auto_only: 自動実行可能なパッチのみ実行
        
        Returns:
            Dict[str, Any]: 実行サマリー
        """
        pending_patches = self.get_pending_patches()
        
        if auto_only:
            pending_patches = [p for p in pending_patches if p.auto_execute]
        
        logger.info(f"Executing {len(pending_patches)} pending patches...")
        
        results = {
            'total': len(pending_patches),
            'success': 0,
            'failed': 0,
            'skipped': 0,
            'details': []
        }
        
        for patch in pending_patches:
            result = self.execute_patch(patch.id)
            
            if result['success']:
                results['success'] += 1
            elif result.get('status') == 'skipped':
                results['skipped'] += 1
            else:
                results['failed'] += 1
            
            results['details'].append({
                'patch_id': patch.id,
                'patch_name': patch.name,
                'status': result.get('status'),
                'error': result.get('error')
            })
        
        logger.info(
            f"Patch execution completed: "
            f"{results['success']} success, "
            f"{results['failed']} failed, "
            f"{results['skipped']} skipped"
        )
        
        return results
    
    def rollback_patch(self, patch_id: str) -> Dict[str, Any]:
        """
        パッチをロールバック
        
        Args:
            patch_id: パッチID
        
        Returns:
            Dict[str, Any]: ロールバック結果
        """
        patch = self.get_patch(patch_id)
        
        if not patch:
            return {
                'success': False,
                'error': f'Patch not found: {patch_id}'
            }
        
        if not patch.can_rollback:
            return {
                'success': False,
                'error': f'Patch cannot be rolled back: {patch_id}'
            }
        
        if patch.status != PatchStatus.SUCCESS:
            return {
                'success': False,
                'error': f'Patch not in success state: {patch_id}'
            }
        
        # ロールバック実行
        logger.info(f"Rolling back patch: {patch_id}")
        record = self.executor.rollback_patch(patch)
        
        # 実行履歴に追加
        self.execution_history.append(record)
        
        # レジストリを更新
        if record.status == PatchStatus.ROLLBACK:
            self.registry.mark_rolled_back(patch_id)
        
        return {
            'success': record.status == PatchStatus.ROLLBACK,
            'patch_id': patch.id,
            'status': record.status.value,
            'execution_time': record.execution_time,
            'error': record.error_message
        }
    
    def dry_run(self, patch_id: str) -> Dict[str, Any]:
        """
        パッチのドライラン
        
        Args:
            patch_id: パッチID
        
        Returns:
            Dict[str, Any]: ドライラン結果
        """
        patch = self.get_patch(patch_id)
        
        if not patch:
            return {
                'success': False,
                'error': f'Patch not found: {patch_id}'
            }
        
        return self.executor.dry_run(patch)
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        パッチ統計を取得
        
        Returns:
            Dict[str, Any]: 統計情報
        """
        total = len(self.patches)
        by_status = {}
        by_type = {}
        
        for patch in self.patches.values():
            # ステータス別
            status = patch.status.value
            by_status[status] = by_status.get(status, 0) + 1
            
            # タイプ別
            ptype = patch.patch_type.value
            by_type[ptype] = by_type.get(ptype, 0) + 1
        
        return {
            'total_patches': total,
            'by_status': by_status,
            'by_type': by_type,
            'critical_patches': len(self.get_critical_patches()),
            'pending_patches': len(self.get_pending_patches()),
            'execution_history_count': len(self.execution_history)
        }
    
    def _check_dependencies(self, patch: Patch) -> List[str]:
        """
        パッチの依存関係をチェック
        
        Args:
            patch: パッチオブジェクト
        
        Returns:
            List[str]: 未満たされた依存関係のリスト
        """
        unmet_deps = []
        
        for dep_id in patch.dependencies:
            dep_patch = self.get_patch(dep_id)
            
            if not dep_patch:
                unmet_deps.append(f"{dep_id} (not found)")
            elif dep_patch.status != PatchStatus.SUCCESS:
                unmet_deps.append(f"{dep_id} (not executed)")
        
        return unmet_deps
    
    def _sync_with_registry(self):
        """レジストリと同期して実行済みパッチをマーク"""
        executed_patches = self.registry.get_all_executed()
        
        for patch_id in executed_patches:
            if patch_id in self.patches:
                self.patches[patch_id].status = PatchStatus.SUCCESS


# グローバルインスタンス
patch_manager = PatchManager()

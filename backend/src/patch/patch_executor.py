"""
Patch Executor Module

パッチの実行とロールバック
"""
import time
from datetime import datetime
from typing import Dict, Any, Optional
import traceback

from src.core.logger import logger
from src.database.connection import get_session
from .models import Patch, PatchStatus, PatchExecutionRecord


class PatchExecutor:
    """
    パッチ実行エンジン
    
    パッチの実行、ロールバック、検証を管理
    """
    
    def __init__(self):
        """初期化"""
        self.current_execution: Optional[PatchExecutionRecord] = None
    
    def execute_patch(self, patch: Patch) -> PatchExecutionRecord:
        """
        パッチを実行
        
        Args:
            patch: パッチオブジェクト
        
        Returns:
            PatchExecutionRecord: 実行記録
        """
        record = PatchExecutionRecord(
            patch_id=patch.id,
            status=PatchStatus.RUNNING,
            started_at=datetime.utcnow(),
            rollback_available=patch.can_rollback
        )
        
        self.current_execution = record
        
        logger.info(f"=" * 60)
        logger.info(f"Executing patch: {patch.id} - {patch.name}")
        logger.info(f"Type: {patch.patch_type.value}")
        logger.info(f"Description: {patch.description}")
        logger.info(f"=" * 60)
        
        start_time = time.time()
        
        try:
            # ステップ1: バリデーション（検証関数がある場合）
            if patch.validate_func:
                logger.info("Step 1: Running pre-execution validation...")
                validation_result = self._run_validation(patch)
                
                if not validation_result['valid']:
                    raise Exception(f"Pre-execution validation failed: {validation_result.get('reason', 'Unknown')}")
                
                logger.info("Pre-execution validation passed")
            
            # ステップ2: パッチ実行
            logger.info("Step 2: Executing patch...")
            result = self._run_patch_execute(patch)
            
            # ステップ3: 実行後検証（検証関数がある場合）
            if patch.validate_func:
                logger.info("Step 3: Running post-execution validation...")
                validation_result = self._run_validation(patch)
                
                if not validation_result['valid']:
                    logger.warning(f"Post-execution validation failed: {validation_result.get('reason', 'Unknown')}")
                    # ロールバック可能な場合は自動ロールバック
                    if patch.can_rollback:
                        logger.info("Attempting automatic rollback...")
                        self._run_patch_rollback(patch)
                        raise Exception("Post-execution validation failed, rolled back")
                    else:
                        raise Exception("Post-execution validation failed, rollback not available")
                
                logger.info("Post-execution validation passed")
            
            # 成功
            execution_time = time.time() - start_time
            record.status = PatchStatus.SUCCESS
            record.completed_at = datetime.utcnow()
            record.execution_time = execution_time
            record.result = result
            
            logger.info(f"Patch executed successfully in {execution_time:.2f}s")
            logger.info(f"Result: {result}")
            
            # パッチオブジェクトの状態を更新
            patch.status = PatchStatus.SUCCESS
            patch.executed_at = record.completed_at
            patch.execution_time = execution_time
            patch.result = result
            
        except Exception as e:
            # 失敗
            execution_time = time.time() - start_time
            error_message = str(e)
            error_traceback = traceback.format_exc()
            
            record.status = PatchStatus.FAILED
            record.completed_at = datetime.utcnow()
            record.execution_time = execution_time
            record.error_message = error_message
            
            logger.error(f"Patch execution failed: {error_message}")
            logger.error(f"Traceback:\n{error_traceback}")
            
            # パッチオブジェクトの状態を更新
            patch.status = PatchStatus.FAILED
            patch.executed_at = record.completed_at
            patch.execution_time = execution_time
            patch.error_message = error_message
        
        finally:
            self.current_execution = None
        
        logger.info(f"=" * 60)
        return record
    
    def rollback_patch(self, patch: Patch) -> PatchExecutionRecord:
        """
        パッチをロールバック
        
        Args:
            patch: パッチオブジェクト
        
        Returns:
            PatchExecutionRecord: ロールバック記録
        """
        if not patch.can_rollback:
            raise Exception(f"Patch {patch.id} cannot be rolled back")
        
        record = PatchExecutionRecord(
            patch_id=patch.id,
            status=PatchStatus.RUNNING,
            started_at=datetime.utcnow()
        )
        
        logger.info(f"=" * 60)
        logger.info(f"Rolling back patch: {patch.id} - {patch.name}")
        logger.info(f"=" * 60)
        
        start_time = time.time()
        
        try:
            # ロールバック実行
            logger.info("Executing rollback...")
            result = self._run_patch_rollback(patch)
            
            # 成功
            execution_time = time.time() - start_time
            record.status = PatchStatus.ROLLBACK
            record.completed_at = datetime.utcnow()
            record.execution_time = execution_time
            record.result = result
            
            logger.info(f"Patch rolled back successfully in {execution_time:.2f}s")
            
            # パッチオブジェクトの状態を更新
            patch.status = PatchStatus.ROLLBACK
            
        except Exception as e:
            # 失敗
            execution_time = time.time() - start_time
            error_message = str(e)
            error_traceback = traceback.format_exc()
            
            record.status = PatchStatus.FAILED
            record.completed_at = datetime.utcnow()
            record.execution_time = execution_time
            record.error_message = f"Rollback failed: {error_message}"
            
            logger.error(f"Rollback failed: {error_message}")
            logger.error(f"Traceback:\n{error_traceback}")
        
        logger.info(f"=" * 60)
        return record
    
    def _run_patch_execute(self, patch: Patch) -> Dict[str, Any]:
        """
        パッチのexecute関数を実行
        
        Args:
            patch: パッチオブジェクト
        
        Returns:
            Dict[str, Any]: 実行結果
        """
        try:
            result = patch.execute_func()
            
            # 結果が辞書でない場合は辞書化
            if not isinstance(result, dict):
                result = {'result': result, 'success': True}
            
            return result
        except Exception as e:
            logger.error(f"Error in patch execute function: {e}", exc_info=True)
            raise
    
    def _run_patch_rollback(self, patch: Patch) -> Dict[str, Any]:
        """
        パッチのrollback関数を実行
        
        Args:
            patch: パッチオブジェクト
        
        Returns:
            Dict[str, Any]: ロールバック結果
        """
        if not patch.rollback_func:
            raise Exception("No rollback function defined")
        
        try:
            result = patch.rollback_func()
            
            # 結果が辞書でない場合は辞書化
            if not isinstance(result, dict):
                result = {'result': result, 'success': True}
            
            return result
        except Exception as e:
            logger.error(f"Error in patch rollback function: {e}", exc_info=True)
            raise
    
    def _run_validation(self, patch: Patch) -> Dict[str, Any]:
        """
        パッチの検証関数を実行
        
        Args:
            patch: パッチオブジェクト
        
        Returns:
            Dict[str, Any]: 検証結果
        """
        if not patch.validate_func:
            return {'valid': True}
        
        try:
            result = patch.validate_func()
            
            # 結果が辞書でない場合は辞書化
            if isinstance(result, bool):
                result = {'valid': result}
            elif not isinstance(result, dict):
                result = {'valid': bool(result)}
            
            # validキーがない場合は追加
            if 'valid' not in result:
                result['valid'] = result.get('success', True)
            
            return result
        except Exception as e:
            logger.error(f"Error in patch validate function: {e}", exc_info=True)
            return {
                'valid': False,
                'reason': str(e)
            }
    
    def dry_run(self, patch: Patch) -> Dict[str, Any]:
        """
        ドライラン（実行シミュレーション）
        
        Args:
            patch: パッチオブジェクト
        
        Returns:
            Dict[str, Any]: シミュレーション結果
        """
        logger.info(f"Dry run for patch: {patch.id}")
        
        result = {
            'patch_id': patch.id,
            'patch_name': patch.name,
            'patch_type': patch.patch_type.value,
            'dependencies_met': True,
            'validation_passed': False,
            'estimated_risk': 'unknown',
            'can_execute': False
        }
        
        # 検証関数がある場合は実行
        if patch.validate_func:
            validation_result = self._run_validation(patch)
            result['validation_passed'] = validation_result['valid']
            result['validation_message'] = validation_result.get('reason', '')
        else:
            result['validation_passed'] = True
        
        # リスク評価
        if patch.is_critical:
            result['estimated_risk'] = 'high'
        elif patch.patch_type.value == 'hotfix':
            result['estimated_risk'] = 'medium'
        else:
            result['estimated_risk'] = 'low'
        
        # 実行可能性
        result['can_execute'] = result['validation_passed'] and result['dependencies_met']
        
        return result

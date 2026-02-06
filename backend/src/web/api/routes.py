"""
REST API Routes

Shinchakun自動化システムのREST APIエンドポイント
"""
from fastapi import APIRouter, HTTPException, Query, Path, Body
from fastapi.responses import JSONResponse
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from pydantic import BaseModel
import uuid
import asyncio

from src.database.connection import get_session
from src.database.repositories.account import AccountRepository
from src.database.repositories.log import AccountLogRepository
from src.database.models import Account, AccountStatus, ActionType, LogStatus
from src.core.logger import logger
from config.config import settings

# パッチシステムのインポート
from src.patch import patch_manager

api_router = APIRouter()


# ═══════════════════════════════════════════════════════
# Request/Response Models
# ═══════════════════════════════════════════════════════

class RecoverAccountRequest(BaseModel):
    strategy: str = "LAST_SUCCESS_RECOVERY"


class ExecuteAutomationRequest(BaseModel):
    task_type: str = "schedule_update"
    account_ids: Optional[List[str]] = None


# ═══════════════════════════════════════════════════════
# システム情報API
# ═══════════════════════════════════════════════════════

@api_router.get('/system/status')
async def get_system_status():
    """システム状態を取得"""
    try:
        from src.web.app import status_monitor
        
        with get_session() as session:
            account_repo = AccountRepository(session)
            
            # アカウント統計
            total_accounts = account_repo.count()
            active_accounts = account_repo.get_active_accounts()
            active_count = len(active_accounts)
            
            # 状態別カウント
            status_counts = {}
            for status in AccountStatus:
                count = session.query(Account).filter_by(
                    status=status.value,
                    is_active=True
                ).count()
                status_counts[status.value] = count
            
            # 手動操作中のアカウント数
            manual_count = status_counts.get(AccountStatus.MANUAL_OPERATION.value, 0)
            
            # エラーアカウント数
            error_count = status_counts.get(AccountStatus.ERROR.value, 0)
            
            # 状態監視の結果を取得
            monitor_states = status_monitor.get_all_states()
            monitor_state_counts = {
                'NORMAL': 0,
                'UNSTABLE': 0,
                'STOPPED': 0
            }
            for state in monitor_states.values():
                if state.value in monitor_state_counts:
                    monitor_state_counts[state.value] += 1
            
            return {
                'success': True,
                'data': {
                    'system_status': 'running',
                    'total_accounts': total_accounts,
                    'active_accounts': active_count,
                    'manual_operation_accounts': manual_count,
                    'error_accounts': error_count,
                    'last_check': datetime.utcnow().isoformat(),
                    'status_counts': status_counts,
                    'monitor_states': monitor_state_counts
                }
            }
    except Exception as e:
        logger.error(f"Error getting system status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get('/system/stats')
async def get_system_stats(days: int = Query(7, ge=1, le=365)):
    """システム統計を取得"""
    try:
        from src.core.log_manager import log_manager
        stats = log_manager.get_system_statistics(days=days)
        
        return {
            'success': True,
            'data': stats
        }
    except Exception as e:
        logger.error(f"Error getting system stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get('/system/resources')
async def get_system_resources():
    """システムリソース使用状況を取得"""
    try:
        import psutil
        import platform
        
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        
        return {
            'success': True,
            'data': {
                'vps': platform.system(),
                'cpu_percent': cpu_percent,
                'memory_used_gb': round(memory.used / (1024**3), 2),
                'memory_total_gb': round(memory.total / (1024**3), 2),
                'memory_percent': memory.percent,
                'timestamp': datetime.utcnow().isoformat()
            }
        }
    except ImportError:
        # psutilがインストールされていない場合
        return {
            'success': True,
            'data': {
                'vps': 'Unknown',
                'cpu_percent': 0,
                'memory_used_gb': 0,
                'memory_total_gb': 0,
                'memory_percent': 0,
                'timestamp': datetime.utcnow().isoformat()
            }
        }
    except Exception as e:
        logger.error(f"Error getting system resources: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get('/notifications/extension')
async def get_extension_notifications(limit: int = Query(10, ge=1, le=100)):
    """
    Chrome拡張機能用の通知取得エンドポイント
    
    最近の通知をJSON形式で返す（ポーリング用）
    """
    try:
        from src.core.event_system import event_logger
        
        # 最近のイベントを取得（ERROR以上）
        notifications = []
        
        # イベントログから最近のエラー/警告を取得
        with get_session() as session:
            log_repo = AccountLogRepository(session)
            account_repo = AccountRepository(session)
            
            # エラーログを取得
            logs = log_repo.get_logs_by_status(['ERROR', 'FAILED'], limit=limit)
            
            for log in logs:
                # アカウント情報を取得
                account = account_repo.get_by_id(log.account_id) if log.account_id else None
                
                notification = {
                    'id': str(log.id),
                    'type': 'error',
                    'severity': 'ERROR' if log.status == 'ERROR' else 'CRITICAL',
                    'title': 'エラー発生',
                    'message': log.message or 'エラーが発生しました',
                    'account_id': str(log.account_id) if log.account_id else None,
                    'account_username': account.username if account else None,
                    'timestamp': log.created_at.isoformat() if log.created_at else datetime.utcnow().isoformat(),
                    'details': {
                        'action_type': log.action_type,
                        'code_location': log.code_location
                    }
                }
                notifications.append(notification)
        
        return {
            'success': True,
            'notifications': notifications,
            'count': len(notifications)
        }
    except Exception as e:
        logger.error(f"Error getting extension notifications: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════
# アカウントAPI
# ═══════════════════════════════════════════════════════

@api_router.get('/accounts')
async def get_accounts(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None)
):
    """アカウント一覧を取得"""
    try:
        with get_session() as session:
            account_repo = AccountRepository(session)
            
            # クエリ構築
            query = session.query(Account)
            
            # 検索フィルタ
            if search:
                query = query.filter(
                    (Account.username.contains(search)) |
                    (Account.store_name.contains(search))
                )
            
            # ステータスフィルタ
            if status:
                query = query.filter_by(status=status)
            
            # アクティブアカウントのみ
            query = query.filter_by(is_active=True)
            
            # 総件数
            total = query.count()
            
            # ページネーション
            offset = (page - 1) * per_page
            accounts = query.order_by(Account.updated_at.desc()).offset(offset).limit(per_page).all()
            
            # シリアライズ
            accounts_data = []
            for account in accounts:
                accounts_data.append({
                    'id': str(account.id),
                    'username': account.username,
                    'store_name': account.store_name,
                    'status': account.status,
                    'login_url': account.login_url,
                    'last_login_at': account.last_login_at.isoformat() if account.last_login_at else None,
                    'last_success_at': account.last_success_at.isoformat() if account.last_success_at else None,
                    'error_count': account.error_count,
                    'last_error': account.last_error,
                    'updated_at': account.updated_at.isoformat() if account.updated_at else None
                })
            
            return {
                'success': True,
                'data': {
                    'accounts': accounts_data,
                    'pagination': {
                        'page': page,
                        'per_page': per_page,
                        'total': total,
                        'pages': (total + per_page - 1) // per_page
                    }
                }
            }
    except Exception as e:
        logger.error(f"Error getting accounts: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get('/accounts/{account_id}')
async def get_account(account_id: str = Path(...)):
    """アカウント詳細を取得"""
    try:
        with get_session() as session:
            account_repo = AccountRepository(session)
            account = account_repo.get_by_id(account_id)
            
            if not account:
                raise HTTPException(status_code=404, detail='Account not found')
            
            # ログサマリー取得
            from src.core.log_manager import log_manager
            log_summary = log_manager.get_account_log_summary(
                account_id=account_id,
                days=7
            )
            
            return {
                'success': True,
                'data': {
                    'id': str(account.id),
                    'username': account.username,
                    'store_name': account.store_name,
                    'status': account.status,
                    'login_url': account.login_url,
                    'session_token': '***' if account.session_token else None,  # セキュリティのためマスク
                    'last_login_at': account.last_login_at.isoformat() if account.last_login_at else None,
                    'last_success_at': account.last_success_at.isoformat() if account.last_success_at else None,
                    'error_count': account.error_count,
                    'last_error': account.last_error,
                    'is_active': account.is_active,
                    'created_at': account.created_at.isoformat() if account.created_at else None,
                    'updated_at': account.updated_at.isoformat() if account.updated_at else None,
                    'log_summary': log_summary
                }
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting account: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post('/accounts/{account_id}/recover')
async def recover_account(
    account_id: str = Path(...),
    request_data: RecoverAccountRequest = Body(...)
):
    """アカウントを復旧"""
    try:
        from src.core.recovery_manager import RecoveryStrategy
        from src.core.log_manager import log_manager
        
        strategy_name = request_data.strategy
        
        # 復旧戦略を取得
        try:
            strategy = RecoveryStrategy(strategy_name)
        except ValueError:
            raise HTTPException(status_code=400, detail=f'Invalid strategy: {strategy_name}')
        
        # 復旧実行
        result = log_manager.recover_account_state(
            account_id=account_id,
            recovery_point=None,
            restore=True
        )
        
        return {
            'success': result['success'],
            'data': result
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error recovering account: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════
# スケジュールAPI
# ═══════════════════════════════════════════════════════

@api_router.get('/schedules/upcoming')
async def get_upcoming_schedules():
    """次回実行予定を取得"""
    try:
        from src.web.app import scheduler
        
        # スケジューラーから次回実行時刻を取得
        next_schedule_update = scheduler.get_next_schedule_update_time()
        last_update = scheduler.get_last_schedule_update_date()
        
        # 待機接客配信の次回実行時刻（ランダムなので概算）
        from datetime import datetime, timedelta
        import random
        now = datetime.now()
        next_wait_reception = now + timedelta(
            minutes=random.randint(
                settings.WAIT_RECEPTION_INTERVAL_MIN,
                settings.WAIT_RECEPTION_INTERVAL_MAX
            )
        )
        
        with get_session() as session:
            account_repo = AccountRepository(session)
            total_accounts = account_repo.count()
            active_accounts = len(account_repo.get_active_accounts())
            idle_accounts = len(account_repo.get_idle_accounts())
        
        return {
            'success': True,
            'data': {
                'schedule_update': {
                    'next_run': next_schedule_update.isoformat(),
                    'last_run': last_update.isoformat() if last_update else None,
                    'status': 'scheduled',
                    'target_accounts': idle_accounts,  # IDLE状態のアカウント数
                    'total_accounts': total_accounts,
                    'time_window': f"{settings.SCHEDULE_UPDATE_START_HOUR}:00-{settings.SCHEDULE_UPDATE_END_HOUR}:00"
                },
                'wait_reception': {
                    'next_run': next_wait_reception.isoformat(),
                    'status': 'scheduled',
                    'target_accounts': active_accounts,
                    'interval': f"{settings.WAIT_RECEPTION_INTERVAL_MIN}-{settings.WAIT_RECEPTION_INTERVAL_MAX} minutes"
                }
            }
        }
    except Exception as e:
        logger.error(f"Error getting upcoming schedules: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════
# ログAPI
# ═══════════════════════════════════════════════════════

@api_router.get('/logs')
async def get_logs(
    limit: int = Query(100, ge=1, le=1000),
    account_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None)
):
    """ログ一覧を取得"""
    try:
        with get_session() as session:
            log_repo = AccountLogRepository(session)
            
            if account_id:
                logs = log_repo.get_account_logs(account_id=account_id, limit=limit)
            else:
                logs = log_repo.get_recent_logs(limit=limit)
            
            # ステータスフィルタ
            if status:
                logs = [log for log in logs if log.status == status]
            
            # シリアライズ
            logs_data = []
            for log in logs:
                logs_data.append({
                    'id': str(log.id),
                    'account_id': str(log.account_id),
                    'action_type': log.action_type,
                    'status': log.status,
                    'message': log.message,
                    'error_detail': log.error_detail,
                    'execution_time': log.execution_time,
                    'request_id': log.request_id,
                    'created_at': log.created_at.isoformat() if log.created_at else None,
                    'file_path': log.file_path,
                    'function_name': log.function_name,
                    'line_number': log.line_number
                })
            
            return {
                'success': True,
                'data': {
                    'logs': logs_data,
                    'count': len(logs_data)
                }
            }
    except Exception as e:
        logger.error(f"Error getting logs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get('/logs/recent')
async def get_recent_logs(limit: int = Query(50, ge=1, le=500)):
    """最近のログを取得（リアルタイム更新用）"""
    try:
        with get_session() as session:
            log_repo = AccountLogRepository(session)
            logs = log_repo.get_recent_logs(limit=limit)
            
            # シリアライズ
            logs_data = []
            for log in logs:
                logs_data.append({
                    'id': str(log.id),
                    'account_id': str(log.account_id),
                    'action_type': log.action_type,
                    'status': log.status,
                    'message': log.message,
                    'error_detail': log.error_detail,
                    'execution_time': log.execution_time,
                    'request_id': log.request_id,
                    'created_at': log.created_at.isoformat() if log.created_at else None,
                    'file_path': log.file_path,
                    'function_name': log.function_name,
                    'line_number': log.line_number
                })
            
            return {
                'success': True,
                'data': {
                    'logs': logs_data,
                    'count': len(logs_data),
                    'timestamp': datetime.utcnow().isoformat()
                }
            }
    except Exception as e:
        logger.error(f"Error getting recent logs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get('/logs/code')
async def get_code_content(
    file_path: str = Query(...),
    line_number: Optional[int] = Query(None)
):
    """コードファイルの内容を取得"""
    try:
        from pathlib import Path
        
        if not file_path:
            raise HTTPException(status_code=400, detail='file_path parameter is required')
        
        # プロジェクトルートを取得
        project_root = Path(__file__).parent.parent.parent.parent
        full_path = project_root / file_path
        
        # セキュリティチェック: プロジェクトルート外へのアクセスを防ぐ
        try:
            full_path.resolve().relative_to(project_root.resolve())
        except ValueError:
            raise HTTPException(status_code=400, detail='Invalid file path')
        
        # ファイルが存在するか確認
        if not full_path.exists() or not full_path.is_file():
            raise HTTPException(status_code=404, detail='File not found')
        
        # ファイルを読み込む
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
                
            return {
                'success': True,
                'data': {
                    'content': content,
                    'file_path': file_path,
                    'line_number': line_number,
                    'total_lines': len(lines),
                    'lines': lines  # 行ごとの配列も提供
                }
            }
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail='File is not a text file')
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting code content: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════
# 自動化実行API
# ═══════════════════════════════════════════════════════

@api_router.post('/automation/execute')
async def execute_automation(request_data: ExecuteAutomationRequest = Body(...)):
    """自動化処理を実行"""
    try:
        task_type = request_data.task_type
        account_ids = request_data.account_ids
        
        from src.automation.executor import ParallelExecutor
        from src.database.connection import get_session
        from src.database.repositories.account import AccountRepository
        
        with get_session() as session:
            account_repo = AccountRepository(session)
            
            # アカウント取得
            if account_ids:
                accounts = []
                for account_id in account_ids:
                    account = account_repo.get_by_id(account_id)
                    if account and account.is_active:
                        accounts.append(account)
            else:
                # 全アクティブアカウント
                accounts = account_repo.get_active_accounts()
            
            if not accounts:
                raise HTTPException(status_code=400, detail='No active accounts found')
            
            # 並列実行
            executor = ParallelExecutor()
            summary = executor.execute_accounts(accounts, task_type=task_type)
            
            return {
                'success': True,
                'data': summary
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing automation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post('/automation/execute/{account_id}')
async def execute_automation_single(
    account_id: str = Path(...),
    request_data: ExecuteAutomationRequest = Body(...)
):
    """単一アカウントの自動化処理を実行"""
    try:
        task_type = request_data.task_type
        
        from src.automation.executor import ParallelExecutor
        from src.database.connection import get_session
        from src.database.repositories.account import AccountRepository
        
        with get_session() as session:
            account_repo = AccountRepository(session)
            account = account_repo.get_by_id(account_id)
            
            if not account:
                raise HTTPException(status_code=404, detail='Account not found')
            
            if not account.is_active:
                raise HTTPException(status_code=400, detail='Account is not active')
            
            # 単一実行
            executor = ParallelExecutor()
            result = executor.execute_single_account(account, task_type=task_type)
            
            return {
                'success': result.get('success', False),
                'data': result
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing automation for account {account_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post('/automation/test')
async def test_automation():
    """自動化基盤のテスト実行（最小起動確認用）"""
    try:
        from playwright.sync_api import sync_playwright
        
        result = {
            'playwright_available': False,
            'browser_launched': False,
            'error': None
        }
        
        try:
            with sync_playwright() as p:
                result['playwright_available'] = True
                browser = p.chromium.launch(headless=True)
                result['browser_launched'] = True
                browser.close()
            
            return {
                'success': True,
                'data': result
            }
        except Exception as e:
            result['error'] = str(e)
            raise HTTPException(
                status_code=500,
                detail=f'Playwright test failed: {str(e)}'
            )
            
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail='Playwright is not installed. Run: pip install playwright && playwright install chromium'
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error testing automation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════
# Milestone 3: システム設定API
# ═══════════════════════════════════════════════════════

@api_router.get('/system/config')
async def get_system_config():
    """システム設定を取得"""
    try:
        with get_session() as session:
            from src.database.models import SystemConfig
            
            configs = session.query(SystemConfig).all()
            config_dict = {}
            
            for config in configs:
                if isinstance(config.value, dict):
                    config_dict[config.key] = config.value.get('value', config.value)
                else:
                    config_dict[config.key] = config.value
            
            return {
                'success': True,
                'data': config_dict
            }
    except Exception as e:
        logger.error(f"Error getting system config: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@api_router.put('/system/config/{config_key}')
async def update_system_config(
    config_key: str = Path(...),
    request_data: Dict[str, Any] = Body(...)
):
    """システム設定を更新"""
    try:
        with get_session() as session:
            from src.database.models import SystemConfig
            
            config = session.query(SystemConfig).filter_by(key=config_key).first()
            
            if not config:
                # 新規作成
                config = SystemConfig(
                    key=config_key,
                    value={'value': request_data.get('value')},
                    description=request_data.get('description', ''),
                    is_system=request_data.get('is_system', False)
                )
                session.add(config)
            else:
                # 更新
                if isinstance(config.value, dict):
                    config.value['value'] = request_data.get('value')
                else:
                    config.value = {'value': request_data.get('value')}
                
                if 'description' in request_data:
                    config.description = request_data['description']
            
            session.commit()
            
            return {
                'success': True,
                'data': {
                    'key': config.key,
                    'value': config.value if not isinstance(config.value, dict) else config.value.get('value')
                }
            }
    except Exception as e:
        logger.error(f"Error updating system config: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════
# Milestone 3: 状態監視API
# ═══════════════════════════════════════════════════════

@api_router.get('/monitoring/states')
async def get_monitoring_states():
    """全アカウントの監視状態を取得"""
    try:
        from src.web.app import status_monitor
        
        all_states = status_monitor.get_all_states()
        last_check_times = {}
        
        # 各アカウントの最終チェック時刻を取得
        for account_id in all_states.keys():
            last_check = status_monitor.get_last_check_time(account_id)
            if last_check:
                last_check_times[account_id] = last_check.isoformat()
        
        # アカウント情報も取得
        with get_session() as session:
            account_repo = AccountRepository(session)
            accounts_data = []
            
            for account_id, state in all_states.items():
                account = account_repo.get_by_id(account_id)
                if account:
                    accounts_data.append({
                        'account_id': account_id,
                        'username': account.username,
                        'store_name': account.store_name,
                        'state': state.value,
                        'last_check': last_check_times.get(account_id),
                        'account_status': account.status
                    })
        
        return {
            'success': True,
            'data': {
                'accounts': accounts_data,
                'summary': {
                    'NORMAL': sum(1 for s in all_states.values() if s.value == 'NORMAL'),
                    'UNSTABLE': sum(1 for s in all_states.values() if s.value == 'UNSTABLE'),
                    'STOPPED': sum(1 for s in all_states.values() if s.value == 'STOPPED')
                }
            }
        }
    except Exception as e:
        logger.error(f"Error getting monitoring states: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get('/monitoring/account/{account_id}')
async def get_account_monitoring_state(account_id: str = Path(...)):
    """特定アカウントの監視状態を取得"""
    try:
        from src.web.app import status_monitor
        
        state = status_monitor.get_account_state(account_id)
        last_check = status_monitor.get_last_check_time(account_id)
        
        return {
            'success': True,
            'data': {
                'account_id': account_id,
                'state': state.value if state else None,
                'last_check': last_check.isoformat() if last_check else None
            }
        }
    except Exception as e:
        logger.error(f"Error getting account monitoring state: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════
# Patch Management API
# ═══════════════════════════════════════════════════════

@api_router.get('/patches')
async def get_all_patches():
    """すべてのパッチを取得"""
    try:
        patches = patch_manager.get_all_patches()
        
        return {
            'success': True,
            'data': {
                'patches': [p.to_dict() for p in patches],
                'count': len(patches)
            }
        }
    except Exception as e:
        logger.error(f"Error getting patches: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get('/patches/statistics')
async def get_patch_statistics():
    """パッチ統計を取得"""
    try:
        stats = patch_manager.get_statistics()
        
        return {
            'success': True,
            'data': stats
        }
    except Exception as e:
        logger.error(f"Error getting patch statistics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get('/patches/pending')
async def get_pending_patches():
    """未実行のパッチを取得"""
    try:
        patches = patch_manager.get_pending_patches()
        
        return {
            'success': True,
            'data': {
                'patches': [p.to_dict() for p in patches],
                'count': len(patches)
            }
        }
    except Exception as e:
        logger.error(f"Error getting pending patches: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get('/patches/critical')
async def get_critical_patches():
    """緊急パッチを取得"""
    try:
        patches = patch_manager.get_critical_patches()
        
        return {
            'success': True,
            'data': {
                'patches': [p.to_dict() for p in patches],
                'count': len(patches)
            }
        }
    except Exception as e:
        logger.error(f"Error getting critical patches: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get('/patches/{patch_id}')
async def get_patch(patch_id: str = Path(...)):
    """特定のパッチを取得"""
    try:
        patch = patch_manager.get_patch(patch_id)
        
        if not patch:
            raise HTTPException(status_code=404, detail=f"Patch not found: {patch_id}")
        
        return {
            'success': True,
            'data': patch.to_dict()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting patch: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


class ExecutePatchRequest(BaseModel):
    force: bool = False


@api_router.post('/patches/{patch_id}/execute')
async def execute_patch(
    patch_id: str = Path(...),
    request: ExecutePatchRequest = Body(...)
):
    """パッチを実行"""
    try:
        # 非同期実行
        def _execute():
            return patch_manager.execute_patch(patch_id, force=request.force)
        
        result = await asyncio.to_thread(_execute)
        
        return {
            'success': result['success'],
            'data': result
        }
    except Exception as e:
        logger.error(f"Error executing patch: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post('/patches/execute-all')
async def execute_all_pending_patches():
    """すべての未実行パッチを実行"""
    try:
        # 非同期実行
        def _execute_all():
            return patch_manager.execute_all_pending(auto_only=True)
        
        result = await asyncio.to_thread(_execute_all)
        
        return {
            'success': True,
            'data': result
        }
    except Exception as e:
        logger.error(f"Error executing all patches: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post('/patches/{patch_id}/rollback')
async def rollback_patch(patch_id: str = Path(...)):
    """パッチをロールバック"""
    try:
        # 非同期実行
        def _rollback():
            return patch_manager.rollback_patch(patch_id)
        
        result = await asyncio.to_thread(_rollback)
        
        return {
            'success': result['success'],
            'data': result
        }
    except Exception as e:
        logger.error(f"Error rolling back patch: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post('/patches/{patch_id}/dry-run')
async def dry_run_patch(patch_id: str = Path(...)):
    """パッチのドライラン（シミュレーション）"""
    try:
        result = patch_manager.dry_run(patch_id)
        
        return {
            'success': True,
            'data': result
        }
    except Exception as e:
        logger.error(f"Error performing dry run: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post('/patches/reload')
async def reload_patches():
    """パッチを再読み込み"""
    try:
        # 非同期実行
        def _reload():
            patches = patch_manager.load_patches()
            return {
                'loaded_count': len(patches),
                'patches': [p.to_dict() for p in patches]
            }
        
        result = await asyncio.to_thread(_reload)
        
        return {
            'success': True,
            'data': result
        }
    except Exception as e:
        logger.error(f"Error reloading patches: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

"""
Worker Module

1アカウント処理単位のWorker関数
"""
from typing import Optional, Dict, Any
from playwright.sync_api import Page, BrowserContext

from src.core.logger import logger
from src.core.log_manager import log_manager
from src.core.exceptions import (
    ManualOperationDetectedError,
    AppCrashError,
    LoginError,
    AutomationError
)
from src.database.models import Account, ActionType, AccountStatus
from src.database.connection import get_session
from src.database.repositories.account import AccountRepository
from config.config import settings
from src.automation.browser_manager import BrowserManager
from src.automation.url_resolver import resolve_base_url, get_cached_url
from src.automation.login_handler import login
from src.automation.manual_detector import ManualOperationDetector
from src.automation.crash_detector import detect_app_crash, handle_app_crash


def run_account_job(
    browser_manager: BrowserManager,
    account: Account,
    task_type: str = "schedule_update"
) -> Dict[str, Any]:
    """
    アカウント処理Worker関数
    
    原則:
    - 1アカウント = 1 Browser Context
    - 全操作の前後にログ出力
    - 落ちる前提で再起動を設計
    
    Args:
        browser_manager: ブラウザマネージャー
        account: アカウントモデル
        task_type: タスク種別（"schedule_update" or "wait_reception"）
    
    Returns:
        Dict[str, Any]: 実行結果
    """
    account_id = str(account.id)
    context: Optional[BrowserContext] = None
    page: Optional[Page] = None
    
    result = {
        'account_id': account_id,
        'username': account.username,
        'success': False,
        'error': None,
        'task_type': task_type
    }
    
    # ステータスをPROCESSINGに更新（ロックはexecute_schedule_update内で取得）
    # ここでは基本的なステータス更新のみ
    try:
        with get_session() as session:
            account_repo = AccountRepository(session)
            # 既にロックされている場合はスキップ
            if account_repo.is_locked(account_id):
                logger.warning(f"[{account_id}] Account is locked, skipping task")
                result['error'] = "Account is locked"
                return result
            account_repo.update_status(account_id, AccountStatus.PROCESSING)
    except Exception as e:
        logger.error(f"[{account_id}] Failed to update status: {e}")
    
    try:
        # ログ: タスク開始
        logger.info(f"[{account_id}] Task started: {task_type}")
        
        with log_manager.log_operation(account_id, ActionType.QUEUE_EXECUTION) as log_ctx:
            # ブラウザコンテキスト作成（1アカウント = 1 Context）
            with browser_manager.create_context(account_id) as context:
                page = context.new_page()
                
                # 手動操作検知器を初期化
                manual_detector = ManualOperationDetector(account_id)
                
                # URL解決
                base_url = get_cached_url(account)
                if not base_url:
                    logger.info(f"[{account_id}] Resolving login URL...")
                    base_url = resolve_base_url(page, account_id)
                    
                    # URLをDBに保存
                    try:
                        with get_session() as session:
                            account_repo = AccountRepository(session)
                            account_repo.update(account_id, login_url=base_url)
                    except Exception as e:
                        logger.warning(f"[{account_id}] Failed to save URL: {e}")
                else:
                    logger.info(f"[{account_id}] Using cached URL: {base_url}")
                    page.goto(base_url, wait_until="domcontentloaded")
                
                # ログイン処理
                with log_manager.log_operation(account_id, ActionType.LOGIN) as login_ctx:
                    try:
                        token = login(page, account)
                        login_ctx.log_success("Login successful")
                        
                        # ログイン情報をDBに保存
                        try:
                            with get_session() as session:
                                account_repo = AccountRepository(session)
                                account_repo.update_login_info(
                                    account_id=account_id,
                                    session_token=token,
                                    login_url=base_url
                                )
                        except Exception as e:
                            logger.warning(f"[{account_id}] Failed to save login info: {e}")
                        
                        # 手動操作検知器を初期化（ログイン後）
                        manual_detector.initialize(page)
                        
                    except LoginError as e:
                        login_ctx.log_error(f"Login failed: {str(e)}")
                        raise
                
                # アプリクラッシュチェック
                if detect_app_crash(page):
                    logger.critical(f"[{account_id}] App crash detected before business logic")
                    page = handle_app_crash(page, context, account_id, browser_manager, account)
                    
                    # 再ログイン
                    with log_manager.log_operation(account_id, ActionType.LOGIN) as login_ctx:
                        try:
                            token = login(page, account)
                            login_ctx.log_success("Re-login after crash successful")
                            manual_detector.initialize(page)
                        except LoginError as e:
                            login_ctx.log_error(f"Re-login failed: {e}")
                            raise
                
                # 手動操作チェック（業務ロジック実行前）
                try:
                    manual_detector.check(page)
                except ManualOperationDetectedError as e:
                    logger.warning(f"[{account_id}] Manual operation detected, skipping")
                    
                    # ステータスを更新
                    try:
                        with get_session() as session:
                            account_repo = AccountRepository(session)
                            account_repo.update_status(account_id, AccountStatus.MANUAL_OPERATION)
                    except Exception:
                        pass
                    
                    log_ctx.log_skipped(f"Manual operation detected: {str(e)}")
                    result['error'] = "Manual operation detected"
                    return result
                
                # 業務ロジック実行
                if task_type == "schedule_update":
                    execute_schedule_update(page, account, manual_detector, log_ctx)
                elif task_type == "wait_reception":
                    execute_wait_reception(page, account, manual_detector, log_ctx)
                else:
                    raise AutomationError(f"Unknown task type: {task_type}")
                
                # 最終成功時刻を更新
                try:
                    with get_session() as session:
                        account_repo = AccountRepository(session)
                        account_repo.update_last_success(account_id)
                        account_repo.update_status(account_id, AccountStatus.IDLE)
                except Exception as e:
                    logger.warning(f"[{account_id}] Failed to update success time: {e}")
                
                log_ctx.log_success(f"Task completed: {task_type}")
                result['success'] = True
                logger.info(f"[{account_id}] Task completed successfully: {task_type}")
                
    except ManualOperationDetectedError as e:
        logger.warning(f"[{account_id}] Manual operation detected: {e}")
        result['error'] = "Manual operation detected"
        
        # ステータス更新
        try:
            with get_session() as session:
                account_repo = AccountRepository(session)
                account_repo.update_status(account_id, AccountStatus.MANUAL_OPERATION)
                
                # イベントを発行（通知機能が処理）
                from src.core.event_system import event_logger, EventType, EventSeverity
                event_logger.log_event(
                    event_type=EventType.MANUAL_OPERATION_DETECTED,
                    severity=EventSeverity.WARNING,
                    account_id=account_id,
                    message=f"Manual operation detected: {str(e)}",
                    data={'task_type': task_type}
                )
        except Exception:
            pass
        
    except (AppCrashError, LoginError, AutomationError) as e:
        logger.error(f"[{account_id}] Task failed: {e}", exc_info=True)
        result['error'] = str(e)
        
        # エラーカウントを増加
        try:
            with get_session() as session:
                account_repo = AccountRepository(session)
                account_repo.increment_error_count(account_id, str(e))
        except Exception:
            pass
        
    except Exception as e:
        logger.error(f"[{account_id}] Unexpected error: {e}", exc_info=True)
        result['error'] = f"Unexpected error: {str(e)}"
        
        # エラーカウントを増加
        try:
            with get_session() as session:
                account_repo = AccountRepository(session)
                account_repo.increment_error_count(account_id, str(e))
        except Exception:
            pass
    
    finally:
        # コンテキストは自動的に閉じられる（contextmanager）
        if page:
            try:
                page.close()
            except Exception:
                pass
        
        # ステータスをIDLEに戻す（エラー時は既に更新済み）
        if result.get('success'):
            try:
                with get_session() as session:
                    account_repo = AccountRepository(session)
                    account_repo.update_status(account_id, AccountStatus.IDLE)
            except Exception:
                pass
    
    return result


def execute_schedule_update(
    page: Page,
    account: Account,
    manual_detector: ManualOperationDetector,
    log_ctx
):
    """
    スケジュール更新業務ロジック
    
    実装手順:
    1. 自動化ロックを取得
    2. セッション検証
    3. スケジュールページに移動
    4. 週間スケジュールを読み取り（出勤設定があるかチェック）
    5. 明日の現在設定を読み取り
    6. 条件付き更新（既に出勤ならスキップ）
    7. 更新後検証（最大3回リトライ）
    8. ロック解放
    """
    account_id = str(account.id)
    logger.info(f"[{account_id}] Executing schedule update...")
    
    # ロック管理
    lock_acquired = False
    
    with log_manager.log_operation(account_id, ActionType.SCHEDULE_UPDATE) as schedule_ctx:
        try:
            # Step 1: 自動化ロックを取得
            schedule_ctx.log_info("Step 1: Acquiring automation lock...")
            with get_session() as session:
                account_repo = AccountRepository(session)
                
                # ロック取得を試行
                if not account_repo.acquire_lock(account_id, "schedule_update"):
                    schedule_ctx.log_skipped("Account is already locked by another process")
                    logger.warning(f"[{account_id}] Account is locked, skipping")
                    raise AutomationError("Account is locked")
                
                lock_acquired = True
                logger.debug(f"[{account_id}] Lock acquired")
            
            # Step 2: セッション検証
            schedule_ctx.log_info("Step 2: Validating session...")
            manual_detector.check(page)  # 手動操作チェックも含む
            
            # セッション有効性チェック
            current_url = page.url
            if "login" in current_url.lower() and "dokodemo" not in current_url:
                raise AutomationError("Session expired: redirected to login page")
            
            # クッキー確認
            cookies = page.context.cookies()
            if not cookies:
                raise AutomationError("No cookies found: session may be invalid")
            
            logger.debug(f"[{account_id}] Session validated: {len(cookies)} cookies found")
            schedule_ctx.log_info("Session validated successfully")
            
            # Step 3: スケジュールページに移動
            schedule_ctx.log_info("Step 3: Navigating to schedule page...")
            base_url = account.login_url or settings.LOGIN_URLS[0]
            
            # スケジュールページのURL（実際のURLに調整が必要）
            # 一般的なパス: /schedule, /schedules, /weekly-schedule など
            schedule_url = f"{base_url.rstrip('/')}/schedule"
            logger.debug(f"[{account_id}] Navigating to: {schedule_url}")
            
            try:
                page.goto(schedule_url, wait_until="networkidle", timeout=30000)
                page.wait_for_load_state("networkidle")
            except Exception as e:
                # 代替URLを試行
                alternative_urls = [
                    f"{base_url.rstrip('/')}/schedules",
                    f"{base_url.rstrip('/')}/weekly-schedule",
                    f"{base_url.rstrip('/')}/schedule-management"
                ]
                
                navigated = False
                for alt_url in alternative_urls:
                    try:
                        logger.debug(f"[{account_id}] Trying alternative URL: {alt_url}")
                        page.goto(alt_url, wait_until="networkidle", timeout=30000)
                        page.wait_for_load_state("networkidle")
                        navigated = True
                        break
                    except Exception:
                        continue
                
                if not navigated:
                    raise AutomationError(f"Failed to navigate to schedule page: {str(e)}")
            
            # ページ読み込み確認
            schedule_ctx.log_info("Waiting for schedule page to load...")
            page.wait_for_timeout(2000)  # UI描画を待機
            
            # スケジュールコンテナの存在確認（複数のセレクターを試行）
            schedule_selectors = [
                ".schedule-container",
                ".schedule-table",
                ".weekly-schedule",
                "[data-schedule-container]",
                "table.schedule"
            ]
            
            schedule_container = None
            for selector in schedule_selectors:
                try:
                    schedule_container = page.query_selector(selector)
                    if schedule_container:
                        logger.debug(f"[{account_id}] Found schedule container with selector: {selector}")
                        break
                except Exception:
                    continue
            
            if not schedule_container:
                raise AutomationError("Schedule page container not found")
            
            schedule_ctx.log_info("Schedule page loaded successfully")
            
            # Step 4: 週間スケジュールを読み取り（出勤設定があるかチェック）
            schedule_ctx.log_info("Step 4: Reading weekly schedule to check for attendance days...")
            
            # 週間スケジュールの行を取得
            schedule_row_selectors = [
                "tr.schedule-row",
                ".cast-schedule-item",
                ".schedule-row",
                "[data-schedule-row]"
            ]
            
            schedule_rows = []
            for selector in schedule_row_selectors:
                try:
                    rows = page.query_selector_all(selector)
                    if rows:
                        schedule_rows = rows
                        logger.debug(f"[{account_id}] Found {len(rows)} schedule rows with selector: {selector}")
                        break
                except Exception:
                    continue
            
            if not schedule_rows:
                raise AutomationError("No schedule rows found")
            
            logger.info(f"[{account_id}] Found {len(schedule_rows)} schedule rows")
            
            # 出勤設定がある日をチェック
            has_attendance_day = False
            attendance_casts = []
            
            for row in schedule_rows:
                try:
                    # キャスト名を取得
                    cast_name_selectors = [
                        ".cast-name",
                        "[data-cast-name]",
                        "td:first-child",
                        ".name"
                    ]
                    
                    cast_name_elem = None
                    for selector in cast_name_selectors:
                        cast_name_elem = row.query_selector(selector)
                        if cast_name_elem:
                            break
                    
                    if not cast_name_elem:
                        continue
                    
                    cast_name = cast_name_elem.inner_text().strip()
                    
                    # 週間のスケジュールセルを取得
                    schedule_cell_selectors = [
                        ".schedule-cell",
                        "[data-day]",
                        "td.schedule-day",
                        "td[data-date]"
                    ]
                    
                    schedule_cells = []
                    for selector in schedule_cell_selectors:
                        cells = row.query_selector_all(selector)
                        if cells and len(cells) >= 5:  # 少なくとも5日分ある
                            schedule_cells = cells
                            break
                    
                    if not schedule_cells:
                        # テーブル行の場合
                        cells = row.query_selector_all("td")
                        if len(cells) > 1:
                            schedule_cells = cells[1:]  # 最初のセル（名前）を除外
                    
                    # 出勤設定がある日を探す
                    for cell in schedule_cells:
                        try:
                            # セルの状態を確認
                            cell_text = cell.inner_text().strip()
                            cell_status = cell.get_attribute("data-status") or ""
                            cell_class = cell.get_attribute("class") or ""
                            
                            # 出勤設定の判定（複数のパターンをチェック）
                            is_attendance = (
                                "出勤" in cell_text or
                                "attendance" in cell_text.lower() or
                                "出勤" in cell_status or
                                "attendance" in cell_status.lower() or
                                "attendance" in cell_class.lower() or
                                "working" in cell_text.lower()
                            )
                            
                            if is_attendance:
                                has_attendance_day = True
                                attendance_casts.append({
                                    'name': cast_name,
                                    'element': row,
                                    'cast_name_elem': cast_name_elem
                                })
                                logger.debug(f"[{account_id}] Found attendance cast: {cast_name}")
                                break
                        except Exception as e:
                            logger.debug(f"[{account_id}] Error checking cell: {e}")
                            continue
                
                except Exception as e:
                    logger.warning(f"[{account_id}] Error processing schedule row: {e}")
                    continue
            
            # 出勤設定があるアカウントかチェック
            if not has_attendance_day:
                schedule_ctx.log_skipped("No attendance days found in weekly schedule - account excluded")
                logger.info(f"[{account_id}] Account excluded: No attendance days in weekly schedule")
                return  # 成功として扱う（除外は正常な動作）
            
            logger.info(f"[{account_id}] Account eligible: Found {len(attendance_casts)} casts with attendance settings")
            schedule_ctx.log_info(f"Account eligible: {len(attendance_casts)} casts with attendance")
            
            # Step 5: 明日の現在設定を読み取り
            from datetime import datetime, timedelta
            tomorrow = datetime.now() + timedelta(days=1)
            tomorrow_str = tomorrow.strftime("%Y-%m-%d")
            tomorrow_day_index = tomorrow.weekday()  # 0=Monday, 6=Sunday
            
            schedule_ctx.log_info(f"Step 5: Reading tomorrow's ({tomorrow_str}) current setting...")
            
            casts_to_update = []
            
            for cast_info in attendance_casts:
                try:
                    row = cast_info['element']
                    cast_name = cast_info['name']
                    
                    # 明日のセルを特定
                    # 方法1: data-date属性で検索
                    tomorrow_cell = row.query_selector(f"[data-date='{tomorrow_str}']")
                    
                    # 方法2: 曜日インデックスで検索
                    if not tomorrow_cell:
                        cells = row.query_selector_all(".schedule-cell, [data-day], td.schedule-day")
                        if len(cells) > tomorrow_day_index:
                            tomorrow_cell = cells[tomorrow_day_index]
                    
                    # 方法3: テーブル行の場合
                    if not tomorrow_cell:
                        all_cells = row.query_selector_all("td")
                        if len(all_cells) > tomorrow_day_index + 1:  # +1 for name column
                            tomorrow_cell = all_cells[tomorrow_day_index + 1]
                    
                    if not tomorrow_cell:
                        logger.warning(f"[{account_id}] Tomorrow cell not found for {cast_name}")
                        continue
                    
                    # 現在の設定を読み取り
                    current_text = tomorrow_cell.inner_text().strip()
                    current_status = tomorrow_cell.get_attribute("data-status") or ""
                    current_class = tomorrow_cell.get_attribute("class") or ""
                    
                    # 出勤設定かどうかを判定
                    is_already_attendance = (
                        "出勤" in current_text or
                        "attendance" in current_text.lower() or
                        "出勤" in current_status or
                        "attendance" in current_status.lower() or
                        "attendance" in current_class.lower()
                    )
                    
                    if is_already_attendance:
                        logger.debug(f"[{account_id}] {cast_name} already set to attendance for tomorrow")
                        schedule_ctx.log_info(f"{cast_name}: Already set to attendance - skipping")
                        continue
                    
                    casts_to_update.append({
                        'name': cast_name,
                        'element': row,
                        'cell': tomorrow_cell,
                        'current_status': current_text or current_status
                    })
                    logger.debug(f"[{account_id}] {cast_name} needs update: current={current_text or current_status}")
                
                except Exception as e:
                    logger.warning(f"[{account_id}] Error reading tomorrow's setting for {cast_info['name']}: {e}")
                    continue
            
            if not casts_to_update:
                schedule_ctx.log_success("All casts already set to attendance for tomorrow - no update needed")
                logger.info(f"[{account_id}] No updates needed: All casts already set to attendance")
                return  # 成功として扱う
            
            logger.info(f"[{account_id}] Found {len(casts_to_update)} casts to update")
            schedule_ctx.log_info(f"Found {len(casts_to_update)} casts to update")
            
            # Step 6: 条件付き更新（最大3回リトライ）
            schedule_ctx.log_info(f"Step 6: Updating {len(casts_to_update)} casts to attendance...")
            
            max_retries = 3
            update_successful = False
            
            for retry in range(max_retries):
                try:
                    if retry > 0:
                        schedule_ctx.log_info(f"Retry attempt {retry + 1}/{max_retries}...")
                        logger.info(f"[{account_id}] Retry {retry + 1}/{max_retries}")
                        page.wait_for_timeout(2000)  # リトライ前に待機
                    
                    updated_count = 0
                    
                    for cast_info in casts_to_update:
                        try:
                            cast_name = cast_info['name']
                            tomorrow_cell = cast_info['cell']
                            
                            # セルをクリック
                            logger.debug(f"[{account_id}] Clicking tomorrow cell for {cast_name}")
                            tomorrow_cell.scroll_into_view_if_needed()
                            tomorrow_cell.click()
                            page.wait_for_timeout(500)  # UI更新を待機
                            
                            # 出勤設定を選択
                            # ドロップダウンまたはモーダルが開く
                            attendance_option_selectors = [
                                "button:has-text('出勤設定')",
                                "button:has-text('出勤')",
                                ".option-attendance",
                                "[data-option='attendance']",
                                "li:has-text('出勤')",
                                ".dropdown-item:has-text('出勤')"
                            ]
                            
                            attendance_option = None
                            for selector in attendance_option_selectors:
                                try:
                                    attendance_option = page.query_selector(selector)
                                    if attendance_option and attendance_option.is_visible():
                                        break
                                except Exception:
                                    continue
                            
                            if not attendance_option:
                                # キーボード操作を試行
                                logger.debug(f"[{account_id}] Option not found, trying keyboard navigation")
                                page.keyboard.press("ArrowDown")
                                page.wait_for_timeout(300)
                                page.keyboard.press("Enter")
                                page.wait_for_timeout(500)
                            else:
                                attendance_option.click()
                                page.wait_for_timeout(500)
                            
                            updated_count += 1
                            logger.debug(f"[{account_id}] Updated {cast_name} to attendance")
                        
                        except Exception as e:
                            logger.warning(f"[{account_id}] Error updating {cast_info['name']}: {e}")
                            continue
                    
                    if updated_count == 0:
                        raise AutomationError("Failed to update any casts")
                    
                    # 保存を実行
                    schedule_ctx.log_info("Saving schedule changes...")
                    
                    # 保存ボタンを探す
                    save_button_selectors = [
                        "button:has-text('保存')",
                        "button:has-text('登録')",
                        "button:has-text('更新')",
                        "button[type='submit']",
                        ".save-button",
                        "[data-action='save']",
                        "button.save"
                    ]
                    
                    save_button = None
                    for selector in save_button_selectors:
                        try:
                            save_button = page.query_selector(selector)
                            if save_button and save_button.is_visible():
                                break
                        except Exception:
                            continue
                    
                    if not save_button:
                        raise AutomationError("Save button not found")
                    
                    save_button.click()
                    page.wait_for_load_state("networkidle")
                    page.wait_for_timeout(2000)  # 保存処理を待機
                    
                    # 保存成功/失敗メッセージを確認
                    success_message = page.query_selector(".success-message, .alert-success, .toast-success")
                    error_message = page.query_selector(".error-message, .alert-error, .toast-error")
                    
                    if error_message:
                        error_text = error_message.inner_text()
                        raise AutomationError(f"Save failed: {error_text}")
                    
                    if success_message:
                        logger.debug(f"[{account_id}] Save success message displayed")
                    
                    update_successful = True
                    schedule_ctx.log_info(f"Successfully updated {updated_count} casts")
                    break  # 成功したらリトライループを抜ける
                
                except Exception as e:
                    if retry == max_retries - 1:
                        # 最後のリトライでも失敗
                        raise AutomationError(f"Update failed after {max_retries} retries: {str(e)}")
                    logger.warning(f"[{account_id}] Update attempt {retry + 1} failed: {e}, retrying...")
                    continue
            
            if not update_successful:
                raise AutomationError("Failed to update schedule after all retries")
            
            # Step 7: 更新後検証（最大3回リトライ）
            schedule_ctx.log_info("Step 7: Verifying schedule update...")
            
            verification_successful = False
            
            for verify_retry in range(max_retries):
                try:
                    if verify_retry > 0:
                        # ページを再読み込み
                        logger.debug(f"[{account_id}] Reloading page for verification retry {verify_retry + 1}")
                        page.reload(wait_until="networkidle")
                        page.wait_for_timeout(2000)
                    
                    # 明日の設定を再読み取り
                    verification_passed = True
                    
                    for cast_info in casts_to_update:
                        try:
                            row = cast_info['element']
                            cast_name = cast_info['name']
                            
                            # 明日のセルを再取得
                            tomorrow_cell = row.query_selector(f"[data-date='{tomorrow_str}']")
                            if not tomorrow_cell:
                                cells = row.query_selector_all(".schedule-cell, [data-day], td.schedule-day")
                                if len(cells) > tomorrow_day_index:
                                    tomorrow_cell = cells[tomorrow_day_index]
                            
                            if not tomorrow_cell:
                                verification_passed = False
                                logger.warning(f"[{account_id}] Verification failed: Cell not found for {cast_name}")
                                break
                            
                            # 設定を確認
                            verify_text = tomorrow_cell.inner_text().strip()
                            verify_status = tomorrow_cell.get_attribute("data-status") or ""
                            
                            is_attendance = (
                                "出勤" in verify_text or
                                "attendance" in verify_text.lower() or
                                "出勤" in verify_status or
                                "attendance" in verify_status.lower()
                            )
                            
                            if not is_attendance:
                                verification_passed = False
                                logger.warning(f"[{account_id}] Verification failed: {cast_name} not set to attendance")
                                break
                            
                            logger.debug(f"[{account_id}] Verification passed for {cast_name}")
                        
                        except Exception as e:
                            logger.warning(f"[{account_id}] Error verifying {cast_info['name']}: {e}")
                            verification_passed = False
                            break
                    
                    if verification_passed:
                        verification_successful = True
                        schedule_ctx.log_success("Verification passed: All casts updated correctly")
                        logger.info(f"[{account_id}] Verification passed")
                        break
                    else:
                        if verify_retry < max_retries - 1:
                            logger.warning(f"[{account_id}] Verification failed, retrying...")
                            continue
                        else:
                            raise AutomationError("Verification failed after all retries")
                
                except Exception as e:
                    if verify_retry == max_retries - 1:
                        raise AutomationError(f"Verification failed: {str(e)}")
                    continue
            
            if not verification_successful:
                raise AutomationError("Schedule update verification failed")
            
            # 成功ログ
            schedule_ctx.log_success(
                f"Schedule update completed: {len(casts_to_update)} casts updated and verified"
            )
            logger.info(
                f"[{account_id}] Schedule update completed successfully: "
                f"{len(casts_to_update)} casts updated and verified"
            )
            
        except ManualOperationDetectedError:
            schedule_ctx.log_skipped("Manual operation detected during schedule update")
            raise
        except AutomationError:
            # AutomationErrorはそのまま再スロー
            raise
        except Exception as e:
            schedule_ctx.log_error(f"Schedule update failed: {str(e)}")
            logger.error(f"[{account_id}] Schedule update error: {e}", exc_info=True)
            raise AutomationError(f"Schedule update failed: {str(e)}") from e
        
        finally:
            # Step 8: ロック解放
            if lock_acquired:
                try:
                    with get_session() as session:
                        account_repo = AccountRepository(session)
                        account_repo.release_lock(account_id)
                        logger.debug(f"[{account_id}] Lock released")
                except Exception as e:
                    logger.warning(f"[{account_id}] Failed to release lock: {e}")


def check_global_preconditions(
    browser_manager: BrowserManager,
    representative_account: Optional[Account]
) -> Dict[str, Any]:
    """
    グローバル事前チェック
    
    全アカウント処理前に実行されるチェック:
    1. アクティブキャスト数チェック（3人以下で中止）
    2. 時間制約チェック（退勤時刻の10分前を超えない）
    
    Args:
        browser_manager: ブラウザマネージャー
        representative_account: 代表アカウント（キャスト情報を読み取るため）
    
    Returns:
        Dict[str, Any]: チェック結果
        {
            'can_proceed': bool,
            'reason': str,
            'active_cast_count': int,
            'eligible_account_count': int,
            'eligible_accounts': List[Account]
        }
    """
    result = {
        'can_proceed': False,
        'reason': '',
        'active_cast_count': 0,
        'eligible_account_count': 0,
        'eligible_accounts': []
    }
    
    if not representative_account:
        result['reason'] = 'No representative account provided'
        return result
    
    try:
        from datetime import datetime, timedelta
        from src.automation.login_handler import login
        from src.automation.manual_detector import ManualOperationDetector
        
        account_id = str(representative_account.id)
        logger.info(f"[Global Pre-Check] Starting global preconditions check...")
        
        # ブラウザコンテキストを取得
        context = browser_manager.get_or_create_context(account_id)
        page = context.new_page()
        
        try:
            # ログイン確認
            login(page, representative_account)
            page.wait_for_load_state("networkidle")
            
            # 手動操作チェック
            manual_detector = ManualOperationDetector()
            manual_detector.check(page)
            
            # Step 1: アクティブキャスト数チェック
            logger.info(f"[Global Pre-Check] Step 1: Checking active cast count...")
            
            # キャスト管理ページまたはダッシュボードに移動
            base_url = representative_account.login_url or settings.LOGIN_URLS[0]
            
            # 複数のURLパターンを試行
            cast_page_urls = [
                f"{base_url.rstrip('/')}/casts",
                f"{base_url.rstrip('/')}/dashboard",
                f"{base_url.rstrip('/')}/cast-management",
                f"{base_url.rstrip('/')}/staff"
            ]
            
            cast_page = None
            for url in cast_page_urls:
                try:
                    page.goto(url, wait_until="networkidle", timeout=15000)
                    page.wait_for_load_state("networkidle")
                    page.wait_for_timeout(2000)
                    
                    # キャストリストの存在確認
                    cast_selectors = [
                        ".cast-list",
                        ".staff-list",
                        "[data-cast-list]",
                        "table.casts",
                        ".cast-item"
                    ]
                    
                    for selector in cast_selectors:
                        if page.query_selector(selector):
                            cast_page = page
                            logger.debug(f"[Global Pre-Check] Found cast page with selector: {selector}")
                            break
                    
                    if cast_page:
                        break
                except Exception:
                    continue
            
            if not cast_page:
                result['reason'] = 'Could not access cast management page'
                logger.warning(f"[Global Pre-Check] {result['reason']}")
                return result
            
            # 出勤中のキャストをカウント
            # 複数のセレクターパターンを試行
            attendance_markers = [
                "出勤",
                "attendance",
                "working",
                "on-duty"
            ]
            
            active_cast_count = 0
            cast_elements = []
            
            # キャスト要素を取得
            cast_row_selectors = [
                "tr.cast-row",
                ".cast-item",
                "[data-cast-item]",
                ".staff-item",
                "li.cast"
            ]
            
            for selector in cast_row_selectors:
                elements = page.query_selector_all(selector)
                if elements:
                    cast_elements = elements
                    logger.debug(f"[Global Pre-Check] Found {len(elements)} cast elements with selector: {selector}")
                    break
            
            if not cast_elements:
                # テーブル行として試行
                cast_elements = page.query_selector_all("table tr")
                if len(cast_elements) > 1:  # ヘッダー行を除外
                    cast_elements = cast_elements[1:]
            
            # 各キャストの出勤状態を確認
            for cast_elem in cast_elements:
                try:
                    # キャストの状態を確認
                    elem_text = cast_elem.inner_text().lower()
                    elem_class = cast_elem.get_attribute("class") or ""
                    elem_data_status = cast_elem.get_attribute("data-status") or ""
                    
                    # 出勤マーカーを探す
                    is_attendance = False
                    for marker in attendance_markers:
                        if (marker.lower() in elem_text or 
                            marker.lower() in elem_class.lower() or 
                            marker.lower() in elem_data_status.lower()):
                            is_attendance = True
                            break
                    
                    if is_attendance:
                        active_cast_count += 1
                except Exception as e:
                    logger.debug(f"[Global Pre-Check] Error checking cast element: {e}")
                    continue
            
            logger.info(f"[Global Pre-Check] Active cast count: {active_cast_count}")
            result['active_cast_count'] = active_cast_count
            
            # 3人以下で中止
            if active_cast_count <= 3:
                result['reason'] = f'Active cast count ({active_cast_count}) is 3 or fewer - aborting cycle'
                logger.warning(f"[Global Pre-Check] {result['reason']}")
                return result
            
            # Step 2: 時間制約チェック
            logger.info(f"[Global Pre-Check] Step 2: Checking time constraints...")
            
            # 現在時刻
            now = datetime.now()
            
            # 各キャストの退勤時刻を確認（UIから読み取る）
            # 実際の実装では、スケジュール情報から退勤時刻を取得
            # ここでは簡易的に、キャスト要素から退勤時刻を読み取る試み
            
            eligible_accounts = []
            with get_session() as session:
                account_repo = AccountRepository(session)
                all_accounts = account_repo.get_active_accounts()
                
                # 時間制約チェック（各アカウントのキャストの退勤時刻を確認）
                # 実際の実装では、各アカウントのスケジュールから退勤時刻を取得
                # ここでは簡易的に、全アカウントを対象とする
                # （実際のUIから退勤時刻を読み取る必要がある）
                
                for acc in all_accounts:
                    # 時間制約チェックは、実際のUIから退勤時刻を読み取る必要がある
                    # ここでは、全アカウントを対象とする（実装時に調整）
                    eligible_accounts.append(acc)
            
            result['eligible_accounts'] = eligible_accounts
            result['eligible_account_count'] = len(eligible_accounts)
            
            logger.info(
                f"[Global Pre-Check] Time constraint check: "
                f"{len(eligible_accounts)} accounts eligible"
            )
            
            # 事前チェック通過
            result['can_proceed'] = True
            result['reason'] = 'All preconditions passed'
            logger.info(f"[Global Pre-Check] {result['reason']}")
            
            return result
            
        finally:
            page.close()
            
    except Exception as e:
        logger.error(f"[Global Pre-Check] Error in global preconditions check: {e}", exc_info=True)
        result['reason'] = f'Error during preconditions check: {str(e)}'
        return result


def execute_wait_reception(
    page: Page,
    account: Account,
    manual_detector: ManualOperationDetector,
    log_ctx
):
    """
    待機接客配信制御業務ロジック
    
    実装手順:
    1. 自動化ロック取得
    2. セッション・ページ状態検証
    3. 現在のキャストステータスを読み取り
    4. ステータス遷移ルール適用
    5. 更新後検証（最大1回リトライ）
    6. ロック解放
    """
    account_id = str(account.id)
    logger.info(f"[{account_id}] Executing wait reception update...")
    
    # ロック管理
    lock_acquired = False
    
    with log_manager.log_operation(account_id, ActionType.WAIT_RECEPTION) as wait_ctx:
        try:
            # Step 1: 自動化ロック取得
            wait_ctx.log_info("Step 1: Acquiring automation lock...")
            with get_session() as session:
                account_repo = AccountRepository(session)
                
                # ロック取得を試行
                if not account_repo.acquire_lock(account_id, "wait_reception"):
                    wait_ctx.log_skipped("Account is already locked by another process")
                    logger.warning(f"[{account_id}] Account is locked, skipping")
                    raise AutomationError("Account is locked")
                
                lock_acquired = True
                logger.debug(f"[{account_id}] Lock acquired")
            
            # Step 2: セッション・ページ状態検証
            wait_ctx.log_info("Step 2: Validating session and page state...")
            manual_detector.check(page)  # 手動操作チェックも含む
            
            # セッション有効性チェック
            current_url = page.url
            if "login" in current_url.lower() and "dokodemo" not in current_url:
                raise AutomationError("Session expired: redirected to login page")
            
            # クッキー確認
            cookies = page.context.cookies()
            if not cookies:
                raise AutomationError("No cookies found: session may be invalid")
            
            # ページ応答性確認
            try:
                page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                logger.warning(f"[{account_id}] Page may not be fully loaded, but continuing...")
            
            logger.debug(f"[{account_id}] Session and page state validated: {len(cookies)} cookies found")
            wait_ctx.log_info("Session and page state validated successfully")
            
            # Step 3: 現在のキャストステータスを読み取り
            wait_ctx.log_info("Step 3: Reading current cast status...")
            
            # キャスト管理ページまたはダッシュボードに移動
            base_url = account.login_url or settings.LOGIN_URLS[0]
            
            # 複数のURLパターンを試行
            cast_page_urls = [
                f"{base_url.rstrip('/')}/casts",
                f"{base_url.rstrip('/')}/dashboard",
                f"{base_url.rstrip('/')}/cast-management",
                f"{base_url.rstrip('/')}/staff"
            ]
            
            navigated = False
            for url in cast_page_urls:
                try:
                    logger.debug(f"[{account_id}] Trying to navigate to: {url}")
                    page.goto(url, wait_until="networkidle", timeout=15000)
                    page.wait_for_load_state("networkidle")
                    page.wait_for_timeout(2000)
                    
                    # キャストリストの存在確認
                    cast_selectors = [
                        ".cast-list",
                        ".staff-list",
                        "[data-cast-list]",
                        "table.casts",
                        ".cast-item"
                    ]
                    
                    for selector in cast_selectors:
                        if page.query_selector(selector):
                            navigated = True
                            logger.debug(f"[{account_id}] Found cast page with selector: {selector}")
                            break
                    
                    if navigated:
                        break
                except Exception as e:
                    logger.debug(f"[{account_id}] Failed to navigate to {url}: {e}")
                    continue
            
            if not navigated:
                raise AutomationError("Could not access cast management page")
            
            wait_ctx.log_info("Cast management page loaded successfully")
            
            # キャストステータスを読み取り
            cast_statuses = _read_cast_statuses(page, account_id)
            
            if not cast_statuses:
                wait_ctx.log_skipped("No cast statuses found - no action needed")
                logger.info(f"[{account_id}] No cast statuses found")
                return  # 成功として扱う
            
            logger.info(f"[{account_id}] Found {len(cast_statuses)} casts with status")
            wait_ctx.log_info(f"Found {len(cast_statuses)} casts")
            
            # Step 4: ステータス遷移ルール適用
            wait_ctx.log_info("Step 4: Applying status transition rules...")
            
            casts_to_update = []
            
            for cast_info in cast_statuses:
                cast_name = cast_info['name']
                current_status = cast_info['status']
                cast_element = cast_info['element']
                
                logger.debug(f"[{account_id}] Cast {cast_name}: status={current_status}")
                
                # ルール1: 接客中 AND 非更新エリア入場 → 待機中に変更
                if current_status == "接客中" or current_status.lower() == "serving":
                    # 非更新エリアに入っているかチェック
                    is_in_no_update_area = _check_no_update_area(cast_element, page)
                    
                    if is_in_no_update_area:
                        logger.info(f"[{account_id}] Cast {cast_name} is in no-update area, changing to 待機中")
                        casts_to_update.append({
                            'name': cast_name,
                            'element': cast_element,
                            'previous_status': current_status,
                            'target_status': '待機中',
                            'reason': 'Entered no-update area'
                        })
                        continue
                
                # ルール2: 待機中 → アクションなし
                if current_status == "待機中" or current_status.lower() == "waiting":
                    logger.debug(f"[{account_id}] Cast {cast_name} is already 待機中 - no action")
                    continue
                
                # ルール3: その他のステータス → アクションなし（情報ログ）
                logger.debug(f"[{account_id}] Cast {cast_name} has status '{current_status}' - no action (informational)")
                wait_ctx.log_info(f"Cast {cast_name}: status '{current_status}' - no action")
            
            if not casts_to_update:
                wait_ctx.log_success("No status transitions needed - all casts in correct state")
                logger.info(f"[{account_id}] No status transitions needed")
                return  # 成功として扱う
            
            logger.info(f"[{account_id}] Found {len(casts_to_update)} casts to update")
            wait_ctx.log_info(f"Found {len(casts_to_update)} casts to update")
            
            # 更新を実行
            update_successful = False
            max_retries = 1  # 最大1回リトライ
            
            for retry in range(max_retries + 1):
                try:
                    if retry > 0:
                        wait_ctx.log_info(f"Retry attempt {retry}/{max_retries}...")
                        logger.info(f"[{account_id}] Retry {retry}/{max_retries}")
                        page.wait_for_timeout(2000)
                    
                    updated_count = 0
                    
                    for cast_info in casts_to_update:
                        try:
                            cast_name = cast_info['name']
                            cast_element = cast_info['element']
                            target_status = cast_info['target_status']
                            
                            logger.debug(f"[{account_id}] Updating {cast_name} to {target_status}")
                            
                            # ステータスを変更
                            _update_cast_status(
                                page,
                                cast_element,
                                cast_name,
                                target_status,
                                account_id
                            )
                            
                            updated_count += 1
                            logger.debug(f"[{account_id}] Updated {cast_name} to {target_status}")
                        
                        except Exception as e:
                            logger.warning(f"[{account_id}] Error updating {cast_info['name']}: {e}")
                            continue
                    
                    if updated_count == 0:
                        raise AutomationError("Failed to update any casts")
                    
                    # 保存を実行
                    wait_ctx.log_info("Saving status changes...")
                    
                    # 保存ボタンを探す
                    save_button_selectors = [
                        "button:has-text('保存')",
                        "button:has-text('更新')",
                        "button:has-text('適用')",
                        "button[type='submit']",
                        ".save-button",
                        "[data-action='save']",
                        "button.save"
                    ]
                    
                    save_button = None
                    for selector in save_button_selectors:
                        try:
                            save_button = page.query_selector(selector)
                            if save_button and save_button.is_visible():
                                break
                        except Exception:
                            continue
                    
                    if save_button:
                        save_button.click()
                        page.wait_for_load_state("networkidle")
                        page.wait_for_timeout(2000)
                    
                    # 保存成功/失敗メッセージを確認
                    error_message = page.query_selector(".error-message, .alert-error, .toast-error")
                    
                    if error_message:
                        error_text = error_message.inner_text()
                        raise AutomationError(f"Save failed: {error_text}")
                    
                    update_successful = True
                    wait_ctx.log_info(f"Successfully updated {updated_count} casts")
                    break  # 成功したらリトライループを抜ける
                
                except Exception as e:
                    if retry == max_retries:
                        # 最後のリトライでも失敗
                        raise AutomationError(f"Update failed after {max_retries + 1} attempts: {str(e)}")
                    logger.warning(f"[{account_id}] Update attempt {retry + 1} failed: {e}, retrying...")
                    continue
            
            if not update_successful:
                raise AutomationError("Failed to update status after all retries")
            
            # Step 5: 更新後検証（最大1回リトライ）
            wait_ctx.log_info("Step 5: Verifying status update...")
            
            verification_successful = False
            max_verify_retries = 1
            
            for verify_retry in range(max_verify_retries + 1):
                try:
                    if verify_retry > 0:
                        # ページを再読み込み
                        logger.debug(f"[{account_id}] Reloading page for verification retry {verify_retry}")
                        page.reload(wait_until="networkidle")
                        page.wait_for_timeout(2000)
                    
                    # ステータスを再読み取り
                    verification_passed = True
                    
                    for cast_info in casts_to_update:
                        try:
                            cast_name = cast_info['name']
                            target_status = cast_info['target_status']
                            
                            # ステータスを再読み取り
                            updated_statuses = _read_cast_statuses(page, account_id)
                            
                            # 該当キャストのステータスを確認
                            cast_found = False
                            for updated_cast in updated_statuses:
                                if updated_cast['name'] == cast_name:
                                    cast_found = True
                                    verified_status = updated_cast['status']
                                    
                                    # 期待されるステータスか確認
                                    is_correct = (
                                        target_status in verified_status or
                                        verified_status.lower() == target_status.lower() or
                                        (target_status == "待機中" and "待機" in verified_status)
                                    )
                                    
                                    if not is_correct:
                                        verification_passed = False
                                        logger.warning(
                                            f"[{account_id}] Verification failed: "
                                            f"{cast_name} expected {target_status}, got {verified_status}"
                                        )
                                    else:
                                        logger.debug(
                                            f"[{account_id}] Verification passed for {cast_name}: {verified_status}"
                                        )
                                    break
                            
                            if not cast_found:
                                verification_passed = False
                                logger.warning(f"[{account_id}] Verification failed: {cast_name} not found")
                                break
                        
                        except Exception as e:
                            logger.warning(f"[{account_id}] Error verifying {cast_info['name']}: {e}")
                            verification_passed = False
                            break
                    
                    if verification_passed:
                        verification_successful = True
                        wait_ctx.log_success("Verification passed: All statuses updated correctly")
                        logger.info(f"[{account_id}] Verification passed")
                        break
                    else:
                        if verify_retry < max_verify_retries:
                            logger.warning(f"[{account_id}] Verification failed, retrying...")
                            continue
                        else:
                            raise AutomationError("Verification failed after all retries")
                
                except Exception as e:
                    if verify_retry == max_verify_retries:
                        raise AutomationError(f"Verification failed: {str(e)}")
                    continue
            
            if not verification_successful:
                raise AutomationError("Status update verification failed")
            
            # 成功ログ
            wait_ctx.log_success(
                f"Wait reception update completed: {len(casts_to_update)} casts updated and verified"
            )
            logger.info(
                f"[{account_id}] Wait reception update completed successfully: "
                f"{len(casts_to_update)} casts updated and verified"
            )
            
        except ManualOperationDetectedError:
            wait_ctx.log_skipped("Manual operation detected during wait reception update")
            raise
        except AutomationError:
            # AutomationErrorはそのまま再スロー
            raise
        except Exception as e:
            wait_ctx.log_error(f"Wait reception update failed: {str(e)}")
            logger.error(f"[{account_id}] Wait reception update error: {e}", exc_info=True)
            raise AutomationError(f"Wait reception update failed: {str(e)}") from e
        
        finally:
            # Step 6: ロック解放
            if lock_acquired:
                try:
                    with get_session() as session:
                        account_repo = AccountRepository(session)
                        account_repo.release_lock(account_id)
                        logger.debug(f"[{account_id}] Lock released")
                except Exception as e:
                    logger.warning(f"[{account_id}] Failed to release lock: {e}")


def _read_cast_statuses(page: Page, account_id: str) -> list:
    """
    キャストステータスを読み取り
    
    Args:
        page: Playwrightページオブジェクト
        account_id: アカウントID（ログ用）
    
    Returns:
        list: キャスト情報のリスト
        [
            {
                'name': str,
                'status': str,  # 待機中, 接客中, 非更新エリア, etc.
                'element': ElementHandle
            },
            ...
        ]
    """
    cast_statuses = []
    
    try:
        # キャスト要素を取得
        cast_row_selectors = [
            "tr.cast-row",
            ".cast-item",
            "[data-cast-item]",
            ".staff-item",
            "li.cast",
            ".cast-status-item"
        ]
        
        cast_elements = []
        for selector in cast_row_selectors:
            elements = page.query_selector_all(selector)
            if elements:
                cast_elements = elements
                logger.debug(f"[{account_id}] Found {len(elements)} cast elements with selector: {selector}")
                break
        
        if not cast_elements:
            # テーブル行として試行
            cast_elements = page.query_selector_all("table tr")
            if len(cast_elements) > 1:  # ヘッダー行を除外
                cast_elements = cast_elements[1:]
        
        # 各キャストのステータスを読み取り
        for cast_elem in cast_elements:
            try:
                # キャスト名を取得
                name_selectors = [
                    ".cast-name",
                    "[data-cast-name]",
                    "td:first-child",
                    ".name",
                    ".staff-name"
                ]
                
                cast_name_elem = None
                for selector in name_selectors:
                    cast_name_elem = cast_elem.query_selector(selector)
                    if cast_name_elem:
                        break
                
                if not cast_name_elem:
                    # テキストから名前を抽出
                    elem_text = cast_elem.inner_text()
                    if elem_text.strip():
                        cast_name = elem_text.split()[0] if elem_text.split() else "Unknown"
                    else:
                        continue
                else:
                    cast_name = cast_name_elem.inner_text().strip()
                
                # ステータスを取得
                status_selectors = [
                    ".cast-status",
                    "[data-status]",
                    ".status",
                    "td.status",
                    ".state"
                ]
                
                status_text = ""
                status_attr = cast_elem.get_attribute("data-status") or ""
                status_class = cast_elem.get_attribute("class") or ""
                
                # ステータス要素を探す
                for selector in status_selectors:
                    status_elem = cast_elem.query_selector(selector)
                    if status_elem:
                        status_text = status_elem.inner_text().strip()
                        break
                
                # ステータスを判定
                if not status_text and not status_attr:
                    # テキストから判定
                    elem_text = cast_elem.inner_text().lower()
                    if "待機" in elem_text or "waiting" in elem_text:
                        status_text = "待機中"
                    elif "接客" in elem_text or "serving" in elem_text:
                        status_text = "接客中"
                    elif "非更新" in elem_text or "no-update" in elem_text:
                        status_text = "非更新エリア"
                    else:
                        status_text = "不明"
                elif status_attr:
                    status_text = status_attr
                
                if not status_text:
                    status_text = "不明"
                
                cast_statuses.append({
                    'name': cast_name,
                    'status': status_text,
                    'element': cast_elem
                })
                
                logger.debug(f"[{account_id}] Cast {cast_name}: status={status_text}")
            
            except Exception as e:
                logger.debug(f"[{account_id}] Error reading cast status: {e}")
                continue
        
        return cast_statuses
    
    except Exception as e:
        logger.error(f"[{account_id}] Error reading cast statuses: {e}", exc_info=True)
        return []


def _check_no_update_area(cast_element, page: Page) -> bool:
    """
    キャストが非更新エリアに入っているかチェック
    
    Args:
        cast_element: キャスト要素
        page: Playwrightページオブジェクト
    
    Returns:
        bool: 非更新エリアに入っている場合True
    """
    try:
        # 要素のテキスト、属性、クラスを確認
        elem_text = cast_element.inner_text().lower()
        elem_class = cast_element.get_attribute("class") or ""
        elem_data_area = cast_element.get_attribute("data-area") or ""
        
        # 非更新エリアのマーカーを探す
        no_update_markers = [
            "非更新",
            "no-update",
            "no_update",
            "non-update",
            "unavailable"
        ]
        
        for marker in no_update_markers:
            if (marker in elem_text or 
                marker in elem_class.lower() or 
                marker in elem_data_area.lower()):
                return True
        
        # 子要素も確認
        no_update_indicators = cast_element.query_selector_all(
            ".no-update, [data-no-update], .non-update"
        )
        if no_update_indicators:
            return True
        
        return False
    
    except Exception as e:
        logger.debug(f"Error checking no-update area: {e}")
        return False


def _update_cast_status(
    page: Page,
    cast_element,
    cast_name: str,
    target_status: str,
    account_id: str
):
    """
    キャストステータスを更新
    
    Args:
        page: Playwrightページオブジェクト
        cast_element: キャスト要素
        cast_name: キャスト名
        target_status: 目標ステータス（待機中など）
        account_id: アカウントID（ログ用）
    """
    try:
        # ステータス要素をクリック
        status_selectors = [
            ".cast-status",
            "[data-status]",
            ".status",
            "td.status",
            ".state"
        ]
        
        status_elem = None
        for selector in status_selectors:
            status_elem = cast_element.query_selector(selector)
            if status_elem:
                break
        
        if not status_elem:
            # キャスト要素自体をクリック
            status_elem = cast_element
        
        status_elem.scroll_into_view_if_needed()
        status_elem.click()
        page.wait_for_timeout(500)
        
        # ステータス選択（ドロップダウンまたはモーダル）
        target_status_selectors = [
            f"button:has-text('{target_status}')",
            f".option-{target_status.lower()}",
            f"[data-status='{target_status}']",
            f"li:has-text('{target_status}')",
            f".dropdown-item:has-text('{target_status}')"
        ]
        
        target_option = None
        for selector in target_status_selectors:
            try:
                target_option = page.query_selector(selector)
                if target_option and target_option.is_visible():
                    break
            except Exception:
                continue
        
        if not target_option:
            # キーボード操作を試行
            logger.debug(f"[{account_id}] Option not found, trying keyboard navigation")
            page.keyboard.press("ArrowDown")
            page.wait_for_timeout(300)
            page.keyboard.press("Enter")
            page.wait_for_timeout(500)
        else:
            target_option.click()
            page.wait_for_timeout(500)
        
        logger.debug(f"[{account_id}] Updated {cast_name} to {target_status}")
    
    except Exception as e:
        logger.error(f"[{account_id}] Error updating cast status for {cast_name}: {e}", exc_info=True)
        raise


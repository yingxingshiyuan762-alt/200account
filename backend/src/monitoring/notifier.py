"""
Notification Module

Email通知機能
イベント駆動型の通知システム
"""
import asyncio
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Set
from collections import defaultdict
import threading
import uuid

from config.config import settings
from src.core.logger import logger
from src.core.event_system import SystemEvent, EventType, EventSeverity, EventLogger
from src.database.connection import get_session
from src.database.repositories.account import AccountRepository


class Notifier:
    """
    通知モジュール
    
    機能:
    - イベント駆動型の通知
    - 重複抑制（クールダウン期間）
    - 重要度ゲート
    - SMTP経由のメール送信
    - 非同期処理
    """
    
    def __init__(self):
        self.running = False
        self.event_logger: Optional[EventLogger] = None
        self.sent_notifications: Dict[str, datetime] = {}  # (event_type, account_id) -> last_sent_time
        self.cooldown_window: int = getattr(settings, 'NOTIFICATION_COOLDOWN_MINUTES', 12) * 60  # デフォルト12分（秒）
        # メールアドレスリストを処理（カンマ区切りまたはリスト）
        emails_raw = getattr(settings, 'NOTIFICATION_EMAILS', [])
        if isinstance(emails_raw, str):
            # カンマ区切りの文字列の場合
            self.recipient_emails = [email.strip() for email in emails_raw.split(',') if email.strip()]
        elif isinstance(emails_raw, list):
            self.recipient_emails = emails_raw
        else:
            self.recipient_emails = []
        self.smtp_config: Dict[str, Any] = self._load_smtp_config()
        self._lock = threading.Lock()
        self.event_queue: asyncio.Queue = asyncio.Queue()
        self.processor_task: Optional[asyncio.Task] = None
        
    def _load_smtp_config(self) -> Dict[str, Any]:
        """SMTP設定を読み込み"""
        return {
            'host': getattr(settings, 'SMTP_HOST', 'smtp.gmail.com'),
            'port': getattr(settings, 'SMTP_PORT', 587),
            'use_tls': getattr(settings, 'SMTP_USE_TLS', True),
            'username': getattr(settings, 'SMTP_USERNAME', ''),
            'password': getattr(settings, 'SMTP_PASSWORD', ''),
            'from_email': getattr(settings, 'SMTP_FROM_EMAIL', '')
        }
    
    async def start(self):
        """通知モジュールを開始"""
        self.running = True
        
        # イベントロガーを取得
        from src.core.event_system import event_logger
        self.event_logger = event_logger
        
        logger.info("=" * 60)
        logger.info("Email Notifier Starting")
        logger.info("=" * 60)
        logger.info(f"Recipient emails: {len(self.recipient_emails)} addresses")
        logger.info(f"Cooldown window: {self.cooldown_window / 60:.1f} minutes")
        logger.info(f"SMTP host: {self.smtp_config['host']}:{self.smtp_config['port']}")
        logger.info("=" * 60)
        
        # イベント処理タスクを開始
        self.processor_task = asyncio.create_task(
            self._event_processor_loop()
        )
        
        logger.info("Email notifier started successfully")
    
    async def stop(self):
        """通知モジュールを停止"""
        self.running = False
        logger.info("Stopping email notifier...")
        
        if self.processor_task:
            self.processor_task.cancel()
            try:
                await self.processor_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Email notifier stopped")
    
    async def _event_processor_loop(self):
        """イベント処理ループ"""
        while self.running:
            try:
                # イベントキューから取得（タイムアウト: 1秒）
                try:
                    event = await asyncio.wait_for(
                        self.event_queue.get(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue
                
                # イベントを処理
                await self._process_event(event)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in event processor loop: {e}", exc_info=True)
                await asyncio.sleep(1)
    
    def notify_event(self, event: SystemEvent):
        """
        イベントを通知キューに追加
        
        Args:
            event: システムイベント
        """
        if not self.running:
            return
        
        try:
            # 非同期でキューに追加
            asyncio.create_task(self.event_queue.put(event))
        except Exception as e:
            logger.error(f"Error queuing event for notification: {e}", exc_info=True)
    
    async def _process_event(self, event: SystemEvent):
        """
        イベントを処理
        
        1. イベント検証
        2. 通知フィルタリング
        3. メール送信
        4. ログ記録
        """
        try:
            # Step 1: イベント検証
            if not self._validate_event(event):
                logger.debug(f"Event validation failed: {event.event_id}")
                return
            
            # Step 2: 通知フィルタリング
            if not self._should_send_notification(event):
                logger.debug(f"Notification suppressed for event: {event.event_id}")
                self._log_notification_attempt(event, 'suppressed', 'Filtered by notification rules')
                return
            
            # Step 3: メール送信
            send_result = await self._send_email(event)
            
            # Step 4: ログ記録
            self._log_notification_attempt(
                event,
                'success' if send_result['success'] else 'failure',
                send_result.get('reason', '')
            )
            
            # 送信成功時は記録を更新
            if send_result['success']:
                self._record_notification_sent(event)
            
        except Exception as e:
            logger.error(f"Error processing event {event.event_id}: {e}", exc_info=True)
            self._log_notification_attempt(event, 'failure', f'Processing error: {str(e)}')
    
    def _validate_event(self, event: SystemEvent) -> bool:
        """
        イベント検証
        
        必須フィールドの存在確認
        重要度レベルの確認
        """
        # 必須フィールドの確認
        if not event.event_id:
            return False
        
        if not event.event_type:
            return False
        
        if not event.severity:
            return False
        
        if not event.timestamp:
            return False
        
        # 重要度レベルの確認
        if event.severity not in [EventSeverity.INFO, EventSeverity.WARNING, 
                                   EventSeverity.ERROR, EventSeverity.CRITICAL]:
            return False
        
        return True
    
    def _should_send_notification(self, event: SystemEvent) -> bool:
        """
        通知フィルタリングロジック
        
        A. 重複抑制
        B. 重要度ゲート
        """
        # A. 重複抑制チェック
        if self._is_duplicate(event):
            logger.debug(f"Duplicate notification suppressed: {event.event_type.value} for account {event.account_id}")
            return False
        
        # B. 重要度ゲート
        if event.severity == EventSeverity.INFO:
            # INFOレベルは通知しない
            return False
        
        if event.severity == EventSeverity.WARNING:
            # WARNINGは繰り返しの場合のみ通知
            if not self._is_repeated_warning(event):
                return False
        
        if event.severity == EventSeverity.CRITICAL:
            # CRITICALは常に即座に送信
            return True
        
        if event.severity == EventSeverity.ERROR:
            # ERRORは重要度に応じて送信
            # クリティカルなエラーイベントのみ送信
            critical_error_types = [
                EventType.ERROR_OCCURRED,
                EventType.SYSTEM_ERROR,
                EventType.SESSION_CONFLICT_DETECTED
            ]
            return event.event_type in critical_error_types
        
        return False
    
    def _is_duplicate(self, event: SystemEvent) -> bool:
        """
        重複チェック
        
        同じイベントタイプとアカウントIDの組み合わせで、
        クールダウン期間内に送信済みかチェック
        """
        if not event.account_id:
            # アカウントIDがない場合は重複チェックをスキップ
            return False
        
        key = f"{event.event_type.value}:{event.account_id}"
        
        with self._lock:
            last_sent = self.sent_notifications.get(key)
            
            if last_sent:
                time_since_last = (datetime.utcnow() - last_sent).total_seconds()
                if time_since_last < self.cooldown_window:
                    return True  # クールダウン期間内
        
        return False
    
    def _is_repeated_warning(self, event: SystemEvent) -> bool:
        """
        警告イベントが繰り返し発生しているかチェック
        
        同じイベントタイプとアカウントIDの組み合わせで、
        過去に送信済みかチェック
        """
        if not event.account_id:
            return False
        
        key = f"{event.event_type.value}:{event.account_id}"
        
        with self._lock:
            return key in self.sent_notifications
    
    def _record_notification_sent(self, event: SystemEvent):
        """通知送信を記録"""
        if not event.account_id:
            return
        
        key = f"{event.event_type.value}:{event.account_id}"
        
        with self._lock:
            self.sent_notifications[key] = datetime.utcnow()
    
    async def _send_email(self, event: SystemEvent) -> Dict[str, Any]:
        """
        メール送信
        
        最大3回リトライ
        """
        if not self.recipient_emails:
            return {
                'success': False,
                'reason': 'No recipient emails configured'
            }
        
        if not self.smtp_config.get('username') or not self.smtp_config.get('password'):
            return {
                'success': False,
                'reason': 'SMTP credentials not configured'
            }
        
        max_retries = 3
        
        for retry in range(max_retries):
            try:
                # メールメッセージを生成
                subject, body = self._generate_email_content(event)
                
                # メールを送信（同期関数を非同期で実行）
                send_result = await asyncio.to_thread(
                    self._send_email_sync,
                    subject,
                    body,
                    self.recipient_emails
                )
                
                if send_result['success']:
                    return send_result
                
                # 失敗時はリトライ
                if retry < max_retries - 1:
                    logger.warning(f"Email send failed (attempt {retry + 1}/{max_retries}), retrying...")
                    await asyncio.sleep(2 ** retry)  # 指数バックオフ
                    continue
                else:
                    return send_result
                    
            except Exception as e:
                if retry == max_retries - 1:
                    return {
                        'success': False,
                        'reason': f'Email send failed after {max_retries} retries: {str(e)}'
                    }
                await asyncio.sleep(2 ** retry)
                continue
        
        return {
            'success': False,
            'reason': 'Email send failed after all retries'
        }
    
    def _send_email_sync(self, subject: str, body: str, recipients: List[str]) -> Dict[str, Any]:
        """
        メール送信（同期版）
        
        SMTP経由でTLS接続してメールを送信
        """
        try:
            # メールメッセージを作成
            msg = MIMEMultipart()
            msg['From'] = self.smtp_config['from_email']
            msg['To'] = ', '.join(recipients)
            msg['Subject'] = subject
            
            # 本文を追加
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
            
            # SMTPサーバーに接続
            with smtplib.SMTP(self.smtp_config['host'], self.smtp_config['port']) as server:
                if self.smtp_config['use_tls']:
                    server.starttls()
                
                # 認証
                server.login(
                    self.smtp_config['username'],
                    self.smtp_config['password']
                )
                
                # メール送信
                server.send_message(msg)
            
            return {
                'success': True,
                'reason': 'Email sent successfully'
            }
            
        except Exception as e:
            logger.error(f"Email send error: {e}", exc_info=True)
            return {
                'success': False,
                'reason': str(e)
            }
    
    def _generate_email_content(self, event: SystemEvent) -> tuple:
        """
        メール内容を生成
        
        Returns:
            tuple: (subject, body)
        """
        # アカウント情報を取得
        store_name = "Unknown"
        if event.account_id:
            try:
                with get_session() as session:
                    account_repo = AccountRepository(session)
                    account = account_repo.get_by_id(event.account_id)
                    if account:
                        store_name = account.store_name
            except Exception:
                pass
        
        # 件名
        severity_label = event.severity.value
        subject = f"[Automation Alert][{severity_label}] Account {event.account_id or 'N/A'}"
        
        # 本文
        body_lines = [
            "=" * 60,
            "Automation System Alert",
            "=" * 60,
            "",
            f"Account ID: {event.account_id or 'N/A'}",
            f"Store Name: {store_name}",
            f"Event Type: {event.event_type.value}",
            f"Severity: {event.severity.value}",
            f"Occurrence Time: {event.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}",
            "",
            "Description:",
            event.message or "No description available",
            "",
            "Reference ID:",
            f"Event ID: {event.event_id}",
            "",
            "=" * 60,
            "",
            "This is an automated notification from the 200 Account Automation System.",
            "Please check the system logs for more details.",
            ""
        ]
        
        # 追加データがある場合は追加
        if event.data:
            body_lines.extend([
                "Additional Information:",
                str(event.data),
                ""
            ])
        
        body = "\n".join(body_lines)
        
        return subject, body
    
    def _log_notification_attempt(
        self,
        event: SystemEvent,
        result: str,
        reason: str = ""
    ):
        """
        通知試行をログに記録
        
        Args:
            event: システムイベント
            result: 送信結果 (success / failure / suppressed)
            reason: 理由
        """
        log_message = (
            f"[NOTIFICATION] Event {event.event_id}: "
            f"result={result}, "
            f"severity={event.severity.value}, "
            f"account_id={event.account_id or 'N/A'}, "
            f"recipients={len(self.recipient_emails)}"
        )
        
        if reason:
            log_message += f", reason={reason}"
        
        if result == 'success':
            logger.info(log_message)
        elif result == 'suppressed':
            logger.debug(log_message)
        else:
            logger.warning(log_message)
        
        # データベースにも記録（オプション）
        try:
            with get_session() as session:
                from src.database.repositories.log import AccountLogRepository
                from src.database.models import ActionType, LogStatus
                
                log_repo = AccountLogRepository(session)
                
                if event.account_id:
                    log_repo.create_log(
                        account_id=event.account_id,
                        action_type=ActionType.STATUS_CHECK,  # 通知はSTATUS_CHECKとして記録
                        status=LogStatus.SUCCESS if result == 'success' else LogStatus.FAILURE,
                        message=f"Notification {result}: {reason}",
                        error_detail={'event_id': event.event_id, 'result': result} if result != 'success' else None
                    )
        except Exception as e:
            logger.debug(f"Failed to log notification attempt to database: {e}")


# グローバル通知インスタンス
notifier = Notifier()


def setup_notifier_event_subscription():
    """
    イベントシステムに通知機能をサブスクライブ
    
    既存のイベントロガーにフックを追加
    """
    from src.core.event_system import event_logger
    
    # 元のlog_eventメソッドを保存
    original_log_event = event_logger.log_event
    
    def log_event_with_notification(*args, **kwargs):
        """イベントログと通知を統合"""
        # 元のメソッドを呼び出し
        event = original_log_event(*args, **kwargs)
        
        # 通知が必要なイベントの場合、通知キューに追加
        if notifier.running:
            # クリティカルイベントと警告イベントをチェック
            if event.severity in [EventSeverity.CRITICAL, EventSeverity.ERROR, EventSeverity.WARNING]:
                notifier.notify_event(event)
        
        return event
    
    # メソッドを置き換え
    event_logger.log_event = log_event_with_notification
    
    logger.info("Notifier event subscription set up successfully")

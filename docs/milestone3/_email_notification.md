# 通知機能 (Email Notification)

## 実装状況

✅ **完全実装完了・準備完了**

## 概要

クリティカルまたは対応が必要なイベントが発生した際に、オペレーターにメールで即座に通知する機能。通知の氾濫を防止し、トレーサビリティを確保します。

## 主要機能

### 通知トリガーソース

イベント駆動型。以下のイベント発生時にのみトリガー:

**クリティカルイベント**:

- アプリケーション停止検出（赤い×）
- 最大リトライ後の復旧失敗
- セッション破損検出
- 自動化プロセスクラッシュ

**警告イベント**:

- 不安定なセッションによる自動化スキップ
- 手動操作検出 → 自動化一時停止
- UI操作の繰り返し失敗

### イベント受信ロジック

- 内部コンポーネントがイベントを発行
- 通知モジュールがイベントを受信
- イベントを検証（必須フィールドの存在、重大度レベルの割り当て）
- 無効なイベントは破棄され、ログ記録

### 通知フィルタリングロジック（スパム防止制御）

メール送信前に以下をチェック:

#### A. 重複抑制

- 同じイベントタイプで同じアカウントについて、クールダウン期間内（デフォルト: 10-15分）に送信済みの場合、送信を抑制
- 抑制をログ記録

#### B. 重大度ゲート

- INFOレベルイベント → メール送信なし
- WARNING → 繰り返し発生時のみメール送信
- CRITICAL → 常に即座に送信

### メールメッセージ生成ロジック

承認されたイベントについて、以下の内容でメールを構築:

**件名**: `[Automation Alert][CRITICAL] Account {AccountID}`

**本文**:

- アカウントID
- 店舗名（利用可能な場合）
- イベントタイプ
- 重大度
- 発生時刻
- 短い人間が読める説明
- ログ参照用の参照ID

**セキュリティ**: パスワード、トークンなどの機密データは含まれない

### メール送信ロジック

- 事前設定されたSMTP認証情報を使用
- TLS経由で接続
- 1つ以上の事前定義されたオペレーターアドレスに送信
- 送信確認を待機

### 失敗処理（メール）

メール送信が失敗した場合:

- 最大3回リトライ
- それでも失敗した場合: 失敗をログ記録、無限リトライは行わない
- メイン自動化フローをブロックしない
- **メール送信の失敗は自動化を停止しない**

### 送信後ログ記録

すべての通知試行について記録:

- イベントID、アカウントID
- 重大度、受信者メールアドレス
- 送信結果（成功/失敗/抑制）、タイムスタンプ

### 分離ルール

- 通知処理は非同期で実行
- 通知の失敗は以下に影響しない:
  - 自動スケジュール更新
  - 待機接客自動化
  - 状態監視

## 技術実装

### コード構造

#### 1. 通知モジュール (`backend/src/monitoring/notifier.py`)

**`Notifier`クラス**:

- `event_queue`: イベントキュー（`asyncio.Queue`）
- `sent_notifications`: 送信済み通知の記録（`(event_type, account_id) -> last_sent_time`）
- `cooldown_window`: クールダウン期間（デフォルト12分、`NOTIFICATION_COOLDOWN_MINUTES`設定）
- `recipient_emails`: 受信者メールアドレスリスト
- `smtp_config`: SMTP設定（ホスト、ポート、認証情報など）

**`_event_processor_loop`メソッド** (行103-123):

- 非同期でイベントキューからイベントを取得
- 1秒のタイムアウトでポーリング
- `_process_event`でイベントを処理

```python
while self.running:
    try:
        event = await asyncio.wait_for(
            self.event_queue.get(),
            timeout=1.0
        )
        await self._process_event(event)
    except asyncio.TimeoutError:
        continue
```

**`_process_event`メソッド** (行141-178):
4ステップの処理:

1. **イベント検証**: `_validate_event`で必須フィールドを確認
2. **通知フィルタリング**: `_should_send_notification`で送信可否を判定
3. **メール送信**: `_send_email`でメールを送信
4. **ログ記録**: `_log_notification_attempt`で結果を記録

**`_validate_event`メソッド** (行180-205):

- `event_id`, `event_type`, `severity`, `timestamp`の存在確認
- 重要度レベルの妥当性確認

**`_should_send_notification`メソッド** (行207-243):
通知フィルタリングロジック:

**A. 重複抑制** (行215-217):

```python
if self._is_duplicate(event):
    return False
```

**`_is_duplicate`メソッド** (行245-266):

- `(event_type, account_id)`の組み合わせでキーを生成
- クールダウン期間内に送信済みかチェック

**B. 重要度ゲート** (行219-241):

- **INFO**: 通知しない
- **WARNING**: 繰り返し発生時のみ通知（`_is_repeated_warning`）
- **CRITICAL**: 常に即座に送信
- **ERROR**: クリティカルなエラーイベントのみ送信

**`_send_email`メソッド** (行293-349):

- 最大3回リトライ
- `_generate_email_content`でメール内容を生成
- `_send_email_sync`（同期関数）を `asyncio.to_thread`で実行
- 指数バックオフでリトライ間隔を調整

**`_send_email_sync`メソッド** (行351-391):

- `smtplib.SMTP`でSMTPサーバーに接続
- TLS接続（`starttls()`）
- 認証（`login`）
- `send_message`でメール送信

**`_generate_email_content`メソッド** (行393-451):
メール内容を生成:

**件名**:

```python
subject = f"[Automation Alert][{severity_label}] Account {event.account_id or 'N/A'}"
```

**本文**:

- アカウントID、店舗名（データベースから取得）
- イベントタイプ、重要度、発生時刻
- 説明、参照ID（Event ID）
- 追加データ（`event.data`がある場合）

**`_log_notification_attempt`メソッド** (行453-502):

- 通知試行をログに記録（成功/失敗/抑制）
- データベースログにも記録（`ActionType.STATUS_CHECK`）

#### 2. イベントサブスクリプション

**`setup_notifier_event_subscription`関数** (行509-536):

- グローバル `EventLogger`の `log_event`メソッドにフックを追加
- 元のメソッドを保存し、通知機能を統合

```python
def log_event_with_notification(*args, **kwargs):
    event = original_log_event(*args, **kwargs)
    if notifier.running:
        if event.severity in [EventSeverity.CRITICAL, EventSeverity.ERROR, EventSeverity.WARNING]:
            notifier.notify_event(event)
    return event

event_logger.log_event = log_event_with_notification
```

**`notify_event`メソッド** (行125-139):

- イベントを非同期キューに追加
- `asyncio.create_task`で非ブロッキングに実行

#### 3. 統合

**`backend/src/web/app.py`**:

```python
notifier = Notifier()

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_notifier_event_subscription()
    await notifier.start()
    yield
    await notifier.stop()
```

#### 4. 設定 (`backend/config/config.py`)

**SMTP設定**:

- `SMTP_HOST`: SMTPサーバーホスト（デフォルト: `smtp.gmail.com`）
- `SMTP_PORT`: SMTPポート（デフォルト: `587`）
- `SMTP_USE_TLS`: TLS使用フラグ（デフォルト: `True`）
- `SMTP_USERNAME`: SMTP認証ユーザー名
- `SMTP_PASSWORD`: SMTP認証パスワード
- `SMTP_FROM_EMAIL`: 送信者メールアドレス

**通知設定**:

- `NOTIFICATION_EMAILS`: 受信者メールアドレス（カンマ区切りまたはリスト）
- `NOTIFICATION_COOLDOWN_MINUTES`: クールダウン期間（分、デフォルト: `12`）

### イベント統合

通知機能は以下のイベントを処理:

- **`EventType.APP_STOP_DETECTED`** (CRITICAL): アプリ停止検出時（Feature 3から）
- **`EventType.UNSTABLE_SESSION_SKIPPED`** (WARNING): 不安定なセッション検出時（Feature 3から）
- **`EventType.MANUAL_OPERATION_DETECTED`** (WARNING): 手動操作検出時（Feature 1, 2から）
- **`EventType.ERROR_OCCURRED`** (ERROR): エラー発生時
- **`EventType.SYSTEM_ERROR`** (ERROR): システムエラー時
- **`EventType.SESSION_CONFLICT_DETECTED`** (ERROR): セッション競合検出時

### エラーハンドリング

- **メール送信失敗**: 最大3回リトライ、それでも失敗時はログ記録のみ
- **SMTP認証失敗**: エラーをログ記録、自動化は継続
- **イベント処理エラー**: エラーをログ記録、次のイベント処理を継続
- **通知の失敗は自動化に影響しない**: 非同期処理で分離

### パフォーマンス

- 非同期処理でメインスレッドをブロックしない
- イベントキューでバッファリング
- 重複抑制でスパムを防止
- 指数バックオフでリトライ負荷を軽減

## 完了条件

✅ クリティカルイベントは常にメールを生成
✅ 重複アラートが抑制される
✅ メールに十分な診断情報が含まれる
✅ 通知の失敗が自動化に影響しない

## ステータス

**実装完了・準備完了**

**注意**: 本番環境では、`config/config.py` のSMTP設定（`SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL`）および通知設定（`NOTIFICATION_EMAILS`, `NOTIFICATION_COOLDOWN_MINUTES`）を適切に設定する必要があります。

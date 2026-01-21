# 自動スケジュール更新 (Automatic Schedule Update)

## 実装状況

✅ **完全実装完了**

## 概要

明日のスケジュールを自動的に「出勤」に設定する機能。週間スケジュールに「出勤」が含まれるアカウントのみを対象とし、重複や漏れを防止します。

## 主要機能

### 実行トリガー

- 毎日 07:00-10:00 の時間帯に1回実行
- 実行失敗時も安全に再実行可能（冪等性保証）

### アカウント選択ロジック

- 週間スケジュールに「出勤」が1日以上含まれるアカウントを対象
- アクティブなキャストメンバーを確実に含む

### 処理フロー

1. **ロック取得**: アカウント単位の自動化ロックを取得
2. **セッション検証**: 有効なセッション（クッキー、ページ到達性）を確認
3. **スケジュールページ遷移**: スケジュール管理画面を開き、UI要素の読み込みを待機
4. **明日の状態読み取り**: 明日の日付セルから現在の状態（出勤/退勤/未設定）を取得
5. **条件付き更新**: 明日が「出勤」でない場合のみ「出勤」を選択して保存
6. **更新後検証**: UIを再読み込みし、明日の状態が「出勤」であることを確認（最大3回リトライ）
7. **ロック解放**: 自動化ロックを解除

### エラーハンドリング

- UI操作失敗時は最大3回リトライ
- 1アカウントの失敗は他のアカウント処理を停止しない
- すべてのエラーは個別にログ記録

### ログ記録

- アカウントID、実行タイムスタンプ
- 初期スケジュール状態、実行アクション（更新/スキップ）
- 最終検証結果、エラー理由（該当時）

## 技術実装

### コード構造

#### 1. スケジューラー (`backend/src/monitoring/scheduler.py`)

**`_schedule_update_loop`メソッド** (行80-149):

- 毎日07:00-10:00の時間帯を監視
- `last_schedule_update_date`で1日1回の実行を保証
- `_is_schedule_update_enabled()`でシステム設定を確認
- 実行時間外は次回実行時刻まで待機

```python
# 実行時間帯チェック（7:00-10:00）
if settings.SCHEDULE_UPDATE_START_HOUR <= current_hour < settings.SCHEDULE_UPDATE_END_HOUR:
    # 今日すでに実行済みかチェック
    if self.last_schedule_update_date == current_date:
        # 今日は実行済み：次の実行時刻まで待機
        continue
```

**`_execute_schedule_update`メソッド** (行151-198):

- `asyncio.to_thread`で同期データベース操作を非同期実行
- `ParallelExecutor.execute_accounts`で全アカウントを並列処理
- 実行結果のサマリーを返却

#### 2. 業務ロジック (`backend/src/automation/worker.py`)

**`execute_schedule_update`関数** (行249-788):
8ステップの詳細実装:

**Step 1: ロック取得** (行276-288)

```python
if not account_repo.acquire_lock(account_id, "schedule_update"):
    schedule_ctx.log_skipped("Account is already locked by another process")
    raise AutomationError("Account is locked")
```

**Step 2: セッション検証** (行290-305)

- `manual_detector.check(page)`で手動操作を検知
- クッキーの存在確認
- ログインページへのリダイレクト検知

**Step 3: スケジュールページ遷移** (行307-367)

- 複数のURLパターンを試行 (`/schedule`, `/schedules`, `/weekly-schedule`)
- 複数のセレクターでスケジュールコンテナを検索
- `wait_for_load_state("networkidle")`で完全な読み込みを待機

**Step 4: 週間スケジュール読み取り** (行369-485)

- 複数のセレクターでスケジュール行を取得
- 各キャストの週間スケジュールを走査
- 「出勤」マーカーを検出（テキスト、属性、クラス名をチェック）
- 出勤設定がないアカウントは除外（正常な動作）

**Step 5: 明日の状態読み取り** (行486-556)

```python
tomorrow = datetime.now() + timedelta(days=1)
tomorrow_str = tomorrow.strftime("%Y-%m-%d")
tomorrow_day_index = tomorrow.weekday()
```

- `data-date`属性、曜日インデックス、テーブル列で明日のセルを特定
- 現在の状態を判定（出勤/退勤/未設定）
- 既に出勤の場合はスキップ

**Step 6: 条件付き更新** (行560-680)

- 最大3回リトライ
- 各キャストの明日セルをクリック
- ドロップダウンまたはモーダルから「出勤」を選択
- 保存ボタンをクリックして変更を適用
- 成功/失敗メッセージを確認

**Step 7: 更新後検証** (行682-756)

- 最大3回リトライ
- ページを再読み込み
- 明日の状態を再読み取り
- すべてのキャストが「出勤」に設定されていることを確認

**Step 8: ロック解放** (行778-787)

```python
finally:
    if lock_acquired:
        account_repo.release_lock(account_id)
```

#### 3. ロック管理 (`backend/src/database/repositories/account.py`)

**`acquire_lock`メソッド** (行240-279):

- `metadata_json`にロック情報を保存
- `AccountStatus.PROCESSING`にステータスを更新
- 既にロックされている場合は `False`を返却

**`release_lock`メソッド** (行281-307):

- `metadata_json`からロック情報を削除
- `AccountStatus.IDLE`にステータスを戻す

**`is_locked`メソッド** (行309-329):

- `AccountStatus.PROCESSING`と `metadata_json`のロック情報を確認

#### 4. 並列実行 (`backend/src/automation/executor.py`)

- `ThreadPoolExecutor`で複数アカウントを並列処理
- ロック済みアカウントは事前にフィルタリング
- 各アカウントの処理は独立して実行され、1つの失敗が他に影響しない

### エラーハンドリング

- **UI操作失敗**: 最大3回リトライ（更新と検証の両方）
- **セッション失効**: `AutomationError`を発生させ、アカウントをスキップ
- **手動操作検知**: `ManualOperationDetectedError`を発生させ、イベントを発行
- **ロック競合**: ロック取得失敗時はスキップ（正常な動作）

### ログ記録

- `log_manager.log_operation`で全操作を記録
- 各ステップで `schedule_ctx.log_info/log_success/log_error`を呼び出し
- アカウントID、タイムスタンプ、アクション、結果を記録

## 完了条件

✅ すべての対象アカウントが処理された
✅ アカウントが暗黙的にスキップされていない
✅ すべての変更が検証された
✅ エラー（該当時）が完全にログ記録され、追跡可能

## ステータス

**実装完了・テスト準備完了**

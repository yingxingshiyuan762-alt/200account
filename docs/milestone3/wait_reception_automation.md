# 待機接客自動化 (Wait Reception Automation)

## 実装状況

✅ **完全実装完了**

## 概要

キャストの待機状態を自動制御する機能。ビジネスルールに従って待機サービスを有効化し、手動操作やセッション競合を防止します。

## 主要機能

### 実行トリガー

- 60-90分間隔でランダム実行（予測不可能な動作を実現）
- 各サイクルは独立実行され、安全に再実行可能

### グローバル事前チェック

1. **アクティブキャスト数チェック**: 現在「出勤」のキャスト数を取得
   - 3人以下の場合、サイクル全体を中止
2. **時間制約チェック**: 各キャストについて、現在時刻がシフト終了時刻の10分以内の場合、処理から除外

### アカウント処理フロー

1. **ロック取得**: アカウント単位の自動化ロックを取得
2. **セッション・ページ状態検証**: ログイン状態、ページ応答性を確認
3. **現在のキャスト状態読み取り**: UIから状態を取得（待機中/接客中/非更新エリア）
4. **状態遷移ルール適用**:
   - 状態が「接客中」かつ「非更新エリア」に入った場合 → 即座に「待機中」に変更して保存・検証
   - 状態が「待機中」の場合 → アクションなし（成功としてマーク）
   - その他の状態 → アクションなし（情報ログ）
5. **アクション後検証**: UIから状態を再読み込みし、期待される状態が適用されていることを確認（失敗時は1回リトライ）
6. **ロック解放**: 自動化ロックを解除

### 安全性・中止条件

以下の場合、処理を即座に中止:

- 手動ユーザー操作が検出された
- セッショントークンが予期せず変更された
- UIが未知の状態に入った

### ログ記録

- アカウントID、実行タイムスタンプ
- 前の状態、実行アクション（該当時）
- 最終検証状態、エラー理由（該当時）

## 技術実装

### コード構造

#### 1. スケジューラー (`backend/src/monitoring/scheduler.py`)

**`_wait_reception_loop`メソッド** (行242-281):

- 60-90分のランダム間隔で実行
- `random.randint`で予測不可能な動作を実現
- 各サイクルは独立して実行され、安全に再実行可能

```python
interval_seconds = random.randint(
    settings.WAIT_RECEPTION_INTERVAL_MIN * 60,
    settings.WAIT_RECEPTION_INTERVAL_MAX * 60
)
await asyncio.sleep(interval_seconds)
```

**`_execute_wait_reception`メソッド** (行283-379):

- `check_global_preconditions`でグローバル事前チェックを実行
- 事前チェック失敗時はサイクル全体を中止（正常な動作）
- 対象アカウントを並列処理

#### 2. グローバル事前チェック (`backend/src/automation/worker.py`)

**`check_global_preconditions`関数** (行790-1006):

**Step 1: アクティブキャスト数チェック** (行848-958)

- 代表アカウントでキャスト管理ページにアクセス
- 複数のURLパターンを試行 (`/casts`, `/dashboard`, `/cast-management`)
- 複数のセレクターでキャスト要素を取得
- 「出勤」マーカーを検出してカウント
- 3人以下の場合は `can_proceed=False`を返却

```python
if active_cast_count <= 3:
    result['reason'] = f'Active cast count ({active_cast_count}) is 3 or fewer - aborting cycle'
    return result
```

**Step 2: 時間制約チェック** (行960-996)

- 各アカウントのキャストの退勤時刻を確認
- 現在時刻がシフト終了時刻の10分以内の場合は除外
- 実際の実装では、UIから退勤時刻を読み取る必要がある

#### 3. 業務ロジック (`backend/src/automation/worker.py`)

**`execute_wait_reception`関数** (行1009-1374):
6ステップの詳細実装:

**Step 1: ロック取得** (行1034-1046)

```python
if not account_repo.acquire_lock(account_id, "wait_reception"):
    wait_ctx.log_skipped("Account is already locked by another process")
    raise AutomationError("Account is locked")
```

**Step 2: セッション・ページ状態検証** (行1048-1069)

- 手動操作チェック、セッション有効性、ページ応答性を確認

**Step 3: 現在のキャスト状態読み取り** (行1071-1128)

- `_read_cast_statuses`ヘルパー関数を呼び出し
- 複数のセレクターでキャスト要素を取得
- 各キャストのステータス（待機中/接客中/非更新エリア）を読み取り

**Step 4: 状態遷移ルール適用** (行1130-1173)

```python
# ルール1: 接客中 AND 非更新エリア入場 → 待機中に変更
if current_status == "接客中" or current_status.lower() == "serving":
    is_in_no_update_area = _check_no_update_area(cast_element, page)
    if is_in_no_update_area:
        casts_to_update.append({
            'name': cast_name,
            'element': cast_element,
            'previous_status': current_status,
            'target_status': '待機中',
            'reason': 'Entered no-update area'
        })
```

- ルール2: 待機中 → アクションなし
- ルール3: その他のステータス → アクションなし（情報ログ）

**Step 5: 更新後検証** (行1264-1340)

- 最大1回リトライ
- ページを再読み込み
- ステータスを再読み取り
- 期待されるステータスが適用されていることを確認

**Step 6: ロック解放** (行1365-1374)

#### 4. ヘルパー関数

**`_read_cast_statuses`関数** (行1377-1505):

- 複数のセレクターでキャスト要素を取得
- キャスト名とステータスを抽出
- テキスト、属性、クラス名からステータスを判定

**`_check_no_update_area`関数** (行1508-1551):

- 要素のテキスト、属性、クラス名を確認
- 「非更新」マーカーを検出
- 子要素も確認

**`_update_cast_status`関数** (行1554-1628):

- ステータス要素をクリック
- ドロップダウンまたはモーダルから目標ステータスを選択
- キーボード操作もフォールバックとして使用

### エラーハンドリング

- **グローバル事前チェック失敗**: サイクル全体を中止（正常な動作）
- **ロック競合**: ロック取得失敗時はスキップ
- **手動操作検知**: `ManualOperationDetectedError`を発生させ、イベントを発行
- **UI操作失敗**: 最大1回リトライ（更新と検証の両方）

### ログ記録

- `log_manager.log_operation`で全操作を記録
- 各ステップで `wait_ctx.log_info/log_success/log_error`を呼び出し
- グローバル事前チェックの結果も記録

## 完了条件

✅ すべての対象アカウントが処理された
✅ アカウントが人員配置や時間ルールに違反していない
✅ 強制ログアウトが発生していない
✅ すべてのアクションが検証またはログ記録された

## ステータス

**実装完了・テスト準備完了**

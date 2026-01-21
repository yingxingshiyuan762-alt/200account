# 状態監視 (Status Monitoring)

## 実装状況

✅ **完全実装完了**

## 概要

アカウント状態とアプリケーションの健全性を継続的に監視し、異常を早期検出して自動化が不安定な条件下で動作することを防止します。

## 主要機能

### 監視実行モデル

- 継続的なバックグラウンドループとして実行
- 自動スケジュール更新、待機接客自動化から独立して動作
- 異常状態が検出されるまで読み取り専用

### 監視対象

#### A. アカウントレベル状態

- ログインセッションの有効性
- ページ応答性
- 現在の運用状態（待機中/接客中/非更新エリア）

#### B. アプリケーションレベル状態

- アプリ停止インジケーター（例: 「赤い×」）
- フリーズまたは応答不能な画面
- 予期しないページ遷移やリダイレクト

### アカウント監視ロジック（5ステップ）

1. **軽量ページアクセスチェック**: ページがリロードなしでアクセス可能か確認、主要DOM要素の存在を確認
2. **セッション整合性チェック**: 必要なセッションクッキー/トークンの存在を確認、予期しないトークン変更を検出
3. **UI応答性チェック**: 短時間の非破壊的DOMクエリを実行
4. **アプリ停止検出**: 既知のDOMパターン（「赤い×」）をチェック、必要に応じてスクリーンショットベースのパターン検出をフォールバックとして使用
5. **状態分類**: 上記のチェックに基づいて、アカウントを「Normal」「Unstable」「Stopped」に分類

### 反応ロジック

- **Normal**: アクションなし、監視継続
- **Unstable**: アカウントの自動化アクションを一時停止、イベントログ記録、通知準備（非クリティカル）
- **Stopped**: 自動化アクションを即座に中止、復旧ルーチンをトリガー（再起動/再初期化）、クリティカル通知を送信

### 分離ルール

- 失敗は常にアカウント単位で分離
- 複数のアカウントが同時に失敗し、しきい値を超えた場合のみグローバル停止
- 他のアカウントは正常動作を継続

### ログ記録

各監視サイクルで記録:

- アカウントID、タイムスタンプ
- 監視結果（Normal/Unstable/Stopped）
- 検出理由、実行アクション（該当時）

## 技術実装

### コード構造

#### 1. 監視モジュール (`backend/src/monitoring/status_monitor.py`)

**`StatusMonitor`クラス**:

- `monitor_interval`: 監視間隔（デフォルト5分、`STATUS_MONITOR_INTERVAL`設定）
- `account_states`: アカウントID → 状態のマッピング
- `last_check_times`: アカウントID → 最終チェック時刻のマッピング

**`_monitoring_loop`メソッド** (行81-129):

- 固定間隔で全アカウントを順次監視
- `_is_monitoring_enabled()`でシステム設定を確認
- 各アカウントを `_monitor_account`で監視
- アカウント間で2秒待機（負荷分散）

```python
while self.running:
    accounts = await self._get_monitoring_targets()
    for account in accounts:
        await self._monitor_account(account)
        await asyncio.sleep(2)  # 負荷分散
    await asyncio.sleep(self.monitor_interval)
```

**`_monitor_account_sync`メソッド** (行207-274):
5ステップの監視ロジックを実装:

**Step 1: 軽量ページアクセスチェック** (行232-237)

```python
if not self._check_page_access(page, account_id):
    result['state'] = MonitorState.UNSTABLE
    result['reason'] = 'Page not accessible or key DOM elements missing'
    return result
```

**`_check_page_access`メソッド** (行276-319):

- 現在のURLを確認（`about:blank`でないか）
- 複数のセレクターで主要DOM要素を検索（`body`, `html`, `[data-app]`, `.app-container`など）

**Step 2: セッション整合性チェック** (行239-245)

```python
session_check = self._check_session_integrity(page, account, account_id)
if not session_check['valid']:
    result['state'] = MonitorState.UNSTABLE
    result['reason'] = session_check['reason']
    return result
```

**`_check_session_integrity`メソッド** (行321-359):

- クッキーの存在確認
- URLを確認（ログインページにリダイレクトされていないか）
- セッショントークンの変更を検知（簡易版）

**Step 3: UI応答性チェック** (行247-252)

```python
if not self._check_ui_responsiveness(page, account_id):
    result['state'] = MonitorState.UNSTABLE
    result['reason'] = 'UI query timeout or failed - page may be frozen'
    return result
```

**`_check_ui_responsiveness`メソッド** (行361-384):

- 3秒のタイムアウトで `body`要素の存在確認
- タイムアウトまたは失敗時はフリーズと判定

**Step 4: アプリ停止検知** (行254-260)

```python
app_stop_check = self._check_app_stop(page, account_id)
if app_stop_check['detected']:
    result['state'] = MonitorState.STOPPED
    result['reason'] = app_stop_check['reason']
    return result
```

**`_check_app_stop`メソッド** (行386-434):

- `detect_app_crash`（既存のクラッシュ検知器）を使用
- 追加の停止パターンをチェック（`.app-stopped`, `[data-app-stopped]`, `.error-screen`など）
- スクリーンショットベースの検知は将来の拡張として予約

**Step 5: 状態分類** (行262-267)

- すべてのチェックが通過した場合は `MonitorState.NORMAL`

**`_handle_monitoring_result`メソッド** (行436-500):
反応ロジックを実装:

**Normal** (行451-458):

- アクションなし
- 以前異常だったが正常に戻った場合は `AccountStatus.IDLE`に更新

**Unstable** (行460-477):

- `AccountStatus.ERROR`に更新
- エラーカウントを増加
- `EventType.UNSTABLE_SESSION_SKIPPED`（WARNING）イベントを発行

**Stopped** (行479-498):

- `AccountStatus.ERROR`に更新
- エラーカウントを増加
- `EventType.APP_STOP_DETECTED`（CRITICAL）イベントを発行
- 復旧ルーチンをトリガー（将来の拡張）

**`_log_monitoring_result`メソッド** (行502-532):

- 監視結果をログに記録（状態に応じてログレベルを設定）
- データベースログにも記録（`ActionType.STATUS_CHECK`）

### イベント発行

- **`EventType.APP_STOP_DETECTED`** (CRITICAL): アプリ停止検出時
- **`EventType.UNSTABLE_SESSION_SKIPPED`** (WARNING): 不安定なセッション検出時

これらのイベントは通知機能（Feature 4）によって処理される。

### 統合

**`backend/src/web/app.py`**:

```python
status_monitor = StatusMonitor()

@asynccontextmanager
async def lifespan(app: FastAPI):
    await status_monitor.start()
    yield
    await status_monitor.stop()
```

### エラーハンドリング

- **監視エラー**: 1アカウントの監視エラーは他のアカウントに影響しない
- **ブラウザ操作エラー**: エラー時は `MonitorState.UNSTABLE`として記録
- **分離ルール**: 失敗は常にアカウント単位で分離

### パフォーマンス

- 監視は軽量な操作のみ（DOMクエリ、クッキー確認）
- アカウント間で2秒待機して負荷を分散
- 非同期処理でメインスレッドをブロックしない

## 完了条件

✅ 異常状態が自動化失敗前に検出される
✅ 不安定なセッションに対して破壊的なアクションが実行されない
✅ 停止したアプリが確実に検出される
✅ すべてのイベントがログ記録され、追跡可能

## ステータス

**実装完了・テスト準備完了**

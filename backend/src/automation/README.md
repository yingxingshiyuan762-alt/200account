# Playwright ブラウザ自動化基盤

## 概要

このモジュールは、200アカウントの自動化処理を実行するPlaywrightベースの基盤です。

## 原則

1. **1アカウント = 1 Browser Context**
   - Cookie / localStorage / session を完全分離
   - 強制ログアウト防止
   - 手動操作検知が正確になる

2. **ログは全操作の前後に必ず出す**
   - すべての操作は `log_manager.log_operation()` でラップ
   - デバッグ用ではなく制御装置として機能

3. **落ちる前提で再起動を設計**
   - アプリクラッシュ検知と自動再起動
   - タイムアウト・例外耐性

## 使用方法

### 1. 依存関係のインストール

```bash
pip install playwright
playwright install chromium
```

### 2. 単一アカウントの実行

```python
from src.automation.executor import ParallelExecutor
from src.database.connection import get_session
from src.database.repositories.account import AccountRepository

with get_session() as session:
    account_repo = AccountRepository(session)
    account = account_repo.get_by_id("account-id")
    
    executor = ParallelExecutor()
    result = executor.execute_single_account(account, task_type="schedule_update")
```

### 3. 複数アカウントの並列実行

```python
from src.automation.executor import ParallelExecutor
from src.database.connection import get_session
from src.database.repositories.account import AccountRepository

with get_session() as session:
    account_repo = AccountRepository(session)
    accounts = account_repo.get_active_accounts()
    
    executor = ParallelExecutor(max_workers=5)
    summary = executor.execute_accounts(accounts, task_type="schedule_update")
```

### 4. API経由での実行

```bash
# 全アカウント実行
curl -X POST http://localhost:5000/api/automation/execute \
  -H "Content-Type: application/json" \
  -d '{"task_type": "schedule_update"}'

# 単一アカウント実行
curl -X POST http://localhost:5000/api/automation/execute/{account_id} \
  -H "Content-Type: application/json" \
  -d '{"task_type": "schedule_update"}'

# テスト実行
curl -X POST http://localhost:5000/api/automation/test
```

## モジュール構成

- `browser_manager.py`: ブラウザとコンテキストの管理
- `url_resolver.py`: ログインURL自動判別
- `login_handler.py`: ログイン処理
- `manual_detector.py`: 手動操作検知
- `crash_detector.py`: アプリクラッシュ検知と再起動
- `worker.py`: 1アカウント処理単位のWorker関数
- `executor.py`: 並列実行エンジン

## タスク種別

- `schedule_update`: スケジュール自動更新
- `wait_reception`: 待機接客配信制御

## 並列実行制限

- **推奨**: 5〜10並列
- **禁止**: 200並列（リソース不足の原因）

## エラーハンドリング

- `ManualOperationDetectedError`: 手動操作検知時はスキップ
- `AppCrashError`: アプリクラッシュ時は自動再起動
- `LoginError`: ログイン失敗時はエラーカウント増加
- 5回連続エラーでアカウント無効化

## ログ

すべての操作は `AccountLog` テーブルに記録されます：
- 操作種別（LOGIN, SCHEDULE_UPDATE, WAIT_RECEPTION）
- ステータス（SUCCESS, FAILURE, SKIPPED）
- 実行時間
- コード位置（file_path, function_name, line_number）

## 次のステップ

1. 業務ロジックの実装（`worker.py` の `execute_schedule_update` と `execute_wait_reception`）
2. 赤× DOM の特定（`crash_detector.py` のセレクタ調整）
3. 5アカウント耐久テスト


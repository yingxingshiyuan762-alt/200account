# Account Loading Guide

## 概要

Google Sheetsから126アカウントを読み込み、データベースに登録する方法。

## Google Sheets情報

- **Sheet URL**: https://docs.google.com/spreadsheets/d/1-2ydkZ1K08HxB73EkJ5kZ3a3_Gp_Av54X4j5RcGOCso/edit?gid=556373435
- **除外行**: 1, 11, 101, 105
- **合計**: 126アカウント

## 2つの方法

### 方法1: 簡単読み込み（推奨）⚡

店舗名検証なしで高速読み込み。店舗名とURLは初回ログイン時に自動取得。

```bash
cd backend
python scripts/load_accounts_simple.py
```

**特徴**:
- ✅ 高速（数秒で完了）
- ✅ 店舗名は後でシステムが自動取得
- ✅ ログインURLも自動解決
- ✅ すぐに使用可能

**処理内容**:
1. Google Sheetsから126アカウントを取得
2. 既存のすべてのアカウントを削除
3. 新しいアカウントをデータベースに登録
   - `username`: Sheetsから
   - `password`: 暗号化してSheetsから
   - `store_name`: ユーザー名をデフォルト使用
   - `login_url`: doors1.shinchakun.info をデフォルト使用

### 方法2: 完全検証読み込み 🔍

Playwrightで実際にログインして店舗名を取得。

```bash
cd backend
python scripts/load_accounts_from_gsheet.py
```

**特徴**:
- ✅ 実際の店舗名を取得
- ✅ 各アカウントのログインURLを確認
- ⚠️ 時間がかかる（126アカウント × 約10秒 = 約20分）
- ⚠️ ブラウザ自動化が必要

**処理内容**:
1. Google Sheetsから126アカウントを取得
2. 既存のすべてのアカウントを削除
3. Playwrightでログイン検証（オプション）:
   - 各アカウントでログイン
   - 実際の店舗名を取得
   - 使用可能なログインURLを確認
4. データベースに登録

## 使用方法

### 前提条件

1. **Google Sheetsが公開されていること**
   - シートの共有設定: 「リンクを知っている全員」が閲覧可能
   - または、CSVエクスポートが有効

2. **必要なPythonパッケージ**
   ```bash
   pip install requests playwright
   ```

3. **データベース接続**
   - MySQL/MariaDBが起動していること
   - `.env`ファイルに正しい接続情報

### 実行手順（方法1: 簡単読み込み）

```bash
# バックエンドディレクトリに移動
cd backend

# スクリプトを実行
python scripts/load_accounts_simple.py
```

**実行例**:
```
============================================================
SIMPLE ACCOUNT LOADING SCRIPT
============================================================
Source: Google Sheets
Excluded rows: [1, 11, 101, 105]
Expected total: 126 accounts
============================================================

Step 1: Fetching accounts from Google Sheets...
✓ Fetched 126 accounts

📊 Found 126 accounts
📋 First 5 accounts:
  1. szo22_25794 (password: s89***)
  2. inpon_hmm (password: 3F6***)
  3. inpon_hmm02 (password: 714***)
  4. szo22_75934 (password: hCw***)
  5. szo22_46598 (password: t8q***)

⚠️  Delete all existing accounts and load these? (yes/no): yes

Step 2: Deleting existing accounts...
✓ Deleted 0 existing accounts

Step 3: Loading accounts to database...
✓ Database load completed: 126 success, 0 failed

Step 4: Verification...
✓ Total accounts in database: 126
✓ Active accounts: 126

============================================================
✅ ACCOUNT LOADING COMPLETED
============================================================
✓ Loaded: 126 accounts
✓ Store names will be auto-updated on first login
✓ Login URLs will be auto-resolved on first run
============================================================
```

### 実行手順（方法2: 完全検証）

```bash
cd backend
python scripts/load_accounts_from_gsheet.py
```

**選択肢**:
- `y`: 全126アカウントを検証（約20分）
- `10`: 最初の10アカウントのみ検証
- `n`: 検証スキップ（方法1と同じ）

## 自動更新について

方法1（簡単読み込み）を使用した場合でも、システムが自動的に更新します：

### 初回ログイン時の自動更新

```python
# worker.py の run_account_job 関数内（約115-120行目）
# ログイン成功後、URLをDBに保存
with get_session() as session:
    account_repo = AccountRepository(session)
    account_repo.update_login_info(
        account_id=account_id,
        session_token=token,
        login_url=base_url  # 実際に使用されたURL
    )
```

**自動的に更新される情報**:
- ✅ `login_url`: 実際にログインできたURL（doors1 or doors2）
- ✅ `session_token`: セッショントークン
- ✅ `last_login_at`: 最終ログイン時刻
- ✅ `last_success_at`: 最終成功時刻

**店舗名の更新**:
店舗名は現在自動取得されませんが、必要に応じて以下の方法で更新できます：

1. **手動更新**: Web UIから編集
2. **パッチで更新**: 店舗名取得パッチを作成
3. **スクリプトで更新**: 別途スクリプトを実行

## データベース構造

アカウント情報は `accounts` テーブルに保存されます：

```sql
CREATE TABLE accounts (
    id CHAR(36) PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,      -- Google Sheetsから
    password_encrypted TEXT NOT NULL,           -- 暗号化されたパスワード
    store_name VARCHAR(200) NOT NULL,           -- 店舗名（デフォルト: username）
    login_url VARCHAR(255),                     -- ログインURL
    is_active BOOLEAN DEFAULT TRUE,
    status VARCHAR(50) DEFAULT 'IDLE',
    session_token TEXT,
    last_login_at DATETIME,
    last_success_at DATETIME,
    error_count INTEGER DEFAULT 0,
    last_error TEXT,
    metadata_json JSON,
    created_at DATETIME,
    updated_at DATETIME
);
```

## トラブルシューティング

### Google Sheetsからの取得失敗

**エラー**: `Failed to fetch from Google Sheets`

**原因**:
- シートが公開されていない
- URLが間違っている
- ネットワーク接続エラー

**解決**:
1. Google Sheetsの共有設定を確認
2. シートIDとGIDが正しいか確認
3. ブラウザでCSV URLに直接アクセスして確認:
   ```
   https://docs.google.com/spreadsheets/d/1-2ydkZ1K08HxB73EkJ5kZ3a3_Gp_Av54X4j5RcGOCso/export?format=csv&gid=556373435
   ```

### データベース接続エラー

**エラー**: `Failed to delete accounts` / `Failed to load accounts`

**原因**:
- データベースが起動していない
- 接続情報が間違っている

**解決**:
1. XAMPPでMySQLを起動
2. `.env`の`DATABASE_URL`を確認
3. 接続テスト:
   ```bash
   python check_connection.py
   ```

### 暗号化エラー

**エラー**: `ENCRYPTION_KEY` related error

**原因**:
- `.env`に`ENCRYPTION_KEY`が設定されていない

**解決**:
1. `.env`を確認
2. キーが存在しない場合は生成:
   ```python
   from cryptography.fernet import Fernet
   print(Fernet.generate_key().decode())
   ```

## CSV フォーマット

Google Sheetsは以下の形式である必要があります：

```csv
NO,ID,PASS,備考
1,szo22_25794,s89ynkXR52,テストアカウント
2,inpon_hmm,3F6KwLSdEe,
3,inpon_hmm02,714036,
...
```

**カラム**:
- A (NO): 番号（オプション）
- B (ID): ユーザー名（必須）
- C (PASS): パスワード（必須）
- D (備考): メモ（オプション）

## セキュリティ

1. **パスワードの暗号化**
   - すべてのパスワードはFernet（AES-256-GCM）で暗号化
   - 暗号化キーは`.env`で管理
   - 平文パスワードはデータベースに保存されない

2. **Google Sheetsのアクセス**
   - 読み取り専用アクセス
   - 公開CSVエンドポイントを使用
   - 認証情報は不要

3. **ログ出力**
   - パスワードはログに出力しない
   - 最初の3文字のみ表示（デバッグ用）

## まとめ

**推奨フロー**:
1. `load_accounts_simple.py` で126アカウントを高速読み込み
2. システムを起動
3. 初回実行時に各アカウントが自動的にログインURLと店舗情報を更新

**メリット**:
- ⚡ 高速（数秒で完了）
- 🔄 自動更新される
- 🎯 シンプルで確実

---

**作成日**: 2024-01-28  
**対象アカウント数**: 126  
**除外行**: 1, 11, 101, 105

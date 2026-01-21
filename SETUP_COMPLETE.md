# 200アカウント自動化システム - セットアップ完了ガイド

## 📋 セットアップの概要

このプロジェクトのデータベース、バックエンド、フロントエンドを正しく接続するためのセットアップ手順です。

---

## ✅ 完了した作業

### 1. MySQLデータベーススキーマファイルの作成
- ✅ `database/mysql_schema.sql` - 完全なMySQLスキーマファイル
- ✅ `database/mysql_migration_fix.sql` - 既存データベース用のマイグレーションファイル

### 2. アカウントインポートスクリプトの作成
- ✅ `backend/scripts/import_accounts.py` - CSV/テキストファイルからアカウントをインポート
- ✅ `backend/accounts_template.csv` - アカウントデータのテンプレート

### 3. セットアップガイドの作成
- ✅ `database/MYSQL_SETUP_GUIDE.md` - 詳細なセットアップ手順

---

## 🚀 セットアップ手順

### ステップ1: データベースの作成

1. **phpMyAdminを開く**
   - ブラウザで http://localhost/phpmyadmin/ を開く
   - XAMPP Control Panel で MySQL が起動していることを確認

2. **データベースを作成**
   - 左サイドバーで「新規作成」をクリック
   - データベース名: `200account`
   - 照合順序: `utf8mb4_unicode_ci`
   - 「作成」をクリック

3. **スキーマを実行**
   - 作成した `200account` データベースを選択
   - 「SQL」タブをクリック
   - `database/mysql_schema.sql` の内容をすべてコピー＆貼り付け
   - 「実行」をクリック
   - 成功メッセージを確認

### ステップ2: アカウントデータのインポート

#### オプションA: CSVファイルからインポート（推奨）

1. **CSVファイルを準備**
   - `backend/accounts_template.csv` をテンプレートとして使用
   - すべての200アカウントを以下の形式で記録：

```csv
username,password,store_name,login_url
szo22_25794,s89ynkXR52,サンプル店舗1,https://doors1.shinchakun.info/dokodemo/#/
szo22_25795,password2,サンプル店舗2,https://doors2.shinchakun.info/dokodemo/#/
...
```

2. **インポート実行**
```bash
cd backend
python scripts/import_accounts.py accounts.csv
```

#### オプションB: サンプルアカウントを生成（テスト用）

```bash
cd backend
python scripts/insert_sample_accounts.py --count 200
```

### ステップ3: 環境変数の設定

1. **`.env` ファイルを作成**
   - `backend/.env` ファイルを作成（存在しない場合）

2. **設定を記述**
```env
# データベース接続 (MySQL - XAMPP)
DATABASE_URL=mysql+pymysql://root@localhost:3306/200account?charset=utf8mb4

# 暗号化キー（パスワード暗号化用）
ENCRYPTION_KEY=your-encryption-key-here

# Webサーバー設定
WEB_HOST=0.0.0.0
WEB_PORT=5000
SECRET_KEY=your-secret-key-here

# デバッグモード
DEBUG=False
LOG_LEVEL=INFO
```

3. **暗号化キーを生成（オプション）**
```bash
cd backend
python -m src.database.encryption generate
```

### ステップ4: データベース接続の確認

```bash
cd backend
python check_connection.py
```

**期待される出力：**
```
============================================================
MYSQL CONNECTION STATUS
============================================================

1. Testing basic connection...
   Status: [CONNECTED]

2. Testing query execution...
   Database: 200account
   MySQL: 8.0.x...
   [OK] Query successful

3. Health check...
   Connected: True
   Tables Exist: True

============================================================
[RESULT] PROJECT IS CONNECTED TO MYSQL
============================================================
```

### ステップ5: バックエンドサーバーの起動

```bash
cd backend
python run.py
```

**期待される出力：**
```
============================================================
Starting FastAPI Server
============================================================
Host: 0.0.0.0
Port: 5000
Backend API: http://localhost:5000/api/system/status
API Docs: http://localhost:5000/docs
Frontend: http://localhost:8080
============================================================
Server is starting...
```

### ステップ6: フロントエンドの起動

**新しいターミナルウィンドウで：**

```bash
cd frontend
npm install  # 初回のみ
npm run dev
```

**期待される出力：**
```
  VITE v5.x.x  ready in xxx ms

  ➜  Local:   http://localhost:8080/
  ➜  Network: use --host to expose
```

### ステップ7: 動作確認

1. **バックエンドAPIの確認**
   - ブラウザで http://localhost:5000/api/system/status を開く
   - JSON形式でシステム状態が表示されることを確認

2. **APIドキュメントの確認**
   - ブラウザで http://localhost:5000/docs を開く
   - Swagger UI が表示されることを確認

3. **フロントエンドの確認**
   - ブラウザで http://localhost:8080 を開く
   - ダッシュボードが表示されることを確認
   - アカウント一覧が表示されることを確認

---

## 🔍 接続設定の確認

### バックエンド → データベース

- **設定ファイル**: `backend/config/config.py`
- **デフォルト接続**: `mysql+pymysql://root@localhost:3306/200account?charset=utf8mb4`
- **環境変数**: `DATABASE_URL` (`.env` ファイルで設定可能)

### フロントエンド → バックエンド

- **設定ファイル**: `frontend/src/lib/api.ts`
- **デフォルトURL**: `http://localhost:5000/api`
- **環境変数**: `VITE_API_URL` (`.env` ファイルで設定可能、例: `VITE_API_URL=http://localhost:5000/api`)

---

## 📝 チェックリスト

セットアップが完了したら、以下を確認してください：

### データベース
- [ ] データベース `200account` が作成されている
- [ ] テーブル `accounts`, `account_logs`, `session_histories`, `system_configs` が存在する
- [ ] `system_configs` テーブルに6件のデフォルト設定が入っている
- [ ] アカウントデータがインポートされている（`accounts` テーブルを確認）
- [ ] `python check_connection.py` が成功する

### バックエンド
- [ ] `.env` ファイルが正しく設定されている
- [ ] `python run.py` でサーバーが起動する
- [ ] http://localhost:5000/api/system/status が応答する
- [ ] http://localhost:5000/docs が表示される

### フロントエンド
- [ ] `npm install` が完了している
- [ ] `npm run dev` でサーバーが起動する
- [ ] http://localhost:8080 が表示される
- [ ] ダッシュボードでアカウント一覧が表示される

---

## 🐛 トラブルシューティング

### エラー: "Access denied for user 'root'@'localhost'"

**解決方法:**
- `.env` ファイルで `DATABASE_URL` を確認
- MySQL のパスワードが設定されている場合は、URL に含める：
  ```
  DATABASE_URL=mysql+pymysql://root:yourpassword@localhost:3306/200account?charset=utf8mb4
  ```

### エラー: "Unknown database '200account'"

**解決方法:**
- ステップ1を完了し、データベース `200account` を作成してください

### エラー: "Table 'accounts' doesn't exist"

**解決方法:**
- `database/mysql_schema.sql` を実行してテーブルを作成してください

### エラー: "Foreign key constraint is incorrectly formed"

**解決方法:**
- `database/mysql_schema.sql` を使用してください（`mysql_migration_fix.sql` ではなく）

### フロントエンドがバックエンドに接続できない

**解決方法:**
1. バックエンドサーバーが起動していることを確認
2. `frontend/.env` ファイルを作成して以下を設定：
   ```
   VITE_API_URL=http://localhost:5000/api
   ```
3. フロントエンドサーバーを再起動

---

## 📚 関連ファイル

- **データベーススキーマ**: `database/mysql_schema.sql`
- **セットアップガイド**: `database/MYSQL_SETUP_GUIDE.md`
- **アカウントインポートスクリプト**: `backend/scripts/import_accounts.py`
- **接続確認スクリプト**: `backend/check_connection.py`
- **バックエンド設定**: `backend/config/config.py`
- **フロントエンドAPI設定**: `frontend/src/lib/api.ts`

---

## 🎉 セットアップ完了後の次のステップ

1. **アカウントデータの確認**
   - phpMyAdmin で `accounts` テーブルを確認
   - 200アカウントが正しくインポートされていることを確認

2. **システムのテスト**
   - フロントエンドからアカウント一覧を表示
   - システム状態を確認
   - ログ機能をテスト

3. **本番環境への準備**
   - 暗号化キーを安全に保管
   - データベースのバックアップ設定
   - 環境変数の適切な管理

---

**問題が発生した場合:**
- ログファイルを確認: `backend/logs/`
- データベース接続を再確認: `python backend/check_connection.py`
- phpMyAdmin でデータベースとテーブルの状態を確認

# MySQL Database Setup Guide

200アカウント自動化システムのMySQLデータベースセットアップガイド

## 📋 前提条件

1. **XAMPP** がインストールされていること
2. **MySQL** が起動していること（XAMPP Control Panel から開始）
3. **phpMyAdmin** にアクセスできること（http://localhost/phpmyadmin/）

---

## 🔧 ステップ1: データベーススキーマの作成

### 方法1: phpMyAdminを使用（推奨）

1. ブラウザで http://localhost/phpmyadmin/ を開く
2. 左サイドバーで「新規作成」をクリック
3. データベース名: `200account`
4. 照合順序: `utf8mb4_unicode_ci`
5. 「作成」をクリック
6. 作成した `200account` データベースを選択
7. 上部の「SQL」タブをクリック
8. `database/mysql_schema.sql` ファイルを開く
9. ファイルの内容をすべてコピーしてSQLクエリボックスに貼り付け
10. 「実行」ボタンをクリック（または Ctrl+Enter）
11. 成功メッセージが表示されることを確認

### 方法2: MySQLコマンドラインを使用

```bash
mysql -u root -p < database/mysql_schema.sql
```

---

## 📊 ステップ2: アカウントデータのインポート

200アカウントのデータをインポートする方法：

### 方法1: CSVファイルからインポート（推奨）

1. `backend/accounts_template.csv` をテンプレートとして使用
2. すべてのアカウント情報をCSV形式で記録：

```csv
username,password,store_name,login_url
szo22_25794,s89ynkXR52,サンプル店舗1,https://doors1.shinchakun.info/dokodemo/#/
szo22_25795,password2,サンプル店舗2,https://doors2.shinchakun.info/dokodemo/#/
...
```

3. ファイルを保存（例: `backend/accounts.csv`）
4. 以下のコマンドでインポート：

```bash
cd backend
python scripts/import_accounts.py accounts.csv
```

### 方法2: テキストファイルからインポート

1. アカウント情報をテキストファイルに記録（カンマ区切りまたはコロン区切り）：

```
szo22_25794,s89ynkXR52,サンプル店舗1,https://doors1.shinchakun.info/dokodemo/#/
szo22_25795:password2:サンプル店舗2:https://doors2.shinchakun.info/dokodemo/#/
...
```

2. ファイルを保存（例: `backend/accounts.txt`）
3. 以下のコマンドでインポート：

```bash
cd backend
python scripts/import_accounts.py accounts.txt --format text
```

### 方法3: サンプルアカウントを生成（テスト用）

テスト目的で200個のサンプルアカウントを生成：

```bash
cd backend
python scripts/insert_sample_accounts.py --count 200
```

---

## ✅ ステップ3: データベース接続の確認

### 接続テストスクリプトを実行

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

---

## 🔍 トラブルシューティング

### エラー: "Access denied for user 'root'@'localhost'"

**解決方法:**
1. XAMPP Control Panel で MySQL を停止
2. `backend/.env` ファイルを作成（存在しない場合）
3. データベース接続情報を設定：

```env
DATABASE_URL=mysql+pymysql://root:@localhost:3306/200account?charset=utf8mb4
```

または、パスワードが設定されている場合：

```env
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
- `database/mysql_migration_fix.sql` を使用する場合は、テーブルを個別に作成するか、`mysql_schema.sql` を使用してください

---

## 📝 環境変数の設定

`backend/.env` ファイルを作成または確認：

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

**暗号化キーを生成する場合：**
```bash
cd backend
python -m src.database.encryption generate
```

---

## ✅ 確認チェックリスト

セットアップが完了したら、以下を確認してください：

- [ ] データベース `200account` が作成されている
- [ ] テーブル `accounts`, `account_logs`, `session_histories`, `system_configs` が存在する
- [ ] `system_configs` テーブルに6件のデフォルト設定が入っている
- [ ] アカウントデータがインポートされている（`accounts` テーブルを確認）
- [ ] `python check_connection.py` が成功する
- [ ] `.env` ファイルが正しく設定されている

---

## 📚 次のステップ

データベースセットアップが完了したら：

1. **バックエンドサーバーの起動**
   ```bash
   cd backend
   python run.py
   ```

2. **フロントエンドの起動**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

3. **ブラウザでアクセス**
   - フロントエンド: http://localhost:5173 (または設定したポート)
   - バックエンドAPI: http://localhost:5000/api/system/status
   - APIドキュメント: http://localhost:5000/docs

---

**問題が発生した場合:**
- ログファイルを確認: `backend/logs/`
- データベース接続を再確認: `python backend/check_connection.py`
- phpMyAdmin でデータベースとテーブルの状態を確認

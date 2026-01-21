# Database Error Fix Guide

## 🔴 エラーの原因

バックエンドが起動時に以下のエラーを発生しています：

```
pymysql.err.OperationalError: (1054, "Unknown column 'accounts.is_active' in 'field list'")
```

**原因：**
- `accounts` テーブルに `is_active` カラムが存在しない
- コードのモデル定義（`backend/src/database/models.py`）では `is_active` カラムが必須だが、データベースのスキーマと一致していない
- 他のテーブル（`account_logs`, `session_histories`, `system_configs`）も存在しない可能性がある

---

## ✅ 解決方法

### 方法1: SQLスクリプトを実行（推奨）

1. **phpMyAdminを開く**
   - ブラウザで http://localhost/phpmyadmin/ を開く

2. **データベースを選択**
   - 左サイドバーで `200account` データベースを選択

3. **SQLタブを開く**
   - 上部の「SQL」タブをクリック

4. **SQLスクリプトを実行**
   - `database/fix_database.sql` ファイルを開く
   - ファイルの内容をすべてコピー
   - SQLクエリボックスに貼り付け
   - 「実行」ボタンをクリック（または Ctrl+Enter）

5. **成功メッセージを確認**
   - "Database fix completed successfully!" というメッセージが表示されることを確認

6. **バックエンドを再起動**
   ```bash
   cd backend
   python run.py
   ```

### 方法2: 完全なスキーマを実行

もしテーブルがほとんど存在しない場合は、完全なスキーマを実行：

1. phpMyAdminで `200account` データベースを選択
2. 「SQL」タブを開く
3. `database/mysql_schema.sql` ファイルの内容をコピー＆実行
4. バックエンドを再起動

---

## 🔍 確認方法

### データベース接続の確認

```bash
cd backend
python check_connection.py
```

**期待される出力：**
```
Tables Exist: True
```

### バックエンドの起動確認

```bash
cd backend
python run.py
```

**期待される動作：**
- エラーが発生しない
- サーバーが正常に起動する
- "Server is starting..." が表示される

---

## 📋 修正される内容

`database/fix_database.sql` スクリプトは以下を実行します：

1. ✅ `accounts` テーブルに `is_active` カラムを追加
2. ✅ `accounts` テーブルに必要なインデックスを追加
3. ✅ `account_logs` テーブルを作成（存在しない場合）
4. ✅ `session_histories` テーブルを作成（存在しない場合）
5. ✅ `system_configs` テーブルを作成（存在しない場合）
6. ✅ デフォルトのシステム設定を挿入

---

## ⚠️ 注意事項

- 既存のデータがある場合、`is_active` カラムはデフォルト値 `TRUE` で追加されます
- スクリプトは既に存在するカラムやテーブルをスキップするため、安全に何度でも実行できます
- 外部キー制約は個別に追加されるため、文字セット/照合順序の問題を回避します

---

## 🐛 トラブルシューティング

### エラー: "Table 'accounts' doesn't exist"

**解決方法：**
- `database/mysql_schema.sql` を実行して完全なスキーマを作成してください

### エラー: "Foreign key constraint is incorrectly formed"

**解決方法：**
- `database/fix_database.sql` を使用してください（外部キーを個別に追加するため）

### エラーが続く場合

1. phpMyAdminでテーブル構造を確認
2. `accounts` テーブルに `is_active` カラムが存在するか確認
3. ログファイルを確認：`backend/logs/error_2026-01-11.log`

---

## 📚 関連ファイル

- **修正スクリプト**: `database/fix_database.sql`
- **完全スキーマ**: `database/mysql_schema.sql`
- **モデル定義**: `backend/src/database/models.py`
- **接続確認**: `backend/check_connection.py`

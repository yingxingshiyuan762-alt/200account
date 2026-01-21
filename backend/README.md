# Backend - 200 Account Automation System

Shinchakun自動化システムのバックエンドサーバー

## セットアップ

### 1. 依存関係のインストール

```bash
pip install -r requirements.txt
```

### 2. 環境変数の設定

`.env`ファイルを作成し、以下の変数を設定してください：

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

暗号化キーを生成する場合：
```bash
python -m src.database.encryption generate
```

### 3. データベースの初期化

MySQL (phpMyAdminまたはMySQLコマンドライン)で`database/mysql_schema.sql`を実行してください。

### 4. サーバーの起動

**推奨方法:**

```bash
python run.py
```

または

```bash
uvicorn src.web.app:app --host 0.0.0.0 --port 5000 --reload
```

**Windowsの場合:**
```bash
start.bat
```

**注意:** FastAPIアプリケーションは`uvicorn`で起動します。開発モードでは`--reload`オプションで自動リロードが有効になります。

## API エンドポイント

- `GET /api/system/status` - システム状態
- `GET /api/accounts` - アカウント一覧
- `GET /api/accounts/<id>` - アカウント詳細
- `GET /api/logs` - ログ一覧
- `GET /api/schedules/upcoming` - スケジュール情報

詳細は各エンドポイントのドキュメントを参照してください。

## ディレクトリ構造

```
backend/
├── config/          # 設定ファイル
├── src/             # ソースコード
│   ├── core/        # コア機能（ログ、イベントなど）
│   ├── database/    # データベース関連
│   └── web/         # Web API
├── scripts/         # ユーティリティスクリプト
└── requirements.txt # Python依存関係
```

## 開発

### サンプルデータの挿入

```bash
python scripts/insert_sample_accounts.py --count 200
```

### データベース接続の確認

```bash
python scripts/verify_accounts.py
```

### データベース接続テスト

```bash
python check_connection.py
```

## 注意事項

- `psutil`はオプションです。インストールされていない場合、システムリソースAPIはデフォルト値を返します。
- 本番環境では必ず`ENCRYPTION_KEY`を設定してください。


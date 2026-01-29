# Patch System Guide

## 概要

パッチシステムは、システムの修正や更新を**実行するだけで自動適用**できる強力な機能です。

### 特徴

- ✅ **簡単実行**: Pythonスクリプトを配置するだけで自動読み込み
- ✅ **依存関係管理**: パッチ間の依存関係を自動解決
- ✅ **ロールバック対応**: 実行済みパッチを安全に元に戻せる
- ✅ **検証機能**: 実行前後にパッチの妥当性を自動検証
- ✅ **Web UI管理**: ブラウザから簡単に管理・実行
- ✅ **実行履歴**: データベースで実行状態を永続化
- ✅ **自動実行**: 起動時に未実行パッチを自動検出

## パッチファイルの作成

### ディレクトリ構造

```
backend/
└── patches/
    ├── _template.py              # パッチテンプレート
    ├── example_001_database_fix.py
    ├── example_002_config_update.py
    └── patch_xxx_your_fix.py     # 新しいパッチ
```

### パッチファイルの構造

パッチファイルは以下の構造に従います：

```python
# ========================================
# パッチメタデータ（必須）
# ========================================

PATCH_ID = 'unique_patch_id'           # 一意のパッチID
PATCH_NAME = 'Patch Name'              # 表示名
PATCH_DESCRIPTION = 'What this does'   # 説明
PATCH_VERSION = '1.0.0'                # バージョン
PATCH_TYPE = 'hotfix'                  # タイプ（後述）

# オプション設定
AUTHOR = 'Developer Name'
DEPENDENCIES = []                      # 依存パッチID
TAGS = ['tag1', 'tag2']               # 検索用タグ

# フラグ
IS_CRITICAL = False                    # 緊急パッチか
REQUIRE_CONFIRMATION = False           # 実行前確認が必要か
AUTO_EXECUTE = True                    # 自動実行を許可するか

# ========================================
# パッチ実装（execute関数は必須）
# ========================================

def execute():
    """パッチのメイン処理（必須）"""
    # 実装コード
    return {
        'success': True,
        'message': '実行完了'
    }

def rollback():
    """ロールバック処理（オプション）"""
    # ロールバックコード
    return {
        'success': True
    }

def validate():
    """検証処理（オプション）"""
    # 検証コード
    return {
        'valid': True
    }
```

### パッチタイプ

| タイプ | 用途 |
|--------|------|
| `database` | データベーススキーマやデータの修正 |
| `code` | コードロジックの修正 |
| `config` | 設定値の変更 |
| `data` | データの移行や修正 |
| `migration` | 大規模なマイグレーション |
| `hotfix` | 緊急修正 |

## 実装例

### 例1: データベース修正パッチ

```python
PATCH_ID = 'fix_001_account_status'
PATCH_NAME = 'Fix Account Status'
PATCH_DESCRIPTION = 'Reset stuck account statuses to IDLE'
PATCH_VERSION = '1.0.0'
PATCH_TYPE = 'database'

def execute():
    from src.database.connection import get_session
    from src.database.models import Account, AccountStatus
    
    with get_session() as session:
        # PROCESSINGで停止しているアカウントをIDLEに戻す
        stuck_accounts = session.query(Account).filter_by(
            status=AccountStatus.PROCESSING.value
        ).all()
        
        count = 0
        for account in stuck_accounts:
            account.status = AccountStatus.IDLE.value
            count += 1
        
        session.commit()
        
        return {
            'success': True,
            'affected_rows': count,
            'message': f'{count} accounts reset to IDLE'
        }

def validate():
    from src.database.connection import get_session
    
    with get_session() as session:
        # データベース接続確認
        session.execute("SELECT 1")
        return {'valid': True}
```

### 例2: 設定変更パッチ

```python
PATCH_ID = 'config_001_update_schedule'
PATCH_NAME = 'Update Schedule Settings'
PATCH_DESCRIPTION = 'Enable automatic schedule updates'
PATCH_VERSION = '1.0.0'
PATCH_TYPE = 'config'
AUTO_EXECUTE = False  # 手動実行のみ
REQUIRE_CONFIRMATION = True  # 実行前確認が必要

def execute():
    from src.database.connection import get_session
    from src.database.models import SystemConfig
    
    with get_session() as session:
        config = session.query(SystemConfig).filter_by(
            key='schedule_update_enabled'
        ).first()
        
        if config:
            config.value = {'value': True}
            session.commit()
            
            return {
                'success': True,
                'message': 'Schedule update enabled'
            }
        else:
            return {
                'success': False,
                'error': 'Config not found'
            }

def rollback():
    from src.database.connection import get_session
    from src.database.models import SystemConfig
    
    with get_session() as session:
        config = session.query(SystemConfig).filter_by(
            key='schedule_update_enabled'
        ).first()
        
        if config:
            config.value = {'value': False}
            session.commit()
            
            return {
                'success': True,
                'message': 'Schedule update disabled'
            }
```

### 例3: 依存関係のあるパッチ

```python
PATCH_ID = 'migration_002_add_column'
PATCH_NAME = 'Add New Column'
PATCH_DESCRIPTION = 'Add email_verified column to accounts'
PATCH_VERSION = '1.0.0'
PATCH_TYPE = 'migration'
DEPENDENCIES = ['migration_001_create_table']  # 先に実行すべきパッチ
IS_CRITICAL = True  # 緊急パッチ

def execute():
    from src.database.connection import get_session
    from sqlalchemy import text
    
    with get_session() as session:
        # カラムが存在するか確認
        result = session.execute(text("""
            SELECT COUNT(*) FROM information_schema.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE()
            AND TABLE_NAME = 'accounts'
            AND COLUMN_NAME = 'email_verified'
        """)).scalar()
        
        if result == 0:
            # カラムを追加
            session.execute(text("""
                ALTER TABLE accounts 
                ADD COLUMN email_verified BOOLEAN DEFAULT FALSE
            """))
            session.commit()
            
            return {
                'success': True,
                'message': 'Column added successfully'
            }
        else:
            return {
                'success': True,
                'message': 'Column already exists',
                'skipped': True
            }

def rollback():
    from src.database.connection import get_session
    from sqlalchemy import text
    
    with get_session() as session:
        session.execute(text("""
            ALTER TABLE accounts 
            DROP COLUMN IF EXISTS email_verified
        """))
        session.commit()
        
        return {
            'success': True,
            'message': 'Column removed'
        }

def validate():
    from src.database.connection import get_session
    from src.database.models import Account
    
    with get_session() as session:
        # accountsテーブルが存在するか確認
        try:
            session.query(Account).first()
            return {'valid': True}
        except Exception as e:
            return {
                'valid': False,
                'reason': f'Accounts table not accessible: {str(e)}'
            }
```

## パッチの使用方法

### 方法1: Web UI（推奨）

1. **ブラウザでアクセス**:
   ```
   http://localhost:8080
   ```

2. **「パッチ管理」タブを開く**

3. **パッチを確認**:
   - すべて: 全パッチ一覧
   - 未実行: 実行されていないパッチ
   - 緊急: 緊急パッチのみ

4. **実行**:
   - 個別実行: 「実行」ボタンをクリック
   - 一括実行: 「未実行パッチを一括実行」ボタン

5. **ロールバック**:
   - ロールバック可能なパッチは「ロールバック」ボタンが表示される

### 方法2: REST API

#### すべてのパッチを取得
```bash
curl http://localhost:5000/api/patches
```

#### 未実行パッチを取得
```bash
curl http://localhost:5000/api/patches/pending
```

#### パッチを実行
```bash
curl -X POST http://localhost:5000/api/patches/{patch_id}/execute \
  -H "Content-Type: application/json" \
  -d '{"force": false}'
```

#### すべての未実行パッチを実行
```bash
curl -X POST http://localhost:5000/api/patches/execute-all
```

#### パッチをロールバック
```bash
curl -X POST http://localhost:5000/api/patches/{patch_id}/rollback
```

#### パッチを再読み込み
```bash
curl -X POST http://localhost:5000/api/patches/reload
```

### 方法3: Pythonコード

```python
from src.patch import patch_manager

# パッチを読み込み
patches = patch_manager.load_patches()

# 未実行パッチを取得
pending = patch_manager.get_pending_patches()

# パッチを実行
result = patch_manager.execute_patch('patch_id')

# すべての未実行パッチを実行
summary = patch_manager.execute_all_pending()

# パッチをロールバック
result = patch_manager.rollback_patch('patch_id')

# 統計を取得
stats = patch_manager.get_statistics()
```

## パッチの実行フロー

```
1. パッチ読み込み
   ↓
2. 依存関係チェック
   ↓
3. 実行前検証（validate関数）
   ↓
4. パッチ実行（execute関数）
   ↓
5. 実行後検証（validate関数）
   ↓
6. 結果をデータベースに記録
   ↓
7. 完了
```

### 失敗時の動作

- 実行前検証失敗 → パッチ実行せず、スキップ
- 実行中エラー → 失敗として記録
- 実行後検証失敗 → 自動ロールバック（可能な場合）

## ベストプラクティス

### 1. パッチIDの命名規則

```
{type}_{number}_{description}

例:
- database_001_fix_account_status
- config_001_enable_scheduler
- hotfix_001_session_timeout
- migration_001_add_email_field
```

### 2. バージョン管理

- パッチファイルはGitで管理
- 実行済みパッチは変更しない
- 新しい修正は新しいパッチで対応

### 3. テスト

```python
# ドライラン（シミュレーション）
result = patch_manager.dry_run('patch_id')

# 実行前に必ずvalidate関数をテスト
```

### 4. ロールバック

- 重要な変更は必ずロールバック関数を実装
- データ削除の場合は特に慎重に
- ロールバックもテストすること

### 5. ドキュメント

- パッチの説明は詳細に記述
- 影響範囲を明記
- 手動対応が必要な場合は記載

## トラブルシューティング

### パッチが読み込まれない

**原因**:
- ファイル名が不正（`_`で始まる）
- 必須フィールドが不足
- Pythonの構文エラー

**解決**:
```bash
# ログを確認
tail -f backend/logs/app.log | grep "patch"

# パッチを再読み込み
curl -X POST http://localhost:5000/api/patches/reload
```

### パッチ実行が失敗する

**原因**:
- 依存関係が満たされていない
- validate関数が失敗
- 実装にバグがある

**解決**:
1. ドライランで事前確認
2. ログでエラー詳細を確認
3. パッチファイルを修正
4. 再読み込みして再実行

### ロールバックできない

**原因**:
- rollback関数が未実装
- ロールバック不可能な変更（データ削除など）

**解決**:
- 手動で元に戻す
- 新しいパッチで修正

## セキュリティ

### 注意点

1. **パッチファイルは信頼できるソースのみ**
   - 未検証のパッチは実行しない
   - コードレビューを実施

2. **データベース変更は慎重に**
   - 本番環境では必ずバックアップ
   - まずステージング環境でテスト

3. **権限管理**
   - パッチディレクトリへの書き込み権限を制限
   - Web UIへのアクセス制御

## パッチ統計

システムは以下の統計を自動収集：

- 総パッチ数
- ステータス別カウント（成功/失敗/未実行）
- タイプ別カウント
- 緊急パッチ数
- 実行履歴

Web UIの「パッチ管理」ページで確認できます。

## 開発者向け情報

### データベーススキーマ

```sql
CREATE TABLE patch_records (
    patch_id VARCHAR(255) PRIMARY KEY,
    patch_name VARCHAR(255) NOT NULL,
    patch_type VARCHAR(50) NOT NULL,
    patch_version VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL,
    executed_at DATETIME NOT NULL,
    execution_time FLOAT DEFAULT 0.0,
    result JSON,
    error_message TEXT,
    rolled_back BOOLEAN DEFAULT FALSE,
    rolled_back_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

### API エンドポイント

| メソッド | パス | 説明 |
|----------|------|------|
| GET | `/api/patches` | 全パッチ取得 |
| GET | `/api/patches/statistics` | 統計取得 |
| GET | `/api/patches/pending` | 未実行パッチ取得 |
| GET | `/api/patches/critical` | 緊急パッチ取得 |
| GET | `/api/patches/{id}` | 特定パッチ取得 |
| POST | `/api/patches/{id}/execute` | パッチ実行 |
| POST | `/api/patches/execute-all` | 一括実行 |
| POST | `/api/patches/{id}/rollback` | ロールバック |
| POST | `/api/patches/{id}/dry-run` | ドライラン |
| POST | `/api/patches/reload` | 再読み込み |

### モジュール構成

```
src/patch/
├── __init__.py          # パッケージ初期化
├── models.py            # データモデル
├── patch_loader.py      # パッチ読み込み
├── patch_executor.py    # パッチ実行
├── patch_manager.py     # 統合管理
└── patch_registry.py    # 実行履歴管理
```

## FAQ

**Q: パッチを削除するには？**
A: パッチファイルを削除し、再読み込みしてください。実行済みパッチの記録はデータベースに残ります。

**Q: 同じパッチを再実行するには？**
A: `force=true`で実行するか、データベースから記録を削除してください。

**Q: パッチの実行順序は？**
A: 依存関係を考慮して自動的に決定されます。依存関係がない場合はファイル名順です。

**Q: 本番環境での推奨設定は？**
A: `AUTO_EXECUTE=False`, `REQUIRE_CONFIRMATION=True`を設定し、手動実行を推奨します。

---

**作成日**: 2024-01-27  
**最終更新**: 2024-01-27  
**バージョン**: 1.0.0

# Quick Start: Load 126 Accounts

## 最速の方法（推奨）⚡

```bash
cd backend
python scripts/load_accounts_simple.py
```

入力を求められたら `yes` と入力してEnter。

## 実行内容

1. ✅ Google Sheetsから126アカウント取得
2. ✅ 既存アカウント削除
3. ✅ 新規アカウント登録（暗号化されたパスワード）

## 完了後

```bash
# バックエンド起動
python run.py
```

システムが起動したら、各アカウントの初回実行時に：
- ✅ 実際のログインURLを自動検出
- ✅ 店舗名を自動取得
- ✅ データベースに保存

## トラブルシューティング

### Google Sheets アクセスエラー

シートが公開されていることを確認:
```
https://docs.google.com/spreadsheets/d/1-2ydkZ1K08HxB73EkJ5kZ3a3_Gp_Av54X4j5RcGOCso/edit?gid=556373435
```

### データベースエラー

XAMPPでMySQLが起動していることを確認。

---

**所要時間**: 約10秒  
**結果**: 126アカウントが使用可能

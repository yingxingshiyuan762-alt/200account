# Quick Start: Automatic Schedule Attendance Setting

## 概要

翌日のスケジュールを自動的に「出勤設定」に変更するスクリプト

## テスト実行

### 1. 単一アカウントでテスト

```bash
cd "C:\Users\Administrator\Documents\200 account automation\backend"
python scripts/auto_schedule_attendance.py
```

**テストアカウント**:
- Username: `inpon_hmm`
- Password: `3F6KwLSdEe`

### 2. 処理内容

スクリプトは以下を実行します:

1. ✅ ログイン（Playwright使用、ブラウザ可視化）
2. ✅ スケジュールページへ移動
3. ✅ 翌日の日付列を特定
4. ✅ 各行をスキャン:
   - 翌日が「休み」の場合
   - その行に出勤時間があればコピー
   - 翌日に出勤設定として登録
5. ✅ 変更を保存
6. ✅ ログアウト

### 3. 結果の確認

実行後、以下が表示されます:

```
SUCCESS!
================================================================================
Account: inpon_hmm
Rows processed: 24
Attendance set: 5
Already set: 15
Errors: 0
================================================================================
```

## UI調整が必要な場合

スケジュールページのUI構造によって、以下のセレクタ調整が必要な場合があります:

### スケジュールタブの検索

```python
schedule_selectors = [
    'a:has-text("カシュテ")',
    'a:has-text("カシ")',
    'a:has-text("キャスト")',
    # 必要に応じて追加
]
```

### 保存ボタンの検索

```python
save_selectors = [
    'button:has-text("一括登録")',
    'button:has-text("保存")',
    'button:has-text("更新")',
    # 必要に応じて追加
]
```

## デバッグモード

問題が発生した場合:

1. **ブラウザを可視化** (already enabled):
   ```python
   headless=False  # Line 682
   ```

2. **待機時間を増やす**:
   ```python
   slow_mo=2000  # Line 683 (default: 1000)
   ```

3. **スクリーンショットを撮る**:
   ```python
   page.screenshot(path=f"debug_{username}.png")
   ```

## 全アカウント実行

テストが成功したら、全126アカウント用のスクリプトを作成できます。

## トラブルシューティング

### エラー: "Schedule tab not found"

→ スケジュールタブのセレクタを調整してください

### エラー: "Tomorrow column not found"

→ 日付フォーマットを確認してください（例: "2/4(水)"）

### エラー: 編集ができない

→ UI の編集方法を確認し、`process_schedule_attendance` 関数内のクリック処理を調整してください

## ログの確認

詳細なログは以下で確認できます:

```bash
# コンソール出力にリアルタイムで表示されます
# ログファイルにも記録されます（設定による）
```

## 次のステップ

1. ✅ テスト実行
2. 🔧 UI要素の調整（必要に応じて）
3. 📋 全アカウント版の作成
4. ⏰ 定期実行の設定（AM 7:00-10:00）

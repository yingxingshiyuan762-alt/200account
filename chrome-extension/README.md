# Chrome Extension Installation Guide

## 概要

200 Account Automation Monitorは、バックエンドシステムからリアルタイムでエラー通知を受け取り、Chrome通知として表示するChrome拡張機能です。

## 機能

- ✅ リアルタイムエラー通知（WebSocket接続）
- ✅ フォールバックHTTPポーリング（接続失敗時）
- ✅ Chrome通知ポップアップ
- ✅ 通知履歴の表示
- ✅ 重要度別フィルタリング（CRITICAL/ERROR/WARNING）
- ✅ 自動再接続機能

## インストール手順

### 1. アイコンの準備

`icons`フォルダに以下のアイコンファイルを配置してください：

- `icon16.png` (16x16 pixels)
- `icon32.png` (32x32 pixels)
- `icon48.png` (48x48 pixels)
- `icon128.png` (128x128 pixels)
- `error.png` (128x128 pixels - 赤いアイコン)
- `warning.png` (128x128 pixels - 黄色いアイコン)

**簡易方法：** オンラインアイコンジェネレーター（https://www.favicon-generator.org/ など）を使用して、1つの画像から複数サイズを生成できます。

### 2. Chrome拡張機能として読み込む

1. Chromeブラウザを開く
2. アドレスバーに `chrome://extensions/` と入力してEnter
3. 右上の「デベロッパーモード」をONにする
4. 「パッケージ化されていない拡張機能を読み込む」をクリック
5. `chrome-extension`フォルダを選択

### 3. バックエンド接続の確認

1. バックエンドサーバーが起動していることを確認：
   ```bash
   cd backend
   python run.py
   ```

2. 拡張機能アイコンをクリックしてポップアップを開く

3. ステータスインジケーターが緑色（接続済み）になることを確認

## 使用方法

### 通知の受信

エラーが発生すると、自動的にChrome通知が表示されます：

- **CRITICAL/ERROR**: 赤いアイコン、自動で閉じない
- **WARNING**: 黄色いアイコン、自動で閉じる

通知をクリックすると、拡張機能ポップアップが開きます。

### 通知履歴の確認

1. 拡張機能アイコンをクリック
2. 通知履歴が表示されます
3. 未読通知は青いハイライトで表示されます

### 通知の管理

- **すべて既読**: すべての通知を既読にする
- **履歴を消去**: 通知履歴をすべて削除する
- **再接続**: WebSocket接続を再確立する

## トラブルシューティング

### 接続できない場合

1. バックエンドが起動していることを確認：
   ```bash
   # Windows PowerShell
   netstat -ano | findstr :5000
   ```

2. ファイアウォールが5000番ポートをブロックしていないか確認

3. `manifest.json`の`host_permissions`を確認：
   ```json
   "host_permissions": [
     "http://localhost:5000/*",
     "http://127.0.0.1:5000/*"
   ]
   ```

### 通知が表示されない場合

1. Chrome通知の許可を確認：
   - Chromeの設定 > プライバシーとセキュリティ > サイトの設定 > 通知
   - 拡張機能の通知が「許可」になっているか確認

2. Windowsの通知設定を確認：
   - Windows設定 > システム > 通知
   - 「アプリやその他の送信者からの通知を取得する」がON

3. 拡張機能を再読み込み：
   - `chrome://extensions/`を開く
   - 拡張機能の「更新」ボタンをクリック

### WebSocket接続エラー

接続エラーが発生した場合、自動的にHTTPポーリングにフォールバックします（30秒間隔）。

接続を回復するには：
1. バックエンドを再起動
2. 拡張機能の「再接続」ボタンをクリック

## 設定のカスタマイズ

### バックエンドURLの変更

VPSや別のホストで実行する場合、`background.js`の設定を変更してください：

```javascript
// Configuration
const BACKEND_WS_URL = 'ws://your-server:5000/ws/notifications';
const BACKEND_HTTP_URL = 'http://your-server:5000/api/notifications/extension';
```

同時に`manifest.json`の`host_permissions`も更新してください：

```json
"host_permissions": [
  "http://your-server:5000/*",
  "ws://your-server:5000/*"
]
```

### ポーリング間隔の変更

`background.js`の以下の値を変更してください：

```javascript
const RECONNECT_INTERVAL = 5000; // 再接続間隔（ミリ秒）
const POLL_INTERVAL = 30000; // ポーリング間隔（ミリ秒）
```

## セキュリティに関する注意

- この拡張機能は開発版であり、本番環境では適切な認証とHTTPS接続を使用してください
- `manifest.json`の`host_permissions`は必要最小限に制限してください
- 本番環境ではWebSocket接続にWSS（SSL/TLS）を使用することを推奨します

## 開発者向け情報

### ファイル構成

```
chrome-extension/
├── manifest.json       # 拡張機能の設定
├── background.js       # バックグラウンドサービスワーカー
├── popup.html          # ポップアップUI
├── popup.js            # ポップアップロジック
├── icons/              # アイコンファイル
└── README.md           # このファイル
```

### デバッグ方法

1. `chrome://extensions/`を開く
2. 拡張機能の「詳細」をクリック
3. 「Service Workerを検証」をクリックしてDevToolsを開く
4. Console タブでログを確認

### WebSocket通信フォーマット

**クライアント → サーバー（登録）:**
```json
{
  "type": "register",
  "client": "chrome_extension",
  "timestamp": "2024-01-01T00:00:00Z"
}
```

**サーバー → クライアント（通知）:**
```json
{
  "type": "notification",
  "id": "unique-event-id",
  "severity": "ERROR",
  "title": "エラー発生",
  "message": "エラーメッセージ",
  "account_id": "account-uuid",
  "account_username": "username",
  "timestamp": "2024-01-01T00:00:00Z"
}
```

## サポート

問題が発生した場合は、以下を確認してください：

1. バックエンドのログ（`backend/logs/app.log`）
2. 拡張機能のコンソールログ（`chrome://extensions/` > Service Workerを検証）
3. Chrome DevToolsのNetworkタブ（WebSocket接続を確認）

---

**作成日**: 2024-01-27  
**バージョン**: 1.0.0  
**対応Chrome**: バージョン 88以上

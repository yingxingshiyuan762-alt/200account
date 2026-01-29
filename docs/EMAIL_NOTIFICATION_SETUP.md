# Email Notification Setup Guide

## 概要

このガイドでは、Gmail SMTPを使用してエラー通知メールを設定する方法を説明します。

## 前提条件

- Gmailアカウント（送信用）
- アプリパスワードの生成が必要

## セットアップ手順

### 1. Gmailアプリパスワードの生成

Googleアカウントで2段階認証を有効にし、アプリパスワードを生成します。

#### ステップ 1: 2段階認証を有効化

1. [Googleアカウント](https://myaccount.google.com/)にアクセス
2. 左側メニューから「セキュリティ」をクリック
3. 「Googleへのログイン」セクションで「2段階認証プロセス」をクリック
4. 画面の指示に従って2段階認証を有効にする

#### ステップ 2: アプリパスワードを生成

1. [アプリパスワード](https://myaccount.google.com/apppasswords)にアクセス
2. 「アプリを選択」ドロップダウンから「メール」を選択
3. 「デバイスを選択」ドロップダウンから「Windowsパソコン」を選択
4. 「生成」をクリック
5. 表示された16文字のパスワードをコピー（スペースなし）

**重要**: このパスワードは1回しか表示されません。安全な場所に保存してください。

### 2. .envファイルの設定

`backend/.env`ファイルを開き、以下の設定を更新してください：

```env
# Email Notification Settings (Gmail SMTP)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USE_TLS=True
SMTP_USERNAME=your-gmail@gmail.com
SMTP_PASSWORD=xxxx-xxxx-xxxx-xxxx
SMTP_FROM_EMAIL=your-gmail@gmail.com
NOTIFICATION_EMAILS=yingxingshiyuan762@gmail.com
NOTIFICATION_COOLDOWN_MINUTES=12
```

#### 設定項目の説明

| 項目 | 説明 | 例 |
|------|------|-----|
| `SMTP_HOST` | SMTPサーバーのホスト名 | `smtp.gmail.com` |
| `SMTP_PORT` | SMTPポート（TLS） | `587` |
| `SMTP_USE_TLS` | TLS使用の有無 | `True` |
| `SMTP_USERNAME` | 送信用Gmailアドレス | `your-email@gmail.com` |
| `SMTP_PASSWORD` | アプリパスワード（16文字） | `abcd efgh ijkl mnop` |
| `SMTP_FROM_EMAIL` | 送信者アドレス | `your-email@gmail.com` |
| `NOTIFICATION_EMAILS` | 受信者アドレス（カンマ区切り） | `user1@gmail.com,user2@gmail.com` |
| `NOTIFICATION_COOLDOWN_MINUTES` | 同一通知の再送間隔（分） | `12` |

### 3. 複数の受信者を設定する場合

複数のメールアドレスに通知を送信する場合、カンマ区切りで指定します：

```env
NOTIFICATION_EMAILS=email1@gmail.com,email2@gmail.com,email3@gmail.com
```

### 4. 設定のテスト

バックエンドを再起動して設定をテストします：

```bash
cd backend
python run.py
```

起動ログで以下の内容を確認してください：

```
Email Notifier Starting
Recipient emails: 1 addresses
Cooldown window: 12.0 minutes
SMTP host: smtp.gmail.com:587
```

### 5. 手動テスト（オプション）

設定が正しいか手動でテストする場合：

```python
# backend/test_email.py
import smtplib
from email.mime.text import MIMEText

SMTP_HOST = 'smtp.gmail.com'
SMTP_PORT = 587
SMTP_USERNAME = 'your-gmail@gmail.com'
SMTP_PASSWORD = 'your-app-password'
TO_EMAIL = 'yingxingshiyuan762@gmail.com'

msg = MIMEText('Test notification from 200 Account Automation System')
msg['Subject'] = '[Test] Email Notification'
msg['From'] = SMTP_USERNAME
msg['To'] = TO_EMAIL

try:
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.send_message(msg)
    print("Email sent successfully!")
except Exception as e:
    print(f"Failed to send email: {e}")
```

実行：
```bash
cd backend
python test_email.py
```

## 通知のトリガー条件

以下の場合にメール通知が送信されます：

### 1. エラー重要度

| 重要度 | 通知 | 説明 |
|--------|------|------|
| `CRITICAL` | ✅ 常に送信 | システムクリティカルなエラー |
| `ERROR` | ✅ 主要エラーのみ | ログイン失敗、自動化エラーなど |
| `WARNING` | ⚠️ 繰り返し発生時のみ | 警告レベル |
| `INFO` | ❌ 送信しない | 情報レベル |

### 2. エラータイプ

以下のエラータイプは必ず通知されます：

- `ERROR_OCCURRED` - 汎用エラー
- `SYSTEM_ERROR` - システムエラー
- `SESSION_CONFLICT_DETECTED` - セッション競合検知

### 3. クールダウン期間

同じアカウント・同じエラータイプの通知は、設定した期間内（デフォルト12分）に1回のみ送信されます。これにより、通知スパムを防止します。

## メールの内容

### 件名フォーマット

```
[Automation Alert][ERROR] Account {account_id}
```

### 本文フォーマット

```
============================================================
Automation System Alert
============================================================

Account ID: account-uuid
Store Name: 店舗名
Event Type: ERROR_OCCURRED
Severity: ERROR
Occurrence Time: 2024-01-27 10:30:45 UTC

Description:
エラーメッセージの詳細

Reference ID:
Event ID: event-uuid

============================================================

This is an automated notification from the 200 Account Automation System.
Please check the system logs for more details.
```

## トラブルシューティング

### メールが送信されない

#### 1. SMTPログを確認

バックエンドログ（`backend/logs/app.log`）で以下のエラーを確認：

```
Error sending email: (535, b'5.7.8 Username and Password not accepted')
```

**解決策**: アプリパスワードが正しいか確認してください。

#### 2. 2段階認証エラー

```
Error: Please log in via your web browser
```

**解決策**: Googleアカウントで2段階認証を有効にし、アプリパスワードを使用してください。

#### 3. TLS接続エラー

```
Error: [SSL: CERTIFICATE_VERIFY_FAILED]
```

**解決策**: `SMTP_USE_TLS=True`が設定されていることを確認してください。

#### 4. ファイアウォール/ネットワークエラー

```
Error: [Errno 10060] Connection timed out
```

**解決策**:
- ファイアウォールがポート587をブロックしていないか確認
- VPNやプロキシの設定を確認
- 別のネットワークで試してみる

### メールが迷惑メールに分類される

#### 対策

1. **SPFレコードの設定**（独自ドメインを使用する場合）
2. **送信者メールアドレスの確認**: 送信元と差出人が同じGmailアカウントであることを確認
3. **メール内容の最適化**: スパムワードを避ける

### 通知が多すぎる場合

#### クールダウン期間を延長

`.env`ファイルで期間を延長：

```env
NOTIFICATION_COOLDOWN_MINUTES=30  # 30分に変更
```

#### 通知フィルタを調整

`backend/src/monitoring/notifier.py`の`_should_send_notification`メソッドをカスタマイズして、通知条件を調整できます。

## Gmail以外のSMTPサーバーを使用する場合

### Outlook/Hotmail

```env
SMTP_HOST=smtp-mail.outlook.com
SMTP_PORT=587
SMTP_USE_TLS=True
SMTP_USERNAME=your-email@outlook.com
SMTP_PASSWORD=your-password
```

### Yahoo Mail

```env
SMTP_HOST=smtp.mail.yahoo.com
SMTP_PORT=587
SMTP_USE_TLS=True
SMTP_USERNAME=your-email@yahoo.com
SMTP_PASSWORD=your-app-password
```

### カスタムSMTPサーバー

```env
SMTP_HOST=mail.your-domain.com
SMTP_PORT=587
SMTP_USE_TLS=True
SMTP_USERNAME=your-username
SMTP_PASSWORD=your-password
SMTP_FROM_EMAIL=noreply@your-domain.com
```

## セキュリティのベストプラクティス

1. **アプリパスワードを使用**: Googleアカウントのメインパスワードは使用しないでください
2. **.envファイルを保護**: `.gitignore`に`.env`が含まれていることを確認
3. **送信元を制限**: 信頼できるIPアドレスからのみ送信
4. **定期的なパスワード更新**: 3〜6ヶ月ごとにアプリパスワードを再生成

## 参考リンク

- [Googleアカウント - 2段階認証](https://www.google.com/landing/2step/)
- [Googleアカウント - アプリパスワード](https://myaccount.google.com/apppasswords)
- [Gmail SMTP設定ガイド](https://support.google.com/a/answer/176600)

---

**作成日**: 2024-01-27  
**更新日**: 2024-01-27  
**通知先**: yingxingshiyuan762@gmail.com

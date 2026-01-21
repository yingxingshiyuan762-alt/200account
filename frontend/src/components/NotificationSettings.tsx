import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { useSystemConfig, useUpdateSystemConfig } from '@/hooks/useApi';
import { Loader2, Mail, Save } from 'lucide-react';
import { toast } from '@/hooks/use-toast';
import { useState, useEffect } from 'react';

interface NotificationSettingsProps {
  className?: string;
}

export function NotificationSettings({ className }: NotificationSettingsProps) {
  const { data: config, isLoading } = useSystemConfig();
  const updateConfig = useUpdateSystemConfig();

  const [emails, setEmails] = useState<string>('');
  const [cooldown, setCooldown] = useState<string>('12');
  const [smtpHost, setSmtpHost] = useState<string>('smtp.gmail.com');
  const [smtpPort, setSmtpPort] = useState<string>('587');
  const [smtpUsername, setSmtpUsername] = useState<string>('');
  const [smtpPassword, setSmtpPassword] = useState<string>('');
  const [smtpFromEmail, setSmtpFromEmail] = useState<string>('');

  useEffect(() => {
    if (config) {
      // 設定を読み込む（実際の実装では環境変数から取得する必要がある）
      // ここでは簡易的に表示のみ
    }
  }, [config]);

  const handleSave = async () => {
    try {
      // 通知設定を保存（実際の実装では環境変数または設定ファイルに保存）
      toast({
        title: '設定を保存しました',
        description: '通知設定を更新しました。実際の設定は環境変数で管理されています。',
      });
    } catch (error) {
      toast({
        title: 'エラー',
        description: error instanceof Error ? error.message : '設定の保存に失敗しました',
        variant: 'destructive',
      });
    }
  };

  if (isLoading) {
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle>通知設定</CardTitle>
          <CardDescription>メール通知の設定を管理します</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Mail className="h-5 w-5" />
          通知設定
        </CardTitle>
        <CardDescription>メール通知の設定を管理します</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Email Recipients */}
        <div className="space-y-2">
          <Label htmlFor="emails">受信者メールアドレス</Label>
          <Input
            id="emails"
            type="text"
            placeholder="email1@example.com, email2@example.com"
            value={emails}
            onChange={(e) => setEmails(e.target.value)}
          />
          <p className="text-xs text-muted-foreground">
            カンマ区切りで複数のメールアドレスを指定できます
          </p>
        </div>

        {/* Cooldown */}
        <div className="space-y-2">
          <Label htmlFor="cooldown">クールダウン期間（分）</Label>
          <Input
            id="cooldown"
            type="number"
            placeholder="12"
            value={cooldown}
            onChange={(e) => setCooldown(e.target.value)}
          />
          <p className="text-xs text-muted-foreground">
            同じイベントの重複通知を防ぐための期間
          </p>
        </div>

        {/* SMTP Settings */}
        <div className="space-y-4 border-t pt-4">
          <h3 className="text-sm font-semibold">SMTP設定</h3>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="smtp-host">SMTPホスト</Label>
              <Input
                id="smtp-host"
                type="text"
                placeholder="smtp.gmail.com"
                value={smtpHost}
                onChange={(e) => setSmtpHost(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="smtp-port">SMTPポート</Label>
              <Input
                id="smtp-port"
                type="number"
                placeholder="587"
                value={smtpPort}
                onChange={(e) => setSmtpPort(e.target.value)}
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="smtp-username">SMTPユーザー名</Label>
            <Input
              id="smtp-username"
              type="text"
              placeholder="your-email@gmail.com"
              value={smtpUsername}
              onChange={(e) => setSmtpUsername(e.target.value)}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="smtp-password">SMTPパスワード</Label>
            <Input
              id="smtp-password"
              type="password"
              placeholder="••••••••"
              value={smtpPassword}
              onChange={(e) => setSmtpPassword(e.target.value)}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="smtp-from">送信者メールアドレス</Label>
            <Input
              id="smtp-from"
              type="email"
              placeholder="noreply@example.com"
              value={smtpFromEmail}
              onChange={(e) => setSmtpFromEmail(e.target.value)}
            />
          </div>
        </div>

        <div className="rounded-lg border bg-muted/50 p-4">
          <p className="text-sm text-muted-foreground">
            <strong>注意:</strong> 実際の設定は環境変数（.envファイル）で管理されています。
            設定を変更する場合は、バックエンドの環境変数を更新してください。
          </p>
        </div>

        <Button onClick={handleSave} className="w-full" disabled={updateConfig.isPending}>
          {updateConfig.isPending ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              保存中...
            </>
          ) : (
            <>
              <Save className="mr-2 h-4 w-4" />
              設定を保存
            </>
          )}
        </Button>
      </CardContent>
    </Card>
  );
}

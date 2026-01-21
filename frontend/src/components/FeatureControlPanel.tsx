import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { useSystemConfig, useUpdateSystemConfig } from '@/hooks/useApi';
import { Loader2, CheckCircle, XCircle } from 'lucide-react';
import { toast } from '@/hooks/use-toast';

interface FeatureControlPanelProps {
  className?: string;
}

export function FeatureControlPanel({ className }: FeatureControlPanelProps) {
  const { data: config, isLoading } = useSystemConfig();
  const updateConfig = useUpdateSystemConfig();

  const handleToggle = async (key: string, currentValue: any) => {
    try {
      const newValue = !currentValue;
      await updateConfig.mutateAsync({
        configKey: key,
        value: newValue,
      });
      toast({
        title: '設定を更新しました',
        description: `${key} を ${newValue ? '有効' : '無効'} に設定しました。`,
      });
    } catch (error) {
      toast({
        title: 'エラー',
        description: error instanceof Error ? error.message : '設定の更新に失敗しました',
        variant: 'destructive',
      });
    }
  };

  if (isLoading) {
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle>機能制御</CardTitle>
          <CardDescription>各機能の有効/無効を切り替えます</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        </CardContent>
      </Card>
    );
  }

  const features = [
    {
      key: 'schedule_update_enabled',
      label: '自動スケジュール更新',
      description: '毎日07:00-10:00に明日のスケジュールを自動更新します',
      value: config?.schedule_update_enabled ?? true,
    },
    {
      key: 'wait_reception_enabled',
      label: '待機接客自動化',
      description: '60-90分間隔でキャストの待機状態を自動制御します',
      value: config?.wait_reception_enabled ?? true,
    },
    {
      key: 'status_monitoring_enabled',
      label: '状態監視',
      description: 'アカウント状態とアプリケーション健全性を継続監視します',
      value: config?.status_monitoring_enabled ?? true,
    },
  ];

  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle>機能制御</CardTitle>
        <CardDescription>各機能の有効/無効を切り替えます</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {features.map((feature) => (
          <div key={feature.key} className="flex items-start justify-between space-x-4">
            <div className="flex-1 space-y-1">
              <div className="flex items-center gap-2">
                <Label htmlFor={feature.key} className="text-base font-semibold cursor-pointer">
                  {feature.label}
                </Label>
                {feature.value ? (
                  <CheckCircle className="h-4 w-4 text-success" />
                ) : (
                  <XCircle className="h-4 w-4 text-muted-foreground" />
                )}
              </div>
              <p className="text-sm text-muted-foreground">{feature.description}</p>
            </div>
            <Switch
              id={feature.key}
              checked={feature.value}
              onCheckedChange={() => handleToggle(feature.key, feature.value)}
              disabled={updateConfig.isPending}
            />
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

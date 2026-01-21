import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { FeatureControlPanel } from '@/components/FeatureControlPanel';
import { NotificationSettings } from '@/components/NotificationSettings';
import { Settings as SettingsIcon, ToggleLeft, Mail } from 'lucide-react';

export function Settings() {
  return (
    <div className="space-y-6 animate-fade-in">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold text-foreground flex items-center gap-2">
          <SettingsIcon className="h-6 w-6" />
          システム設定
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Milestone 3機能の有効/無効と通知設定を管理します
        </p>
      </div>

      {/* Settings Tabs */}
      <Tabs defaultValue="features" className="space-y-6">
        <TabsList>
          <TabsTrigger value="features" className="flex items-center gap-2">
            <ToggleLeft className="h-4 w-4" />
            機能制御
          </TabsTrigger>
          <TabsTrigger value="notifications" className="flex items-center gap-2">
            <Mail className="h-4 w-4" />
            通知設定
          </TabsTrigger>
        </TabsList>

        <TabsContent value="features" className="space-y-6">
          <FeatureControlPanel />
        </TabsContent>

        <TabsContent value="notifications" className="space-y-6">
          <NotificationSettings />
        </TabsContent>
      </Tabs>
    </div>
  );
}

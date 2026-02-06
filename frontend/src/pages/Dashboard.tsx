import { CheckCircle, Users, Calendar, Clock, AlertCircle, Monitor, Play } from 'lucide-react';
import { StatusCard } from '@/components/StatusCard';
import { AccountTable } from '@/components/AccountTable';
import { ScheduleMonitor } from '@/components/ScheduleMonitor';
import { ExecutionLog } from '@/components/ExecutionLog';
import { StatusMonitoringDashboard } from '@/components/StatusMonitoringDashboard';
import { ManualExecutionControl } from '@/components/ManualExecutionControl';
import { useState } from 'react';
import { useSystemStatus, useAccounts, useSchedules, useRecentLogs, useMonitoringStates } from '@/hooks/useApi';
import { format } from 'date-fns';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

const ACCOUNTS_PER_PAGE = 10;

export function Dashboard() {
  const { data: systemStatus, isLoading: systemLoading, error: systemError } = useSystemStatus();
  const [accountsPage, setAccountsPage] = useState(1);
  const { data: accountsData, isLoading: accountsLoading } = useAccounts({
    page: accountsPage,
    per_page: ACCOUNTS_PER_PAGE,
  });
  const { data: schedules, isLoading: schedulesLoading } = useSchedules();
  const { data: logsData, isLoading: logsLoading } = useRecentLogs(50);
  const { data: monitoringData, isLoading: monitoringLoading } = useMonitoringStates();

  // エラー状態の表示
  if (systemError) {
    return (
      <div className="space-y-6 animate-fade-in">
        <div className="rounded-xl border border-destructive bg-destructive/10 p-8 text-center">
          <AlertCircle className="h-12 w-12 text-destructive mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-destructive mb-2">バックエンドに接続できません</h2>
          <p className="text-muted-foreground mb-4">
            バックエンドサーバーが起動しているか確認してください。
          </p>
          <p className="text-sm text-muted-foreground">
            URL: http://localhost:5000/api
          </p>
        </div>
      </div>
    );
  }

  const currentTime = format(new Date(), 'HH:mm:ss');
  const systemStatusValue = systemStatus?.isRunning ? '正常稼働中' : '停止中';
  const activeAccounts = systemStatus?.activeAccounts || 0;
  const totalAccounts = systemStatus?.totalAccounts || 0;
  const manualOperations = systemStatus?.manualOperations || 0;
  
  // Extract schedule times from schedules data (Feature 1 & 2)
  const scheduleUpdate = schedules?.find(s => s.id === '1' || s.name === 'スケジュール自動更新');
  const waitReception = schedules?.find(s => s.id === '2' || s.name === '待機接客配信');
  const nextSchedule = scheduleUpdate?.time || systemStatus?.nextSchedule || '-';
  const waitingTime = waitReception?.time || systemStatus?.waitingTime || '-';
  
  const vpsInfo = systemStatus?.vpsInfo || 'Unknown';
  const cpuUsage = systemStatus?.cpuUsage || 0;
  const memoryUsage = systemStatus?.memoryUsage || '0GB/0GB';
  
  // Monitoring states summary (from system status or monitoring API) - Feature 3
  const normalCount = systemStatus?.monitorStates?.NORMAL || monitoringData?.summary?.NORMAL || 0;
  const unstableCount = systemStatus?.monitorStates?.UNSTABLE || monitoringData?.summary?.UNSTABLE || 0;
  const stoppedCount = systemStatus?.monitorStates?.STOPPED || monitoringData?.summary?.STOPPED || 0;

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold text-foreground">自動化ダッシュボード</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          shinchakun.net 200アカウント自動管理システム
        </p>
      </div>

      {/* Status Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatusCard
          icon={<CheckCircle className="h-5 w-5" />}
          iconBg="success"
          label="システム稼働状況"
          value={systemLoading ? '読み込み中...' : systemStatusValue}
          subValue={systemLoading ? '' : '最終チェック: 数秒前'}
        />
        <StatusCard
          icon={<Users className="h-5 w-5" />}
          iconBg="primary"
          label="稼働中アカウント"
          value={systemLoading ? '-' : `${activeAccounts}/${totalAccounts}`}
          subValue={systemLoading ? '' : `${manualOperations}アカウント手動操作中`}
        />
        <StatusCard
          icon={<Calendar className="h-5 w-5" />}
          iconBg="warning"
          label="次回スケジュール更新"
          value={schedulesLoading ? '読み込み中...' : nextSchedule}
          subValue="自動実行予定"
        />
        <StatusCard
          icon={<Clock className="h-5 w-5" />}
          iconBg="info"
          label="待機接客配信"
          value={schedulesLoading ? '読み込み中...' : waitingTime}
          subValue="次回実行まで"
        />
      </div>

      {/* Monitoring Status Cards (Milestone 3 Feature 3) */}
      {!monitoringLoading && (normalCount > 0 || unstableCount > 0 || stoppedCount > 0) && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <StatusCard
            icon={<CheckCircle className="h-5 w-5" />}
            iconBg="success"
            label="正常状態アカウント"
            value={normalCount}
            subValue="監視状態: 正常"
          />
          <StatusCard
            icon={<Monitor className="h-5 w-5" />}
            iconBg="warning"
            label="不安定状態アカウント"
            value={unstableCount}
            subValue="監視状態: 不安定"
          />
          <StatusCard
            icon={<AlertCircle className="h-5 w-5" />}
            iconBg="error"
            label="停止状態アカウント"
            value={stoppedCount}
            subValue="監視状態: 停止"
          />
        </div>
      )}

      {/* Real-time Monitoring Bar */}
      <div className="flex flex-wrap items-center gap-4 rounded-lg border bg-card px-4 py-3">
        <div className="flex items-center gap-2">
          <span className={`h-2 w-2 rounded-full ${systemStatus?.isRunning ? 'bg-success' : 'bg-destructive'} animate-pulse`} />
          <span className="text-sm font-medium text-foreground">リアルタイム監視中</span>
        </div>
        <div className="h-4 w-px bg-border" />
        <span className="text-sm text-muted-foreground">現在時刻: {currentTime}</span>
        <div className="h-4 w-px bg-border" />
        <span className="text-sm text-muted-foreground">VPS: {vpsInfo}</span>
        <div className="h-4 w-px bg-border" />
        <span className="text-sm text-muted-foreground">
          CPU: {cpuUsage}% | メモリ: {memoryUsage}
        </span>
        {!monitoringLoading && monitoringData && (
          <>
            <div className="h-4 w-px bg-border" />
            <span className="text-sm text-muted-foreground">
              監視状態: 正常 {normalCount} / 不安定 {unstableCount} / 停止 {stoppedCount}
            </span>
          </>
        )}
      </div>

      {/* Account Table: 10 per page, 13 pages */}
      <AccountTable 
        accounts={accountsData?.accounts || []} 
        isLoading={accountsLoading}
        totalAccounts={accountsData?.pagination?.total ?? totalAccounts}
        page={accountsPage}
        totalPages={accountsData?.pagination?.pages ?? 1}
        onPageChange={setAccountsPage}
      />

      {/* Schedule Monitor and Execution Log */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <ScheduleMonitor
          schedules={schedules || []}
          isLoading={schedulesLoading}
          nextExecutionTime={waitingTime}
        />
        <ExecutionLog 
          logs={logsData?.logs || []} 
          isLoading={logsLoading}
        />
      </div>

      {/* Milestone 3 Features: Status Monitoring and Manual Execution */}
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-semibold text-foreground">自動化機能制御</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              状態監視（Feature 3）と手動実行制御（Feature 1 & 2）
            </p>
          </div>
        </div>

        <Tabs defaultValue="monitoring" className="space-y-6">
          <TabsList>
            <TabsTrigger value="monitoring" className="flex items-center gap-2">
              <Monitor className="h-4 w-4" />
              状態監視
            </TabsTrigger>
            <TabsTrigger value="execution" className="flex items-center gap-2">
              <Play className="h-4 w-4" />
              手動実行
            </TabsTrigger>
          </TabsList>

          <TabsContent value="monitoring" className="space-y-6">
            <StatusMonitoringDashboard />
          </TabsContent>

          <TabsContent value="execution" className="space-y-6">
            <ManualExecutionControl />
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}

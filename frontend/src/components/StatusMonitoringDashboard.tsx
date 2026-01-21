import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { useMonitoringStates } from '@/hooks/useApi';
import { Loader2, CheckCircle, AlertTriangle, XCircle } from 'lucide-react';
import { format } from 'date-fns';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';

interface StatusMonitoringDashboardProps {
  className?: string;
}

export function StatusMonitoringDashboard({ className }: StatusMonitoringDashboardProps) {
  const { data, isLoading, error } = useMonitoringStates();

  if (isLoading) {
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle>状態監視ダッシュボード</CardTitle>
          <CardDescription>全アカウントの監視状態を表示します</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle>状態監視ダッシュボード</CardTitle>
          <CardDescription>全アカウントの監視状態を表示します</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="text-center py-8 text-destructive">
            データの取得に失敗しました
          </div>
        </CardContent>
      </Card>
    );
  }

  const getStateIcon = (state: string) => {
    switch (state) {
      case 'NORMAL':
        return <CheckCircle className="h-4 w-4 text-success" />;
      case 'UNSTABLE':
        return <AlertTriangle className="h-4 w-4 text-warning" />;
      case 'STOPPED':
        return <XCircle className="h-4 w-4 text-destructive" />;
      default:
        return null;
    }
  };

  const getStateBadge = (state: string) => {
    switch (state) {
      case 'NORMAL':
        return <Badge variant="success">正常</Badge>;
      case 'UNSTABLE':
        return <Badge variant="warning">不安定</Badge>;
      case 'STOPPED':
        return <Badge variant="destructive">停止</Badge>;
      default:
        return <Badge variant="secondary">不明</Badge>;
    }
  };

  const summary = data?.summary || { NORMAL: 0, UNSTABLE: 0, STOPPED: 0 };
  const accounts = data?.accounts || [];

  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle>状態監視ダッシュボード</CardTitle>
        <CardDescription>全アカウントの監視状態を表示します</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Summary Cards */}
        <div className="grid grid-cols-3 gap-4">
          <div className="rounded-lg border bg-card p-4">
            <div className="flex items-center gap-2 mb-2">
              <CheckCircle className="h-5 w-5 text-success" />
              <span className="text-sm font-medium text-muted-foreground">正常</span>
            </div>
            <div className="text-2xl font-bold text-foreground">{summary.NORMAL}</div>
          </div>
          <div className="rounded-lg border bg-card p-4">
            <div className="flex items-center gap-2 mb-2">
              <AlertTriangle className="h-5 w-5 text-warning" />
              <span className="text-sm font-medium text-muted-foreground">不安定</span>
            </div>
            <div className="text-2xl font-bold text-foreground">{summary.UNSTABLE}</div>
          </div>
          <div className="rounded-lg border bg-card p-4">
            <div className="flex items-center gap-2 mb-2">
              <XCircle className="h-5 w-5 text-destructive" />
              <span className="text-sm font-medium text-muted-foreground">停止</span>
            </div>
            <div className="text-2xl font-bold text-foreground">{summary.STOPPED}</div>
          </div>
        </div>

        {/* Accounts Table */}
        {accounts.length > 0 ? (
          <div className="rounded-lg border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>アカウント</TableHead>
                  <TableHead>店舗名</TableHead>
                  <TableHead>監視状態</TableHead>
                  <TableHead>最終チェック</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {accounts.slice(0, 10).map((account) => (
                  <TableRow key={account.account_id}>
                    <TableCell className="font-medium">{account.username}</TableCell>
                    <TableCell>{account.store_name}</TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        {getStateIcon(account.state)}
                        {getStateBadge(account.state)}
                      </div>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {account.last_check
                        ? format(new Date(account.last_check), 'MM/dd HH:mm:ss')
                        : '-'}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        ) : (
          <div className="text-center py-8 text-muted-foreground">
            監視対象のアカウントがありません
          </div>
        )}
      </CardContent>
    </Card>
  );
}

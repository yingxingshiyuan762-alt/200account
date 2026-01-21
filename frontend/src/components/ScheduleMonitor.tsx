import { Clock, CheckCircle, Play, Timer } from 'lucide-react';
import { ScheduleItem } from '@/types/account';
import { cn } from '@/lib/utils';

interface ScheduleMonitorProps {
  schedules: ScheduleItem[];
  nextExecutionTime: string;
  isLoading?: boolean;
}

export function ScheduleMonitor({ schedules, nextExecutionTime, isLoading = false }: ScheduleMonitorProps) {
  const getStatusIcon = (status: ScheduleItem['status']) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="h-4 w-4 text-success" />;
      case 'running':
        return <Play className="h-4 w-4 text-primary" />;
      default:
        return <Clock className="h-4 w-4 text-muted-foreground" />;
    }
  };

  const getStatusLabel = (status: ScheduleItem['status']) => {
    switch (status) {
      case 'completed':
        return <span className="text-xs font-medium text-success">完了</span>;
      case 'running':
        return <span className="text-xs font-medium text-primary">実行中</span>;
      default:
        return <span className="text-xs text-muted-foreground">予定</span>;
    }
  };

  return (
    <div className="rounded-xl border bg-card shadow-sm">
      <div className="flex items-center justify-between border-b p-4">
        <h3 className="font-semibold text-foreground">スケジュール監視</h3>
        <button className="text-sm text-primary hover:underline">すべて表示</button>
      </div>
      
      <div className="divide-y">
        {isLoading && schedules.length === 0 ? (
          <div className="px-4 py-8 text-center text-sm text-muted-foreground">
            読み込み中...
          </div>
        ) : schedules.length === 0 ? (
          <div className="px-4 py-8 text-center text-sm text-muted-foreground">
            スケジュールが見つかりません
          </div>
        ) : (
          schedules.map((schedule) => (
          <div
            key={schedule.id}
            className={cn(
              'flex items-center gap-3 px-4 py-3 transition-colors hover:bg-muted/20',
              schedule.status === 'running' && 'bg-primary/5'
            )}
          >
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-muted/50">
              {getStatusIcon(schedule.status)}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <p className="text-sm font-medium text-foreground truncate">{schedule.name}</p>
                {getStatusLabel(schedule.status)}
              </div>
              <p className="text-xs text-muted-foreground">{schedule.accountCount}アカウント対象</p>
            </div>
            <span className="text-sm font-medium text-foreground">{schedule.time}</span>
          </div>
          ))
        )}
      </div>

      <div className="flex items-center gap-3 border-t bg-primary/5 px-4 py-3">
        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10">
          <Timer className="h-4 w-4 text-primary" />
        </div>
        <div>
          <p className="text-sm font-medium text-primary">次回実行: 待機接客配信</p>
          <p className="text-xs text-muted-foreground">{nextExecutionTime}</p>
        </div>
      </div>
    </div>
  );
}

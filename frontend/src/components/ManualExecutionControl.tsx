import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { useExecuteAutomation } from '@/hooks/useApi';
import { Loader2, Play, Calendar, Clock } from 'lucide-react';
import { toast } from '@/hooks/use-toast';
import { useState } from 'react';

interface ManualExecutionControlProps {
  className?: string;
}

export function ManualExecutionControl({ className }: ManualExecutionControlProps) {
  const [taskType, setTaskType] = useState<string>('schedule_update');
  const executeAutomation = useExecuteAutomation();

  const handleExecute = async () => {
    try {
      const result = await executeAutomation.mutateAsync({
        taskType,
        accountIds: undefined, // 全アカウントを対象
      });

      toast({
        title: '自動化処理を実行しました',
        description: `成功: ${result.success}, 失敗: ${result.failed}, スキップ: ${result.skipped}`,
      });
    } catch (error) {
      toast({
        title: 'エラー',
        description: error instanceof Error ? error.message : '自動化処理の実行に失敗しました',
        variant: 'destructive',
      });
    }
  };

  const taskTypes = [
    {
      value: 'schedule_update',
      label: '自動スケジュール更新',
      icon: Calendar,
      description: '明日のスケジュールを「出勤」に設定します',
    },
    {
      value: 'wait_reception',
      label: '待機接客自動化',
      icon: Clock,
      description: 'キャストの待機状態を自動制御します',
    },
  ];

  const selectedTask = taskTypes.find((t) => t.value === taskType);

  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle>手動実行制御</CardTitle>
        <CardDescription>自動化処理を手動で実行します</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <label className="text-sm font-medium">実行するタスク</label>
          <Select value={taskType} onValueChange={setTaskType}>
            <SelectTrigger>
              <SelectValue placeholder="タスクを選択" />
            </SelectTrigger>
            <SelectContent>
              {taskTypes.map((task) => (
                <SelectItem key={task.value} value={task.value}>
                  {task.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {selectedTask && (
            <p className="text-sm text-muted-foreground">{selectedTask.description}</p>
          )}
        </div>

        <Button
          onClick={handleExecute}
          disabled={executeAutomation.isPending}
          className="w-full"
          size="lg"
        >
          {executeAutomation.isPending ? (
            <>
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              実行中...
            </>
          ) : (
            <>
              <Play className="mr-2 h-4 w-4" />
              実行
            </>
          )}
        </Button>

        <div className="rounded-lg border bg-muted/50 p-4">
          <p className="text-sm text-muted-foreground">
            <strong>注意:</strong> この操作は全アクティブアカウントに対して実行されます。
            実行中は他の自動化処理と競合する可能性があります。
          </p>
        </div>
      </CardContent>
    </Card>
  );
}

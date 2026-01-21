import { useState } from 'react';
import { CheckCircle, AlertTriangle, XCircle, Info, ChevronDown, Code } from 'lucide-react';
import { LogEntry, LogLevel } from '@/types/account';
import { cn } from '@/lib/utils';
import { CodeViewer } from '@/components/CodeViewer';

interface ExecutionLogProps {
  logs: LogEntry[];
  isLoading?: boolean;
}

type LogFilter = 'all' | 'success' | 'warning' | 'error';

export function ExecutionLog({ logs, isLoading = false }: ExecutionLogProps) {
  const [filter, setFilter] = useState<LogFilter>('all');
  const [selectedLog, setSelectedLog] = useState<LogEntry | null>(null);
  const [isCodeViewerOpen, setIsCodeViewerOpen] = useState(false);

  const filteredLogs = logs.filter((log) => {
    if (filter === 'all') return true;
    return log.level === filter;
  });

  const getLogIcon = (level: LogLevel) => {
    switch (level) {
      case 'success':
        return <CheckCircle className="h-4 w-4 text-success" />;
      case 'warning':
        return <AlertTriangle className="h-4 w-4 text-warning" />;
      case 'error':
        return <XCircle className="h-4 w-4 text-destructive" />;
      default:
        return <Info className="h-4 w-4 text-info" />;
    }
  };

  const filterButtons: { id: LogFilter; label: string }[] = [
    { id: 'all', label: 'すべて' },
    { id: 'success', label: '成功' },
    { id: 'warning', label: '警告' },
    { id: 'error', label: 'エラー' },
  ];

  return (
    <div className="rounded-xl border bg-card shadow-sm">
      <div className="flex items-center justify-between border-b p-4">
        <h3 className="font-semibold text-foreground">実行ログ</h3>
        <button className="text-sm text-primary hover:underline">すべて表示</button>
      </div>

      <div className="border-b px-4 py-2">
        <div className="flex gap-1 rounded-lg border bg-muted/50 p-1 w-fit">
          {filterButtons.map((btn) => (
            <button
              key={btn.id}
              onClick={() => setFilter(btn.id)}
              className={cn(
                'px-3 py-1 text-xs font-medium rounded-md transition-colors',
                filter === btn.id
                  ? 'bg-card text-foreground shadow-sm'
                  : 'text-muted-foreground hover:text-foreground'
              )}
            >
              {btn.label}
            </button>
          ))}
        </div>
      </div>

      <div className="max-h-[320px] overflow-y-auto">
        {isLoading && filteredLogs.length === 0 ? (
          <div className="px-4 py-8 text-center text-sm text-muted-foreground">
            読み込み中...
          </div>
        ) : filteredLogs.length === 0 ? (
          <div className="px-4 py-8 text-center text-sm text-muted-foreground">
            ログが見つかりません
          </div>
        ) : (
          filteredLogs.map((log) => (
          <div
            key={log.id}
            className="flex items-start gap-3 border-b px-4 py-3 transition-colors hover:bg-muted/20 last:border-b-0"
          >
            <div className="mt-0.5">{getLogIcon(log.level)}</div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-xs text-muted-foreground">{log.timestamp}</span>
                <span className="text-xs font-medium text-primary">{log.accountId}</span>
                {log.filePath && (
                  <button
                    onClick={() => {
                      setSelectedLog(log);
                      setIsCodeViewerOpen(true);
                    }}
                    className="flex items-center gap-1 text-xs text-primary hover:text-primary/80 hover:underline transition-colors"
                    title="コードを表示"
                  >
                    <Code className="h-3 w-3" />
                    <span className="truncate max-w-[200px]">
                      {log.filePath.split('/').pop()}
                      {log.lineNumber && `:${log.lineNumber}`}
                    </span>
                  </button>
                )}
              </div>
              <p className="mt-0.5 text-sm text-foreground">{log.message}</p>
              {log.functionName && (
                <p className="mt-1 text-xs text-muted-foreground">
                  関数: {log.functionName}
                </p>
              )}
            </div>
          </div>
          ))
        )}
      </div>

      <div className="flex items-center justify-between border-t px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-success animate-pulse" />
          <span className="text-xs text-muted-foreground">リアルタイム更新中</span>
        </div>
        <span className="text-xs text-muted-foreground">最終更新: 2秒前</span>
      </div>

      {/* Code Viewer Dialog */}
      {selectedLog && (
        <CodeViewer
          filePath={selectedLog.filePath!}
          lineNumber={selectedLog.lineNumber}
          functionName={selectedLog.functionName}
          isOpen={isCodeViewerOpen}
          onClose={() => {
            setIsCodeViewerOpen(false);
            setSelectedLog(null);
          }}
        />
      )}
    </div>
  );
}

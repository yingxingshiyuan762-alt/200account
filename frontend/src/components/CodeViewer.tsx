import { useState, useEffect } from 'react';
import { X, FileCode, ExternalLink } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { ScrollArea, ScrollBar } from '@/components/ui/scroll-area';
import { logApi } from '@/lib/api';
import { cn } from '@/lib/utils';

interface CodeViewerProps {
  filePath: string;
  lineNumber?: number;
  functionName?: string;
  isOpen: boolean;
  onClose: () => void;
}

export function CodeViewer({ filePath, lineNumber, functionName, isOpen, onClose }: CodeViewerProps) {
  const [content, setContent] = useState<string>('');
  const [lines, setLines] = useState<string[]>([]);
  const [totalLines, setTotalLines] = useState<number>(0);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen && filePath) {
      loadCode();
    } else {
      setContent('');
      setLines([]);
      setError(null);
    }
  }, [isOpen, filePath, lineNumber]);

  const loadCode = async () => {
    setIsLoading(true);
    setError(null);
    
    try {
      const response = await logApi.getCodeContent(filePath, lineNumber);
      
      if (response.success && response.data) {
        setContent(response.data.content);
        setLines(response.data.lines || []);
        setTotalLines(response.data.total_lines || 0);
      } else {
        setError(response.error || 'Failed to load code');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load code');
    } finally {
      setIsLoading(false);
    }
  };

  const highlightLine = lineNumber || 0;
  const startLine = highlightLine > 0 ? Math.max(1, highlightLine - 10) : 1; // 10行前から表示
  const endLine = highlightLine > 0 ? Math.min(totalLines, highlightLine + 10) : Math.min(totalLines, 50); // 10行後まで表示（ハイライトがない場合は50行まで）

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-4xl max-h-[90vh]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <FileCode className="h-5 w-5" />
            <span className="truncate">{filePath}</span>
            {functionName && (
              <span className="text-sm font-normal text-muted-foreground">
                ({functionName})
              </span>
            )}
          </DialogTitle>
        </DialogHeader>

        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <div className="text-sm text-muted-foreground">読み込み中...</div>
          </div>
        ) : error ? (
          <div className="flex flex-col items-center justify-center py-12">
            <div className="text-sm text-destructive mb-2">{error}</div>
            <Button variant="outline" size="sm" onClick={loadCode}>
              再試行
            </Button>
          </div>
        ) : (
          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between text-xs text-muted-foreground px-2">
              <span>
                {lineNumber ? `行 ${lineNumber}` : ''} 
                {totalLines > 0 && ` / 全 ${totalLines} 行`}
              </span>
              {filePath && (
                <a
                  href={`vscode://file/${filePath}:${lineNumber || 1}`}
                  className="flex items-center gap-1 hover:text-primary transition-colors"
                  title="VS Codeで開く"
                >
                  <ExternalLink className="h-3 w-3" />
                  VS Codeで開く
                </a>
              )}
            </div>
            
            <ScrollArea className="h-[60vh] rounded-md border bg-muted/30">
              <div className="p-4 font-mono text-sm">
                {lines.length > 0 ? (
                  lines.slice(startLine - 1, endLine).map((line, index) => {
                    const lineNum = startLine + index;
                    const isHighlighted = lineNum === highlightLine;
                    
                    return (
                      <div
                        key={lineNum}
                        className={cn(
                          'flex gap-4 px-2 py-0.5',
                          isHighlighted && 'bg-primary/20 border-l-2 border-primary',
                          !isHighlighted && 'hover:bg-muted/50'
                        )}
                      >
                        <span className="text-muted-foreground select-none w-12 text-right">
                          {lineNum}
                        </span>
                        <span className="flex-1 whitespace-pre-wrap break-words">
                          {line || ' '}
                        </span>
                      </div>
                    );
                  })
                ) : (
                  <div className="text-sm text-muted-foreground">コードが見つかりません</div>
                )}
              </div>
              <ScrollBar />
            </ScrollArea>
          </div>
        )}

        <div className="flex justify-end">
          <Button variant="outline" onClick={onClose}>
            閉じる
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}


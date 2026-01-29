import { useState, useEffect } from 'react';
import { Settings, PlayCircle, RotateCcw, FileCode, AlertTriangle, CheckCircle2, Clock, XCircle } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { useToast } from '@/hooks/use-toast';

interface Patch {
  id: string;
  name: string;
  description: string;
  version: string;
  patch_type: string;
  status: string;
  executed_at: string | null;
  execution_time: number;
  can_rollback: boolean;
  is_critical: boolean;
  auto_execute: boolean;
}

interface PatchStatistics {
  total_patches: number;
  by_status: Record<string, number>;
  by_type: Record<string, number>;
  critical_patches: number;
  pending_patches: number;
}

export function Patches() {
  const [patches, setPatches] = useState<Patch[]>([]);
  const [statistics, setStatistics] = useState<PatchStatistics | null>(null);
  const [loading, setLoading] = useState(true);
  const [executing, setExecuting] = useState<string | null>(null);
  const { toast } = useToast();

  useEffect(() => {
    loadPatches();
    loadStatistics();
  }, []);

  const loadPatches = async () => {
    try {
      const response = await fetch('http://localhost:5000/api/patches');
      const data = await response.json();
      if (data.success) {
        setPatches(data.data.patches);
      }
    } catch (error) {
      console.error('Failed to load patches:', error);
      toast({
        title: 'エラー',
        description: 'パッチの読み込みに失敗しました',
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  };

  const loadStatistics = async () => {
    try {
      const response = await fetch('http://localhost:5000/api/patches/statistics');
      const data = await response.json();
      if (data.success) {
        setStatistics(data.data);
      }
    } catch (error) {
      console.error('Failed to load statistics:', error);
    }
  };

  const executePatch = async (patchId: string, force: boolean = false) => {
    setExecuting(patchId);
    try {
      const response = await fetch(`http://localhost:5000/api/patches/${patchId}/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ force }),
      });
      const data = await response.json();
      
      if (data.success) {
        toast({
          title: '成功',
          description: `パッチ ${patchId} を実行しました`,
        });
        loadPatches();
        loadStatistics();
      } else {
        toast({
          title: 'エラー',
          description: data.data?.error || 'パッチの実行に失敗しました',
          variant: 'destructive',
        });
      }
    } catch (error) {
      console.error('Failed to execute patch:', error);
      toast({
        title: 'エラー',
        description: 'パッチの実行に失敗しました',
        variant: 'destructive',
      });
    } finally {
      setExecuting(null);
    }
  };

  const rollbackPatch = async (patchId: string) => {
    if (!confirm(`パッチ ${patchId} をロールバックしますか？`)) return;
    
    try {
      const response = await fetch(`http://localhost:5000/api/patches/${patchId}/rollback`, {
        method: 'POST',
      });
      const data = await response.json();
      
      if (data.success) {
        toast({
          title: '成功',
          description: `パッチ ${patchId} をロールバックしました`,
        });
        loadPatches();
        loadStatistics();
      } else {
        toast({
          title: 'エラー',
          description: data.data?.error || 'ロールバックに失敗しました',
          variant: 'destructive',
        });
      }
    } catch (error) {
      console.error('Failed to rollback patch:', error);
      toast({
        title: 'エラー',
        description: 'ロールバックに失敗しました',
        variant: 'destructive',
      });
    }
  };

  const executeAllPending = async () => {
    if (!confirm('すべての未実行パッチを実行しますか？')) return;
    
    try {
      const response = await fetch('http://localhost:5000/api/patches/execute-all', {
        method: 'POST',
      });
      const data = await response.json();
      
      if (data.success) {
        const result = data.data;
        toast({
          title: '実行完了',
          description: `成功: ${result.success}, 失敗: ${result.failed}, スキップ: ${result.skipped}`,
        });
        loadPatches();
        loadStatistics();
      }
    } catch (error) {
      console.error('Failed to execute all patches:', error);
      toast({
        title: 'エラー',
        description: '一括実行に失敗しました',
        variant: 'destructive',
      });
    }
  };

  const reloadPatches = async () => {
    try {
      const response = await fetch('http://localhost:5000/api/patches/reload', {
        method: 'POST',
      });
      const data = await response.json();
      
      if (data.success) {
        toast({
          title: '成功',
          description: `${data.data.loaded_count}個のパッチを再読み込みしました`,
        });
        loadPatches();
        loadStatistics();
      }
    } catch (error) {
      console.error('Failed to reload patches:', error);
      toast({
        title: 'エラー',
        description: 'パッチの再読み込みに失敗しました',
        variant: 'destructive',
      });
    }
  };

  const getStatusBadge = (status: string) => {
    const statusMap: Record<string, { variant: any; icon: any; label: string }> = {
      pending: { variant: 'secondary', icon: Clock, label: '未実行' },
      success: { variant: 'default', icon: CheckCircle2, label: '成功' },
      failed: { variant: 'destructive', icon: XCircle, label: '失敗' },
      running: { variant: 'default', icon: PlayCircle, label: '実行中' },
    };
    
    const config = statusMap[status] || statusMap.pending;
    const Icon = config.icon;
    
    return (
      <Badge variant={config.variant} className="flex items-center gap-1">
        <Icon className="h-3 w-3" />
        {config.label}
      </Badge>
    );
  };

  const getTypeBadge = (type: string) => {
    const typeColors: Record<string, string> = {
      database: 'bg-blue-100 text-blue-800',
      code: 'bg-purple-100 text-purple-800',
      config: 'bg-green-100 text-green-800',
      hotfix: 'bg-red-100 text-red-800',
      migration: 'bg-yellow-100 text-yellow-800',
    };
    
    return (
      <Badge className={typeColors[type] || 'bg-gray-100 text-gray-800'}>
        {type}
      </Badge>
    );
  };

  const pendingPatches = patches.filter(p => p.status === 'pending');
  const criticalPatches = patches.filter(p => p.is_critical && p.status === 'pending');

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Page Header */}
      <div className="flex justify-between items-start">
        <div>
          <h1 className="text-2xl font-bold text-foreground flex items-center gap-2">
            <Settings className="h-6 w-6" />
            パッチ管理
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            自動修正パッチシステム - 実行するだけで修正を適用
          </p>
        </div>
        <div className="flex gap-2">
          <Button onClick={reloadPatches} variant="outline">
            再読み込み
          </Button>
          {pendingPatches.length > 0 && (
            <Button onClick={executeAllPending}>
              <PlayCircle className="h-4 w-4 mr-2" />
              未実行パッチを一括実行
            </Button>
          )}
        </div>
      </div>

      {/* Critical Patches Alert */}
      {criticalPatches.length > 0 && (
        <Alert className="border-red-500 bg-red-50">
          <AlertTriangle className="h-4 w-4 text-red-600" />
          <AlertDescription className="text-red-800">
            <strong>{criticalPatches.length}個の緊急パッチ</strong>が未実行です。早急に実行してください。
          </AlertDescription>
        </Alert>
      )}

      {/* Statistics Cards */}
      {statistics && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium">総パッチ数</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{statistics.total_patches}</div>
            </CardContent>
          </Card>
          
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium">未実行</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-yellow-600">{statistics.pending_patches}</div>
            </CardContent>
          </Card>
          
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium">実行済み</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-green-600">{statistics.by_status.success || 0}</div>
            </CardContent>
          </Card>
          
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium">緊急</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-red-600">{statistics.critical_patches}</div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Patches Table */}
      <Card>
        <CardHeader>
          <CardTitle>パッチ一覧</CardTitle>
          <CardDescription>
            システムで利用可能なすべてのパッチ
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Tabs defaultValue="all">
            <TabsList>
              <TabsTrigger value="all">すべて ({patches.length})</TabsTrigger>
              <TabsTrigger value="pending">未実行 ({pendingPatches.length})</TabsTrigger>
              <TabsTrigger value="critical">緊急 ({criticalPatches.length})</TabsTrigger>
            </TabsList>

            <TabsContent value="all" className="mt-4">
              <PatchTable
                patches={patches}
                executing={executing}
                onExecute={executePatch}
                onRollback={rollbackPatch}
                getStatusBadge={getStatusBadge}
                getTypeBadge={getTypeBadge}
              />
            </TabsContent>

            <TabsContent value="pending" className="mt-4">
              <PatchTable
                patches={pendingPatches}
                executing={executing}
                onExecute={executePatch}
                onRollback={rollbackPatch}
                getStatusBadge={getStatusBadge}
                getTypeBadge={getTypeBadge}
              />
            </TabsContent>

            <TabsContent value="critical" className="mt-4">
              <PatchTable
                patches={criticalPatches}
                executing={executing}
                onExecute={executePatch}
                onRollback={rollbackPatch}
                getStatusBadge={getStatusBadge}
                getTypeBadge={getTypeBadge}
              />
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>
    </div>
  );
}

interface PatchTableProps {
  patches: Patch[];
  executing: string | null;
  onExecute: (id: string, force: boolean) => void;
  onRollback: (id: string) => void;
  getStatusBadge: (status: string) => JSX.Element;
  getTypeBadge: (type: string) => JSX.Element;
}

function PatchTable({ patches, executing, onExecute, onRollback, getStatusBadge, getTypeBadge }: PatchTableProps) {
  if (patches.length === 0) {
    return (
      <div className="text-center py-12 text-muted-foreground">
        <FileCode className="h-12 w-12 mx-auto mb-4 opacity-50" />
        <p>パッチがありません</p>
      </div>
    );
  }

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>ID</TableHead>
          <TableHead>名前</TableHead>
          <TableHead>タイプ</TableHead>
          <TableHead>ステータス</TableHead>
          <TableHead>実行時間</TableHead>
          <TableHead>フラグ</TableHead>
          <TableHead className="text-right">アクション</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {patches.map((patch) => (
          <TableRow key={patch.id}>
            <TableCell className="font-mono text-xs">{patch.id}</TableCell>
            <TableCell>
              <div>
                <div className="font-medium">{patch.name}</div>
                <div className="text-sm text-muted-foreground">{patch.description}</div>
              </div>
            </TableCell>
            <TableCell>{getTypeBadge(patch.patch_type)}</TableCell>
            <TableCell>{getStatusBadge(patch.status)}</TableCell>
            <TableCell>
              {patch.execution_time > 0 ? `${patch.execution_time.toFixed(2)}s` : '-'}
            </TableCell>
            <TableCell>
              <div className="flex gap-1">
                {patch.is_critical && (
                  <Badge variant="destructive" className="text-xs">
                    緊急
                  </Badge>
                )}
                {patch.can_rollback && (
                  <Badge variant="outline" className="text-xs">
                    ロールバック可
                  </Badge>
                )}
              </div>
            </TableCell>
            <TableCell className="text-right space-x-2">
              {patch.status === 'pending' && (
                <Button
                  size="sm"
                  onClick={() => onExecute(patch.id, false)}
                  disabled={executing === patch.id}
                >
                  <PlayCircle className="h-4 w-4 mr-1" />
                  実行
                </Button>
              )}
              {patch.status === 'success' && patch.can_rollback && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => onRollback(patch.id)}
                >
                  <RotateCcw className="h-4 w-4 mr-1" />
                  ロールバック
                </Button>
              )}
              {patch.status === 'failed' && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => onExecute(patch.id, true)}
                  disabled={executing === patch.id}
                >
                  再実行
                </Button>
              )}
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

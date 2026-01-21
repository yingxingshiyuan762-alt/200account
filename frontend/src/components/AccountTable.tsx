import { useState } from 'react';
import { Search, MoreVertical, ChevronLeft, ChevronRight } from 'lucide-react';
import { Account } from '@/types/account';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

interface AccountTableProps {
  accounts: Account[];
  isLoading?: boolean;
  totalAccounts?: number;
}

type FilterType = 'all' | 'active' | 'manual' | 'error';

export function AccountTable({ accounts, isLoading = false, totalAccounts }: AccountTableProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [filter, setFilter] = useState<FilterType>('all');
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 8;

  const filteredAccounts = accounts.filter((account) => {
    const matchesSearch =
      account.accountId.toLowerCase().includes(searchQuery.toLowerCase()) ||
      account.storeName.toLowerCase().includes(searchQuery.toLowerCase());
    
    const matchesFilter =
      filter === 'all' ||
      (filter === 'active' && account.status === 'active') ||
      (filter === 'manual' && account.status === 'manual') ||
      (filter === 'error' && account.status === 'error');

    return matchesSearch && matchesFilter;
  });

  const totalPages = Math.ceil(filteredAccounts.length / itemsPerPage);
  const paginatedAccounts = filteredAccounts.slice(
    (currentPage - 1) * itemsPerPage,
    currentPage * itemsPerPage
  );

  const getStatusBadge = (status: Account['status']) => {
    switch (status) {
      case 'active':
        return <Badge variant="success">自動稼働中</Badge>;
      case 'manual':
        return <Badge variant="warning">手動操作中</Badge>;
      case 'error':
        return <Badge variant="error">エラー</Badge>;
      default:
        return <Badge variant="secondary">無効</Badge>;
    }
  };

  const filterButtons: { id: FilterType; label: string }[] = [
    { id: 'all', label: 'すべて' },
    { id: 'active', label: '稼働中' },
    { id: 'manual', label: '手動操作' },
    { id: 'error', label: 'エラー' },
  ];

  return (
    <div className="rounded-xl border bg-card shadow-sm">
      <div className="border-b p-5">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <h2 className="text-lg font-semibold text-foreground">アカウント一覧</h2>
          <p className="text-sm text-muted-foreground">
            {totalAccounts !== undefined ? `全${totalAccounts}アカウント` : '読み込み中...'}
          </p>
        </div>
        
        <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="アカウントIDまたは店名で検索..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9"
            />
          </div>
          
          <div className="flex gap-1 rounded-lg border bg-muted/50 p-1">
            {filterButtons.map((btn) => (
              <button
                key={btn.id}
                onClick={() => {
                  setFilter(btn.id);
                  setCurrentPage(1);
                }}
                className={`px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                  filter === btn.id
                    ? 'bg-card text-foreground shadow-sm'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                {btn.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b bg-muted/30">
              <th className="px-5 py-3 text-left text-xs font-medium text-muted-foreground">アカウントID</th>
              <th className="px-5 py-3 text-left text-xs font-medium text-muted-foreground">店名</th>
              <th className="px-5 py-3 text-left text-xs font-medium text-muted-foreground">状態</th>
              <th className="px-5 py-3 text-left text-xs font-medium text-muted-foreground">スケジュール</th>
              <th className="px-5 py-3 text-left text-xs font-medium text-muted-foreground">待機状態</th>
              <th className="px-5 py-3 text-left text-xs font-medium text-muted-foreground">URL</th>
              <th className="px-5 py-3 text-left text-xs font-medium text-muted-foreground">最終更新</th>
              <th className="px-5 py-3 text-left text-xs font-medium text-muted-foreground">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {isLoading && paginatedAccounts.length === 0 ? (
              <tr>
                <td colSpan={8} className="px-5 py-8 text-center text-sm text-muted-foreground">
                  読み込み中...
                </td>
              </tr>
            ) : paginatedAccounts.length === 0 ? (
              <tr>
                <td colSpan={8} className="px-5 py-8 text-center text-sm text-muted-foreground">
                  アカウントが見つかりません
                </td>
              </tr>
            ) : (
              paginatedAccounts.map((account) => (
              <tr key={account.id} className="transition-colors hover:bg-muted/20">
                <td className="px-5 py-4 text-sm font-medium text-foreground">{account.accountId}</td>
                <td className="px-5 py-4 text-sm text-foreground">{account.storeName}</td>
                <td className="px-5 py-4">{getStatusBadge(account.status)}</td>
                <td className="px-5 py-4 text-sm text-muted-foreground">{account.schedule}</td>
                <td className="px-5 py-4 text-sm text-muted-foreground">{account.waitingStatus}</td>
                <td className="px-5 py-4">
                  <span className="text-sm text-primary hover:underline cursor-pointer">{account.url}</span>
                </td>
                <td className="px-5 py-4 text-sm text-muted-foreground">{account.lastUpdated}</td>
                <td className="px-5 py-4">
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon" className="h-8 w-8">
                        <MoreVertical className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem>詳細を表示</DropdownMenuItem>
                      <DropdownMenuItem>編集</DropdownMenuItem>
                      <DropdownMenuItem>ログを表示</DropdownMenuItem>
                      <DropdownMenuItem className="text-destructive">無効化</DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </td>
              </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between border-t px-5 py-4">
        <p className="text-sm text-muted-foreground">
          {filteredAccounts.length}件のアカウントを表示中
        </p>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
            disabled={currentPage === 1}
          >
            前へ
          </Button>
          {Array.from({ length: Math.min(3, totalPages) }, (_, i) => i + 1).map((page) => (
            <Button
              key={page}
              variant={currentPage === page ? 'default' : 'outline'}
              size="sm"
              onClick={() => setCurrentPage(page)}
              className="w-9"
            >
              {page}
            </Button>
          ))}
          <Button
            variant="outline"
            size="sm"
            onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
            disabled={currentPage === totalPages}
          >
            次へ
          </Button>
        </div>
      </div>
    </div>
  );
}

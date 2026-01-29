import { Bell, User, RefreshCw, Settings } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useQueryClient } from '@tanstack/react-query';
import { toast } from '@/hooks/use-toast';

interface HeaderProps {
  currentPage: string;
  onPageChange: (page: string) => void;
}

export function Header({ currentPage, onPageChange }: HeaderProps) {
  const queryClient = useQueryClient();

  const handleRefresh = () => {
    // すべてのクエリを再取得
    queryClient.invalidateQueries();
    toast({
      title: 'データを更新しました',
      description: 'すべてのデータを再取得しました',
    });
  };

  const navItems = [
    { id: 'dashboard', label: 'ダッシュボード' },
    { id: 'patches', label: 'パッチ管理' },
    { id: 'accounts', label: 'アカウント管理' },
    { id: 'schedule', label: 'スケジュール' },
    { id: 'logs', label: 'ログ' },
    { id: 'settings', label: '設定' },
  ];

  return (
    <header className="sticky top-0 z-50 w-full border-b bg-card">
      <div className="flex h-16 items-center justify-between px-6">
        <div className="flex items-center gap-8">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary">
              <RefreshCw className="h-5 w-5 text-primary-foreground" />
            </div>
            <div>
              <h1 className="text-base font-semibold text-foreground">Shinchakun 自動化システム</h1>
              <p className="text-xs text-muted-foreground">200アカウント管理</p>
            </div>
          </div>
          
          <nav className="hidden md:flex items-center gap-1">
            {navItems.map((item) => (
              <button
                key={item.id}
                onClick={() => onPageChange(item.id)}
                className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                  currentPage === item.id
                    ? 'text-primary bg-primary/5'
                    : 'text-muted-foreground hover:text-foreground hover:bg-muted'
                }`}
              >
                {item.label}
              </button>
            ))}
          </nav>
        </div>

        <div className="flex items-center gap-2">
          <Button 
            variant={currentPage === 'settings' ? 'default' : 'outline'} 
            size="sm" 
            className="gap-2"
            onClick={() => onPageChange('settings')}
          >
            <Settings className="h-4 w-4" />
            設定
          </Button>
          <Button 
            size="sm" 
            className="gap-2 bg-success hover:bg-success/90 text-success-foreground"
            onClick={handleRefresh}
          >
            <RefreshCw className="h-4 w-4" />
            手動更新
          </Button>
          <Button variant="ghost" size="icon" className="relative">
            <Bell className="h-5 w-5" />
            <span className="absolute -right-0.5 -top-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-destructive text-[10px] font-medium text-destructive-foreground">
              3
            </span>
          </Button>
          <Button variant="ghost" size="icon">
            <User className="h-5 w-5" />
          </Button>
        </div>
      </div>
    </header>
  );
}

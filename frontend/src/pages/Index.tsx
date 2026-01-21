import { useState } from 'react';
import { Header } from '@/components/Header';
import { Dashboard } from '@/pages/Dashboard';
import { Settings } from '@/pages/Settings';

const Index = () => {
  const [currentPage, setCurrentPage] = useState('dashboard');

  return (
    <div className="min-h-screen bg-background">
      <Header currentPage={currentPage} onPageChange={setCurrentPage} />
      <main className="container mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
        {currentPage === 'dashboard' && <Dashboard />}
        {currentPage === 'settings' && <Settings />}
        {currentPage === 'accounts' && (
          <div className="rounded-xl border bg-card p-8 text-center">
            <h2 className="text-xl font-semibold text-foreground">アカウント管理</h2>
            <p className="mt-2 text-muted-foreground">アカウントの追加・編集・削除機能</p>
          </div>
        )}
        {currentPage === 'schedule' && (
          <div className="rounded-xl border bg-card p-8 text-center">
            <h2 className="text-xl font-semibold text-foreground">スケジュール設定</h2>
            <p className="mt-2 text-muted-foreground">自動実行スケジュールの管理</p>
          </div>
        )}
        {currentPage === 'logs' && (
          <div className="rounded-xl border bg-card p-8 text-center">
            <h2 className="text-xl font-semibold text-foreground">ログ閲覧</h2>
            <p className="mt-2 text-muted-foreground">システムログの詳細表示</p>
          </div>
        )}
      </main>
    </div>
  );
};

export default Index;

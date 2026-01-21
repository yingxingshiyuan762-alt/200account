import { Account, LogEntry, ScheduleItem, SystemStatus } from '@/types/account';

export const mockAccounts: Account[] = [
  { id: '1', accountId: 'szo22_25794', storeName: '新宿店', status: 'active', schedule: '出勤設定', waitingStatus: '待機中', url: 'doors1', lastUpdated: '2分前' },
  { id: '2', accountId: 'szo22_25795', storeName: '渋谷店', status: 'active', schedule: '出勤設定', waitingStatus: '稼働中', url: 'doors1', lastUpdated: '3分前' },
  { id: '3', accountId: 'szo22_25796', storeName: '池袋店', status: 'manual', schedule: '出勤設定', waitingStatus: '待機中', url: 'doors2', lastUpdated: '1分前' },
  { id: '4', accountId: 'szo22_25797', storeName: '六本木店', status: 'active', schedule: '出勤設定', waitingStatus: '待機中', url: 'doors1', lastUpdated: '5分前' },
  { id: '5', accountId: 'szo22_25798', storeName: '銀座店', status: 'error', schedule: '未設定', waitingStatus: '-', url: 'doors1', lastUpdated: '10分前' },
  { id: '6', accountId: 'szo22_25799', storeName: '品川店', status: 'active', schedule: '出勤設定', waitingStatus: '稼働中', url: 'doors2', lastUpdated: '2分前' },
  { id: '7', accountId: 'szo22_25800', storeName: '上野店', status: 'active', schedule: '出勤設定', waitingStatus: '待機中', url: 'doors1', lastUpdated: '4分前' },
  { id: '8', accountId: 'szo22_25801', storeName: '新橋店', status: 'manual', schedule: '出勤設定', waitingStatus: '待機中', url: 'doors1', lastUpdated: '6分前' },
  { id: '9', accountId: 'szo22_25802', storeName: '秋葉原店', status: 'active', schedule: '出勤設定', waitingStatus: '待機中', url: 'doors2', lastUpdated: '1分前' },
  { id: '10', accountId: 'szo22_25803', storeName: '浅草店', status: 'active', schedule: '出勤設定', waitingStatus: '稼働中', url: 'doors1', lastUpdated: '7分前' },
];

export const mockLogs: LogEntry[] = [
  { id: '1', timestamp: '14:32:15', accountId: 'szo22_25794', level: 'success', message: '待機接客配信を正常に設定しました' },
  { id: '2', timestamp: '14:32:10', accountId: 'szo22_25796', level: 'warning', message: '手動操作を検知したため処理をスキップしました' },
  { id: '3', timestamp: '14:31:58', accountId: 'szo22_25795', level: 'success', message: 'ステータスを「待機中」に変更しました' },
  { id: '4', timestamp: '14:31:45', accountId: 'szo22_25798', level: 'error', message: 'ログインに失敗しました。再試行します' },
  { id: '5', timestamp: '14:31:30', accountId: 'システム', level: 'info', message: '待機接客配信の自動実行を開始しました' },
  { id: '6', timestamp: '14:30:22', accountId: 'szo22_25799', level: 'success', message: 'スケジュール更新が完了しました' },
];

export const mockSchedules: ScheduleItem[] = [
  { id: '1', name: 'スケジュール自動更新', status: 'scheduled', time: '07:00', accountCount: 200 },
  { id: '2', name: '待機接客配信', status: 'scheduled', time: '08:30', accountCount: 185 },
  { id: '3', name: '待機接客配信', status: 'scheduled', time: '10:00', accountCount: 192 },
  { id: '4', name: '待機接客配信', status: 'completed', time: '11:30', accountCount: 198 },
  { id: '5', name: '待機接客配信', status: 'completed', time: '13:00', accountCount: 195 },
  { id: '6', name: '待機接客配信', status: 'running', time: '14:30', accountCount: 198 },
];

export const mockSystemStatus: SystemStatus = {
  isRunning: true,
  activeAccounts: 198,
  totalAccounts: 200,
  manualOperations: 2,
  nextSchedule: '明日 07:00',
  waitingTime: '75分後',
  cpuUsage: 45,
  memoryUsage: '3.2GB/4GB',
  vpsInfo: 'ConoHa (AlmaLinux)',
};

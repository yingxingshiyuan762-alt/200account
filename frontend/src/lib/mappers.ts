/**
 * Data Mappers
 * 
 * Backend APIのレスポンスをフロントエンドの型にマッピング
 */

import { Account, LogEntry, ScheduleItem, SystemStatus } from '@/types/account';
import { formatDistanceToNow, format } from 'date-fns';

/**
 * Backendのアカウントステータスをフロントエンドのステータスにマッピング
 */
function mapAccountStatus(status: string): Account['status'] {
  const statusMap: Record<string, Account['status']> = {
    'IDLE': 'active',              // 待機中 → 自動稼働中
    'PROCESSING': 'active',        // 処理中 → 自動稼働中
    'MANUAL_OPERATION': 'manual',  // 手動操作中
    'ERROR': 'error',              // エラー
    'DISABLED': 'inactive',        // 無効化
  };
  return statusMap[status] || 'inactive';
}

/**
 * ログのステータスをログレベルにマッピング
 */
function mapLogLevel(status: string): LogEntry['level'] {
  const levelMap: Record<string, LogEntry['level']> = {
    'SUCCESS': 'success',
    'ERROR': 'error',
    'WARNING': 'warning',
    'INFO': 'info',
  };
  return levelMap[status] || 'info';
}

/**
 * ログインURLからURLタイプを取得
 */
function extractUrlType(loginUrl: string): Account['url'] {
  if (loginUrl.includes('doors1')) return 'doors1';
  if (loginUrl.includes('doors2')) return 'doors2';
  return 'doors1'; // デフォルト
}

/**
 * 時刻から相対時間を取得（日本語）
 */
function getRelativeTime(dateString: string | null): string {
  if (!dateString) return '-';
  try {
    const date = new Date(dateString);
    return formatDistanceToNow(date, { addSuffix: true });
  } catch {
    return '-';
  }
}

/**
 * 時刻から時刻文字列を取得
 */
function getTimeString(dateString: string | null): string {
  if (!dateString) return '-';
  try {
    const date = new Date(dateString);
    return format(date, 'HH:mm:ss');
  } catch {
    return '-';
  }
}

/**
 * BackendのアカウントデータをフロントエンドのAccount型にマッピング
 */
export function mapAccount(account: {
  id: string;
  username: string;
  store_name: string;
  status: string;
  login_url: string;
  last_login_at: string | null;
  last_success_at: string | null;
  error_count: number;
  last_error: string | null;
  updated_at: string | null;
}): Account {
  return {
    id: account.id,
    accountId: account.username,
    storeName: account.store_name,
    status: mapAccountStatus(account.status),
    schedule: '出勤設定', // TODO: バックエンドから取得する必要がある
    waitingStatus: '待機中', // TODO: バックエンドから取得する必要がある
    url: extractUrlType(account.login_url),
    lastUpdated: getRelativeTime(account.updated_at),
  };
}

/**
 * BackendのログデータをフロントエンドのLogEntry型にマッピング
 */
export function mapLogEntry(log: {
  id: string;
  account_id: string;
  action_type: string;
  status: string;
  message: string;
  error_detail: string | null;
  execution_time: number | null;
  request_id: string | null;
  created_at: string | null;
  file_path?: string | null;
  function_name?: string | null;
  line_number?: number | null;
}): LogEntry {
  // アカウントIDから表示用のIDを抽出（必要に応じて）
  const accountId = log.account_id.length > 20 
    ? log.account_id.substring(0, 20) + '...' 
    : log.account_id;

  return {
    id: log.id,
    timestamp: getTimeString(log.created_at),
    accountId: accountId,
    level: mapLogLevel(log.status),
    message: log.message || log.action_type,
    filePath: log.file_path || undefined,
    functionName: log.function_name || undefined,
    lineNumber: log.line_number || undefined,
  };
}

/**
 * システムステータスをマッピング
 */
export function mapSystemStatus(data: {
  system_status: string;
  total_accounts: number;
  active_accounts: number;
  manual_operation_accounts: number;
  error_accounts: number;
  last_check: string;
  status_counts: Record<string, number>;
  monitor_states?: {
    NORMAL: number;
    UNSTABLE: number;
    STOPPED: number;
  };
}, resources?: {
  cpu_percent: number;
  memory_used_gb: number;
  memory_total_gb: number;
  memory_percent: number;
  vps: string;
}): SystemStatus {
  return {
    isRunning: data.system_status === 'running',
    activeAccounts: data.active_accounts,
    totalAccounts: data.total_accounts,
    manualOperations: data.manual_operation_accounts,
    nextSchedule: '明日 07:00', // TODO: スケジュールAPIから取得
    waitingTime: '75分後', // TODO: スケジュールAPIから取得
    cpuUsage: resources?.cpu_percent || 0,
    memoryUsage: resources 
      ? `${resources.memory_used_gb.toFixed(1)}GB/${resources.memory_total_gb.toFixed(1)}GB`
      : '0GB/0GB',
    vpsInfo: resources?.vps || 'Unknown',
    monitorStates: data.monitor_states,
  };
}

/**
 * スケジュールアイテムをマッピング
 */
export function mapScheduleItem(schedule: {
  next_run: string;
  last_run?: string | null;
  status: string;
  target_accounts: number;
  time_window?: string;
  interval?: string;
}, name: string, id: string): ScheduleItem {
  const date = new Date(schedule.next_run);
  const now = new Date();
  const diffMs = date.getTime() - now.getTime();
  const diffMinutes = Math.floor(diffMs / (1000 * 60));
  const diffHours = Math.floor(diffMinutes / 60);
  
  // 時刻をフォーマット
  let timeString: string;
  if (diffHours > 24) {
    timeString = format(date, 'MM/dd HH:mm');
  } else if (diffHours > 0) {
    timeString = `${diffHours}時間後 (${format(date, 'HH:mm')})`;
  } else if (diffMinutes > 0) {
    timeString = `${diffMinutes}分後 (${format(date, 'HH:mm')})`;
  } else {
    timeString = '実行中';
  }
  
  return {
    id,
    name,
    status: schedule.status === 'scheduled' ? 'scheduled' : 
            schedule.status === 'running' ? 'running' : 'completed',
    time: timeString,
    accountCount: schedule.target_accounts,
  };
}


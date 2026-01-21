export type AccountStatus = 'active' | 'manual' | 'error' | 'inactive';
export type ScheduleStatus = '出勤設定' | '未設定';
export type WaitingStatus = '待機中' | '稼働中' | '-';
export type LoginUrl = 'doors1' | 'doors2';

export interface Account {
  id: string;
  accountId: string;
  storeName: string;
  status: AccountStatus;
  schedule: ScheduleStatus;
  waitingStatus: WaitingStatus;
  url: LoginUrl;
  lastUpdated: string;
  password?: string;
}

export type LogLevel = 'info' | 'success' | 'warning' | 'error';

export interface LogEntry {
  id: string;
  timestamp: string;
  accountId: string;
  level: LogLevel;
  message: string;
  filePath?: string;
  functionName?: string;
  lineNumber?: number;
}

export interface ScheduleItem {
  id: string;
  name: string;
  status: 'scheduled' | 'completed' | 'running';
  time: string;
  accountCount: number;
}

export interface SystemStatus {
  isRunning: boolean;
  activeAccounts: number;
  totalAccounts: number;
  manualOperations: number;
  nextSchedule: string;
  waitingTime: string;
  cpuUsage: number;
  memoryUsage: string;
  vpsInfo: string;
  monitorStates?: {
    NORMAL: number;
    UNSTABLE: number;
    STOPPED: number;
  };
}

/**
 * API Hooks
 * 
 * React Queryを使用したAPIデータフェッチングフック
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { systemApi, accountApi, scheduleApi, logApi } from '@/lib/api';
import { mapAccount, mapLogEntry, mapSystemStatus, mapScheduleItem } from '@/lib/mappers';

/**
 * システム状態を取得するフック
 */
export function useSystemStatus() {
  return useQuery({
    queryKey: ['system', 'status'],
    queryFn: async () => {
      const [statusRes, resourcesRes] = await Promise.all([
        systemApi.getStatus(),
        systemApi.getResources(),
      ]);

      if (!statusRes.success || !statusRes.data) {
        throw new Error(statusRes.error || 'Failed to fetch system status');
      }

      const systemStatus = mapSystemStatus(
        statusRes.data,
        resourcesRes.success ? resourcesRes.data : undefined
      );

      return systemStatus;
    },
    refetchInterval: 30000, // 30秒ごとに更新
  });
}

/**
 * アカウント一覧を取得するフック
 */
export function useAccounts(params?: {
  page?: number;
  per_page?: number;
  search?: string;
  status?: string;
}) {
  return useQuery({
    queryKey: ['accounts', params],
    queryFn: async () => {
      const response = await accountApi.getAccounts(params);

      if (!response.success || !response.data) {
        throw new Error(response.error || 'Failed to fetch accounts');
      }

      return {
        accounts: response.data.accounts.map(mapAccount),
        pagination: response.data.pagination,
      };
    },
    refetchInterval: 10000, // 10秒ごとに更新
  });
}

/**
 * スケジュール情報を取得するフック
 */
export function useSchedules() {
  return useQuery({
    queryKey: ['schedules', 'upcoming'],
    queryFn: async () => {
      const response = await scheduleApi.getUpcoming();

      if (!response.success || !response.data) {
        throw new Error(response.error || 'Failed to fetch schedules');
      }

      const schedules: Array<{ id: string; name: string; status: 'scheduled' | 'completed' | 'running'; time: string; accountCount: number }> = [
        mapScheduleItem(response.data.schedule_update, 'スケジュール自動更新', '1'),
        mapScheduleItem(response.data.wait_reception, '待機接客配信', '2'),
      ];

      return schedules;
    },
    refetchInterval: 60000, // 1分ごとに更新
  });
}

/**
 * ログ一覧を取得するフック
 */
export function useLogs(params?: {
  limit?: number;
  account_id?: string;
  status?: string;
}) {
  return useQuery({
    queryKey: ['logs', params],
    queryFn: async () => {
      const response = await logApi.getLogs(params);

      if (!response.success || !response.data) {
        throw new Error(response.error || 'Failed to fetch logs');
      }

      return {
        logs: response.data.logs.map(mapLogEntry),
        count: response.data.count,
      };
    },
    refetchInterval: 5000, // 5秒ごとに更新
  });
}

/**
 * 最近のログを取得するフック
 */
export function useRecentLogs(limit: number = 50) {
  return useQuery({
    queryKey: ['logs', 'recent', limit],
    queryFn: async () => {
      const response = await logApi.getRecentLogs(limit);

      if (!response.success || !response.data) {
        throw new Error(response.error || 'Failed to fetch recent logs');
      }

      return {
        logs: response.data.logs.map(mapLogEntry),
        count: response.data.count,
        timestamp: response.data.timestamp,
      };
    },
    refetchInterval: 5000, // 5秒ごとに更新
  });
}

/**
 * アカウント復旧のミューテーションフック
 */
export function useRecoverAccount() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ accountId, strategy }: { accountId: string; strategy?: string }) => {
      const response = await accountApi.recoverAccount(accountId, strategy);
      if (!response.success) {
        throw new Error(response.error || 'Failed to recover account');
      }
      return response.data;
    },
    onSuccess: () => {
      // アカウント一覧を再取得
      queryClient.invalidateQueries({ queryKey: ['accounts'] });
      queryClient.invalidateQueries({ queryKey: ['system', 'status'] });
    },
  });
}

/**
 * システム設定を取得するフック
 */
export function useSystemConfig() {
  return useQuery({
    queryKey: ['system', 'config'],
    queryFn: async () => {
      const { configApi } = await import('@/lib/api');
      const response = await configApi.getConfig();
      if (!response.success || !response.data) {
        throw new Error(response.error || 'Failed to fetch system config');
      }
      return response.data;
    },
    refetchInterval: 30000, // 30秒ごとに更新
  });
}

/**
 * システム設定を更新するミューテーションフック
 */
export function useUpdateSystemConfig() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ configKey, value, description }: { configKey: string; value: any; description?: string }) => {
      const { configApi } = await import('@/lib/api');
      const response = await configApi.updateConfig(configKey, value, description);
      if (!response.success) {
        throw new Error(response.error || 'Failed to update system config');
      }
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['system', 'config'] });
    },
  });
}

/**
 * 監視状態を取得するフック
 */
export function useMonitoringStates() {
  return useQuery({
    queryKey: ['monitoring', 'states'],
    queryFn: async () => {
      const { monitoringApi } = await import('@/lib/api');
      const response = await monitoringApi.getStates();
      if (!response.success || !response.data) {
        throw new Error(response.error || 'Failed to fetch monitoring states');
      }
      return response.data;
    },
    refetchInterval: 10000, // 10秒ごとに更新
  });
}

/**
 * 自動化処理を実行するミューテーションフック
 */
export function useExecuteAutomation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ taskType, accountIds }: { taskType: string; accountIds?: string[] }) => {
      const { automationApi } = await import('@/lib/api');
      const response = await automationApi.executeAutomation(taskType, accountIds);
      if (!response.success) {
        throw new Error(response.error || 'Failed to execute automation');
      }
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['accounts'] });
      queryClient.invalidateQueries({ queryKey: ['system', 'status'] });
      queryClient.invalidateQueries({ queryKey: ['logs'] });
    },
  });
}


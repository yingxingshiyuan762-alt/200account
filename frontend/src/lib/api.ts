/**
 * API Client
 * 
 * Backend APIとの通信を行うクライアント
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000/api';

export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  pagination: {
    page: number;
    per_page: number;
    total: number;
    pages: number;
  };
}

/**
 * APIリクエストの基本関数
 */
async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<ApiResponse<T>> {
  try {
    const url = `${API_BASE_URL}${endpoint}`;
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ error: response.statusText }));
      throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    return data;
  } catch (error) {
    console.error(`API request failed: ${endpoint}`, error);
    return {
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error occurred',
    };
  }
}

/**
 * システム状態API
 */
export const systemApi = {
  /**
   * システム状態を取得
   */
  async getStatus() {
    return apiRequest<{
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
    }>('/system/status');
  },

  /**
   * システム統計を取得
   */
  async getStats(days: number = 7) {
    return apiRequest(`/system/stats?days=${days}`);
  },

  /**
   * システムリソース使用状況を取得
   */
  async getResources() {
    return apiRequest<{
      vps: string;
      cpu_percent: number;
      memory_used_gb: number;
      memory_total_gb: number;
      memory_percent: number;
      timestamp: string;
    }>('/system/resources');
  },
};

/**
 * アカウントAPI
 */
export const accountApi = {
  /**
   * アカウント一覧を取得
   */
  async getAccounts(params?: {
    page?: number;
    per_page?: number;
    search?: string;
    status?: string;
  }) {
    const queryParams = new URLSearchParams();
    if (params?.page) queryParams.append('page', params.page.toString());
    if (params?.per_page) queryParams.append('per_page', params.per_page.toString());
    if (params?.search) queryParams.append('search', params.search);
    if (params?.status) queryParams.append('status', params.status);

    const queryString = queryParams.toString();
    return apiRequest<{
      accounts: Array<{
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
      }>;
      pagination: {
        page: number;
        per_page: number;
        total: number;
        pages: number;
      };
    }>(`/accounts${queryString ? `?${queryString}` : ''}`);
  },

  /**
   * アカウント詳細を取得
   */
  async getAccount(accountId: string) {
    return apiRequest<{
      id: string;
      username: string;
      store_name: string;
      status: string;
      login_url: string;
      last_login_at: string | null;
      last_success_at: string | null;
      error_count: number;
      last_error: string | null;
      is_active: boolean;
      created_at: string | null;
      updated_at: string | null;
      log_summary?: any;
    }>(`/accounts/${accountId}`);
  },

  /**
   * アカウントを復旧
   */
  async recoverAccount(accountId: string, strategy: string = 'LAST_SUCCESS_RECOVERY') {
    return apiRequest<{
      success: boolean;
      data?: any;
    }>(`/accounts/${accountId}/recover`, {
      method: 'POST',
      body: JSON.stringify({ strategy }),
    });
  },
};

/**
 * スケジュールAPI
 */
export const scheduleApi = {
  /**
   * 次回実行予定を取得
   */
  async getUpcoming() {
    return apiRequest<{
      schedule_update: {
        next_run: string;
        status: string;
        target_accounts: number;
      };
      wait_reception: {
        next_run: string;
        status: string;
        target_accounts: number;
      };
    }>('/schedules/upcoming');
  },
};

/**
 * ログAPI
 */
export const logApi = {
  /**
   * ログ一覧を取得
   */
  async getLogs(params?: {
    limit?: number;
    account_id?: string;
    status?: string;
  }) {
    const queryParams = new URLSearchParams();
    if (params?.limit) queryParams.append('limit', params.limit.toString());
    if (params?.account_id) queryParams.append('account_id', params.account_id);
    if (params?.status) queryParams.append('status', params.status);

    const queryString = queryParams.toString();
    return apiRequest<{
      logs: Array<{
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
      }>;
      count: number;
    }>(`/logs${queryString ? `?${queryString}` : ''}`);
  },

  /**
   * 最近のログを取得
   */
  async getRecentLogs(limit: number = 50) {
    return apiRequest<{
      logs: Array<{
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
      }>;
      count: number;
      timestamp: string;
    }>(`/logs/recent?limit=${limit}`);
  },

  /**
   * コードファイルの内容を取得
   */
  async getCodeContent(filePath: string, lineNumber?: number) {
    return apiRequest<{
      content: string;
      file_path: string;
      line_number: number | null;
      total_lines: number;
    }>(`/logs/code?file_path=${encodeURIComponent(filePath)}${lineNumber ? `&line_number=${lineNumber}` : ''}`);
  },
};

/**
 * システム設定API
 */
export const configApi = {
  /**
   * システム設定を取得
   */
  async getConfig() {
    return apiRequest<Record<string, any>>('/system/config');
  },

  /**
   * システム設定を更新
   */
  async updateConfig(configKey: string, value: any, description?: string) {
    return apiRequest<{
      key: string;
      value: any;
    }>(`/system/config/${configKey}`, {
      method: 'PUT',
      body: JSON.stringify({ value, description }),
    });
  },
};

/**
 * 監視API
 */
export const monitoringApi = {
  /**
   * 全アカウントの監視状態を取得
   */
  async getStates() {
    return apiRequest<{
      accounts: Array<{
        account_id: string;
        username: string;
        store_name: string;
        state: 'NORMAL' | 'UNSTABLE' | 'STOPPED';
        last_check: string | null;
        account_status: string;
      }>;
      summary: {
        NORMAL: number;
        UNSTABLE: number;
        STOPPED: number;
      };
    }>('/monitoring/states');
  },

  /**
   * 特定アカウントの監視状態を取得
   */
  async getAccountState(accountId: string) {
    return apiRequest<{
      account_id: string;
      state: 'NORMAL' | 'UNSTABLE' | 'STOPPED' | null;
      last_check: string | null;
    }>(`/monitoring/account/${accountId}`);
  },
};

/**
 * 自動化実行API
 */
export const automationApi = {
  /**
   * 自動化処理を実行
   */
  async executeAutomation(taskType: string, accountIds?: string[]) {
    return apiRequest<{
      total: number;
      success: number;
      failed: number;
      skipped: number;
    }>('/automation/execute', {
      method: 'POST',
      body: JSON.stringify({ task_type: taskType, account_ids: accountIds }),
    });
  },

  /**
   * 単一アカウントの自動化処理を実行
   */
  async executeSingleAccount(accountId: string, taskType: string) {
    return apiRequest<{
      success: boolean;
      account_id: string;
      error?: string;
    }>(`/automation/execute/${accountId}`, {
      method: 'POST',
      body: JSON.stringify({ task_type: taskType }),
    });
  },
};


/**
 * Popup script for 200 Account Automation Monitor
 */

let notifications = [];
let connectionStatus = 'disconnected';

// Initialize popup
document.addEventListener('DOMContentLoaded', () => {
  loadNotifications();
  setupEventListeners();
  
  // Refresh every 5 seconds
  setInterval(loadNotifications, 5000);
});

/**
 * Load notifications from background script
 */
function loadNotifications() {
  chrome.runtime.sendMessage({ action: 'getNotifications' }, (response) => {
    if (chrome.runtime.lastError) {
      console.error('Error loading notifications:', chrome.runtime.lastError);
      return;
    }
    
    if (response) {
      notifications = response.notifications || [];
      connectionStatus = response.status || 'disconnected';
      renderNotifications();
      updateStatusIndicator();
    }
  });
}

/**
 * Render notifications
 */
function renderNotifications() {
  const container = document.getElementById('notificationsContainer');
  
  if (notifications.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon">🔔</div>
        <div class="empty-state-text">通知はありません</div>
      </div>
    `;
    return;
  }
  
  container.innerHTML = notifications.map(notification => {
    const {
      id,
      severity = 'INFO',
      title = 'システム通知',
      message = '',
      account_username,
      timestamp,
      read
    } = notification;
    
    const timeStr = formatTimestamp(timestamp);
    const unreadClass = read ? '' : 'unread';
    
    return `
      <div class="notification-item ${unreadClass}" data-id="${id}">
        <div class="notification-header">
          <div class="notification-title">
            <span class="severity-badge ${severity.toLowerCase()}">${severity}</span>
            ${title}
          </div>
          <div class="notification-time">${timeStr}</div>
        </div>
        <div class="notification-message">${escapeHtml(message)}</div>
        ${account_username ? `<div class="notification-account">Account: ${escapeHtml(account_username)}</div>` : ''}
      </div>
    `;
  }).join('');
}

/**
 * Update status indicator
 */
function updateStatusIndicator() {
  const indicator = document.getElementById('statusIndicator');
  const statusText = document.getElementById('statusText');
  
  indicator.className = 'status-indicator';
  
  if (connectionStatus === 'connected') {
    indicator.classList.add('connected');
    statusText.textContent = 'バックエンドに接続済み';
  } else if (connectionStatus === 'error') {
    indicator.classList.add('error');
    statusText.textContent = '接続エラー';
  } else {
    indicator.classList.add('disconnected');
    statusText.textContent = '未接続';
  }
}

/**
 * Setup event listeners
 */
function setupEventListeners() {
  // Mark all read button
  document.getElementById('markAllReadBtn').addEventListener('click', () => {
    chrome.runtime.sendMessage({ action: 'markAllRead' }, (response) => {
      if (response && response.success) {
        loadNotifications();
      }
    });
  });
  
  // Clear history button
  document.getElementById('clearHistoryBtn').addEventListener('click', () => {
    if (confirm('通知履歴をすべて削除しますか?')) {
      chrome.runtime.sendMessage({ action: 'clearHistory' }, (response) => {
        if (response && response.success) {
          loadNotifications();
        }
      });
    }
  });
  
  // Reconnect button
  document.getElementById('reconnectBtn').addEventListener('click', () => {
    chrome.runtime.sendMessage({ action: 'reconnect' }, (response) => {
      if (response && response.success) {
        setTimeout(loadNotifications, 1000);
      }
    });
  });
}

/**
 * Format timestamp
 */
function formatTimestamp(timestamp) {
  if (!timestamp) return '';
  
  const date = new Date(timestamp);
  const now = new Date();
  const diffMs = now - date;
  const diffMins = Math.floor(diffMs / 60000);
  
  if (diffMins < 1) return 'たった今';
  if (diffMins < 60) return `${diffMins}分前`;
  
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}時間前`;
  
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 7) return `${diffDays}日前`;
  
  // Format as date
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  const hours = String(date.getHours()).padStart(2, '0');
  const minutes = String(date.getMinutes()).padStart(2, '0');
  
  return `${year}/${month}/${day} ${hours}:${minutes}`;
}

/**
 * Escape HTML
 */
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

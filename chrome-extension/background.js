/**
 * Background Service Worker for 200 Account Automation Monitor
 * 
 * Responsibilities:
 * - Connect to backend WebSocket server
 * - Receive error notifications
 * - Display Chrome notifications
 * - Store notification history
 * - Auto-reconnect on connection loss
 */

// Configuration
const BACKEND_WS_URL = 'ws://localhost:5000/ws/notifications';
const BACKEND_HTTP_URL = 'http://localhost:5000/api/notifications/extension';
const RECONNECT_INTERVAL = 5000; // 5 seconds
const POLL_INTERVAL = 30000; // 30 seconds (fallback polling)

let ws = null;
let reconnectTimer = null;
let pollTimer = null;
let notificationHistory = [];
let connectionStatus = 'disconnected';

// Initialize on install
chrome.runtime.onInstalled.addListener(() => {
  console.log('200 Account Automation Monitor installed');
  initializeExtension();
});

// Initialize on startup
chrome.runtime.onStartup.addListener(() => {
  console.log('200 Account Automation Monitor started');
  initializeExtension();
});

/**
 * Initialize extension
 */
function initializeExtension() {
  loadNotificationHistory();
  connectWebSocket();
  startPolling();
  
  // Set up alarm for periodic checks
  chrome.alarms.create('healthCheck', { periodInMinutes: 1 });
}

/**
 * Connect to WebSocket server
 */
function connectWebSocket() {
  if (ws && (ws.readyState === WebSocket.CONNECTING || ws.readyState === WebSocket.OPEN)) {
    console.log('WebSocket already connected or connecting');
    return;
  }
  
  console.log(`Connecting to WebSocket: ${BACKEND_WS_URL}`);
  
  try {
    ws = new WebSocket(BACKEND_WS_URL);
    
    ws.onopen = () => {
      console.log('WebSocket connected');
      connectionStatus = 'connected';
      updateBadge('connected');
      
      // Send registration message
      ws.send(JSON.stringify({
        type: 'register',
        client: 'chrome_extension',
        timestamp: new Date().toISOString()
      }));
      
      // Clear reconnect timer
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
    };
    
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        console.log('Received notification:', data);
        handleNotification(data);
      } catch (error) {
        console.error('Error parsing message:', error);
      }
    };
    
    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      connectionStatus = 'error';
      updateBadge('error');
    };
    
    ws.onclose = () => {
      console.log('WebSocket closed');
      connectionStatus = 'disconnected';
      updateBadge('disconnected');
      scheduleReconnect();
    };
    
  } catch (error) {
    console.error('Failed to create WebSocket:', error);
    connectionStatus = 'error';
    updateBadge('error');
    scheduleReconnect();
  }
}

/**
 * Schedule reconnection
 */
function scheduleReconnect() {
  if (reconnectTimer) {
    return;
  }
  
  console.log(`Scheduling reconnect in ${RECONNECT_INTERVAL}ms`);
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    connectWebSocket();
  }, RECONNECT_INTERVAL);
}

/**
 * Start polling (fallback method)
 */
function startPolling() {
  if (pollTimer) {
    clearInterval(pollTimer);
  }
  
  pollTimer = setInterval(() => {
    fetchNotifications();
  }, POLL_INTERVAL);
  
  // Initial fetch
  fetchNotifications();
}

/**
 * Fetch notifications from backend (HTTP fallback)
 */
async function fetchNotifications() {
  try {
    const response = await fetch(`${BACKEND_HTTP_URL}?limit=10`);
    if (!response.ok) {
      console.error('Failed to fetch notifications:', response.statusText);
      return;
    }
    
    const data = await response.json();
    if (data.success && data.notifications) {
      data.notifications.forEach(notification => {
        // Check if we've already seen this notification
        const isDuplicate = notificationHistory.some(
          n => n.id === notification.id || 
          (n.timestamp === notification.timestamp && n.message === notification.message)
        );
        
        if (!isDuplicate) {
          handleNotification(notification);
        }
      });
    }
  } catch (error) {
    console.error('Error fetching notifications:', error);
  }
}

/**
 * Handle incoming notification
 */
function handleNotification(notification) {
  // Extract notification data
  const {
    id = Date.now().toString(),
    type = 'error',
    severity = 'ERROR',
    title = 'システムエラー',
    message = 'エラーが発生しました',
    account_id,
    account_username,
    timestamp = new Date().toISOString(),
    details
  } = notification;
  
  // Save to history
  const historyEntry = {
    id,
    type,
    severity,
    title,
    message,
    account_id,
    account_username,
    timestamp,
    details,
    read: false
  };
  
  notificationHistory.unshift(historyEntry);
  
  // Keep only last 100 notifications
  if (notificationHistory.length > 100) {
    notificationHistory = notificationHistory.slice(0, 100);
  }
  
  saveNotificationHistory();
  
  // Display Chrome notification
  displayChromeNotification(historyEntry);
  
  // Update badge
  updateBadge('notification');
}

/**
 * Display Chrome notification
 */
function displayChromeNotification(notification) {
  const { id, severity, title, message, account_username } = notification;
  
  // Determine icon and priority
  let iconPath = 'icons/icon128.png';
  let priority = 1;
  
  if (severity === 'CRITICAL' || severity === 'ERROR') {
    iconPath = 'icons/error.png';
    priority = 2;
  } else if (severity === 'WARNING') {
    iconPath = 'icons/warning.png';
    priority = 1;
  }
  
  // Create notification
  const notificationOptions = {
    type: 'basic',
    iconUrl: chrome.runtime.getURL(iconPath),
    title: title,
    message: account_username ? `[${account_username}] ${message}` : message,
    priority: priority,
    requireInteraction: severity === 'CRITICAL' || severity === 'ERROR',
    buttons: [
      { title: '詳細を見る' },
      { title: '閉じる' }
    ]
  };
  
  chrome.notifications.create(id, notificationOptions, (notificationId) => {
    if (chrome.runtime.lastError) {
      console.error('Failed to create notification:', chrome.runtime.lastError);
    } else {
      console.log('Notification created:', notificationId);
    }
  });
}

/**
 * Update extension badge
 */
function updateBadge(status) {
  const unreadCount = notificationHistory.filter(n => !n.read).length;
  
  if (status === 'notification' && unreadCount > 0) {
    chrome.action.setBadgeText({ text: unreadCount > 99 ? '99+' : unreadCount.toString() });
    chrome.action.setBadgeBackgroundColor({ color: '#dc2626' });
  } else if (status === 'connected') {
    chrome.action.setBadgeText({ text: '' });
  } else if (status === 'error' || status === 'disconnected') {
    chrome.action.setBadgeText({ text: '!' });
    chrome.action.setBadgeBackgroundColor({ color: '#f59e0b' });
  }
}

/**
 * Load notification history from storage
 */
async function loadNotificationHistory() {
  try {
    const result = await chrome.storage.local.get(['notificationHistory']);
    if (result.notificationHistory) {
      notificationHistory = result.notificationHistory;
      updateBadge('notification');
    }
  } catch (error) {
    console.error('Error loading notification history:', error);
  }
}

/**
 * Save notification history to storage
 */
async function saveNotificationHistory() {
  try {
    await chrome.storage.local.set({ notificationHistory });
  } catch (error) {
    console.error('Error saving notification history:', error);
  }
}

/**
 * Handle notification click
 */
chrome.notifications.onClicked.addListener((notificationId) => {
  // Mark as read
  const notification = notificationHistory.find(n => n.id === notificationId);
  if (notification) {
    notification.read = true;
    saveNotificationHistory();
    updateBadge('notification');
  }
  
  // Open popup or dashboard
  chrome.action.openPopup();
});

/**
 * Handle notification button click
 */
chrome.notifications.onButtonClicked.addListener((notificationId, buttonIndex) => {
  if (buttonIndex === 0) {
    // 詳細を見る - Open dashboard
    chrome.tabs.create({ url: 'http://localhost:8080' });
  }
  
  // Close notification
  chrome.notifications.clear(notificationId);
  
  // Mark as read
  const notification = notificationHistory.find(n => n.id === notificationId);
  if (notification) {
    notification.read = true;
    saveNotificationHistory();
    updateBadge('notification');
  }
});

/**
 * Handle alarm for health check
 */
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === 'healthCheck') {
    // Check WebSocket connection
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      console.log('Health check: WebSocket not connected, reconnecting...');
      connectWebSocket();
    }
  }
});

/**
 * Handle messages from popup
 */
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'getNotifications') {
    sendResponse({
      notifications: notificationHistory,
      status: connectionStatus
    });
  } else if (request.action === 'markAllRead') {
    notificationHistory.forEach(n => n.read = true);
    saveNotificationHistory();
    updateBadge('notification');
    sendResponse({ success: true });
  } else if (request.action === 'clearHistory') {
    notificationHistory = [];
    saveNotificationHistory();
    updateBadge('notification');
    sendResponse({ success: true });
  } else if (request.action === 'reconnect') {
    connectWebSocket();
    sendResponse({ success: true });
  }
  
  return true; // Keep channel open for async response
});

console.log('Background service worker loaded');

"""
WebSocket Handlers

リアルタイム更新のためのWebSocketイベントハンドラ
"""
from fastapi import WebSocket, WebSocketDisconnect
from datetime import datetime
import asyncio
import json

from src.database.connection import get_session
from src.database.repositories.log import AccountLogRepository
from src.database.repositories.account import AccountRepository
from src.database.models import Account, AccountStatus
from src.core.logger import logger


# クライアント接続管理
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self.rooms: dict[str, set[WebSocket]] = {
            "dashboard": set(),
            "notifications": set()  # Chrome extension notification room
        }
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        self.rooms["dashboard"].add(websocket)
        logger.info(f"WebSocket client connected: {websocket.client}")
        await websocket.send_json({"type": "connected", "message": "Connected to server"})
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        for room_connections in self.rooms.values():
            room_connections.discard(websocket)
        logger.info(f"WebSocket client disconnected: {websocket.client}")
    
    async def send_personal_message(self, message: dict, websocket: WebSocket):
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Error sending personal message: {e}")
    
    async def broadcast_to_room(self, message: dict, room: str = "dashboard"):
        disconnected = []
        for connection in self.rooms.get(room, set()):
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting to connection: {e}")
                disconnected.append(connection)
        
        # 切断された接続を削除
        for conn in disconnected:
            self.disconnect(conn)


manager = ConnectionManager()


async def websocket_endpoint(websocket: WebSocket):
    """WebSocket接続エンドポイント"""
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                message_type = message.get("type")
                
                if message_type == "subscribe":
                    room = message.get("room", "dashboard")
                    await websocket.send_json({"type": "subscribed", "room": room})
                    logger.info(f"Client {websocket.client} subscribed to room: {room}")
                
                elif message_type == "unsubscribe":
                    room = message.get("room", "dashboard")
                    await websocket.send_json({"type": "unsubscribed", "room": room})
                    logger.info(f"Client {websocket.client} unsubscribed from room: {room}")
                
                elif message_type == "start_updates":
                    await websocket.send_json({"type": "updates_started", "message": "Realtime updates started"})
                    logger.info(f"Client {websocket.client} started updates")
                
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "Invalid JSON"})
            except Exception as e:
                logger.error(f"Error handling WebSocket message: {e}", exc_info=True)
                await websocket.send_json({"type": "error", "message": str(e)})
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        manager.disconnect(websocket)


# リアルタイム更新タスク
update_task: asyncio.Task = None


async def start_realtime_updates():
    """リアルタイム更新タスクを開始"""
    global update_task
    
    if update_task and not update_task.done():
        return
    
    async def update_loop():
        """更新ループ"""
        while True:
            try:
                # システム状態をブロードキャスト
                await broadcast_system_status()
                
                # 新しいログをブロードキャスト
                await broadcast_new_logs()
                
                await asyncio.sleep(5)  # 5秒ごとに更新
            except Exception as e:
                logger.error(f"Error in realtime update loop: {e}", exc_info=True)
                await asyncio.sleep(10)
    
    update_task = asyncio.create_task(update_loop())
    logger.info("Realtime update task started")


def stop_realtime_updates():
    """リアルタイム更新タスクを停止"""
    global update_task
    if update_task and not update_task.done():
        update_task.cancel()
        logger.info("Realtime update task stopped")


async def broadcast_system_status():
    """システム状態をブロードキャスト"""
    try:
        with get_session() as session:
            account_repo = AccountRepository(session)
            
            total_accounts = account_repo.count()
            active_accounts = account_repo.get_active_accounts()
            active_count = len(active_accounts)
            
            # 状態別カウント
            status_counts = {}
            for status in AccountStatus:
                count = session.query(Account).filter_by(
                    status=status.value,
                    is_active=True
                ).count()
                status_counts[status.value] = count
            
            await manager.broadcast_to_room({
                "type": "system:status",
                "total_accounts": total_accounts,
                "active_accounts": active_count,
                "status_counts": status_counts,
                "timestamp": datetime.utcnow().isoformat()
            }, room="dashboard")
    except Exception as e:
        logger.error(f"Error broadcasting system status: {e}", exc_info=True)


async def broadcast_new_logs():
    """新しいログをブロードキャスト"""
    try:
        with get_session() as session:
            log_repo = AccountLogRepository(session)
            logs = log_repo.get_recent_logs(limit=10)
            
            logs_data = []
            for log in logs:
                logs_data.append({
                    'id': str(log.id),
                    'account_id': str(log.account_id),
                    'action_type': log.action_type,
                    'status': log.status,
                    'message': log.message,
                    'created_at': log.created_at.isoformat() if log.created_at else None
                })
            
            await manager.broadcast_to_room({
                "type": "log:new",
                "logs": logs_data,
                "timestamp": datetime.utcnow().isoformat()
            }, room="dashboard")
    except Exception as e:
        logger.error(f"Error broadcasting new logs: {e}", exc_info=True)


async def broadcast_account_update(account_id: str):
    """アカウント更新をブロードキャスト"""
    try:
        with get_session() as session:
            account_repo = AccountRepository(session)
            account = account_repo.get_by_id(account_id)
            
            if account:
                await manager.broadcast_to_room({
                    "type": "account:update",
                    "account_id": account_id,
                    "status": account.status,
                    "updated_at": account.updated_at.isoformat() if account.updated_at else None
                }, room="dashboard")
    except Exception as e:
        logger.error(f"Error broadcasting account update: {e}", exc_info=True)


async def broadcast_notification(notification: dict):
    """
    Chrome拡張機能に通知をブロードキャスト
    
    Args:
        notification: 通知データ
    """
    try:
        await manager.broadcast_to_room({
            "type": "notification",
            **notification
        }, room="notifications")
        logger.debug(f"Notification broadcasted to Chrome extension: {notification.get('title', 'N/A')}")
    except Exception as e:
        logger.error(f"Error broadcasting notification to Chrome extension: {e}", exc_info=True)


async def websocket_notifications_endpoint(websocket: WebSocket):
    """Chrome拡張機能用のWebSocketエンドポイント"""
    await websocket.accept()
    manager.active_connections.append(websocket)
    manager.rooms["notifications"].add(websocket)
    logger.info(f"Chrome extension connected: {websocket.client}")
    
    try:
        await websocket.send_json({
            "type": "connected",
            "message": "Connected to notification server",
            "timestamp": datetime.utcnow().isoformat()
        })
        
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                message_type = message.get("type")
                
                if message_type == "register":
                    await websocket.send_json({
                        "type": "registered",
                        "message": "Chrome extension registered successfully",
                        "timestamp": datetime.utcnow().isoformat()
                    })
                    logger.info(f"Chrome extension registered: {message.get('client', 'unknown')}")
                
                elif message_type == "ping":
                    await websocket.send_json({
                        "type": "pong",
                        "timestamp": datetime.utcnow().isoformat()
                    })
                
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "message": "Invalid JSON"})
            except Exception as e:
                logger.error(f"Error handling WebSocket message: {e}", exc_info=True)
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info("Chrome extension disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        manager.disconnect(websocket)



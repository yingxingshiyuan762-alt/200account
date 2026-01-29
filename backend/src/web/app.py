"""
FastAPI Web Application

Shinchakun自動化システムのWeb UIバックエンド
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

from config.config import settings
from src.core.logger import logger

# データベース接続の初期化（最初に実行）
from src.database.startup import initialize_database_connection
logger.info("Initializing database connection...")
try:
    db_initialized = initialize_database_connection()
    if not db_initialized:
        logger.warning("Database connection initialization failed, but continuing...")
except Exception as e:
    logger.error(f"Database initialization error: {e}", exc_info=True)
    logger.warning("Continuing without database connection...")

# ライフサイクル管理
from contextlib import asynccontextmanager

# スケジューラー、状態監視、通知のインポート
from src.monitoring.scheduler import TaskScheduler
from src.monitoring.status_monitor import StatusMonitor
from src.monitoring.notifier import notifier, setup_notifier_event_subscription

# グローバルインスタンス
scheduler = TaskScheduler()
status_monitor = StatusMonitor()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """アプリケーションのライフサイクル管理"""
    # 起動時
    from src.web.api.websocket import start_realtime_updates
    await start_realtime_updates()
    
    # パッチシステムの読み込み
    from src.patch import patch_manager
    logger.info("Loading patches...")
    try:
        patches = patch_manager.load_patches()
        logger.info(f"Loaded {len(patches)} patches")
        
        # 自動実行可能な未実行パッチを確認
        pending = patch_manager.get_pending_patches()
        auto_pending = [p for p in pending if p.auto_execute]
        if auto_pending:
            logger.info(f"Found {len(auto_pending)} auto-executable pending patches")
    except Exception as e:
        logger.error(f"Failed to load patches: {e}", exc_info=True)
    
    # 通知機能のイベントサブスクリプションを設定
    setup_notifier_event_subscription()
    
    # 通知機能を開始
    await notifier.start()
    
    # スケジューラーを開始
    await scheduler.start()
    
    # 状態監視を開始
    await status_monitor.start()
    
    yield
    
    # 終了時
    await status_monitor.stop()
    await scheduler.stop()
    await notifier.stop()
    from src.web.api.websocket import stop_realtime_updates
    stop_realtime_updates()

# FastAPIアプリケーション初期化
app = FastAPI(
    title="200 Account Automation API",
    description="Shinchakun自動化システムのREST API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "http://localhost:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# APIルートの登録
from src.web.api import routes
app.include_router(routes.api_router, prefix="/api", tags=["API"])

# WebSocketハンドラの登録
from src.web.api.websocket import websocket_endpoint, websocket_notifications_endpoint
app.add_websocket_route("/ws", websocket_endpoint)
app.add_websocket_route("/ws/notifications", websocket_notifications_endpoint)

logger.info("FastAPI Web Application initialized")


def create_app():
    """アプリケーションファクトリー"""
    return app


if __name__ == '__main__':
    # 開発サーバー起動
    import uvicorn
    try:
        logger.info("=" * 60)
        logger.info("Starting FastAPI Server")
        logger.info("=" * 60)
        logger.info(f"Host: {settings.WEB_HOST}")
        logger.info(f"Port: {settings.WEB_PORT}")
        logger.info(f"Backend API: http://localhost:{settings.WEB_PORT}/api/system/status")
        logger.info(f"API Docs: http://localhost:{settings.WEB_PORT}/docs")
        logger.info(f"Frontend: http://localhost:3000")
        logger.info("=" * 60)
        logger.info("Server is starting...")
        logger.info("Press Ctrl+C to stop the server")
        logger.info("=" * 60)
        
        uvicorn.run(
            "src.web.app:app",
            host=settings.WEB_HOST,
            port=settings.WEB_PORT,
            reload=settings.DEBUG,
            log_level="info" if not settings.DEBUG else "debug"
        )
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Failed to start server: {e}", exc_info=True)
        raise

"""
Application Entry Point

FastAPIアプリケーションのエントリーポイント
このファイルからアプリケーションを起動します。
"""
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

if __name__ == '__main__':
    import uvicorn
    from config.config import settings
    
    print("=" * 60)
    print("Starting FastAPI Server")
    print("=" * 60)
    print(f"Host: {settings.WEB_HOST}")
    print(f"Port: {settings.WEB_PORT}")
    print(f"Backend API: http://localhost:{settings.WEB_PORT}/api/system/status")
    print(f"API Docs: http://localhost:{settings.WEB_PORT}/docs")
    print("Frontend: http://localhost:8080")
    print("=" * 60)
    print("Server is starting...")
    print("Press Ctrl+C to stop the server")
    print("=" * 60)
    
    uvicorn.run(
        "src.web.app:app",
        host=settings.WEB_HOST,
        port=settings.WEB_PORT,
        reload=settings.DEBUG,
        log_level="info" if not settings.DEBUG else "debug"
    )


"""
設定管理モジュール
環境変数と設定ファイルを管理
"""
import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """アプリケーション設定"""
    
    # 基本設定
    PROJECT_ROOT: Path = Path(__file__).parent.parent
    DEBUG: bool = Field(default=False, env="DEBUG")
    
    # データベース設定 (MySQL - XAMPP)
    DATABASE_URL: str = Field(
        default="mysql+pymysql://root@localhost:3306/200account?charset=utf8mb4",
        env="DATABASE_URL"
    )
    DB_POOL_SIZE: int = Field(default=10, env="DB_POOL_SIZE")
    DB_MAX_OVERFLOW: int = Field(default=20, env="DB_MAX_OVERFLOW")
    DB_POOL_TIMEOUT: int = Field(default=30, env="DB_POOL_TIMEOUT")
    
    # 暗号化設定
    ENCRYPTION_KEY: Optional[str] = Field(
        default=None,
        env="ENCRYPTION_KEY"
    )
    
    # Web管理画面設定
    WEB_HOST: str = Field(default="0.0.0.0", env="WEB_HOST")
    WEB_PORT: int = Field(default=5000, env="WEB_PORT")
    SECRET_KEY: str = Field(
        default="change-this-secret-key-in-production",
        env="SECRET_KEY"
    )
    
    # 対象サービスURL
    SERVICE_BASE_URL: str = "https://shinchakun.net/"
    LOGIN_URLS: list[str] = [
        "https://doors1.shinchakun.info/dokodemo/#/",
        "https://doors2.shinchakun.info/dokodemo/#/"
    ]
    
    # スケジュール設定
    SCHEDULE_UPDATE_START_HOUR: int = 7
    SCHEDULE_UPDATE_END_HOUR: int = 10
    WAIT_RECEPTION_INTERVAL_MIN: int = 60
    WAIT_RECEPTION_INTERVAL_MAX: int = 90
    MIN_ATTENDANCE_CAST: int = 3
    CLOCK_OUT_BUFFER_MINUTES: int = 10
    
    # 状態監視設定
    STATUS_MONITOR_INTERVAL: int = Field(default=300, env="STATUS_MONITOR_INTERVAL")  # デフォルト5分（秒）
    
    # 通知設定
    NOTIFICATION_COOLDOWN_MINUTES: int = Field(default=12, env="NOTIFICATION_COOLDOWN_MINUTES")  # クールダウン期間（分）
    NOTIFICATION_EMAILS: str = Field(default="", env="NOTIFICATION_EMAILS")  # 受信者メールアドレス（カンマ区切り）
    
    @property
    def notification_email_list(self) -> list[str]:
        """メールアドレスをリストに変換"""
        if not self.NOTIFICATION_EMAILS:
            return []
        # カンマ区切りで分割してトリム
        return [email.strip() for email in self.NOTIFICATION_EMAILS.split(',') if email.strip()]
    
    # SMTP設定
    SMTP_HOST: str = Field(default="smtp.gmail.com", env="SMTP_HOST")
    SMTP_PORT: int = Field(default=587, env="SMTP_PORT")
    SMTP_USE_TLS: bool = Field(default=True, env="SMTP_USE_TLS")
    SMTP_USERNAME: str = Field(default="", env="SMTP_USERNAME")
    SMTP_PASSWORD: str = Field(default="", env="SMTP_PASSWORD")
    SMTP_FROM_EMAIL: str = Field(default="", env="SMTP_FROM_EMAIL")
    
    # ブラウザ設定
    BROWSER_HEADLESS: bool = Field(default=True, env="BROWSER_HEADLESS")
    BROWSER_TIMEOUT: int = 30000  # ミリ秒
    BROWSER_WAIT_TIMEOUT: int = 10000
    
    # セッション管理
    SESSION_CHECK_INTERVAL: int = 5  # 秒
    MANUAL_OPERATION_DETECTION_WINDOW: int = 30  # 秒
    
    # ログ設定
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")
    LOG_DIR: Path = PROJECT_ROOT / "logs"
    LOG_MAX_SIZE: int = 10 * 1024 * 1024  # 10MB
    LOG_BACKUP_COUNT: int = 5
    
    # エラー通知設定
    NOTIFICATION_ENABLED: bool = Field(default=True, env="NOTIFICATION_ENABLED")
    CHROME_EXTENSION_ID: Optional[str] = Field(
        default=None,
        env="CHROME_EXTENSION_ID"
    )
    
    # 並列処理設定
    MAX_CONCURRENT_ACCOUNTS: int = 10
    ACCOUNT_PROCESSING_TIMEOUT: int = 300  # 秒
    
    # パッチ管理
    PATCH_DIR: Path = PROJECT_ROOT / "patches"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# グローバル設定インスタンス
settings = Settings()

# ディレクトリの自動作成
settings.LOG_DIR.mkdir(parents=True, exist_ok=True)
settings.PATCH_DIR.mkdir(parents=True, exist_ok=True)
# Only create database directory for SQLite (not for MySQL/PostgreSQL)
if settings.DATABASE_URL.startswith("sqlite:///"):
    Path(settings.DATABASE_URL.replace("sqlite:///", "")).parent.mkdir(parents=True, exist_ok=True)


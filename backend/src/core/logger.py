"""
Core Logger Module

マルチハンドラー対応のロガーシステム
"""
import sys
import logging
from pathlib import Path
from datetime import datetime
from logging.handlers import RotatingFileHandler
import colorlog

from config.config import settings


def setup_logger(name: str = "automation") -> logging.Logger:
    """
    ロガーをセットアップ
    
    構成:
    1. Console Handler (INFO+, カラー表示)
    2. General File Handler (DEBUG+, ローテーション)
    3. Error File Handler (ERROR+, ローテーション)
    
    Args:
        name: ロガー名
    
    Returns:
        logging.Logger: 設定済みロガー
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)  # 全レベル受付
    logger.handlers.clear()  # 既存ハンドラークリア
    
    # ═══ Handler 1: Console (Colored) ═══
    console_handler = colorlog.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    
    console_formatter = colorlog.ColoredFormatter(
        "%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        log_colors={
            "DEBUG": "cyan",
            "INFO": "green",
            "WARNING": "yellow",
            "ERROR": "red",
            "CRITICAL": "red,bg_white",
        }
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # ═══ Handler 2: General File ═══
    date = datetime.now().strftime("%Y-%m-%d")
    log_file = settings.LOG_DIR / f"{name}_{date}.log"
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=settings.LOG_MAX_SIZE,
        backupCount=settings.LOG_BACKUP_COUNT,
        encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    
    file_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - "
        "%(funcName)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    
    # ═══ Handler 3: Error File ═══
    error_log_file = settings.LOG_DIR / f"error_{date}.log"
    error_handler = RotatingFileHandler(
        error_log_file,
        maxBytes=settings.LOG_MAX_SIZE,
        backupCount=settings.LOG_BACKUP_COUNT,
        encoding="utf-8"
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(file_formatter)
    logger.addHandler(error_handler)
    
    return logger


# グローバルロガー
logger = setup_logger("automation")


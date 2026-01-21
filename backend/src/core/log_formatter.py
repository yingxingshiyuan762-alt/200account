"""
Log Formatter Module

ログフォーマッター（JSON、構造化、コンテキスト付き）
"""
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from contextlib import contextmanager


class JSONFormatter(logging.Formatter):
    """
    JSON形式のログフォーマッター
    
    ログ集約ツール(ELK, Splunk)での解析用
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """ログレコードをJSON形式にフォーマット"""
        log_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }
        
        # 例外情報
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        # カスタム属性（extra）
        if hasattr(record, 'account_id'):
            log_data['account_id'] = record.account_id
        
        if hasattr(record, 'request_id'):
            log_data['request_id'] = record.request_id
        
        if hasattr(record, 'execution_time'):
            log_data['execution_time'] = record.execution_time
        
        if hasattr(record, 'event_type'):
            log_data['event_type'] = record.event_type
        
        return json.dumps(log_data, ensure_ascii=False)


class StructuredFormatter(logging.Formatter):
    """
    構造化ログフォーマッター
    
    人間が読みやすく、機械的にも解析しやすい
    """
    
    def __init__(self, include_context: bool = True):
        super().__init__()
        self.include_context = include_context
    
    def format(self, record: logging.LogRecord) -> str:
        """構造化形式にフォーマット"""
        parts = [
            f"[{self.formatTime(record, '%Y-%m-%d %H:%M:%S')}]",
            f"[{record.levelname}]",
            f"[{record.name}]",
            f"{record.getMessage()}"
        ]
        
        # コンテキスト情報
        if self.include_context:
            context_parts = []
            
            if hasattr(record, 'account_id'):
                context_parts.append(f"account={record.account_id}")
            
            if hasattr(record, 'request_id'):
                context_parts.append(f"request={record.request_id}")
            
            if hasattr(record, 'execution_time'):
                context_parts.append(f"time={record.execution_time:.3f}s")
            
            if context_parts:
                parts.append(f"[{', '.join(context_parts)}]")
        
        # 位置情報
        parts.append(f"({record.funcName}:{record.lineno})")
        
        return " ".join(parts)


class LogContext:
    """
    ログコンテキストマネージャー
    
    コンテキスト情報を自動付加
    
    使用例:
        with LogContext(logger, account_id="123", request_id="req-456") as log:
            log.info("Processing account")
            # → 自動的に account_id と request_id が付加される
    """
    
    def __init__(
        self,
        logger: logging.Logger,
        account_id: str = None,
        request_id: str = None,
        **kwargs
    ):
        self.logger = logger
        self.context = {}
        
        if account_id:
            self.context['account_id'] = account_id
        
        if request_id:
            self.context['request_id'] = request_id
        
        self.context.update(kwargs)
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass
    
    def debug(self, message: str, **kwargs):
        """DEBUGレベルログ"""
        extra = self.context.copy()
        extra.update(kwargs)
        self.logger.debug(message, extra=extra)
    
    def info(self, message: str, **kwargs):
        """INFOレベルログ"""
        extra = self.context.copy()
        extra.update(kwargs)
        self.logger.info(message, extra=extra)
    
    def warning(self, message: str, **kwargs):
        """WARNINGレベルログ"""
        extra = self.context.copy()
        extra.update(kwargs)
        self.logger.warning(message, extra=extra)
    
    def error(self, message: str, **kwargs):
        """ERRORレベルログ"""
        extra = self.context.copy()
        extra.update(kwargs)
        self.logger.error(message, extra=extra)
    
    def critical(self, message: str, **kwargs):
        """CRITICALレベルログ"""
        extra = self.context.copy()
        extra.update(kwargs)
        self.logger.critical(message, extra=extra)


def format_execution_time(seconds: float) -> str:
    """
    実行時間を人間が読みやすい形式にフォーマット
    
    例:
        0.001234 → "1.23ms"
        1.234 → "1.23s"
        65.5 → "1m 5.50s"
    """
    if seconds < 0.001:
        return f"{seconds * 1000000:.2f}µs"
    elif seconds < 1:
        return f"{seconds * 1000:.2f}ms"
    elif seconds < 60:
        return f"{seconds:.2f}s"
    else:
        minutes = int(seconds / 60)
        remaining_seconds = seconds % 60
        return f"{minutes}m {remaining_seconds:.2f}s"


def format_file_size(bytes_size: int) -> str:
    """
    ファイルサイズを人間が読みやすい形式にフォーマット
    
    例:
        1024 → "1.00 KB"
        1048576 → "1.00 MB"
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.2f} PB"


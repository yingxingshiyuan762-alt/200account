"""
Core Package

コア機能（ロガー、例外、イベントシステム、復旧システム）を提供します。
"""
from src.core.logger import logger, setup_logger
from src.core.log_formatter import (
    JSONFormatter,
    StructuredFormatter,
    LogContext as LogFormatterContext,
    format_execution_time,
    format_file_size,
)
from src.core.log_analyzer import LogAnalyzer, analyze_latest_log
from src.core.event_system import (
    EventType,
    EventSeverity,
    SystemEvent,
    EventLogger,
    event_logger,
)
# Lazy imports to avoid circular dependency
# from src.core.recovery_manager import (
#     RecoveryStrategy,
#     RecoveryManager,
#     recovery_manager,
# )
# from src.core.account_state_recovery import (
#     AccountState,
#     AccountStateRecovery,
#     account_state_recovery,
# )
# Lazy import to avoid circular dependency
# from src.core.log_manager import (
#     LogManager,
#     LogContext,
#     log_manager,
# )
from src.core.exceptions import (
    AutomationError,
    SessionConflictError,
    LoginError,
    AppCrashError,
    ManualOperationDetectedError,
    NetworkError,
    TimeoutError,
    DatabaseError,
    ConfigurationError,
)

__all__ = [
    # Logger
    'logger',
    'setup_logger',
    
    # Log Formatter
    'JSONFormatter',
    'StructuredFormatter',
    'LogFormatterContext',
    'format_execution_time',
    'format_file_size',
    
    # Log Analyzer
    'LogAnalyzer',
    'analyze_latest_log',
    
    # Event System
    'EventType',
    'EventSeverity',
    'SystemEvent',
    'EventLogger',
    'event_logger',
    
    # Recovery Manager (lazy import - use: from src.core.recovery_manager import ...)
    # 'RecoveryStrategy',
    # 'RecoveryManager',
    # 'recovery_manager',
    
    # Account State Recovery (lazy import - use: from src.core.account_state_recovery import ...)
    # 'AccountState',
    # 'AccountStateRecovery',
    # 'account_state_recovery',
    
    # Log Manager (lazy import - use: from src.core.log_manager import ...)
    # 'LogManager',
    # 'LogContext',
    # 'log_manager',
    
    # Exceptions
    'AutomationError',
    'SessionConflictError',
    'LoginError',
    'AppCrashError',
    'ManualOperationDetectedError',
    'NetworkError',
    'TimeoutError',
    'DatabaseError',
    'ConfigurationError',
]


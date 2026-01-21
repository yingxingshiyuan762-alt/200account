"""
Custom Exceptions

カスタム例外クラス
"""


class AutomationError(Exception):
    """自動化エラーの基底クラス"""
    pass


class SessionConflictError(AutomationError):
    """セッション競合エラー"""
    pass


class LoginError(AutomationError):
    """ログインエラー"""
    pass


class AppCrashError(AutomationError):
    """アプリケーションクラッシュエラー"""
    pass


class ManualOperationDetectedError(AutomationError):
    """手動操作検知エラー"""
    pass


class NetworkError(AutomationError):
    """ネットワークエラー"""
    pass


class TimeoutError(AutomationError):
    """タイムアウトエラー"""
    pass


class DatabaseError(AutomationError):
    """データベースエラー"""
    pass


class ConfigurationError(AutomationError):
    """設定エラー"""
    pass


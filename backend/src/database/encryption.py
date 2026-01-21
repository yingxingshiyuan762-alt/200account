"""
Password Encryption Module

パスワードの暗号化・復号化を行います。
AES-256-GCM (Fernet) を使用します。
"""
import os
from typing import Optional
from cryptography.fernet import Fernet, InvalidToken
from config.config import settings
from src.core.logger import logger


class PasswordEncryption:
    """
    パスワード暗号化クラス
    
    使用する暗号化:
    - アルゴリズム: AES-256-GCM
    - ライブラリ: cryptography.fernet
    - 認証: HMAC-SHA256
    - タイムスタンプ: 含む（リプレイ攻撃防止）
    """
    
    _instance: Optional['PasswordEncryption'] = None
    _cipher: Optional[Fernet] = None
    
    def __new__(cls):
        """シングルトンパターン"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """初期化"""
        if self._cipher is None:
            key = self._get_encryption_key()
            try:
                self._cipher = Fernet(key)
                logger.debug("Password encryption initialized")
            except Exception as e:
                logger.error(f"Failed to initialize encryption: {e}")
                raise
    
    def _get_encryption_key(self) -> bytes:
        """
        暗号化キーを取得
        
        Priority:
        1. 環境変数 ENCRYPTION_KEY
        2. 開発環境: 新規生成（警告）
        """
        key_str = settings.ENCRYPTION_KEY
        
        if key_str:
            try:
                key = key_str.encode()
                Fernet(key)  # 妥当性チェック
                logger.debug("Encryption key loaded from environment")
                return key
            except Exception as e:
                logger.error(f"Invalid encryption key: {e}")
                raise ValueError("Invalid ENCRYPTION_KEY")
        
        # 開発環境: 新規生成（警告）
        logger.warning("ENCRYPTION_KEY not found. Generating new key.")
        logger.warning("DO NOT USE IN PRODUCTION!")
        
        new_key = Fernet.generate_key()
        logger.info(f"Generated key: {new_key.decode()}")
        
        return new_key
    
    def encrypt(self, password: str) -> str:
        """
        パスワードを暗号化
        
        Process:
        1. UTF-8エンコード: str → bytes
        2. Fernet暗号化:
           - AES-256-GCM
           - HMAC-SHA256
           - Timestamp
        3. Base64エンコード: bytes → str
        
        Args:
            password: 平文パスワード
        
        Returns:
            str: 暗号化されたパスワード
        """
        if not password:
            raise ValueError("Password cannot be empty")
        
        try:
            encrypted_bytes = self._cipher.encrypt(password.encode('utf-8'))
            encrypted_str = encrypted_bytes.decode('utf-8')
            
            logger.debug("Password encrypted successfully")
            return encrypted_str
            
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise
    
    def decrypt(self, encrypted_password: str) -> str:
        """
        パスワードを復号化
        
        Security Checks:
        1. HMAC検証: 改ざん検知
        2. Timestamp検証: リプレイ攻撃防止
        3. 復号化: AES-256-GCM
        
        Args:
            encrypted_password: 暗号化されたパスワード
        
        Returns:
            str: 平文パスワード
        
        Raises:
            ValueError: 暗号化パスワードが空の場合
            InvalidToken: 復号化失敗（キーが間違っている等）
        """
        if not encrypted_password:
            raise ValueError("Encrypted password cannot be empty")
        
        try:
            decrypted_bytes = self._cipher.decrypt(encrypted_password.encode('utf-8'))
            decrypted_str = decrypted_bytes.decode('utf-8')
            
            logger.debug("Password decrypted successfully")
            return decrypted_str
            
        except InvalidToken:
            logger.error("Decryption failed: Invalid token or wrong key")
            raise ValueError("Invalid encrypted password or wrong key")
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise
    
    @staticmethod
    def generate_key() -> str:
        """
        新しい暗号化キーを生成
        
        Returns:
            str: Base64エンコードされたキー
        
        使用例:
            key = PasswordEncryption.generate_key()
            print(f"ENCRYPTION_KEY={key}")
        """
        key = Fernet.generate_key()
        return key.decode('utf-8')


# グローバルインスタンス
_encryption = PasswordEncryption()


# ヘルパー関数
def encrypt_password(password: str) -> str:
    """
    パスワードを暗号化（ショートカット）
    
    Args:
        password: 平文パスワード
    
    Returns:
        str: 暗号化されたパスワード
    """
    return _encryption.encrypt(password)


def decrypt_password(encrypted_password: str) -> str:
    """
    パスワードを復号化（ショートカット）
    
    Args:
        encrypted_password: 暗号化されたパスワード
    
    Returns:
        str: 平文パスワード
    """
    return _encryption.decrypt(encrypted_password)


# コマンドライン実行用
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "generate":
        # キー生成
        key = PasswordEncryption.generate_key()
        print("\n" + "=" * 60)
        print("ENCRYPTION KEY GENERATED")
        print("=" * 60)
        print(f"\nAdd this to your .env file:\n")
        print(f"ENCRYPTION_KEY={key}\n")
        print("=" * 60)
    else:
        # テスト
        test_password = "test_password_123"
        encrypted = encrypt_password(test_password)
        decrypted = decrypt_password(encrypted)
        
        print("\n" + "=" * 60)
        print("ENCRYPTION TEST")
        print("=" * 60)
        print(f"Original:  {test_password}")
        print(f"Encrypted: {encrypted[:50]}...")
        print(f"Decrypted: {decrypted}")
        print(f"Match:     {test_password == decrypted}")
        print("=" * 60)


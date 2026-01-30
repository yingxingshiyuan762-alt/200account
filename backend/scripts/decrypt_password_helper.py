"""
Password Decryption Helper

This script demonstrates how to decrypt passwords when needed.
Passwords are encrypted in the database for security, but can be
decrypted using the encryption key from .env
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.config import settings
from src.database.connection import get_session
from src.database.models import Account
from cryptography.fernet import Fernet
import json


def decrypt_password(encrypted_password: str) -> str:
    """
    パスワードを復号化
    
    Args:
        encrypted_password: 暗号化されたパスワード
    
    Returns:
        str: 復号化されたパスワード（元のテキスト）
    """
    try:
        cipher = Fernet(settings.ENCRYPTION_KEY.encode())
        decrypted = cipher.decrypt(encrypted_password.encode())
        return decrypted.decode()
    except Exception as e:
        return f"[Decryption Error: {e}]"


def show_account_with_decrypted_password(username: str = None, numeric_id: int = None):
    """
    アカウント情報を表示（復号化されたパスワード付き）
    
    Args:
        username: ユーザー名で検索
        numeric_id: 数値IDで検索
    """
    with get_session() as session:
        if username:
            account = session.query(Account).filter_by(username=username).first()
        elif numeric_id:
            # メタデータから検索
            accounts = session.query(Account).all()
            account = None
            for acc in accounts:
                if acc.metadata_json:
                    try:
                        metadata = json.loads(acc.metadata_json)
                        if metadata.get('numeric_id') == numeric_id:
                            account = acc
                            break
                    except:
                        pass
        else:
            print("Error: Provide either username or numeric_id")
            return
        
        if not account:
            print(f"Account not found")
            return
        
        # メタデータ取得
        numeric_id_value = "N/A"
        if account.metadata_json:
            try:
                metadata = json.loads(account.metadata_json)
                numeric_id_value = metadata.get('numeric_id', 'N/A')
            except:
                pass
        
        # パスワード復号化
        decrypted_password = decrypt_password(account.password_encrypted)
        
        print("\n" + "=" * 80)
        print(f"Account Information")
        print("=" * 80)
        print(f"Numeric ID:        {numeric_id_value}")
        print(f"Username:          {account.username}")
        print(f"Password (plain):  {decrypted_password}")
        print(f"Password (encrypted): {account.password_encrypted[:50]}...")
        print(f"Store Name:        {account.store_name or '(blank)'}")
        print(f"Login URL:         {account.login_url or '(blank)'}")
        print(f"Active:            {'Yes (1)' if account.is_active else 'No (0)'}")
        print(f"Session Token:     {account.session_token[:30] + '...' if account.session_token else '(empty)'}")
        print(f"Last Login:        {account.last_login_at or '(never)'}")
        print("=" * 80)


def list_all_accounts_with_passwords(show_passwords: bool = False):
    """
    全アカウントをリスト表示
    
    Args:
        show_passwords: Trueの場合、復号化されたパスワードも表示
    """
    with get_session() as session:
        accounts = session.query(Account).all()
        
        # 数値IDでソート
        ordered = []
        for account in accounts:
            numeric_id = 0
            if account.metadata_json:
                try:
                    metadata = json.loads(account.metadata_json)
                    numeric_id = metadata.get('numeric_id', 0)
                except:
                    pass
            
            ordered.append({
                'numeric_id': numeric_id,
                'account': account
            })
        
        ordered.sort(key=lambda x: x['numeric_id'])
        
        print("\n" + "=" * 80)
        print(f"All Accounts ({len(ordered)} total)")
        print("=" * 80)
        
        for item in ordered:
            acc = item['account']
            numeric_id = item['numeric_id']
            
            if show_passwords:
                password = decrypt_password(acc.password_encrypted)
                print(f"ID {numeric_id:3d}. {acc.username:25s} | Pass: {password:15s} | Active: {1 if acc.is_active else 0}")
            else:
                print(f"ID {numeric_id:3d}. {acc.username:25s} | Active: {1 if acc.is_active else 0}")


def main():
    """メイン処理"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Decrypt and view account passwords')
    parser.add_argument('--username', type=str, help='Username to lookup')
    parser.add_argument('--id', type=int, help='Numeric ID to lookup')
    parser.add_argument('--list', action='store_true', help='List all accounts')
    parser.add_argument('--show-passwords', action='store_true', help='Show decrypted passwords in list')
    
    args = parser.parse_args()
    
    if args.list:
        list_all_accounts_with_passwords(show_passwords=args.show_passwords)
    elif args.username or args.id:
        show_account_with_decrypted_password(username=args.username, numeric_id=args.id)
    else:
        print("Usage:")
        print("  python decrypt_password_helper.py --username inpon_hmm")
        print("  python decrypt_password_helper.py --id 1")
        print("  python decrypt_password_helper.py --list")
        print("  python decrypt_password_helper.py --list --show-passwords")


if __name__ == "__main__":
    main()

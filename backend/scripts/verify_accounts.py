"""
Verify Account Data

データベース内のアカウント数を確認します。
"""
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.database.connection import get_session, ensure_connection
from src.database.repositories.account import AccountRepository
from src.database.models import AccountStatus
from src.core.logger import logger, setup_logger

logger = setup_logger("verify_accounts")


def verify_accounts():
    """アカウントデータを確認"""
    try:
        if not ensure_connection():
            logger.error("Failed to establish database connection")
            return False
        
        with get_session() as session:
            account_repo = AccountRepository(session)
            
            total = account_repo.count()
            active_accounts = account_repo.get_active_accounts()
            active_count = len(active_accounts)
            
            # ステータス別カウント
            from src.database.models import Account
            status_counts = {}
            for status in AccountStatus:
                count = session.query(Account).filter_by(
                    status=status.value,
                    is_active=True
                ).count()
                if count > 0:
                    status_counts[status.value] = count
            
            print("\n" + "=" * 60)
            print("ACCOUNT VERIFICATION")
            print("=" * 60)
            print(f"Total accounts: {total}")
            print(f"Active accounts: {active_count}")
            print("\nStatus breakdown:")
            for status, count in status_counts.items():
                print(f"  {status}: {count}")
            print("=" * 60)
            
            # 最初の5件を表示
            if total > 0:
                print("\nFirst 5 accounts:")
                accounts = session.query(Account).limit(5).all()
                for acc in accounts:
                    try:
                        print(f"  - {acc.username} ({acc.store_name}) - {acc.status}")
                    except UnicodeEncodeError:
                        # Windows console encoding fallback
                        print(f"  - {acc.username} ({acc.store_name.encode('utf-8', errors='replace').decode('utf-8', errors='replace')}) - {acc.status}")
            
            return True
            
    except Exception as e:
        logger.error(f"Verification failed: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    verify_accounts()


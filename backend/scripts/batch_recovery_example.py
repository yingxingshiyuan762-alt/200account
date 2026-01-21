"""
200アカウント一括復旧スクリプト

使用例:
    python scripts/batch_recovery_example.py --strategy LAST_SUCCESS_RECOVERY --filter ERROR
"""
import sys
import argparse
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.database.startup import initialize_database_connection
from src.core import log_manager
from src.core.recovery_manager import RecoveryStrategy
from src.database.models import AccountStatus


def main():
    parser = argparse.ArgumentParser(description='200アカウント一括復旧')
    parser.add_argument(
        '--strategy',
        type=str,
        default='LAST_SUCCESS_RECOVERY',
        choices=['LAST_SUCCESS_RECOVERY', 'STATUS_RECOVERY', 'FULL_RECOVERY', 'PARTIAL_RECOVERY'],
        help='復旧戦略'
    )
    parser.add_argument(
        '--filter',
        type=str,
        default='ERROR',
        choices=['ERROR', 'IDLE', 'PROCESSING', 'DISABLED', 'ALL'],
        help='復旧対象のステータス（ALLの場合は全アカウント）'
    )
    parser.add_argument(
        '--workers',
        type=int,
        default=10,
        help='最大並列処理数'
    )
    
    args = parser.parse_args()
    
    # データベース接続初期化
    print("データベース接続を初期化しています...")
    initialize_database_connection()
    print("データベース接続が確立されました\n")
    
    # 復旧戦略を取得
    strategy = RecoveryStrategy(args.strategy)
    
    # フィルタステータスを取得
    if args.filter == 'ALL':
        filter_status = None
    else:
        filter_status = AccountStatus(args.filter)
    
    print(f"復旧設定:")
    print(f"  戦略: {strategy.value}")
    print(f"  フィルタ: {args.filter}")
    print(f"  並列数: {args.workers}")
    print()
    
    # 一括復旧実行
    print("一括復旧を開始します...")
    result = log_manager.batch_recover_all_accounts(
        strategy=strategy,
        filter_status=filter_status,
        max_workers=args.workers
    )
    
    # 結果表示
    print("\n" + "="*60)
    print("復旧結果")
    print("="*60)
    print(f"総数: {result['total']}")
    print(f"成功: {result['success']}")
    print(f"失敗: {result['failed']}")
    print(f"実行時間: {result['execution_time']:.2f}秒")
    
    if result['success'] > 0:
        print(f"\n復旧成功アカウント:")
        for account in result['recovered_accounts'][:10]:  # 最初の10件
            print(f"  - {account['username']}: {account['recovered_fields']}")
        if len(result['recovered_accounts']) > 10:
            print(f"  ... 他 {len(result['recovered_accounts']) - 10} 件")
    
    if result['failed'] > 0:
        print(f"\n復旧失敗アカウント:")
        for account in result['failed_accounts'][:10]:  # 最初の10件
            print(f"  - {account['username']}: {account['errors']}")
        if len(result['failed_accounts']) > 10:
            print(f"  ... 他 {len(result['failed_accounts']) - 10} 件")
    
    print("\n" + "="*60)


if __name__ == '__main__':
    main()


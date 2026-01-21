"""
ログ分析スクリプト

使用例:
    python scripts/log_analysis_example.py --account-id <uuid> --days 7
    python scripts/log_analysis_example.py --system --days 30
"""
import sys
import argparse
import json
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.database.startup import initialize_database_connection
from src.core import log_manager


def format_percentage(value: float) -> str:
    """パーセンテージをフォーマット"""
    return f"{value * 100:.2f}%"


def print_account_summary(summary: dict):
    """アカウントログサマリーを表示"""
    print("\n" + "="*60)
    print("アカウントログサマリー")
    print("="*60)
    print(f"アカウントID: {summary['account_id']}")
    print(f"期間: {summary['period']['days']}日間")
    print(f"  {summary['period']['start']} ～ {summary['period']['end']}")
    
    stats = summary['statistics']
    print(f"\n統計:")
    print(f"  総ログ数: {stats['total_logs']}")
    print(f"  成功数: {stats['success_count']}")
    print(f"  失敗数: {stats['failure_count']}")
    print(f"  成功率: {format_percentage(stats['success_rate'])}")
    
    if stats['action_counts']:
        print(f"\n操作種別:")
        for action, count in stats['action_counts'].items():
            print(f"  {action}: {count}")
    
    if summary.get('last_success_login'):
        login = summary['last_success_login']
        print(f"\n最後のログイン成功:")
        print(f"  日時: {login['created_at']}")
        if login.get('execution_time'):
            print(f"  実行時間: {login['execution_time']:.2f}秒")
        if login.get('message'):
            print(f"  メッセージ: {login['message']}")
    
    print("="*60)


def print_system_statistics(stats: dict):
    """システム統計を表示"""
    print("\n" + "="*60)
    print("システム全体統計")
    print("="*60)
    print(f"期間: {stats['period']['days']}日間")
    print(f"  {stats['period']['start']} ～ {stats['period']['end']}")
    
    accounts = stats['accounts']
    print(f"\nアカウント:")
    print(f"  総数: {accounts['total']}")
    print(f"  アクティブ: {accounts['active']}")
    print(f"  非アクティブ: {accounts['inactive']}")
    
    statistics = stats['statistics']
    print(f"\n統計:")
    print(f"  総ログ数: {statistics['total_logs']}")
    print(f"  成功数: {statistics['success_count']}")
    print(f"  失敗数: {statistics['failure_count']}")
    print(f"  成功率: {format_percentage(statistics['success_rate'])}")
    print(f"  ログがあるアカウント: {statistics['accounts_with_logs']}")
    
    if stats.get('high_error_accounts'):
        print(f"\n高エラー率アカウント (Top 10):")
        for account in stats['high_error_accounts']:
            print(f"  {account['account_id']}: "
                  f"エラー率 {format_percentage(account['error_rate'])} "
                  f"({account['failure_count']}/{account['total_logs']})")
    
    print("="*60)


def main():
    parser = argparse.ArgumentParser(description='ログ分析')
    parser.add_argument(
        '--account-id',
        type=str,
        help='アカウントID（指定時はアカウント別レポート）'
    )
    parser.add_argument(
        '--system',
        action='store_true',
        help='システム全体の統計を表示'
    )
    parser.add_argument(
        '--days',
        type=int,
        default=7,
        help='取得期間（日数）'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='JSON形式で出力'
    )
    
    args = parser.parse_args()
    
    if not args.account_id and not args.system:
        parser.error('--account-id または --system のいずれかを指定してください')
    
    # データベース接続初期化
    print("データベース接続を初期化しています...")
    initialize_database_connection()
    print("データベース接続が確立されました\n")
    
    if args.account_id:
        # アカウント別レポート
        print(f"アカウント {args.account_id} のログを分析しています...")
        summary = log_manager.get_account_log_summary(
            account_id=args.account_id,
            days=args.days
        )
        
        if 'error' in summary:
            print(f"エラー: {summary['error']}")
            return
        
        if args.json:
            print(json.dumps(summary, indent=2, ensure_ascii=False, default=str))
        else:
            print_account_summary(summary)
    
    if args.system:
        # システム全体レポート
        print(f"システム全体のログを分析しています...")
        stats = log_manager.get_system_statistics(days=args.days)
        
        if 'error' in stats:
            print(f"エラー: {stats['error']}")
            return
        
        if args.json:
            print(json.dumps(stats, indent=2, ensure_ascii=False, default=str))
        else:
            print_system_statistics(stats)


if __name__ == '__main__':
    main()


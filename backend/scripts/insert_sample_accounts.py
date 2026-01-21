"""
Sample Account Data Insertion Script

データベースに200件のサンプルアカウントデータを挿入します。
"""
import sys
import os
from pathlib import Path

# プロジェクトルートをパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import random
from datetime import datetime, timedelta
from src.database.connection import get_session, ensure_connection
from src.database.repositories.account import AccountRepository
from src.database.models import AccountStatus
from src.core.logger import logger, setup_logger

# ロガー設定
logger = setup_logger("insert_accounts")

# 東京の駅名・地名リスト（店名として使用）
STORE_NAMES = [
    '新宿店', '渋谷店', '池袋店', '上野店', '品川店', '東京店', '銀座店',
    '六本木店', '表参道店', '原宿店', '青山店', '赤坂店', '恵比寿店',
    '目黒店', '五反田店', '大崎店', '田町店', '浜松町店', '新橋店',
    '有楽町店', '神田店', '秋葉原店', '御徒町店', '鶯谷店', '日暮里店',
    '西日暮里店', '千駄木店', '根津店', '本郷三丁目店', '湯島店',
    '新大塚店', '茗荷谷店', '後楽園店', '水道橋店', '飯田橋店',
    '市ヶ谷店', '四ッ谷店', '新宿御苑前店', '新宿三丁目店', '新宿西口店',
    '代々木店', '代々木公園店', '明治神宮前店', '北参道店', '参宮橋店',
    '代々木上原店', '東北沢店', '下北沢店', '世田谷代田店', '経堂店',
    '豪徳寺店', '宮の坂店', '山下店', '梅ヶ丘店', '給田店', '仙川店',
    'つつじヶ丘店', '調布店', '西調布店', '飛田給店', '武蔵野台店',
    '多摩境店', '稲城長沼店', '若葉台店', '橋本站前店', '南橋本店',
    '片倉店', '八王子みなみ野店', '狭間店', '高尾店', '相模湖店',
    '藤野店', '上野原店', '四方津店', '梁川店', '鳥沢店',
    '猿橋店', '大月店', '都留文科大学前店', '谷村町店', '都留市役所前店',
    '東桂店', '禾生店', '勝沼ぶどう郷店', '笹子店', '甲斐大和店',
    '甲斐小泉店', '甲斐上野店', '甲斐住吉店', '甲斐大津店', '甲斐常葉店',
    '甲斐上九一色店', '甲斐下九一色店', '甲斐上沢店', '甲斐下沢店',
    '甲斐上大鳥居店', '甲斐下大鳥居店', '甲斐上黒駒店', '甲斐下黒駒店',
    '甲斐上黒駒北店', '甲斐下黒駒北店', '甲斐上黒駒南店', '甲斐下黒駒南店',
    '甲斐上黒駒東店', '甲斐下黒駒東店', '甲斐上黒駒西店', '甲斐下黒駒西店',
    '甲斐上黒駒中央店', '甲斐下黒駒中央店', '甲斐上黒駒新店', '甲斐下黒駒新店',
    '横浜店', '川崎店', '武蔵小杉店', '新百合ヶ丘店', '登戸店',
    '向ヶ丘遊園店', '生田店', '読売ランド前店', '百合ヶ丘店', '新宿店',
    '渋谷店', '池袋店', '上野店', '品川店', '東京店', '銀座店',
    '六本木店', '表参道店', '原宿店', '青山店', '赤坂店', '恵比寿店',
    '目黒店', '五反田店', '大崎店', '田町店', '浜松町店', '新橋店',
    '有楽町店', '神田店', '秋葉原店', '御徒町店', '鶯谷店', '日暮里店',
    '西日暮里店', '千駄木店', '根津店', '本郷三丁目店', '湯島店',
    '新大塚店', '茗荷谷店', '後楽園店', '水道橋店', '飯田橋店',
    '市ヶ谷店', '四ッ谷店', '新宿御苑前店', '新宿三丁目店', '新宿西口店',
    '代々木店', '代々木公園店', '明治神宮前店', '北参道店', '参宮橋店',
]

# ログインURLリスト
LOGIN_URLS = [
    "https://doors1.shinchakun.info/dokodemo/#/",
    "https://doors2.shinchakun.info/dokodemo/#/"
]


def generate_username(index: int) -> str:
    """
    ユーザー名を生成
    
    Args:
        index: アカウントインデックス（1-200）
    
    Returns:
        str: ユーザー名（例: szo22_25794）
    """
    # 既存の命名規則に従って生成
    base_number = 25700 + index
    return f"szo22_{base_number}"


def generate_password() -> str:
    """
    ランダムなパスワードを生成
    
    Returns:
        str: パスワード
    """
    # 8-16文字のランダムなパスワード
    length = random.randint(8, 16)
    chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*"
    return ''.join(random.choice(chars) for _ in range(length))


def generate_store_name(index: int) -> str:
    """
    店名を生成
    
    Args:
        index: アカウントインデックス
    
    Returns:
        str: 店名
    """
    # 重複を避けるために、インデックスを使用して選択
    store_index = index % len(STORE_NAMES)
    base_name = STORE_NAMES[store_index]
    
    # 同じ店名が複数ある場合、番号を付ける
    if index >= len(STORE_NAMES):
        duplicate_num = (index // len(STORE_NAMES)) + 1
        return f"{base_name} ({duplicate_num})"
    
    return base_name


def generate_login_url() -> str:
    """
    ログインURLをランダムに選択
    
    Returns:
        str: ログインURL
    """
    return random.choice(LOGIN_URLS)


def insert_accounts(count: int = 200):
    """
    サンプルアカウントをデータベースに挿入
    
    Args:
        count: 挿入するアカウント数（デフォルト: 200）
    """
    logger.info("=" * 60)
    logger.info("SAMPLE ACCOUNT INSERTION")
    logger.info("=" * 60)
    logger.info(f"Target: {count} accounts")
    
    try:
        # データベース接続確認
        logger.info("\nStep 1: Checking database connection...")
        if not ensure_connection():
            logger.error("Failed to establish database connection")
            return False
        logger.info("Database connection established")
        
        # セッション取得
        logger.info("\nStep 2: Creating accounts...")
        with get_session() as session:
            account_repo = AccountRepository(session)
            
            # 既存のアカウント数を確認
            existing_count = account_repo.count()
            logger.info(f"Existing accounts: {existing_count}")
            
            # アカウントを作成
            created_count = 0
            skipped_count = 0
            
            for i in range(1, count + 1):
                username = generate_username(i)
                
                # 既存のアカウントをチェック
                existing_account = account_repo.get_by_username(username)
                if existing_account:
                    logger.warning(f"Account {username} already exists, skipping...")
                    skipped_count += 1
                    continue
                
                # アカウント作成
                try:
                    account = account_repo.create_account(
                        username=username,
                        password=generate_password(),
                        store_name=generate_store_name(i),
                        login_url=generate_login_url(),
                        is_active=True
                    )
                    
                    created_count += 1
                    if created_count % 20 == 0:
                        logger.info(f"Created {created_count}/{count} accounts...")
                        
                except Exception as e:
                    logger.error(f"Failed to create account {username}: {e}")
                    skipped_count += 1
                    continue
            
            # コミット
            session.commit()
            
            logger.info("\n" + "=" * 60)
            logger.info("INSERTION COMPLETE")
            logger.info("=" * 60)
            logger.info(f"Created: {created_count} accounts")
            logger.info(f"Skipped: {skipped_count} accounts")
            logger.info(f"Total in database: {account_repo.count()} accounts")
            logger.info("=" * 60)
            
            return True
            
    except Exception as e:
        logger.error(f"Failed to insert accounts: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Insert sample accounts into the database")
    parser.add_argument(
        "--count",
        type=int,
        default=200,
        help="Number of accounts to insert (default: 200)"
    )
    
    args = parser.parse_args()
    
    success = insert_accounts(args.count)
    
    if success:
        logger.info("\nAccount insertion completed successfully!")
        sys.exit(0)
    else:
        logger.error("\nAccount insertion failed!")
        sys.exit(1)


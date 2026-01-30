"""
Test Login and Extraction (First 5 Accounts)

Test the login process with just the first 5 accounts to verify:
- Login works correctly
- Store name extraction works
- Session token extraction works
- Database updates correctly
"""
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import the main bulk login script functions
from bulk_login_and_extract import (
    get_accounts_ordered,
    process_account,
    logger
)
from playwright.sync_api import sync_playwright
import time


def main():
    """テスト実行 - 最初の5アカウントのみ"""
    print("=" * 80)
    print("TEST MODE: Processing First 5 Accounts Only")
    print("=" * 80)
    print("\nThis will:")
    print("  1. Login to the first 5 accounts")
    print("  2. Extract store names and sessions")
    print("  3. Update database")
    print("  4. Logout")
    print("\nExpected time: 1-2 minutes")
    print("=" * 80)
    
    # Auto-proceed (no confirmation needed for automation)
    print("\nAuto-proceeding with test...")
    logger.info("Starting test in automated mode")
    
    stats = {
        'success': 0,
        'failed': 0,
        'total': 5
    }
    
    try:
        # 最初の5アカウントを取得
        all_accounts = get_accounts_ordered()
        test_accounts = all_accounts[:5]
        
        logger.info(f"\nTesting with first 5 accounts:")
        for i, acc in enumerate(test_accounts, 1):
            logger.info(f"  {i}. {acc.username}")
        
        # Playwrightを起動
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=False,  # 可視モード
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox'
                ]
            )
            
            # 各アカウントを処理
            for i, account in enumerate(test_accounts, 1):
                logger.info(f"\n[Test {i}/5]")
                success = process_account(account, playwright, browser, stats)
                time.sleep(2)  # レート制限対策
            
            browser.close()
        
        # 結果
        print("\n" + "=" * 80)
        print("TEST COMPLETED")
        print("=" * 80)
        print(f"Successful:  {stats['success']}/5")
        print(f"Failed:      {stats['failed']}/5")
        
        if stats['success'] == 5:
            print("\n✓ All test accounts processed successfully!")
            print("\nYou can now run the full script:")
            print("  python scripts/bulk_login_and_extract.py")
        elif stats['success'] > 0:
            print(f"\n⚠ Partial success ({stats['success']}/5)")
            print("Review the logs and fix issues before running full script")
        else:
            print("\n✗ Test failed - please review errors and fix before proceeding")
        
        print("=" * 80)
    
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()

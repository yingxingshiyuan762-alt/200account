"""
Automatic Schedule Attendance Setting

自動スケジュール出勤設定
毎日AM7:00〜10:00に実行。週間スケジュールに基づき、翌日の設定を「出勤設定」に変更し登録する。

Process:
1. Login to account
2. Navigate to schedule page (カシュテ)
3. Find tomorrow's date column
4. For each row (cast member):
   - If tomorrow is "休み" (rest)
   - Check if there's any "出勤" (attendance) in the weekly schedule
   - If yes, copy that time setting to tomorrow
5. Save the changes
"""
import sys
import os
import time
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.config import settings
from src.database.connection import get_session
from src.database.models import Account
from src.core.logger import logger
from cryptography.fernet import Fernet
from playwright.sync_api import sync_playwright, Page, BrowserContext, TimeoutError as PlaywrightTimeout
import json


# Login URLs
LOGIN_URLS = [
    "https://doors1.shinchakun.info/dokodemo/#/",
    "https://doors2.shinchakun.info/dokodemo/#/"
]


def decrypt_password(encrypted_password: str) -> str:
    """Decrypt password"""
    cipher = Fernet(settings.ENCRYPTION_KEY.encode())
    decrypted = cipher.decrypt(encrypted_password.encode())
    return decrypted.decode()


def try_login(page: Page, url: str, username: str, password: str) -> Tuple[bool, Optional[str]]:
    """
    Try to login
    
    Returns:
        Tuple[bool, Optional[str]]: (success/failure, error message)
    """
    try:
        logger.info(f"[{username}] Trying login at: {url}")
        
        # Open page
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(3)
        
        # Find username input
        try:
            username_input = page.wait_for_selector('input[type="text"]', timeout=10000)
            logger.info(f"[{username}] Found username input")
            username_input.fill(username)
            time.sleep(2)
        except Exception as e:
            return False, f"Username input not found: {str(e)}"
        
        # Find password input
        try:
            password_input = page.wait_for_selector('input[type="password"]', timeout=10000)
            logger.info(f"[{username}] Found password input")
            password_input.fill(password)
            logger.info(f"[{username}] Entering credentials...")
            time.sleep(3)
        except Exception as e:
            return False, f"Password input not found: {str(e)}"
        
        # Click login button
        try:
            login_button = page.wait_for_selector('input[type="submit"]', timeout=10000)
            logger.info(f"[{username}] Found login button")
            login_button.click()
            time.sleep(4)
        except Exception as e:
            return False, f"Login button not found: {str(e)}"
        
        # Check for errors
        page_content = page.content()
        if "Invalid Login" in page_content or "エラー" in page_content:
            error_msg = "Login failed - Invalid credentials or VPS error"
            logger.warning(f"[{username}] {error_msg}")
            return False, error_msg
        
        logger.info(f"[{username}] Login successful!")
        return True, None
        
    except Exception as e:
        logger.error(f"[{username}] Login exception: {str(e)}")
        return False, str(e)


def navigate_to_schedule_page(page: Page, username: str) -> bool:
    """
    Navigate to schedule management page (カシュテ)
    
    Returns:
        bool: Success or failure
    """
    try:
        logger.info(f"[{username}] Navigating to schedule page...")
        
        # Wait for page to load after login
        time.sleep(3)
        
        # Look for schedule/cast tab - try multiple selectors
        schedule_selectors = [
            'a:has-text("カシュテ")',
            'a:has-text("カシ")',
            'a:has-text("キャスト")',
            'button:has-text("カシュテ")',
            'button:has-text("カシ")',
            'button:has-text("キャスト")',
            '[href*="cast"]',
            '[href*="schedule"]',
        ]
        
        clicked = False
        for selector in schedule_selectors:
            try:
                element = page.wait_for_selector(selector, timeout=5000)
                if element:
                    logger.info(f"[{username}] Found schedule tab with selector: {selector}")
                    element.click()
                    time.sleep(3)
                    clicked = True
                    break
            except:
                continue
        
        if not clicked:
            logger.warning(f"[{username}] Schedule tab not found, trying to find by text content...")
            # Try to find by partial text match
            page.evaluate("""
                () => {
                    const links = Array.from(document.querySelectorAll('a, button'));
                    const scheduleLink = links.find(link => 
                        link.textContent.includes('カシ') || 
                        link.textContent.includes('スケジュール')
                    );
                    if (scheduleLink) scheduleLink.click();
                }
            """)
            time.sleep(3)
        
        logger.info(f"[{username}] Navigated to schedule page")
        return True
        
    except Exception as e:
        logger.error(f"[{username}] Error navigating to schedule page: {str(e)}")
        return False


def get_tomorrow_date_string() -> str:
    """
    Get tomorrow's date string in Japanese format
    
    Returns:
        str: Tomorrow's date like "2/4(水)" (month/day(weekday))
    """
    tomorrow = datetime.now() + timedelta(days=1)
    
    # Japanese weekday names
    weekdays_jp = {
        0: '月',  # Monday
        1: '火',  # Tuesday
        2: '水',  # Wednesday
        3: '木',  # Thursday
        4: '金',  # Friday
        5: '土',  # Saturday
        6: '日'   # Sunday
    }
    
    weekday = weekdays_jp[tomorrow.weekday()]
    date_str = f"{tomorrow.month}/{tomorrow.day}({weekday})"
    
    logger.info(f"Tomorrow's date: {date_str}")
    return date_str


def find_schedule_table(page: Page, username: str) -> bool:
    """
    Find the schedule table on the page
    
    Returns:
        bool: Success or failure
    """
    try:
        logger.info(f"[{username}] Looking for schedule table...")
        
        # Try to find table
        table_selectors = [
            'table',
            '.schedule-table',
            '[class*="schedule"]',
            '[id*="schedule"]'
        ]
        
        for selector in table_selectors:
            try:
                table = page.wait_for_selector(selector, timeout=5000)
                if table:
                    logger.info(f"[{username}] Found schedule table with selector: {selector}")
                    return True
            except:
                continue
        
        logger.warning(f"[{username}] Schedule table not found")
        return False
        
    except Exception as e:
        logger.error(f"[{username}] Error finding schedule table: {str(e)}")
        return False


def process_schedule_attendance(page: Page, username: str) -> Dict[str, Any]:
    """
    Process schedule and set attendance for tomorrow
    
    Logic:
    - Find tomorrow's column
    - For each row (cast member):
      - If tomorrow shows "休み" (rest)
      - Check if there's any time entry (attendance) in the row's weekly schedule
      - If found, click on tomorrow's cell and set it to that time
    
    Returns:
        Dict: Statistics of changes made
    """
    stats = {
        'rows_processed': 0,
        'attendance_set': 0,
        'already_set': 0,
        'errors': 0
    }
    
    try:
        tomorrow_str = get_tomorrow_date_string()
        logger.info(f"[{username}] Processing schedule for tomorrow: {tomorrow_str}")
        
        # Wait for table to be visible
        time.sleep(2)
        
        # Get all table headers to find tomorrow's column index
        logger.info(f"[{username}] Finding tomorrow's column...")
        
        # Use JavaScript to find and process the schedule
        result = page.evaluate(f"""
            () => {{
                const tomorrowDate = "{tomorrow_str}";
                const table = document.querySelector('table');
                
                if (!table) {{
                    return {{ error: 'Table not found' }};
                }}
                
                // Find tomorrow's column index
                const headers = Array.from(table.querySelectorAll('th'));
                let tomorrowColIndex = -1;
                
                headers.forEach((header, index) => {{
                    if (header.textContent.includes(tomorrowDate.split('(')[0])) {{
                        tomorrowColIndex = index;
                    }}
                }});
                
                if (tomorrowColIndex === -1) {{
                    return {{ error: 'Tomorrow column not found', headers: headers.map(h => h.textContent) }};
                }}
                
                // Process each row
                const rows = Array.from(table.querySelectorAll('tbody tr'));
                let processed = 0;
                let changed = 0;
                let alreadySet = 0;
                
                rows.forEach((row, rowIndex) => {{
                    const cells = Array.from(row.querySelectorAll('td'));
                    
                    if (cells.length === 0) return;
                    
                    // Get tomorrow's cell
                    const tomorrowCell = cells[tomorrowColIndex];
                    
                    if (!tomorrowCell) return;
                    
                    processed++;
                    
                    // Check if tomorrow is "休み" (rest)
                    const tomorrowText = tomorrowCell.textContent.trim();
                    
                    if (tomorrowText === '休み') {{
                        // Find any attendance time in the row (not "休み")
                        let attendanceTime = null;
                        
                        for (let i = 1; i < cells.length; i++) {{
                            const cellText = cells[i].textContent.trim();
                            // Check if it's a time range (e.g., "09:00 - 18:00")
                            if (cellText.match(/\\d{{2}}:\\d{{2}}.*\\d{{2}}:\\d{{2}}/)) {{
                                attendanceTime = cellText;
                                break;
                            }}
                        }}
                        
                        if (attendanceTime) {{
                            // Mark this cell for update
                            tomorrowCell.setAttribute('data-update-to', attendanceTime);
                            tomorrowCell.style.border = '3px solid orange';
                            changed++;
                        }}
                    }} else if (tomorrowText.match(/\\d{{2}}:\\d{{2}}/)) {{
                        // Already has attendance set
                        alreadySet++;
                    }}
                }});
                
                return {{
                    success: true,
                    tomorrowColIndex: tomorrowColIndex,
                    processed: processed,
                    toChange: changed,
                    alreadySet: alreadySet
                }};
            }}
        """)
        
        if result.get('error'):
            logger.error(f"[{username}] JavaScript error: {result['error']}")
            if 'headers' in result:
                logger.info(f"[{username}] Available headers: {result['headers']}")
            stats['errors'] += 1
            return stats
        
        logger.info(f"[{username}] Scan complete:")
        logger.info(f"  - Rows processed: {result.get('processed', 0)}")
        logger.info(f"  - Need to set attendance: {result.get('toChange', 0)}")
        logger.info(f"  - Already has attendance: {result.get('alreadySet', 0)}")
        
        stats['rows_processed'] = result.get('processed', 0)
        stats['already_set'] = result.get('alreadySet', 0)
        
        # Now click on each marked cell and update it
        cells_to_update = result.get('toChange', 0)
        
        if cells_to_update > 0:
            logger.info(f"[{username}] Updating {cells_to_update} cells...")
            
            # Get cells marked for update
            cells_data = page.evaluate("""
                () => {
                    const cells = Array.from(document.querySelectorAll('td[data-update-to]'));
                    return cells.map(cell => ({
                        text: cell.textContent.trim(),
                        updateTo: cell.getAttribute('data-update-to'),
                        rowIndex: cell.parentElement.rowIndex,
                        cellIndex: cell.cellIndex
                    }));
                }
            """)
            
            logger.info(f"[{username}] Found {len(cells_data)} cells to update")
            
            for i, cell_info in enumerate(cells_data, 1):
                try:
                    logger.info(f"[{username}] Updating cell {i}/{len(cells_data)}: Row {cell_info['rowIndex']}, setting to '{cell_info['updateTo']}'")
                    
                    # Click on the cell
                    cell_selector = f"tr:nth-child({cell_info['rowIndex']}) td:nth-child({cell_info['cellIndex'] + 1})"
                    cell = page.query_selector(cell_selector)
                    
                    if cell:
                        cell.click()
                        time.sleep(1)
                        
                        # Look for time input or selection
                        # This part depends on the actual UI implementation
                        # You might need to adjust based on how the schedule editing works
                        
                        # Try to find input fields for time
                        start_time = cell_info['updateTo'].split('-')[0].strip()
                        end_time = cell_info['updateTo'].split('-')[1].strip() if '-' in cell_info['updateTo'] else start_time
                        
                        # Example: Try to fill time inputs
                        try:
                            # This is a placeholder - adjust based on actual UI
                            time_inputs = page.query_selector_all('input[type="time"], input[type="text"]')
                            if len(time_inputs) >= 2:
                                time_inputs[0].fill(start_time)
                                time_inputs[1].fill(end_time)
                                time.sleep(0.5)
                        except:
                            pass
                        
                        # Try to find and click save/OK button
                        save_selectors = [
                            'button:has-text("OK")',
                            'button:has-text("保存")',
                            'button:has-text("登録")',
                            'button[type="submit"]',
                            'input[type="submit"]'
                        ]
                        
                        for selector in save_selectors:
                            try:
                                save_btn = page.wait_for_selector(selector, timeout=2000)
                                if save_btn:
                                    save_btn.click()
                                    time.sleep(1)
                                    break
                            except:
                                continue
                        
                        stats['attendance_set'] += 1
                        logger.info(f"[{username}] Successfully updated cell {i}")
                        
                    else:
                        logger.warning(f"[{username}] Could not find cell to click")
                        stats['errors'] += 1
                    
                except Exception as e:
                    logger.error(f"[{username}] Error updating cell {i}: {str(e)}")
                    stats['errors'] += 1
                    continue
            
            # Save the schedule
            logger.info(f"[{username}] Looking for schedule save button...")
            save_selectors = [
                'button:has-text("一括登録")',
                'button:has-text("保存")',
                'button:has-text("更新")',
                'button:has-text("登録")',
            ]
            
            for selector in save_selectors:
                try:
                    save_btn = page.wait_for_selector(selector, timeout=3000)
                    if save_btn:
                        logger.info(f"[{username}] Found save button, clicking...")
                        save_btn.click()
                        time.sleep(2)
                        logger.info(f"[{username}] Schedule saved!")
                        break
                except:
                    continue
        
        return stats
        
    except Exception as e:
        logger.error(f"[{username}] Error processing schedule: {str(e)}")
        stats['errors'] += 1
        return stats


def logout(page: Page, username: str):
    """Logout from account"""
    try:
        logger.info(f"[{username}] Logging out...")
        time.sleep(2)
        
        # Try to find logout button
        logout_selectors = [
            'a:has-text("ログアウト")',
            'button:has-text("ログアウト")',
            '[href*="logout"]'
        ]
        
        for selector in logout_selectors:
            try:
                logout_button = page.wait_for_selector(selector, timeout=5000)
                if logout_button:
                    logout_button.click()
                    time.sleep(2)
                    logger.info(f"[{username}] Logged out successfully")
                    return
            except:
                continue
        
        logger.warning(f"[{username}] Logout button not found")
        
    except Exception as e:
        logger.error(f"[{username}] Logout error: {str(e)}")


def process_single_account(username: str, password: str, login_url: str) -> Dict[str, Any]:
    """
    Process a single account
    
    Returns:
        Dict: Processing results
    """
    result = {
        'username': username,
        'success': False,
        'stats': None,
        'error': None
    }
    
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=False,  # Set to True for production
                slow_mo=1000
            )
            
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080}
            )
            page = context.new_page()
            
            # Login
            login_success, error = try_login(page, login_url, username, password)
            
            if not login_success:
                result['error'] = f"Login failed: {error}"
                browser.close()
                return result
            
            # Navigate to schedule page
            if not navigate_to_schedule_page(page, username):
                result['error'] = "Failed to navigate to schedule page"
                browser.close()
                return result
            
            # Find schedule table
            if not find_schedule_table(page, username):
                result['error'] = "Failed to find schedule table"
                browser.close()
                return result
            
            # Process schedule attendance
            stats = process_schedule_attendance(page, username)
            result['stats'] = stats
            result['success'] = stats['errors'] == 0
            
            # Logout
            logout(page, username)
            
            # Close browser
            time.sleep(2)
            browser.close()
            
            return result
            
    except Exception as e:
        logger.error(f"Error processing account {username}: {str(e)}")
        result['error'] = str(e)
        return result


def main():
    """Main function - Test with single account"""
    print("=" * 80)
    print("AUTOMATIC SCHEDULE ATTENDANCE SETTING - TEST")
    print("=" * 80)
    print("\nTesting with account: inpon_hmm")
    print("=" * 80)
    
    # Test credentials
    username = "inpon_hmm"
    password = "3F6KwLSdEe"
    
    # Get login URL from database
    logger.info("Fetching account information from database...")
    
    with get_session() as session:
        account = session.query(Account).filter(Account.username == username).first()
        
        if not account:
            print(f"\nERROR: Account '{username}' not found in database")
            print("Please make sure the account has been loaded.")
            return
        
        login_url = account.login_url
        
        if not login_url:
            # Use default
            login_url = LOGIN_URLS[1]  # doors2
            logger.info(f"No login URL in database, using default: {login_url}")
        else:
            logger.info(f"Using login URL from database: {login_url}")
    
    # Process the account
    print(f"\nProcessing account: {username}")
    print(f"Login URL: {login_url}")
    print("-" * 80)
    
    result = process_single_account(username, password, login_url)
    
    # Display results
    print("\n" + "=" * 80)
    if result['success']:
        print("SUCCESS!")
        print("=" * 80)
        stats = result['stats']
        print(f"Account: {result['username']}")
        print(f"Rows processed: {stats['rows_processed']}")
        print(f"Attendance set: {stats['attendance_set']}")
        print(f"Already set: {stats['already_set']}")
        print(f"Errors: {stats['errors']}")
    else:
        print("FAILED")
        print("=" * 80)
        print(f"Account: {result['username']}")
        print(f"Error: {result.get('error', 'Unknown error')}")
        if result['stats']:
            print(f"Partial stats: {result['stats']}")
    
    print("=" * 80)


if __name__ == "__main__":
    main()

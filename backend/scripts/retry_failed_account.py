"""
Retry Failed Account: shion_nmz02

This script retries login for the one account that failed due to VPS connection error.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.connection import db, get_session
from src.database.models import Account
from playwright.sync_api import sync_playwright
import time
from cryptography.fernet import Fernet
from config.config import settings
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("automation")

# Login URLs
LOGIN_URLS = [
    "https://doors1.shinchakun.info/dokodemo/#/",
    "https://doors2.shinchakun.info/dokodemo/#/"
]

def decrypt_password(encrypted_password: str) -> str:
    """Decrypt password"""
    cipher = Fernet(settings.ENCRYPTION_KEY.encode())
    return cipher.decrypt(encrypted_password.encode()).decode()


def try_login(page, url, username, password):
    """Try to login at a specific URL"""
    try:
        logger.info(f"[{username}] Trying login at: {url}")
        page.goto(url, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(3000)
        
        # Find and fill username
        username_input = page.wait_for_selector('input[type="text"]', timeout=10000)
        logger.info(f"[{username}] Found username input")
        username_input.fill(username)
        page.wait_for_timeout(3000)
        
        # Find and fill password
        password_input = page.wait_for_selector('input[type="password"]', timeout=10000)
        logger.info(f"[{username}] Found password input")
        password_input.fill(password)
        logger.info(f"[{username}] Entering credentials...")
        page.wait_for_timeout(4000)
        
        # Click login button
        login_button = page.wait_for_selector('input[type="submit"]', timeout=10000)
        logger.info(f"[{username}] Found login button")
        login_button.click()
        page.wait_for_timeout(3000)
        
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


def extract_store_name(page, username):
    """Extract store name from page"""
    try:
        logger.info(f"[{username}] Extracting store name...")
        page.wait_for_timeout(2000)
        
        # Try to find shop name element
        try:
            store_element = page.wait_for_selector('a.navbar-brand', timeout=5000)
            store_name = store_element.inner_text().strip()
            logger.info(f"[{username}] Found store name: {store_name}")
            return store_name
        except:
            logger.warning(f"[{username}] Could not find store name, using username")
            return username
            
    except Exception as e:
        logger.error(f"[{username}] Error extracting store name: {str(e)}")
        return username


def extract_session_token(page, context, username):
    """Extract session token from cookies"""
    try:
        logger.info(f"[{username}] Extracting session token...")
        cookies = context.cookies()
        
        for cookie in cookies:
            if cookie['name'] == 'JSESSIONID':
                logger.info(f"[{username}] Found session cookie: JSESSIONID")
                return cookie['value']
        
        logger.warning(f"[{username}] No JSESSIONID found")
        return None
        
    except Exception as e:
        logger.error(f"[{username}] Error extracting session token: {str(e)}")
        return None


def update_account_in_db(account_id, login_url, store_name, session_token):
    """Update account in database"""
    try:
        with get_session() as session:
            account = session.query(Account).filter(Account.id == account_id).first()
            
            if account:
                account.login_url = login_url
                account.store_name = store_name
                if session_token:
                    account.session_token = session_token
                account.is_active = True
                from datetime import datetime
                account.last_login_at = datetime.now()
                
                session.commit()
                logger.info(f"Updated account in database: {account.username}")
                return True
            else:
                logger.error(f"Account not found: {account_id}")
                return False
            
    except Exception as e:
        logger.error(f"Error updating database: {str(e)}")
        return False


def logout(page, username):
    """Logout from account"""
    try:
        logger.info(f"[{username}] Logging out...")
        # Wait a bit before logout
        page.wait_for_timeout(20000)
        
        # Try to find logout button
        try:
            logout_button = page.wait_for_selector('a:has-text("ログアウト")', timeout=5000)
            logout_button.click()
            page.wait_for_timeout(2000)
            logger.info(f"[{username}] Logged out successfully")
        except:
            logger.warning(f"[{username}] Logout button not found, clearing cookies instead")
            
    except Exception as e:
        logger.error(f"[{username}] Logout error: {str(e)}")


def main():
    """Retry failed account"""
    print("=" * 80)
    print("RETRY FAILED ACCOUNT: shion_nmz02")
    print("=" * 80)
    print("\nAttempting to login to the account that failed due to VPS error...")
    print("=" * 80)
    
    # Get the failed account
    with get_session() as session:
        account = session.query(Account).filter(Account.username == "shion_nmz02").first()
    
        if not account:
            print("\nERROR: Account 'shion_nmz02' not found in database")
            return
        
        account_id = account.id
        username = account.username
        encrypted_password = account.password_encrypted
        is_active = account.is_active
        login_url = account.login_url
        store_name = account.store_name
    
    print(f"\nFound account: {username}")
    print(f"Account ID: {account_id}")
    print(f"Current is_active: {is_active}")
    print(f"Current login_url: {login_url or 'None'}")
    print(f"Current store_name: {store_name or 'None'}")
    
    # Decrypt password
    plain_password = decrypt_password(encrypted_password)
    logger.info(f"[{username}] Password decrypted")
    
    # Start Playwright
    print("\nStarting browser...")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=False,
            slow_mo=1000
        )
        
        context = browser.new_context(
            viewport={'width': 1280, 'height': 720}
        )
        page = context.new_page()
        
        # Try both URLs
        success = False
        working_url = None
        
        for url in LOGIN_URLS:
            print(f"\nTrying: {url}")
            login_success, error = try_login(page, url, username, plain_password)
            
            if login_success:
                success = True
                working_url = url
                logger.info(f"[{username}] Login successful with: {url}")
                break
            else:
                logger.warning(f"[{username}] Login failed with {url}: {error}")
        
        if success:
            # Extract information
            extracted_store_name = extract_store_name(page, username)
            session_token = extract_session_token(page, context, username)
            
            # Update database
            update_success = update_account_in_db(
                account_id,
                working_url,
                extracted_store_name,
                session_token
            )
            
            if update_success:
                print("\n" + "=" * 80)
                print("SUCCESS!")
                print("=" * 80)
                print(f"Account: {username}")
                print(f"Login URL: {working_url}")
                print(f"Store Name: {extracted_store_name}")
                print(f"Session Token: {'Yes' if session_token else 'No'}")
                print(f"Status: Active")
                print("=" * 80)
            
            # Logout
            logout(page, username)
        else:
            print("\n" + "=" * 80)
            print("FAILED - Could not login with either URL")
            print("=" * 80)
            print("This account may have server-side issues.")
            print("Please contact shinchakun support or try again later.")
            print("=" * 80)
        
        # Close browser
        page.wait_for_timeout(2000)
        browser.close()


if __name__ == "__main__":
    main()

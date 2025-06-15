"""Test script for BVK login form extraction logic."""
import asyncio
import logging
import sys
import os
from bs4 import BeautifulSoup

# Add the parent directory to the path in case we need to import from the custom component
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the utility function for login form extraction
from custom_components.bvk.token_utils import extract_login_form

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
_LOGGER = logging.getLogger(__name__)

# Path to locally saved login page for testing
LOGIN_PAGE_FILE = os.path.join(os.path.dirname(__file__), "resources", "login_page.html")

async def test_login_form_extraction() -> bool:
    """Test the login form extraction from the local file."""
    _LOGGER.info("Starting login form extraction test")

    try:
        # Load the login page from the local file
        with open(LOGIN_PAGE_FILE, 'r', encoding='utf-8') as f:
            login_page = f.read()

        # Use the utility function to extract the login form
        login_form, username_field, password_field = extract_login_form(login_page, logger=_LOGGER)

        _LOGGER.info("Login form found successfully")
        _LOGGER.info(f"Username field name: {username_field.get('name')}")
        _LOGGER.info(f"Password field name: {password_field.get('name')}")

        return True
    except Exception as e:
        _LOGGER.error(f"Login form extraction test failed: {e}")
        return False

async def main() -> None:
    """Run the login form extraction test."""
    _LOGGER.info("Starting login form extraction test")

    # Test login form extraction from local file
    form_extraction_result = await test_login_form_extraction()
    _LOGGER.info(f"Login form extraction test {'passed' if form_extraction_result else 'failed'}")

    _LOGGER.info("Test completed")

if __name__ == "__main__":
    asyncio.run(main())

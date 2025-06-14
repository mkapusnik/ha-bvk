"""Test script for BVK login form extraction logic."""
import asyncio
import logging
import sys
import os
from bs4 import BeautifulSoup

# Add the parent directory to the path in case we need to import from the custom component
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
_LOGGER = logging.getLogger(__name__)

# Path to locally saved login page for testing
LOGIN_PAGE_FILE = os.path.join(os.path.dirname(__file__), "resources", "login_page.html")

async def test_login_form_extraction():
    """Test the login form extraction from the local file."""
    _LOGGER.info("Starting login form extraction test")

    try:
        # Load the login page from the local file
        with open(LOGIN_PAGE_FILE, 'r', encoding='utf-8') as f:
            login_page = f.read()

        # Parse the login page
        soup = BeautifulSoup(login_page, 'html.parser')

        # Find the login form
        login_form = soup.find('form', {'id': 'form1'})
        if not login_form:
            _LOGGER.debug("Form with id 'form1' not found, looking for alternative login forms")
            forms = soup.find_all('form')
            for form in forms:
                username_field = form.find('input', {'type': 'text'}) or form.find('input', {'type': 'email'})
                password_field = form.find('input', {'type': 'password'})
                if username_field and password_field:
                    login_form = form
                    break

        if not login_form:
            raise Exception("Login form not found")

        # Find form fields
        username_field = login_form.find('input', {'type': 'text'}) or login_form.find('input', {'type': 'email'})
        password_field = login_form.find('input', {'type': 'password'})

        if not username_field or not password_field:
            raise Exception("Username or password fields not found in the login form")

        _LOGGER.info("Login form found successfully")
        _LOGGER.info(f"Username field name: {username_field.get('name')}")
        _LOGGER.info(f"Password field name: {password_field.get('name')}")

        return True
    except Exception as e:
        _LOGGER.error(f"Login form extraction test failed: {e}")
        return False

async def main():
    """Run the login form extraction test."""
    _LOGGER.info("Starting login form extraction test")

    # Test login form extraction from local file
    form_extraction_result = await test_login_form_extraction()
    _LOGGER.info(f"Login form extraction test {'passed' if form_extraction_result else 'failed'}")

    _LOGGER.info("Test completed")

if __name__ == "__main__":
    asyncio.run(main())
"""Test script for BVK token extraction logic."""
import asyncio
import logging
import sys
import os
import aiohttp
from bs4 import BeautifulSoup
import re
from test_login_form import test_login_form_extraction

# Add the parent directory to the path in case we need to import from the custom component
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
_LOGGER = logging.getLogger(__name__)

# Constants
BVK_LOGIN_URL = "https://zis.bvk.cz/"
BVK_MAIN_INFO_URL = "https://zis.bvk.cz/Userdata/MainInfo.aspx"
BVK_TARGET_DOMAIN = "https://cz-sitr.suezsmartsolutions.com"
# Paths to locally saved pages for testing
LOGIN_PAGE_FILE = os.path.join(os.path.dirname(__file__), "resources", "login_page.html")
MAIN_INFO_PAGE_FILE = os.path.join(os.path.dirname(__file__), "resources", "main_info_page.html")

async def extract_token(username, password):
    """Extract authentication token from BVK website."""
    async with aiohttp.ClientSession() as session:
        try:
            # Step 1: Load the login page from local file
            _LOGGER.info("Loading login page from local file")

            # Read the login page from the local file
            with open(LOGIN_PAGE_FILE, 'r', encoding='utf-8') as f:
                login_page = f.read()

            # Parse the login page
            soup = BeautifulSoup(login_page, 'html.parser')

            _LOGGER.info("Testing login form extraction from local file")

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
            viewstate = soup.find('input', {'name': '__VIEWSTATE'})
            viewstategenerator = soup.find('input', {'name': '__VIEWSTATEGENERATOR'})
            eventvalidation = soup.find('input', {'name': '__EVENTVALIDATION'})

            username_field = login_form.find('input', {'type': 'text'}) or login_form.find('input', {'type': 'email'})
            password_field = login_form.find('input', {'type': 'password'})
            submit_button = login_form.find('input', {'type': 'submit'})

            if not username_field or not password_field:
                raise Exception("Username or password fields not found in the login form")

            # Prepare login data
            login_data = {}

            if viewstate:
                login_data['__VIEWSTATE'] = viewstate.get('value', '')
            if viewstategenerator:
                login_data['__VIEWSTATEGENERATOR'] = viewstategenerator.get('value', '')
            if eventvalidation:
                login_data['__EVENTVALIDATION'] = eventvalidation.get('value', '')

            login_data[username_field.get('name')] = username
            login_data[password_field.get('name')] = password

            if submit_button:
                login_data[submit_button.get('name')] = submit_button.get('value', 'Přihlásit')

            # Get form action URL
            form_action = login_form.get('action')
            login_submit_url = BVK_LOGIN_URL

            if form_action:
                if form_action.startswith('http'):
                    login_submit_url = form_action
                elif form_action.startswith('/'):
                    parsed_url = aiohttp.http.URL(BVK_LOGIN_URL)
                    login_submit_url = f"{parsed_url.scheme}://{parsed_url.host}{form_action}"
                else:
                    login_submit_url = BVK_LOGIN_URL.rstrip('/') + '/' + form_action.lstrip('/')

            _LOGGER.info(f"Submitting login form to: {login_submit_url}")

            # Submit login form
            login_post_response = await session.post(login_submit_url, data=login_data)

            # Check login success
            if login_post_response.status != 200:
                raise Exception(f"Login failed: HTTP status {login_post_response.status}")

            # Step 2: Load the main info page from local file
            _LOGGER.info("Loading main info page from local file")

            # Read the main info page from the local file
            with open(MAIN_INFO_PAGE_FILE, 'r', encoding='utf-8') as f:
                main_info_page = f.read()

            # Step 3: Find the token directly in the HTML
            _LOGGER.info("Searching for token directly in the HTML")

            # Define patterns to search for in the HTML
            token_patterns = [
                r'token=([^&"\']+)',  # Standard token format
                r'auth=([^&"\']+)',   # Alternative auth parameter
                r'jwt=([^&"\']+)',    # JWT token format
                r'access_token=([^&"\']+)'  # OAuth style token
            ]

            # Search for the token in the entire HTML
            token_match = None
            for pattern in token_patterns:
                matches = re.findall(pattern, main_info_page)
                if matches:
                    # Use the first match
                    token_match = re.search(pattern, main_info_page)
                    _LOGGER.info(f"Token found using pattern: {pattern}")
                    break

            if not token_match:
                # Try to find the specific link with class "LinkEmis" or ID containing "btnPortalEmis"
                soup = BeautifulSoup(main_info_page, 'html.parser')

                # Log all links for debugging
                all_links = soup.find_all('a', href=lambda href: href and href.strip())
                _LOGGER.info(f"Found {len(all_links)} links on the main info page")

                # Look for specific links that might contain the token
                links_with_token = []
                for link in all_links:
                    link_str = str(link)
                    if 'token=' in link_str:
                        links_with_token.append(link_str)

                if links_with_token:
                    _LOGGER.info(f"Found {len(links_with_token)} links containing 'token='")
                    # Extract the token from the first link
                    for pattern in token_patterns:
                        match = re.search(pattern, links_with_token[0])
                        if match:
                            token_match = match
                            _LOGGER.info(f"Token found in link using pattern: {pattern}")
                            break

                if not token_match:
                    # If still no token found, look for specific elements
                    links = soup.find_all('a', class_="LinkEmis")
                    if not links:
                        links = soup.find_all('a', id=lambda id: id and 'btnPortalEmis' in id)

                    if links:
                        _LOGGER.info(f"Found specific link, checking its HTML")
                        link_str = str(links[0])
                        for pattern in token_patterns:
                            match = re.search(pattern, link_str)
                            if match:
                                token_match = match
                                _LOGGER.info(f"Token found in specific link using pattern: {pattern}")
                                break

            if not token_match:
                # Log some page content for debugging
                _LOGGER.debug(f"Main info page HTML snippet: {main_info_page[:500]}...")
                raise Exception("Authentication token not found in page")

            token = token_match.group(1)
            _LOGGER.info(f"Successfully extracted token: {token[:5]}...")

            return token

        except Exception as e:
            _LOGGER.error(f"Error during token extraction: {e}")
            raise


async def main():
    """Run the token extraction test."""
    # Load credentials from .env file
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    username = None
    password = None

    # Read .env file manually
    try:
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    if key == "BVK_USERNAME":
                        username = value
                    elif key == "BVK_PASSWORD":
                        password = value
    except Exception as e:
        _LOGGER.error(f"Error reading .env file: {e}")
        username = "your_username"
        password = "your_password"

    if not username or not password or username == "your_username":
        _LOGGER.warning("Using default credentials. For real testing, update .env file.")

    _LOGGER.info("Starting tests")

    # Test login form extraction from local file (imported from test_login_form.py)
    form_extraction_result = await test_login_form_extraction()
    _LOGGER.info(f"Login form extraction test {'passed' if form_extraction_result else 'failed'}")

    # Run the token extraction test
    try:
        token = await extract_token(username, password)
        _LOGGER.info(f"Token extraction successful: {token[:10]}...")
    except Exception as e:
        _LOGGER.error(f"Token extraction failed: {e}")

    _LOGGER.info("Tests completed")

if __name__ == "__main__":
    asyncio.run(main())

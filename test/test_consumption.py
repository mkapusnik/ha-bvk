"""Simple test script for BVK API client."""
import asyncio
import logging
import sys
import os
import re
import aiohttp
from bs4 import BeautifulSoup
from pathlib import Path
from dotenv import load_dotenv
from typing import Optional, Tuple, Dict, Any

# Import the constants directly using importlib to avoid triggering __init__.py
import importlib.util
spec = importlib.util.spec_from_file_location(
    "const", 
    os.path.join(os.path.dirname(__file__), '..', 'custom_components', 'bvk', 'const.py')
)
const = importlib.util.module_from_spec(spec)
spec.loader.exec_module(const)

# Use the imported constants
BVK_LOGIN_URL = const.BVK_LOGIN_URL
BVK_MAIN_INFO_URL = const.BVK_MAIN_INFO_URL
BVK_TARGET_DOMAIN = const.BVK_TARGET_DOMAIN

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
_LOGGER = logging.getLogger(__name__)

# Define utility functions
def extract_login_form(html_content, logger=None) -> Tuple[Optional[BeautifulSoup], Optional[BeautifulSoup], Optional[BeautifulSoup]]:
    """Extract login form and its username/password fields from HTML content."""
    # Use provided logger or fallback to module logger
    log = logger or _LOGGER

    # Parse the HTML
    soup = BeautifulSoup(html_content, 'html.parser')

    # Find the login form - first try by ID, then by looking for forms with login fields
    login_form = soup.find('form', {'id': 'form1'})

    # If form1 not found, look for any form that has username and password fields
    if not login_form:
        log.debug("Form with id 'form1' not found, looking for alternative login forms")
        forms = soup.find_all('form')
        for form in forms:
            # Look for username and password fields in this form
            username_field = form.find('input', {'type': 'text'}) or form.find('input', {'type': 'email'})
            password_field = form.find('input', {'type': 'password'})

            if username_field and password_field:
                log.debug(f"Found potential login form with fields: {username_field.get('name')} and {password_field.get('name')}")
                login_form = form
                break

    if not login_form:
        raise Exception("Login form not found")

    # Find username and password field names
    username_field = login_form.find('input', {'type': 'text'}) or login_form.find('input', {'type': 'email'})
    password_field = login_form.find('input', {'type': 'password'})

    if not username_field or not password_field:
        raise Exception("Username or password fields not found in the login form")

    return login_form, username_field, password_field

def extract_token_from_html(html_content, logger=None):
    """Extract authentication token from HTML content."""
    # Use provided logger or fallback to module logger
    log = logger or _LOGGER

    # Define patterns to search for in the HTML
    token_patterns = [
        r'token=([^&"\']+)',  # Standard token format
        r'auth=([^&"\']+)',   # Alternative auth parameter
        r'jwt=([^&"\']+)',    # JWT token format
        r'access_token=([^&"\']+)'  # OAuth style token
    ]

    # Search for the token in the entire HTML first
    token_match = None
    for pattern in token_patterns:
        matches = re.findall(pattern, html_content)
        if matches:
            # Use the first match
            token_match = re.search(pattern, html_content)
            log.debug(f"Token found directly in HTML using pattern: {pattern}")
            break

    if not token_match:
        log.debug("Token not found directly in HTML, trying to find it in specific elements")
        soup = BeautifulSoup(html_content, 'html.parser')

        # Log all links on the page for debugging
        all_links = soup.find_all('a', href=lambda href: href and href.strip())
        log.debug(f"Found {len(all_links)} links on the page")

        # Look for links with token in href
        links_with_token = []
        for link in all_links:
            link_href = link.get('href', '')
            if any(re.search(pattern, link_href) for pattern in token_patterns):
                links_with_token.append(link)

        if links_with_token:
            log.debug(f"Found {len(links_with_token)} links containing token patterns")
            # Extract the token from the first link
            link_href = links_with_token[0].get('href', '')
            for pattern in token_patterns:
                match = re.search(pattern, link_href)
                if match:
                    token_match = match
                    log.debug(f"Token found in link using pattern: {pattern}")
                    break

        # If still no token found, try looking for specific elements
        if not token_match:
            # Look for links with specific class "LinkEmis" or ID containing "btnPortalEmis"
            links = soup.find_all('a', class_="LinkEmis")
            if not links:
                links = soup.find_all('a', id=lambda id: id and 'btnPortalEmis' in id)

            if links:
                log.debug(f"Found {len(links)} links with specific class or ID")
                link_str = str(links[0])
                for pattern in token_patterns:
                    match = re.search(pattern, link_str)
                    if match:
                        token_match = match
                        log.debug(f"Token found in specific link using pattern: {pattern}")
                        break

    if not token_match:
        # Log some page content for debugging
        log.debug(f"HTML snippet: {html_content[:500]}...")
        raise Exception("Authentication token not found in page")

    return token_match.group(1)

# Define the BVKApiClient class here to avoid import issues
class BVKApiClient:
    """API client for BVK."""

    def __init__(self, username: str, password: str) -> None:
        """Initialize the API client."""
        self.username = username
        self.password = password
        self.session = None
        self.token = None

    async def async_get_data(self):
        """Fetch data from BVK website."""
        try:
            # Create a new session if needed
            if self.session is None:
                self.session = aiohttp.ClientSession()

            # If no token, login and get a new one
            if not self.token:
                await self._login_and_get_token()

            # Use the token to get water consumption data
            if self.token:
                # Construct the URL with the token
                consumption_url = f"{BVK_TARGET_DOMAIN}/eMIS.SE_BVK/Login.aspx?token={self.token}&langue=cs-CZ"

                # Fetch the page with consumption data
                _LOGGER.debug(f"Fetching consumption data from: {consumption_url}")
                consumption_response = await self.session.get(consumption_url)
                consumption_page = await consumption_response.text()

                # Parse the page to find consumption data
                _LOGGER.debug("Parsing consumption data page")
                soup = BeautifulSoup(consumption_page, 'html.parser')

                # Look for consumption data in the page
                # This is a generic approach since we don't have a sample of the actual page
                # We'll look for elements that might contain consumption data
                consumption_value = None

                # Log some information about the page structure
                _LOGGER.debug(f"Page title: {soup.title.string if soup.title else 'No title'}")

                # Try different approaches to find the consumption value

                # Approach 1: Look for elements with text containing keywords
                keywords = ['spotřeba', 'm3', 'vody', 'consumption', 'water', 'odběr', 'stav', 'měřidlo', 'meter']
                keyword_pattern = '|'.join(keywords)
                consumption_elements = soup.find_all(string=re.compile(keyword_pattern, re.IGNORECASE))

                _LOGGER.debug(f"Found {len(consumption_elements)} elements with keywords")

                for element in consumption_elements:
                    # Check if the element or its parent contains a number
                    element_text = element.get_text() if hasattr(element, 'get_text') else str(element)
                    parent_text = element.parent.get_text() if hasattr(element, 'parent') and hasattr(element.parent, 'get_text') else ""
                    combined_text = element_text + " " + parent_text

                    _LOGGER.debug(f"Element text: {combined_text[:100]}")

                    # Look for numbers in the text
                    number_match = re.search(r'(\d+[.,]?\d*)\s*m3', combined_text)
                    if number_match:
                        consumption_value = float(number_match.group(1).replace(',', '.'))
                        _LOGGER.debug(f"Found consumption value: {consumption_value} m3")
                        break

                # Approach 2: Look for tables that might contain consumption data
                if consumption_value is None:
                    tables = soup.find_all('table')
                    _LOGGER.debug(f"Found {len(tables)} tables")

                    for table in tables:
                        # Look for table headers or cells containing keywords
                        headers = table.find_all(['th', 'td'], string=re.compile(keyword_pattern, re.IGNORECASE))
                        if headers:
                            _LOGGER.debug(f"Found table with relevant headers: {[h.get_text() for h in headers]}")

                            # Look for cells with numbers
                            cells = table.find_all('td')
                            for cell in cells:
                                cell_text = cell.get_text()
                                number_match = re.search(r'(\d+[.,]?\d*)\s*m3', cell_text)
                                if number_match:
                                    consumption_value = float(number_match.group(1).replace(',', '.'))
                                    _LOGGER.debug(f"Found consumption value in table: {consumption_value} m3")
                                    break

                # Approach 3: Look for specific div structures that might contain consumption data
                if consumption_value is None:
                    # Look for divs with class or id containing keywords
                    divs = soup.find_all('div', {'class': re.compile('|'.join(['consumption', 'meter', 'water', 'spotřeba', 'měřidlo']), re.IGNORECASE)})
                    divs += soup.find_all('div', {'id': re.compile('|'.join(['consumption', 'meter', 'water', 'spotřeba', 'měřidlo']), re.IGNORECASE)})

                    _LOGGER.debug(f"Found {len(divs)} divs with relevant class/id")

                    for div in divs:
                        div_text = div.get_text()
                        number_match = re.search(r'(\d+[.,]?\d*)\s*m3', div_text)
                        if number_match:
                            consumption_value = float(number_match.group(1).replace(',', '.'))
                            _LOGGER.debug(f"Found consumption value in div: {consumption_value} m3")
                            break

                # Approach 4: Look for any numbers followed by m3 in the entire page
                if consumption_value is None:
                    page_text = soup.get_text()
                    all_matches = re.findall(r'(\d+[.,]?\d*)\s*m3', page_text)

                    if all_matches:
                        _LOGGER.debug(f"Found {len(all_matches)} potential consumption values: {all_matches[:5]}")
                        # Use the first match as a fallback
                        consumption_value = float(all_matches[0].replace(',', '.'))
                        _LOGGER.debug(f"Using first match as consumption value: {consumption_value} m3")

                if consumption_value is not None:
                    return {"value": consumption_value}
                else:
                    _LOGGER.warning("Could not find consumption value in the page")
                    return {"value": None}
            else:
                _LOGGER.error("No token available to fetch consumption data")
                return {"value": None}

        except Exception as e:
            _LOGGER.error("Error updating BVK data: %s", str(e))
            return {"value": None}

    async def _login_and_get_token(self):
        """Login to BVK website and extract the authentication token."""
        try:
            # Step 1: Login to the BVK website
            login_response = await self.session.get(BVK_LOGIN_URL)

            # Extract any necessary form fields or tokens for login
            login_page = await login_response.text()

            # Use the utility function to extract the login form
            login_form, username_field, password_field = extract_login_form(login_page, logger=_LOGGER)

            # Parse the page to get additional form fields
            soup = BeautifulSoup(login_page, 'html.parser')

            # Find the required form fields
            viewstate = soup.find('input', {'name': '__VIEWSTATE'})
            viewstategenerator = soup.find('input', {'name': '__VIEWSTATEGENERATOR'})
            eventvalidation = soup.find('input', {'name': '__EVENTVALIDATION'})

            # Find submit button
            submit_button = login_form.find('input', {'type': 'submit'})

            # Log the field names for debugging
            _LOGGER.debug(f"Username field name: {username_field.get('name')}")
            _LOGGER.debug(f"Password field name: {password_field.get('name')}")
            if submit_button:
                _LOGGER.debug(f"Submit button name: {submit_button.get('name')}")

            # Prepare login data with dynamic field names
            login_data = {}

            # Add hidden fields if they exist
            if viewstate:
                login_data['__VIEWSTATE'] = viewstate.get('value', '')
            if viewstategenerator:
                login_data['__VIEWSTATEGENERATOR'] = viewstategenerator.get('value', '')
            if eventvalidation:
                login_data['__EVENTVALIDATION'] = eventvalidation.get('value', '')

            # Add username and password with their actual field names
            login_data[username_field.get('name')] = self.username
            login_data[password_field.get('name')] = self.password

            # Add submit button if found
            if submit_button:
                login_data[submit_button.get('name')] = submit_button.get('value', 'Přihlásit')

            # Get the form action URL (where to submit the form)
            form_action = login_form.get('action')
            login_submit_url = BVK_LOGIN_URL

            # If form has an action attribute, use it to construct the full submission URL
            if form_action:
                if form_action.startswith('http'):
                    # Absolute URL
                    login_submit_url = form_action
                elif form_action.startswith('/'):
                    # Root-relative URL
                    parsed_url = aiohttp.http.URL(BVK_LOGIN_URL)
                    login_submit_url = f"{parsed_url.scheme}://{parsed_url.host}{form_action}"
                else:
                    # Relative URL
                    login_submit_url = BVK_LOGIN_URL.rstrip('/') + '/' + form_action.lstrip('/')

            _LOGGER.debug(f"Submitting login form to: {login_submit_url}")

            # Submit login form
            login_post_response = await self.session.post(login_submit_url, data=login_data)

            # Get the response text for checking login success
            login_response_text = await login_post_response.text()

            # Check if login was successful
            login_failed = False

            # Check HTTP status
            if login_post_response.status != 200:
                login_failed = True
                _LOGGER.debug(f"Login failed: HTTP status {login_post_response.status}")

            # Check for error messages in various languages
            error_messages = ["Přihlášení se nezdařilo", "Login failed", "Nesprávné přihlašovací údaje"]
            for error_msg in error_messages:
                if error_msg in login_response_text:
                    login_failed = True
                    _LOGGER.debug(f"Login failed: Found error message '{error_msg}'")

            # Check if we were redirected back to the login page
            if "login" in login_post_response.url.path.lower() and "password" in login_response_text.lower():
                login_failed = True
                _LOGGER.debug("Login failed: Redirected back to login page")

            if login_failed:
                raise Exception("Login failed")

            # Step 2: Load the main info page
            main_info_response = await self.session.get(BVK_MAIN_INFO_URL)
            main_info_page = await main_info_response.text()

            # Step 3: Find the authentication token in the page
            _LOGGER.debug("Searching for token in the HTML")

            # Use the common token extraction utility
            self.token = extract_token_from_html(main_info_page, logger=_LOGGER)

            _LOGGER.debug("Successfully obtained authentication token")

        except Exception as e:
            _LOGGER.error("Error during login and token extraction: %s", str(e))
            raise

    async def async_close_session(self):
        """Close the aiohttp session."""
        if self.session:
            await self.session.close()
            self.session = None
            _LOGGER.debug("Closed aiohttp session")

# Load environment variables from .env file
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)

async def test_api_client():
    """Test the BVK API client.

    Loads credentials from .env file. Create a .env file in the test directory
    based on the .env.example template.
    """
    # Get credentials from environment variables
    username = os.getenv("BVK_USERNAME")
    password = os.getenv("BVK_PASSWORD")

    if not username or not password:
        _LOGGER.error("Missing credentials. Please set BVK_USERNAME and BVK_PASSWORD in .env file")
        return

    _LOGGER.info("Creating BVK API client")
    api_client = BVKApiClient(username, password)

    try:
        _LOGGER.info("Getting data from BVK API")
        data = await api_client.async_get_data()
        _LOGGER.info(f"Received data: {data}")
    except Exception as e:
        _LOGGER.error(f"Error getting data: {e}")
    finally:
        _LOGGER.info("Closing API client session")
        await api_client.async_close_session()

if __name__ == "__main__":
    _LOGGER.info("Starting BVK API client test")
    asyncio.run(test_api_client())
    _LOGGER.info("BVK API client test completed")

"""Test script for BVK token extraction logic."""
import asyncio
import logging
import sys
import aiohttp
from bs4 import BeautifulSoup
import re

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

async def extract_token(username, password):
    """Extract authentication token from BVK website."""
    async with aiohttp.ClientSession() as session:
        try:
            # Step 1: Login to the BVK website
            _LOGGER.info("Logging in to BVK website")
            login_response = await session.get(BVK_LOGIN_URL)
            
            # Extract form fields for login
            login_page = await login_response.text()
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
            
            # Step 2: Load the main info page
            _LOGGER.info("Loading main info page")
            main_info_response = await session.get(BVK_MAIN_INFO_URL)
            main_info_page = await main_info_response.text()
            
            # Step 3: Find the link to SUEZ Smart Solutions
            soup = BeautifulSoup(main_info_page, 'html.parser')
            
            # Log all links for debugging
            all_links = soup.find_all('a', href=lambda href: href and href.strip())
            _LOGGER.info(f"Found {len(all_links)} links on the main info page")
            
            # First, look specifically for the target URL with Login.aspx
            target_url = "https://cz-sitr.suezsmartsolutions.com/eMIS.SE_BVK/Login.aspx"
            links = soup.find_all('a', href=lambda href: href and target_url in href)
            
            if links:
                _LOGGER.info(f"Found specific target URL: {target_url}")
            
            # If specific URL not found, look for links containing the target domain
            if not links:
                _LOGGER.info("Specific target URL not found, looking for any links with target domain")
                links = soup.find_all('a', href=lambda href: href and BVK_TARGET_DOMAIN in href)
            
            # If no direct links to target domain, look for any links that might contain 'token'
            if not links:
                _LOGGER.info("No direct links to SUEZ Smart Solutions found, looking for alternative links with token")
                links = soup.find_all('a', href=lambda href: href and ('token' in href.lower() or 'auth' in href.lower()))
            
            # If still no links, look for iframe sources
            if not links:
                _LOGGER.info("No links with token found, checking iframes")
                iframes = soup.find_all('iframe', src=lambda src: src and (BVK_TARGET_DOMAIN in src or target_url in src or 'token' in src.lower()))
                if iframes:
                    _LOGGER.info(f"Found {len(iframes)} iframes that might contain token")
                    links = [{'href': iframe['src']} for iframe in iframes]
            
            if not links:
                # Log some page content for debugging
                _LOGGER.debug(f"Main info page HTML snippet: {main_info_page[:500]}...")
                raise Exception("Link to SUEZ Smart Solutions not found")
            
            # Extract the link with authentication token
            target_link = links[0]['href']
            _LOGGER.info(f"Found target link: {target_link}")
            
            # Try different patterns to extract the token
            token_patterns = [
                r'token=([^&]+)',  # Standard token format
                r'auth=([^&]+)',   # Alternative auth parameter
                r'jwt=([^&]+)',    # JWT token format
                r'access_token=([^&]+)'  # OAuth style token
            ]
            
            token_match = None
            for pattern in token_patterns:
                match = re.search(pattern, target_link)
                if match:
                    token_match = match
                    _LOGGER.info(f"Token found using pattern: {pattern}")
                    break
            
            if not token_match:
                raise Exception("Authentication token not found in link")
            
            token = token_match.group(1)
            _LOGGER.info(f"Successfully extracted token: {token[:5]}...")
            
            return token
            
        except Exception as e:
            _LOGGER.error(f"Error during token extraction: {e}")
            raise

async def main():
    """Run the token extraction test."""
    # Replace with your actual credentials
    username = "michal.kapusnik@gmail.com"
    password = "cb7ee1a9f9"
    
    _LOGGER.info("Starting token extraction test")
    try:
        token = await extract_token(username, password)
        _LOGGER.info("Token extraction successful")
    except Exception as e:
        _LOGGER.error(f"Token extraction failed: {e}")
    _LOGGER.info("Token extraction test completed")

if __name__ == "__main__":
    asyncio.run(main())
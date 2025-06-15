"""API client for BVK."""
from __future__ import annotations

import logging
import aiohttp
import re
from typing import Any, Dict, Optional
from bs4 import BeautifulSoup

from .const import (
    BVK_LOGIN_URL,
    BVK_MAIN_INFO_URL,
    BVK_TARGET_DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class BVKApiClient:
    """API client for BVK."""

    def __init__(self, username: str, password: str) -> None:
        """Initialize the API client."""
        self.username = username
        self.password = password
        self.session = None
        self.token = None

    async def async_get_data(self) -> dict[str, Any]:
        """Fetch data from BVK website."""
        try:
            # Create a new session if needed
            if self.session is None:
                self.session = aiohttp.ClientSession()

            # If no token, login and get a new one
            if not self.token:
                await self._login_and_get_token()

            # Use the token to get water consumption data
            # For now, return a placeholder value
            # In a real implementation, you would use the token to access the water consumption data
            return {"value": 42}

        except Exception as e:
            _LOGGER.error("Error updating BVK data: %s", str(e))
            return {"value": None}

    async def _login_and_get_token(self) -> None:
        """Login to BVK website and extract the authentication token."""
        try:
            # Step 1: Login to the BVK website
            login_response = await self.session.get(BVK_LOGIN_URL)

            # Extract any necessary form fields or tokens for login
            login_page = await login_response.text()
            soup = BeautifulSoup(login_page, 'html.parser')

            # Log the forms found on the page for debugging
            forms = soup.find_all('form')
            _LOGGER.debug(f"Found {len(forms)} forms on the login page")

            # Try to find the login form - first try by ID, then by looking for forms with login fields
            login_form = soup.find('form', {'id': 'form1'})

            # If form1 not found, look for any form that has username and password fields
            if not login_form:
                _LOGGER.debug("Form with id 'form1' not found, looking for alternative login forms")
                for form in forms:
                    # Look for username and password fields in this form
                    username_field = form.find('input', {'type': 'text'}) or form.find('input', {'type': 'email'})
                    password_field = form.find('input', {'type': 'password'})

                    if username_field and password_field:
                        _LOGGER.debug(f"Found potential login form with fields: {username_field.get('name')} and {password_field.get('name')}")
                        login_form = form
                        break

            if not login_form:
                # Log the HTML content for debugging
                _LOGGER.debug(f"Login page HTML: {login_page[:500]}...")  # Log first 500 chars to avoid huge logs
                raise Exception("Login form not found")

            # Find the required form fields
            viewstate = soup.find('input', {'name': '__VIEWSTATE'})
            viewstategenerator = soup.find('input', {'name': '__VIEWSTATEGENERATOR'})
            eventvalidation = soup.find('input', {'name': '__EVENTVALIDATION'})

            # Find username and password field names
            username_field = login_form.find('input', {'type': 'text'}) or login_form.find('input', {'type': 'email'})
            password_field = login_form.find('input', {'type': 'password'})
            submit_button = login_form.find('input', {'type': 'submit'})

            if not username_field or not password_field:
                raise Exception("Username or password fields not found in the login form")

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

            # Step 3: Find the icon with link to SUEZ Smart Solutions
            soup = BeautifulSoup(main_info_page, 'html.parser')

            # Log all links on the page for debugging
            all_links = soup.find_all('a', href=lambda href: href and href.strip())
            _LOGGER.debug(f"Found {len(all_links)} links on the main info page")

            # First, look specifically for the target URL with Login.aspx
            target_url = "https://cz-sitr.suezsmartsolutions.com/eMIS.SE_BVK/Login.aspx"
            links = soup.find_all('a', href=lambda href: href and target_url in href)

            if links:
                _LOGGER.debug(f"Found specific target URL: {target_url}")

            # If specific URL not found, look for links containing the target domain
            if not links:
                _LOGGER.debug("Specific target URL not found, looking for any links with target domain")
                links = soup.find_all('a', href=lambda href: href and BVK_TARGET_DOMAIN in href)

            # If no direct links to target domain, look for any links that might contain 'token'
            if not links:
                _LOGGER.debug("No direct links to SUEZ Smart Solutions found, looking for alternative links with token")
                links = soup.find_all('a', href=lambda href: href and ('token' in href.lower() or 'auth' in href.lower()))

            # If still no links, look for links with specific class "LinkEmis" or ID containing "btnPortalEmis"
            if not links:
                _LOGGER.debug("No links with token found, checking for links with class 'LinkEmis' or ID 'btnPortalEmis'")
                links = soup.find_all('a', class_="LinkEmis")
                if not links:
                    links = soup.find_all('a', id=lambda id: id and 'btnPortalEmis' in id)
                if links:
                    _LOGGER.debug(f"Found {len(links)} links with specific class or ID")

            # If still no links, look for iframe sources that might contain the target domain or specific URL
            if not links:
                _LOGGER.debug("No links with specific class or ID found, checking iframes")
                iframes = soup.find_all('iframe', src=lambda src: src and (BVK_TARGET_DOMAIN in src or target_url in src or 'token' in src.lower()))
                if iframes:
                    _LOGGER.debug(f"Found {len(iframes)} iframes that might contain token")
                    # Convert iframe src to links for consistent processing
                    links = [{'href': iframe['src']} for iframe in iframes]

            if not links:
                # Log some of the page content for debugging
                _LOGGER.debug(f"Main info page HTML: {main_info_page[:500]}...")
                raise Exception("Link to SUEZ Smart Solutions not found")

            # Extract the link with authentication token
            target_link = links[0]['href']
            _LOGGER.debug(f"Found target link: {target_link}")

            # Try different patterns to extract the authentication token
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
                    _LOGGER.debug(f"Token found using pattern: {pattern}")
                    break

            if not token_match:
                raise Exception("Authentication token not found in link")

            self.token = token_match.group(1)

            _LOGGER.debug("Successfully obtained authentication token")

        except Exception as e:
            _LOGGER.error("Error during login and token extraction: %s", str(e))
            raise

    async def async_close_session(self) -> None:
        """Close the aiohttp session."""
        if self.session:
            await self.session.close()
            self.session = None
            _LOGGER.debug("Closed aiohttp session")

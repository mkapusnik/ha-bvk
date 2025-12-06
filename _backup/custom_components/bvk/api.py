"""API client for BVK."""
from __future__ import annotations

import logging
import aiohttp
import re
from typing import Any, Dict, Optional
from bs4 import BeautifulSoup

# Support both package-relative imports (in Home Assistant) and absolute imports (in unit tests)
try:  # pragma: no cover - exercised differently in HA vs tests
    from .const import (
        BVK_LOGIN_URL,
        BVK_MAIN_INFO_URL,
        BVK_TARGET_DOMAIN,
    )
    from .token_utils import extract_token_from_html, extract_login_form
except Exception:  # pragma: no cover
    from custom_components.bvk.const import (  # type: ignore
        BVK_LOGIN_URL,
        BVK_MAIN_INFO_URL,
        BVK_TARGET_DOMAIN,
    )
    from custom_components.bvk.token_utils import extract_token_from_html, extract_login_form  # type: ignore

_LOGGER = logging.getLogger(__name__)


class BVKApiClient:
    """API client for BVK."""

    def __init__(self, username: str, password: str) -> None:
        """Initialize the API client."""
        self.username = username
        self.password = password
        self.session = None
        self.token = None

    async def _fetch_consumption_data(self) -> Dict[str, Any]:
        """Fetch consumption data from BVK website using the authentication token."""
        try:
            if not self.token:
                _LOGGER.error("No token available to fetch consumption data")
                return {"value": None}

            # Construct the URL with the token
            consumption_url = f"{BVK_TARGET_DOMAIN}/eMIS.SE_BVK/Login.aspx?token={self.token}&langue=cs-CZ"

            # Fetch the page with consumption data
            _LOGGER.debug("Fetching consumption data from: %s", consumption_url)
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
            _LOGGER.debug("Page title: %s", soup.title.string if soup.title else 'No title')

            # Try different approaches to find the consumption value

            # Approach 1: Look for elements with text containing keywords
            keywords = ['spotřeba', 'm3', 'vody', 'consumption', 'water', 'odběr', 'stav', 'měřidlo', 'meter']
            keyword_pattern = '|'.join(keywords)
            consumption_elements = soup.find_all(string=re.compile(keyword_pattern, re.IGNORECASE))

            _LOGGER.debug("Found %d elements with keywords", len(consumption_elements))

            for element in consumption_elements:
                # Check if the element or its parent contains a number
                element_text = element.get_text() if hasattr(element, 'get_text') else str(element)
                parent_text = element.parent.get_text() if hasattr(element, 'parent') and hasattr(element.parent, 'get_text') else ""
                combined_text = element_text + " " + parent_text

                _LOGGER.debug("Element text: %s", combined_text[:100])

                # Look for numbers in the text
                number_match = re.search(r'(\d+[.,]?\d*)\s*m3', combined_text)
                if number_match:
                    consumption_value = float(number_match.group(1).replace(',', '.'))
                    _LOGGER.debug("Found consumption value: %f m3", consumption_value)
                    break

            # Approach 2: Look for tables that might contain consumption data
            if consumption_value is None:
                tables = soup.find_all('table')
                _LOGGER.debug("Found %d tables", len(tables))

                for table in tables:
                    # Look for table headers or cells containing keywords
                    headers = table.find_all(['th', 'td'], string=re.compile(keyword_pattern, re.IGNORECASE))
                    if headers:
                        _LOGGER.debug("Found table with relevant headers: %s", [h.get_text() for h in headers])

                        # Look for cells with numbers
                        cells = table.find_all('td')
                        for cell in cells:
                            cell_text = cell.get_text()
                            number_match = re.search(r'(\d+[.,]?\d*)\s*m3', cell_text)
                            if number_match:
                                consumption_value = float(number_match.group(1).replace(',', '.'))
                                _LOGGER.debug("Found consumption value in table: %f m3", consumption_value)
                                break

            # Approach 3: Look for specific div structures that might contain consumption data
            if consumption_value is None:
                # Look for divs with class or id containing keywords
                divs = soup.find_all('div', {'class': re.compile('|'.join(['consumption', 'meter', 'water', 'spotřeba', 'měřidlo']), re.IGNORECASE)})
                divs += soup.find_all('div', {'id': re.compile('|'.join(['consumption', 'meter', 'water', 'spotřeba', 'měřidlo']), re.IGNORECASE)})

                _LOGGER.debug("Found %d divs with relevant class/id", len(divs))

                for div in divs:
                    div_text = div.get_text()
                    number_match = re.search(r'(\d+[.,]?\d*)\s*m3', div_text)
                    if number_match:
                        consumption_value = float(number_match.group(1).replace(',', '.'))
                        _LOGGER.debug("Found consumption value in div: %f m3", consumption_value)
                        break

            # Approach 4: Look for any numbers followed by m3 in the entire page
            if consumption_value is None:
                page_text = soup.get_text()
                all_matches = re.findall(r'(\d+[.,]?\d*)\s*m3', page_text)

                if all_matches:
                    _LOGGER.debug("Found %d potential consumption values: %s", len(all_matches), all_matches[:5])
                    # Use the first match as a fallback
                    consumption_value = float(all_matches[0].replace(',', '.'))
                    _LOGGER.debug("Using first match as consumption value: %f m3", consumption_value)

            if consumption_value is not None:
                return {"value": consumption_value}
            else:
                _LOGGER.warning("Could not find consumption value in the page")
                return {"value": None}

        except (aiohttp.ClientError, ValueError, AttributeError) as e:
            _LOGGER.error("Error fetching consumption data: %s", str(e))
            return {"value": None}

    async def async_get_data(self) -> Dict[str, Any]:
        """Fetch data from BVK website."""
        try:
            # Create a new session if needed
            if self.session is None:
                self.session = aiohttp.ClientSession()

            # If no token, login and get a new one
            if not self.token:
                await self._login_and_get_token()

            # Use the token to get water consumption data
            return await self._fetch_consumption_data()

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
            _LOGGER.debug("Username field name: %s", username_field.get('name'))
            _LOGGER.debug("Password field name: %s", password_field.get('name'))
            if submit_button:
                _LOGGER.debug("Submit button name: %s", submit_button.get('name'))

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

            _LOGGER.debug("Submitting login form to: %s", login_submit_url)

            # Submit login form
            login_post_response = await self.session.post(login_submit_url, data=login_data)

            # Get the response text for checking login success
            login_response_text = await login_post_response.text()

            # Check if login was successful
            login_failed = False

            # Check HTTP status
            if login_post_response.status != 200:
                login_failed = True
                _LOGGER.debug("Login failed: HTTP status %d", login_post_response.status)

            # Check for error messages in various languages
            error_messages = ["Přihlášení se nezdařilo", "Login failed", "Nesprávné přihlašovací údaje"]
            for error_msg in error_messages:
                if error_msg in login_response_text:
                    login_failed = True
                    _LOGGER.debug("Login failed: Found error message '%s'", error_msg)

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

    async def async_close_session(self) -> None:
        """Close the aiohttp session."""
        if self.session:
            await self.session.close()
            self.session = None
            _LOGGER.debug("Closed aiohttp session")

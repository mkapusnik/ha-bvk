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
from .token_utils import extract_token_from_html

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

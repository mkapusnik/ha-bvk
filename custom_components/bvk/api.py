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

            # Find the login form and extract any hidden fields
            login_form = soup.find('form', {'id': 'form1'})
            if not login_form:
                raise Exception("Login form not found")

            # Prepare login data
            login_data = {
                '__VIEWSTATE': soup.find('input', {'name': '__VIEWSTATE'}).get('value', ''),
                '__VIEWSTATEGENERATOR': soup.find('input', {'name': '__VIEWSTATEGENERATOR'}).get('value', ''),
                '__EVENTVALIDATION': soup.find('input', {'name': '__EVENTVALIDATION'}).get('value', ''),
                'ctl00$ContentPlaceHolder1$Login1$UserName': self.username,
                'ctl00$ContentPlaceHolder1$Login1$Password': self.password,
                'ctl00$ContentPlaceHolder1$Login1$LoginButton': 'Přihlásit'
            }

            # Submit login form
            login_post_response = await self.session.post(BVK_LOGIN_URL, data=login_data)

            # Check if login was successful
            if login_post_response.status != 200 or "Přihlášení se nezdařilo" in await login_post_response.text():
                raise Exception("Login failed")

            # Step 2: Load the main info page
            main_info_response = await self.session.get(BVK_MAIN_INFO_URL)
            main_info_page = await main_info_response.text()

            # Step 3: Find the icon with link to SUEZ Smart Solutions
            soup = BeautifulSoup(main_info_page, 'html.parser')

            # Look for links containing the target domain
            links = soup.find_all('a', href=lambda href: href and BVK_TARGET_DOMAIN in href)

            if not links:
                raise Exception("Link to SUEZ Smart Solutions not found")

            # Extract the link with authentication token
            target_link = links[0]['href']

            # Extract the authentication token from the link
            token_match = re.search(r'token=([^&]+)', target_link)
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
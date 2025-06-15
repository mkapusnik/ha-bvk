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

# Paths to locally saved pages for testing
LOGIN_PAGE_FILE = os.path.join(os.path.dirname(__file__), "resources", "login_page.html")
MAIN_INFO_PAGE_FILE = os.path.join(os.path.dirname(__file__), "resources", "main_info_page.html")

async def extract_token():
    """Extract authentication token from BVK website."""
    async with aiohttp.ClientSession() as session:
        try:
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
            return token

        except Exception as e:
            _LOGGER.error(f"Error during token extraction: {e}")
            raise


async def main():
    """Run the token extraction test."""
    _LOGGER.info("Starting tests")

    # Run the token extraction test
    try:
        token = await extract_token()
        _LOGGER.info(f"Token extraction successful: {token}...")
    except Exception as e:
        _LOGGER.error(f"Token extraction failed: {e}")

    _LOGGER.info("Tests completed")

if __name__ == "__main__":
    asyncio.run(main())

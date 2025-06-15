"""Utility functions for token extraction and form handling from BVK website."""
import logging
import re
from bs4 import BeautifulSoup
from typing import Optional, Tuple, Dict, Any

_LOGGER = logging.getLogger(__name__)

def extract_login_form(html_content, logger=None) -> Tuple[Optional[BeautifulSoup], Optional[BeautifulSoup], Optional[BeautifulSoup]]:
    """Extract login form and its username/password fields from HTML content.

    Args:
        html_content (str): The HTML content to extract the login form from
        logger (logging.Logger, optional): Logger to use for debug messages.
                                          If None, uses the module logger.

    Returns:
        tuple[Optional[BeautifulSoup], Optional[BeautifulSoup], Optional[BeautifulSoup]]: 
            A tuple containing (login_form, username_field, password_field)

    Raises:
        Exception: If the login form cannot be found
    """
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
                log.debug("Found potential login form with fields: %s and %s", 
                          username_field.get('name'), password_field.get('name'))
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


def extract_token_from_html(html_content, logger=None) -> str:
    """Extract authentication token from HTML content.

    Args:
        html_content (str): The HTML content to extract the token from
        logger (logging.Logger, optional): Logger to use for debug messages. 
                                          If None, uses the module logger.

    Returns:
        str: The extracted token

    Raises:
        Exception: If the token cannot be found
    """
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
            log.debug("Token found directly in HTML using pattern: %s", pattern)
            break

    if not token_match:
        log.debug("Token not found directly in HTML, trying to find it in specific elements")
        soup = BeautifulSoup(html_content, 'html.parser')

        # Log all links on the page for debugging
        all_links = soup.find_all('a', href=lambda href: href and href.strip())
        log.debug("Found %d links on the page", len(all_links))

        # Look for links with token in href
        links_with_token = []
        for link in all_links:
            link_href = link.get('href', '')
            if any(re.search(pattern, link_href) for pattern in token_patterns):
                links_with_token.append(link)

        if links_with_token:
            log.debug("Found %d links containing token patterns", len(links_with_token))
            # Extract the token from the first link
            link_href = links_with_token[0].get('href', '')
            for pattern in token_patterns:
                match = re.search(pattern, link_href)
                if match:
                    token_match = match
                    log.debug("Token found in link using pattern: %s", pattern)
                    break

        # If still no token found, try looking for specific elements
        if not token_match:
            # Look for links with specific class "LinkEmis" or ID containing "btnPortalEmis"
            links = soup.find_all('a', class_="LinkEmis")
            if not links:
                links = soup.find_all('a', id=lambda id: id and 'btnPortalEmis' in id)

            if links:
                log.debug("Found %d links with specific class or ID", len(links))
                link_str = str(links[0])
                for pattern in token_patterns:
                    match = re.search(pattern, link_str)
                    if match:
                        token_match = match
                        log.debug("Token found in specific link using pattern: %s", pattern)
                        break

    if not token_match:
        # Log some page content for debugging
        log.debug("HTML snippet: %s...", html_content[:500])
        raise Exception("Authentication token not found in page")

    return token_match.group(1)

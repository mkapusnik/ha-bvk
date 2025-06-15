"""Test script for BVK token extraction logic."""
import asyncio
import logging
import sys
import os
import unittest

# Add the parent directory to the path in case we need to import from the custom component
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the token_utils module directly
import importlib.util
spec = importlib.util.spec_from_file_location(
    "token_utils", 
    os.path.join(os.path.dirname(__file__), '..', 'custom_components', 'bvk', 'token_utils.py')
)
token_utils = importlib.util.module_from_spec(spec)
spec.loader.exec_module(token_utils)
extract_token_from_html = token_utils.extract_token_from_html

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


class TestTokenExtraction(unittest.TestCase):
    """Test the token extraction functionality."""

    async def async_extract_token(self) -> str:
        """Extract authentication token from BVK website."""
        try:
            _LOGGER.info("Loading main info page from local file")

            # Read the main info page from the local file
            with open(MAIN_INFO_PAGE_FILE, 'r', encoding='utf-8') as f:
                main_info_page = f.read()

            # Use the common token extraction utility
            _LOGGER.info("Searching for token in the HTML")
            token = extract_token_from_html(main_info_page, logger=_LOGGER)
            return token

        except FileNotFoundError as e:
            _LOGGER.error("Error reading file: %s", e)
            raise
        except ValueError as e:
            _LOGGER.error("Error parsing token: %s", e)
            raise
        except Exception as e:
            _LOGGER.error("Unexpected error during token extraction: %s", e)
            raise

    def test_token_extraction(self):
        """Test token extraction from the main info page."""
        _LOGGER.info("Starting token extraction test")

        try:
            token = asyncio.run(self.async_extract_token())
            _LOGGER.info("Token extraction successful: %s...", token)
            self.assertIsNotNone(token, "Token should not be None")
            self.assertTrue(len(token) > 0, "Token should not be empty")
        except (FileNotFoundError, ValueError) as e:
            _LOGGER.error("Token extraction failed: %s", e)
            self.fail(f"Token extraction failed: {e}")
        except Exception as e:
            _LOGGER.error("Unexpected error during token extraction: %s", e)
            self.fail(f"Unexpected error during token extraction: {e}")

        _LOGGER.info("Token extraction test completed")


if __name__ == "__main__":
    unittest.main()

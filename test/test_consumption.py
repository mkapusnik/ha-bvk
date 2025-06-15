"""Simple test script for BVK API client."""
import asyncio
import logging
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Import the constants directly using importlib to avoid triggering __init__.py
import importlib.util
spec = importlib.util.spec_from_file_location(
    "const", 
    os.path.join(os.path.dirname(__file__), '..', 'custom_components', 'bvk', 'const.py')
)
const = importlib.util.module_from_spec(spec)
spec.loader.exec_module(const)

# Import the BVKApiClient class and utility functions
spec_api = importlib.util.spec_from_file_location(
    "api", 
    os.path.join(os.path.dirname(__file__), '..', 'custom_components', 'bvk', 'api.py')
)
api = importlib.util.module_from_spec(spec_api)
spec_api.loader.exec_module(api)

# Import token utilities
spec_token_utils = importlib.util.spec_from_file_location(
    "token_utils", 
    os.path.join(os.path.dirname(__file__), '..', 'custom_components', 'bvk', 'token_utils.py')
)
token_utils = importlib.util.module_from_spec(spec_token_utils)
spec_token_utils.loader.exec_module(token_utils)

# Use the imported modules
BVKApiClient = api.BVKApiClient
extract_login_form = token_utils.extract_login_form
extract_token_from_html = token_utils.extract_token_from_html
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

"""Test script for BVK API client."""
import asyncio
import logging
import sys
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add the parent directory to the path so we can import the custom component
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from custom_components.bvk.api import BVKApiClient

# Load environment variables from .env file
env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
_LOGGER = logging.getLogger(__name__)


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

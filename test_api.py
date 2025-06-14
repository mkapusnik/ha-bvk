"""Test script for BVK API client."""
import asyncio
import logging
import sys
from custom_components.bvk.api import BVKApiClient

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
_LOGGER = logging.getLogger(__name__)


async def test_api_client():
    """Test the BVK API client."""
    # Replace with your actual credentials
    username = "your_username"
    password = "your_password"
    
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
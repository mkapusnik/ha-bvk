# BVK Integration for Home Assistant

This integration allows you to monitor your water consumption from BVK (Brněnské vodárny a kanalizace) in Home Assistant.

## Components

### API Client

The `api.py` file contains a standalone API client for BVK that can be used independently of Home Assistant. This makes it easier to test and debug the data retrieval logic.

```python
from custom_components.bvk.api import BVKApiClient

# Create the API client
api_client = BVKApiClient(username, password)

# Get data
data = await api_client.async_get_data()

# Close the session when done
await api_client.async_close_session()
```

### Sensor

The `sensor.py` file contains the Home Assistant integration code that uses the API client to retrieve data and display it in Home Assistant.

## Testing

You can test the API client independently using the `test_api.py` script in the root directory:

```bash
python test_api.py
```

Make sure to update the username and password in the script before running it.
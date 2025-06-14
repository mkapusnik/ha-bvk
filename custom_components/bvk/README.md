# BVK Integration for Home Assistant

This integration allows you to monitor your water consumption from BVK (Brněnské vodárny a kanalizace) in Home Assistant.

### Sensor

The `sensor.py` file contains the Home Assistant integration code that uses the API client to retrieve data and display it in Home Assistant.

## Authentication

The integration authenticates with BVK and then extracts an authentication token for Suez Smart Solutions. The token is extracted from a link on the BVK main info page, specifically looking for:
```
https://cz-sitr.suezsmartsolutions.com/eMIS.SE_BVK/Login.aspx
```
with a token parameter in the URL.

## Testing

You can test the API client independently using the `test_api.py` script in the `test` directory:

```bash
python test\test_api.py
```

Make sure to update the username and password in the script before running it.

Note: The API test requires the Home Assistant libraries to be available in your Python environment, as it imports from the custom component which depends on Home Assistant.

For testing just the token extraction logic, you can use the `test_token_extraction.py` script:

```bash
python test\test_token_extraction.py
```

This script focuses specifically on the login and token extraction process and does not require the Home Assistant libraries.

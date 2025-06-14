# BVK Integration for Home Assistant

This integration allows you to monitor your water consumption from BVK (Brněnské vodárny a kanalizace) in Home Assistant.

### Sensor

The `sensor.py` file contains the Home Assistant integration code that uses the API client to retrieve data and display it in Home Assistant.

## Testing

You can test the API client independently using the `test_api.py` script in the root directory:

```bash
python test_api.py
```

Make sure to update the username and password in the script before running it.
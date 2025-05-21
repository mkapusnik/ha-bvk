# BVK for Home Assistant

This is a custom component for Home Assistant that provides a basic integration template.

## Installation

### Manual Installation

1. Copy the `bvk` folder from this repository to your Home Assistant's `custom_components` directory.
2. Restart Home Assistant.
3. Go to Configuration -> Integrations and click the "+" button to add a new integration.
4. Search for "BVK" and follow the configuration steps.

### HACS Installation

1. Make sure you have [HACS](https://hacs.xyz/) installed.
2. Go to HACS -> Integrations -> Click the three dots in the top right -> Custom repositories.
3. Add the URL of this repository and select "Integration" as the category.
4. Click "Add".
5. Search for "BVK" in HACS and install it.
6. Restart Home Assistant.
7. Go to Configuration -> Integrations and click the "+" button to add a new integration.
8. Search for "BVK" and follow the configuration steps.

## Configuration

The integration can be configured through the Home Assistant UI:

1. Go to Configuration -> Integrations.
2. Click the "+" button to add a new integration.
3. Search for "BVK" and select it.
4. Enter a name for the integration.
5. Click "Submit".

## Features

- Provides a basic temperature sensor with a static value (42°C)
- Updates every 5 minutes

## Development

This integration is designed to be a starting point for creating your own custom integrations. Here are some tips for customizing it:

1. Rename the `bvk` directory and update all references to "bvk" in the code.
2. Update the `manifest.json` file with your own information.
3. Modify the `sensor.py` file to implement your own sensor logic.
4. Update the translations in the `translations` directory.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

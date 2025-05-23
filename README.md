# !!! Work in Progress !!! 

This project is still in an early stage of development. It's unlikely it will work for you at this moment!
Feel free to watch my progress and check again later

# BVK Water Meter for Home Assistant

This is a custom component for Home Assistant that provides integration with BVK smart meters.

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

For prototyping purposes:
- Provides a basic temperature sensor with a static value (42°C)
- Updates every 5 minutes

## License

This project is licensed under the MIT License - see the LICENSE file for details.

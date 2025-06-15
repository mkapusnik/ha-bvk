## Tech Stack
- **Python 3.x**: Core programming language
- **Home Assistant**: Integration platform

## Running Tests

### Running Individual Tests
- API Test:
  ```bash
  python test/test_api.py
  ```

- Token Extraction Test:
  ```bash
  python test/test_token_extraction.py
  ```

- Login Form Test:
  ```bash
  python test/test_login_form.py
  ```

- Consumption Data Test:
  ```bash
  python test/test_consumption.py
  ```

## Best Practices

### Code Style
- Follow the [Home Assistant Python Style Guide](https://developers.home-assistant.io/docs/development_guidelines)
- Use type hints for function parameters and return values
- Document classes and methods with docstrings
- Avoid code duplication

### Error Handling
- Use try/except blocks to handle potential errors when interacting with external services
- Log errors with appropriate levels (debug, info, warning, error)
- Ensure the integration degrades gracefully when the BVK service is unavailable

### Testing
- Write tests for new functionality
- Test edge cases and error conditions
- Use the provided test scripts as examples for new tests

### Authentication
- Never hardcode credentials
- Use the Home Assistant config flow for secure credential management
- Cache authentication tokens securely using Home Assistant's storage API

### Performance
- Use asynchronous programming (async/await) for I/O operations
- Respect the SCAN_INTERVAL (currently 5 minutes) to avoid overloading the BVK service
- Implement proper session management (creation and cleanup)

### Contributions
- Create descriptive commit messages
- Document changes in the README.md when appropriate
- Update tests when modifying existing functionality
# BVK Test Scripts

This directory contains test scripts for the BVK integration.

## Environment Setup

Some tests require credentials to access the BVK API. To provide these credentials securely:

1. Copy the `.env.example` file to a new file named `.env` in this directory:
   ```
   cp .env.example .env
   ```

2. Edit the `.env` file and replace the placeholder values with your actual BVK credentials:
   ```
   BVK_USERNAME=your_actual_username
   BVK_PASSWORD=your_actual_password
   ```

3. The `.env` file is excluded from git in `.gitignore` to prevent accidentally committing your credentials.

## Running Tests

All tests have been converted to use the Python unittest framework. You can run individual tests or all tests at once.

### Running Individual Tests

To run a specific test:

```
python test_api.py
python test_token_extraction.py
python test_login_form.py
python test_consumption.py
```

Tests that require credentials will load them from the `.env` file. If credentials are not provided, those tests will be skipped.

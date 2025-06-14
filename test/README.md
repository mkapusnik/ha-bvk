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

To run the API test:

```
python test_api.py
```

This will load your credentials from the `.env` file and test the BVK API client.
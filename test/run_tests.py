"""Test runner for BVK integration tests.

This script discovers and runs all unittest-based tests in the test directory.
"""
import unittest
import sys
import os

# Add the parent directory to the path so we can import the custom component
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

if __name__ == "__main__":
    # Discover and run all tests
    test_loader = unittest.TestLoader()
    test_suite = test_loader.discover(os.path.dirname(__file__))
    
    # Run the tests
    test_runner = unittest.TextTestRunner(verbosity=2)
    result = test_runner.run(test_suite)
    
    # Exit with non-zero code if tests failed
    sys.exit(not result.wasSuccessful())
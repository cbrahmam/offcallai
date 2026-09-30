#!/usr/bin/env python3
"""
Test script for OffCall Python SDK

Usage:
    python test_python_sdk.py <api_key> [endpoint]

Example:
    python test_python_sdk.py ofc_test123
    python test_python_sdk.py ofc_test123 http://localhost:8000/api/v1/errors/ingest/python
"""

import sys
import os

# Add SDK to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'python'))

import offcall_errors

def test_sdk(api_key: str, endpoint: str = None):
    print("=" * 60)
    print("OffCall Python SDK Test")
    print("=" * 60)

    # Initialize SDK
    config = {
        "api_key": api_key,
        "environment": "test",
        "release": "1.0.0-test",
        "service": "sdk-test-python",
        "debug": True,  # Enable debug output
    }

    if endpoint:
        config["endpoint"] = endpoint

    print(f"\n1. Initializing SDK...")
    print(f"   API Key: {api_key[:10]}...")
    print(f"   Endpoint: {endpoint or 'default'}")

    offcall_errors.init(**config)
    print("   ✓ SDK initialized")

    # Test user context
    print(f"\n2. Setting user context...")
    offcall_errors.set_user({
        "id": "test-user-123",
        "email": "test@example.com",
        "name": "Test User",
    })
    print("   ✓ User context set")

    # Test tags
    print(f"\n3. Setting tags...")
    offcall_errors.set_tags({
        "test_run": "true",
        "sdk_version": "1.0.0",
    })
    print("   ✓ Tags set")

    # Test breadcrumb
    print(f"\n4. Adding breadcrumb...")
    offcall_errors.add_breadcrumb(
        message="Test breadcrumb",
        category="test",
        level="info",
        data={"action": "sdk_test"},
    )
    print("   ✓ Breadcrumb added")

    # Test capture_message
    print(f"\n5. Sending test message...")
    offcall_errors.capture_message(
        "SDK test message - this is a test from the Python SDK",
        level="info",
    )
    print("   ✓ Message sent (check debug output above)")

    # Test capture_exception
    print(f"\n6. Sending test exception...")
    try:
        raise ValueError("SDK test exception - this is a test error from Python SDK")
    except Exception as e:
        offcall_errors.capture_exception(e)
    print("   ✓ Exception sent (check debug output above)")

    print("\n" + "=" * 60)
    print("Test complete!")
    print("=" * 60)
    print("\nIf you see '[OffCall] Error reported' messages above, the SDK is working.")
    print("Check your OffCall dashboard to verify errors appear in Error Tracking.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_python_sdk.py <api_key> [endpoint]")
        print("\nExample:")
        print("  python test_python_sdk.py ofc_your_api_key")
        print("  python test_python_sdk.py ofc_your_api_key http://localhost:8000/api/v1/errors/ingest/python")
        sys.exit(1)

    api_key = sys.argv[1]
    endpoint = sys.argv[2] if len(sys.argv) > 2 else None

    test_sdk(api_key, endpoint)

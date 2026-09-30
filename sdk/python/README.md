# offcall-errors

Official Python SDK for OffCall AI error tracking. Capture and track errors in your Python applications with automatic exception capture, breadcrumbs, and rich context.

## Installation

```bash
pip install offcall-errors
```

With framework support:

```bash
pip install offcall-errors[flask]
pip install offcall-errors[django]
pip install offcall-errors[fastapi]
```

## Quick Start

```python
import offcall_errors

offcall_errors.init(
    api_key="ofc_your_api_key",
    environment="production",
    release="1.0.0",
)

# Errors are now captured automatically!
```

## Features

- **Automatic Exception Capture**: Catches unhandled exceptions via `sys.excepthook`
- **Framework Integrations**: Django, Flask, FastAPI middleware included
- **Breadcrumbs**: Track user actions and events leading up to errors
- **Rich Context**: Capture user info, tags, and custom data with each error
- **Stack Traces**: Full stack trace with source file context
- **Sampling**: Control error volume with configurable sample rates
- **Thread-safe**: Safe for multi-threaded applications

## Configuration

```python
import offcall_errors

offcall_errors.init(
    # Required
    api_key="ofc_your_api_key",

    # Optional
    environment="production",      # Environment name
    release="1.0.0",               # App version
    service="my-service",          # Service name (auto-detected if not set)
    debug=False,                   # Enable debug logging
    enabled=True,                  # Enable/disable SDK
    max_breadcrumbs=100,           # Max breadcrumbs to keep
    sample_rate=1.0,               # Sample rate (0.0 to 1.0)

    # Filtering
    ignore_exceptions=[KeyboardInterrupt, SystemExit],

    # Transform events before sending
    before_send=lambda event: event,  # Return None to drop
)
```

## API Reference

### Capture Errors

```python
# Capture an exception
try:
    risky_operation()
except Exception as e:
    offcall_errors.capture_exception(e, extra={"order_id": "12345"})

# Capture from current context (in except block)
try:
    risky_operation()
except:
    offcall_errors.capture_exception()  # Uses sys.exc_info()

# Capture a message
offcall_errors.capture_message("User completed onboarding", level="info")
```

### User Context

```python
# Set user info (persists across errors)
offcall_errors.set_user({
    "id": "user-123",
    "email": "user@example.com",
    "name": "John Doe",
    "plan": "premium",  # Custom fields allowed
})

# Clear user on logout
offcall_errors.clear_user()
```

### Tags & Extra Context

```python
# Set tags (indexed, searchable)
offcall_errors.set_tag("environment", "production")
offcall_errors.set_tags({
    "region": "us-east",
    "version": "2.0.0",
})

# Set extra context (not indexed)
offcall_errors.set_extra("last_action", "clicked checkout")
offcall_errors.set_extras({
    "cart_items": 3,
    "total_value": 99.99,
})
```

### Breadcrumbs

Add custom breadcrumbs to track user actions:

```python
offcall_errors.add_breadcrumb(
    message="User logged in",
    category="auth",
    level="info",
    data={
        "method": "oauth",
        "provider": "google",
    },
)
```

## Framework Integrations

### Django

```python
# settings.py
MIDDLEWARE = [
    'offcall_errors.integrations.django.OffCallMiddleware',
    # ... other middleware
]

OFFCALL_API_KEY = "ofc_your_api_key"
OFFCALL_ENVIRONMENT = "production"
OFFCALL_RELEASE = "1.0.0"
```

### Flask

```python
from flask import Flask
from offcall_errors.integrations.flask import OffCallFlask

app = Flask(__name__)
OffCallFlask(app, api_key="ofc_your_api_key")

# Or with factory pattern
offcall = OffCallFlask()

def create_app():
    app = Flask(__name__)
    offcall.init_app(app)
    return app
```

### FastAPI

```python
from fastapi import FastAPI
from offcall_errors.integrations.fastapi import OffCallFastAPI

app = FastAPI()
OffCallFastAPI(app, api_key="ofc_your_api_key")
```

### Logging Integration

```python
import logging
from offcall_errors.integrations.logging import OffCallHandler

# Capture ERROR and above as OffCall events
logging.getLogger().addHandler(OffCallHandler(level=logging.ERROR))

# Or use convenience function
from offcall_errors.integrations.logging import setup_logging
setup_logging(level=logging.ERROR, breadcrumb_level=logging.INFO)
```

## Context Managers

```python
# Configure scope with callback
def configure(scope):
    scope.set_tag("transaction", "checkout")
    scope.set_user({"id": "123"})

offcall_errors.configure_scope(configure)
```

## Advanced Usage

### Custom Before Send

```python
def before_send(event):
    # Remove sensitive data
    if event.get("user"):
        event["user"].pop("email", None)

    # Drop specific errors
    if "harmless" in event.get("message", ""):
        return None

    return event

offcall_errors.init(
    api_key="ofc_xxx",
    before_send=before_send,
)
```

### Async Support

The SDK is safe to use in async applications. For FastAPI, the middleware handles async requests automatically.

```python
@app.get("/api/data")
async def get_data():
    try:
        return await fetch_data()
    except Exception as e:
        offcall_errors.capture_exception(e)
        raise
```

## Environment Variables

The SDK respects these environment variables for service detection:

- `SERVICE_NAME` - Service name
- `APP_NAME` - Alternative service name

## Support

- [Documentation](https://github.com/cbrahmam/offcallai/blob/main/sdk/python/README.md)
- [GitHub Issues](https://github.com/offcall-ai/offcall-python/issues)
- [Email Support](mailto:noreply@example.com)

## License

MIT License - see [LICENSE](LICENSE) for details.

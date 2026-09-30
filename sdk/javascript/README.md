# @offcallai/errors

Official JavaScript SDK for OffCall AI error tracking. Capture and track errors in your web applications with automatic error capture, breadcrumbs, and rich context.

## Installation

```bash
npm install @offcallai/errors
# or
yarn add @offcallai/errors
# or
pnpm add @offcallai/errors
```

Or include via CDN:

```html
<script src="/offcall-errors.min.js"></script>
```

## Quick Start

```javascript
import * as OffCallErrors from '@offcallai/errors';

OffCallErrors.init({
  apiKey: 'ofc_your_api_key',
  environment: 'production',
  release: '1.0.0',
});

// Errors are now captured automatically!
```

## Features

- **Automatic Error Capture**: Catches uncaught exceptions and unhandled promise rejections
- **Breadcrumbs**: Automatic tracking of user clicks, navigation, console logs, and HTTP requests
- **Rich Context**: Capture user info, tags, and custom data with each error
- **Stack Traces**: Full stack trace parsing with source file information
- **Sampling**: Control error volume with configurable sample rates
- **Privacy**: Filter sensitive data with beforeSend hooks

## Configuration

```javascript
OffCallErrors.init({
  // Required
  apiKey: 'ofc_your_api_key',

  // Optional
  environment: 'production',      // Environment name
  release: '1.0.0',               // App version
  service: 'my-frontend',         // Service name
  debug: false,                   // Enable debug logging
  enabled: true,                  // Enable/disable SDK
  maxBreadcrumbs: 100,            // Max breadcrumbs to keep
  sampleRate: 1.0,                // Sample rate (0.0 to 1.0)

  // Filtering
  ignoreErrors: [
    'ResizeObserver loop limit exceeded',
    /^Script error\.?$/,
  ],

  // Transform events before sending
  beforeSend: (event) => {
    // Remove sensitive data
    if (event.user) {
      delete event.user.email;
    }
    return event; // Return null to drop the event
  },
});
```

## API Reference

### Capture Errors

```javascript
// Capture an exception
try {
  riskyOperation();
} catch (error) {
  OffCallErrors.captureException(error, {
    tags: { module: 'checkout' },
    extra: { orderId: '12345' },
  });
}

// Capture a message
OffCallErrors.captureMessage('User completed onboarding', 'info');
```

### User Context

```javascript
// Set user info (persists across errors)
OffCallErrors.setUser({
  id: 'user-123',
  email: 'user@example.com',
  name: 'John Doe',
  plan: 'premium', // Custom fields allowed
});

// Clear user on logout
OffCallErrors.clearUser();
```

### Tags & Extra Context

```javascript
// Set tags (indexed, searchable)
OffCallErrors.setTag('environment', 'production');
OffCallErrors.setTags({
  region: 'us-east',
  version: '2.0.0',
});

// Set extra context (not indexed)
OffCallErrors.setExtra('lastAction', 'clicked checkout');
OffCallErrors.setExtras({
  cartItems: 3,
  totalValue: 99.99,
});
```

### Breadcrumbs

Breadcrumbs are automatically captured for:
- Console logs (log, warn, error, info)
- User clicks
- Navigation (URL changes)
- HTTP requests (XHR and fetch)

Add custom breadcrumbs:

```javascript
OffCallErrors.addBreadcrumb({
  type: 'user',
  category: 'auth',
  message: 'User logged in',
  level: 'info',
  data: {
    method: 'oauth',
    provider: 'google',
  },
});
```

## Framework Integration

### React

```javascript
// Error boundary
import * as OffCallErrors from '@offcallai/errors';

class ErrorBoundary extends React.Component {
  componentDidCatch(error, errorInfo) {
    OffCallErrors.captureException(error, {
      extra: { componentStack: errorInfo.componentStack },
    });
  }

  render() {
    return this.props.children;
  }
}
```

### Vue

```javascript
import * as OffCallErrors from '@offcallai/errors';

app.config.errorHandler = (error, instance, info) => {
  OffCallErrors.captureException(error, {
    extra: { info, componentName: instance?.$options?.name },
  });
};
```

### Angular

```typescript
import * as OffCallErrors from '@offcallai/errors';

@Injectable()
export class GlobalErrorHandler implements ErrorHandler {
  handleError(error: Error) {
    OffCallErrors.captureException(error);
  }
}
```

## TypeScript

Full TypeScript support included:

```typescript
import * as OffCallErrors from '@offcallai/errors';
import type { OffCallConfig, User, Breadcrumb } from '@offcallai/errors';

const config: OffCallConfig = {
  apiKey: 'ofc_xxx',
  environment: 'production',
};

OffCallErrors.init(config);
```

## Privacy & Security

- Errors are sent over HTTPS
- Use `beforeSend` to filter sensitive data
- Use `ignoreErrors` to exclude noisy errors
- Control volume with `sampleRate`

## Support

- [Documentation](https://github.com/cbrahmam/offcallai/blob/main/sdk/javascript/README.md)
- [GitHub Issues](https://github.com/offcall-ai/offcall-javascript/issues)
- [Email Support](mailto:noreply@example.com)

## License

MIT License - see [LICENSE](LICENSE) for details.

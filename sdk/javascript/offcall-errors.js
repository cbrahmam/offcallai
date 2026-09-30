/**
 * OffCall AI - JavaScript Error Tracking SDK
 *
 * Usage:
 * <script src="/offcall-errors.min.js"></script>
 * <script>
 *   OffCallErrors.init({
 *     apiKey: 'ofc_your_api_key',
 *     environment: 'production',
 *     release: '1.0.0',
 *   });
 * </script>
 *
 * Or with npm:
 * npm install @offcall/errors
 *
 * import * as OffCallErrors from '@offcall/errors';
 * OffCallErrors.init({ apiKey: 'ofc_your_api_key' });
 */

(function(global) {
  'use strict';

  const SDK_NAME = 'offcall-js';
  const SDK_VERSION = '1.0.0';
  const DEFAULT_ENDPOINT = 'http://localhost:8000/api/v1/errors/ingest/js';

  // Configuration
  let config = {
    apiKey: null,
    endpoint: DEFAULT_ENDPOINT,
    environment: 'production',
    release: null,
    service: null,
    debug: false,
    enabled: true,
    maxBreadcrumbs: 100,
    beforeSend: null,
    ignoreErrors: [],
    ignoreUrls: [],
    denyUrls: [],
    allowUrls: [],
    sampleRate: 1.0,
  };

  // User context
  let userContext = {
    id: null,
    email: null,
    name: null,
  };

  // Tags context
  let tagsContext = {};

  // Extra context
  let extraContext = {};

  // Breadcrumbs
  let breadcrumbs = [];

  // Is initialized
  let isInitialized = false;

  // Original error handlers
  let originalOnError = null;
  let originalOnUnhandledRejection = null;

  /**
   * Get browser info
   */
  function getBrowserInfo() {
    const ua = navigator.userAgent;
    let browser = { name: 'Unknown', version: '0' };

    if (ua.indexOf('Firefox') > -1) {
      browser.name = 'Firefox';
      browser.version = ua.match(/Firefox\/(\d+)/)?.[1] || '0';
    } else if (ua.indexOf('Chrome') > -1 && ua.indexOf('Edg') === -1) {
      browser.name = 'Chrome';
      browser.version = ua.match(/Chrome\/(\d+)/)?.[1] || '0';
    } else if (ua.indexOf('Safari') > -1 && ua.indexOf('Chrome') === -1) {
      browser.name = 'Safari';
      browser.version = ua.match(/Version\/(\d+)/)?.[1] || '0';
    } else if (ua.indexOf('Edg') > -1) {
      browser.name = 'Edge';
      browser.version = ua.match(/Edg\/(\d+)/)?.[1] || '0';
    } else if (ua.indexOf('MSIE') > -1 || ua.indexOf('Trident') > -1) {
      browser.name = 'IE';
      browser.version = ua.match(/(?:MSIE |rv:)(\d+)/)?.[1] || '0';
    }

    return browser;
  }

  /**
   * Get OS info
   */
  function getOSInfo() {
    const ua = navigator.userAgent;
    let os = { name: 'Unknown', version: '0' };

    if (ua.indexOf('Windows') > -1) {
      os.name = 'Windows';
      os.version = ua.match(/Windows NT (\d+\.\d+)/)?.[1] || '0';
    } else if (ua.indexOf('Mac') > -1) {
      os.name = 'macOS';
      os.version = ua.match(/Mac OS X (\d+[._]\d+)/)?.[1]?.replace('_', '.') || '0';
    } else if (ua.indexOf('Linux') > -1) {
      os.name = 'Linux';
    } else if (ua.indexOf('Android') > -1) {
      os.name = 'Android';
      os.version = ua.match(/Android (\d+)/)?.[1] || '0';
    } else if (ua.indexOf('iOS') > -1 || ua.indexOf('iPhone') > -1 || ua.indexOf('iPad') > -1) {
      os.name = 'iOS';
      os.version = ua.match(/OS (\d+)/)?.[1] || '0';
    }

    return os;
  }

  /**
   * Parse stack trace into frames
   */
  function parseStackTrace(stack) {
    if (!stack) return [];

    const frames = [];
    const lines = stack.split('\n');

    for (const line of lines) {
      // Chrome/Edge format: at functionName (file:line:column)
      let match = line.match(/at\s+(.+?)\s+\((.+?):(\d+):(\d+)\)/);
      if (match) {
        frames.push({
          function: match[1],
          filename: match[2],
          lineno: parseInt(match[3]),
          colno: parseInt(match[4]),
          in_app: !match[2].includes('node_modules') && !match[2].startsWith('http')
        });
        continue;
      }

      // Chrome/Edge format: at file:line:column
      match = line.match(/at\s+(.+?):(\d+):(\d+)/);
      if (match) {
        frames.push({
          function: '<anonymous>',
          filename: match[1],
          lineno: parseInt(match[2]),
          colno: parseInt(match[3]),
          in_app: !match[1].includes('node_modules')
        });
        continue;
      }

      // Firefox/Safari format: functionName@file:line:column
      match = line.match(/(.+?)@(.+?):(\d+):(\d+)/);
      if (match) {
        frames.push({
          function: match[1] || '<anonymous>',
          filename: match[2],
          lineno: parseInt(match[3]),
          colno: parseInt(match[4]),
          in_app: !match[2].includes('node_modules')
        });
      }
    }

    return frames;
  }

  /**
   * Add breadcrumb
   */
  function addBreadcrumb(crumb) {
    const breadcrumb = {
      timestamp: new Date().toISOString(),
      type: crumb.type || 'default',
      category: crumb.category || 'default',
      message: crumb.message,
      data: crumb.data || {},
      level: crumb.level || 'info',
    };

    breadcrumbs.push(breadcrumb);

    // Limit breadcrumbs
    if (breadcrumbs.length > config.maxBreadcrumbs) {
      breadcrumbs.shift();
    }
  }

  /**
   * Should ignore error
   */
  function shouldIgnoreError(error) {
    const message = error.message || '';

    // Check ignore patterns
    for (const pattern of config.ignoreErrors) {
      if (pattern instanceof RegExp) {
        if (pattern.test(message)) return true;
      } else if (typeof pattern === 'string') {
        if (message.includes(pattern)) return true;
      }
    }

    return false;
  }

  /**
   * Should sample error
   */
  function shouldSampleError() {
    if (config.sampleRate >= 1.0) return true;
    if (config.sampleRate <= 0) return false;
    return Math.random() < config.sampleRate;
  }

  /**
   * Build error payload
   */
  function buildPayload(error, additionalData = {}) {
    const browser = getBrowserInfo();
    const os = getOSInfo();
    const stackFrames = parseStackTrace(error.stack);

    return {
      // Error info
      name: error.name || 'Error',
      type: error.name || 'Error',
      message: error.message || 'Unknown error',
      stack: error.stack,
      stackFrames,

      // Context
      url: window.location.href,
      service: config.service || window.location.hostname,
      environment: config.environment,
      release: config.release,

      // User
      user: userContext.id || userContext.email ? {
        id: userContext.id,
        email: userContext.email,
        name: userContext.name,
      } : undefined,

      // Browser info
      browser: {
        name: browser.name,
        version: browser.version,
      },

      // OS info
      os: {
        name: os.name,
        version: os.version,
      },

      // Request context
      request: {
        url: window.location.href,
        headers: {
          'User-Agent': navigator.userAgent,
        },
      },

      // Tags
      tags: { ...tagsContext, ...additionalData.tags },

      // Extra data
      extra: { ...extraContext, ...additionalData.extra },
      context: { ...extraContext, ...additionalData.extra },

      // Breadcrumbs
      breadcrumbs: [...breadcrumbs],

      // SDK info
      sdk: {
        name: SDK_NAME,
        version: SDK_VERSION,
      },

      // Timestamp
      timestamp: new Date().toISOString(),
    };
  }

  /**
   * Send error to API
   */
  async function sendError(payload) {
    if (!config.enabled || !config.apiKey) {
      if (config.debug) {
        console.log('[OffCall] SDK disabled or no API key');
      }
      return;
    }

    // Apply beforeSend hook
    if (config.beforeSend) {
      payload = config.beforeSend(payload);
      if (!payload) {
        if (config.debug) {
          console.log('[OffCall] Event dropped by beforeSend');
        }
        return;
      }
    }

    try {
      const response = await fetch(config.endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-API-Key': config.apiKey,
        },
        body: JSON.stringify(payload),
      });

      if (config.debug) {
        if (response.ok) {
          const data = await response.json();
          console.log('[OffCall] Error reported:', data);
        } else {
          console.error('[OffCall] Failed to report error:', response.status);
        }
      }
    } catch (err) {
      if (config.debug) {
        console.error('[OffCall] Failed to send error:', err);
      }
    }
  }

  /**
   * Capture exception
   */
  function captureException(error, additionalData = {}) {
    if (!isInitialized) {
      console.warn('[OffCall] SDK not initialized. Call OffCallErrors.init() first.');
      return;
    }

    if (!(error instanceof Error)) {
      error = new Error(String(error));
    }

    if (shouldIgnoreError(error)) {
      if (config.debug) {
        console.log('[OffCall] Error ignored:', error.message);
      }
      return;
    }

    if (!shouldSampleError()) {
      if (config.debug) {
        console.log('[OffCall] Error sampled out');
      }
      return;
    }

    addBreadcrumb({
      type: 'error',
      category: 'exception',
      message: error.message,
      level: 'error',
    });

    const payload = buildPayload(error, additionalData);
    sendError(payload);
  }

  /**
   * Capture message
   */
  function captureMessage(message, level = 'info', additionalData = {}) {
    if (!isInitialized) {
      console.warn('[OffCall] SDK not initialized. Call OffCallErrors.init() first.');
      return;
    }

    const error = new Error(message);
    error.name = 'Message';

    addBreadcrumb({
      type: 'info',
      category: 'message',
      message: message,
      level: level,
    });

    const payload = buildPayload(error, additionalData);
    payload.level = level;
    sendError(payload);
  }

  /**
   * Global error handler
   */
  function handleGlobalError(event) {
    const error = event.error || new Error(event.message);

    if (event.filename) {
      error.filename = event.filename;
      error.lineno = event.lineno;
      error.colno = event.colno;
    }

    captureException(error, {
      extra: {
        filename: event.filename,
        lineno: event.lineno,
        colno: event.colno,
      },
    });

    // Call original handler if exists
    if (originalOnError) {
      return originalOnError.apply(this, arguments);
    }
  }

  /**
   * Unhandled promise rejection handler
   */
  function handleUnhandledRejection(event) {
    let error;

    if (event.reason instanceof Error) {
      error = event.reason;
    } else {
      error = new Error(String(event.reason));
      error.name = 'UnhandledRejection';
    }

    captureException(error, {
      tags: { mechanism: 'unhandledrejection' },
    });

    // Call original handler if exists
    if (originalOnUnhandledRejection) {
      return originalOnUnhandledRejection.apply(this, arguments);
    }
  }

  /**
   * Setup automatic breadcrumb collection
   */
  function setupBreadcrumbCollection() {
    // Console breadcrumbs
    const originalConsole = {
      log: console.log,
      warn: console.warn,
      error: console.error,
      info: console.info,
    };

    ['log', 'warn', 'error', 'info'].forEach(level => {
      console[level] = function(...args) {
        addBreadcrumb({
          type: 'console',
          category: 'console',
          message: args.map(arg =>
            typeof arg === 'object' ? JSON.stringify(arg) : String(arg)
          ).join(' '),
          level: level === 'warn' ? 'warning' : level,
        });
        return originalConsole[level].apply(console, args);
      };
    });

    // Click breadcrumbs
    document.addEventListener('click', (event) => {
      const target = event.target;
      let selector = target.tagName.toLowerCase();

      if (target.id) {
        selector += `#${target.id}`;
      } else if (target.className) {
        selector += `.${target.className.split(' ').join('.')}`;
      }

      addBreadcrumb({
        type: 'user',
        category: 'ui.click',
        message: `Click on ${selector}`,
        data: {
          selector,
          text: target.innerText?.substring(0, 100),
        },
      });
    }, true);

    // Navigation breadcrumbs
    window.addEventListener('popstate', () => {
      addBreadcrumb({
        type: 'navigation',
        category: 'navigation',
        message: `Navigate to ${window.location.href}`,
        data: {
          from: document.referrer,
          to: window.location.href,
        },
      });
    });

    // XHR breadcrumbs
    const originalXHROpen = XMLHttpRequest.prototype.open;
    const originalXHRSend = XMLHttpRequest.prototype.send;

    XMLHttpRequest.prototype.open = function(method, url) {
      this._offcall = { method, url, startTime: Date.now() };
      return originalXHROpen.apply(this, arguments);
    };

    XMLHttpRequest.prototype.send = function() {
      const xhr = this;

      xhr.addEventListener('loadend', function() {
        const duration = Date.now() - (xhr._offcall?.startTime || Date.now());
        addBreadcrumb({
          type: 'http',
          category: 'xhr',
          message: `${xhr._offcall?.method} ${xhr._offcall?.url}`,
          data: {
            method: xhr._offcall?.method,
            url: xhr._offcall?.url,
            status_code: xhr.status,
            duration,
          },
          level: xhr.status >= 400 ? 'error' : 'info',
        });
      });

      return originalXHRSend.apply(this, arguments);
    };

    // Fetch breadcrumbs
    const originalFetch = window.fetch;
    window.fetch = async function(input, init) {
      const url = typeof input === 'string' ? input : input.url;
      const method = init?.method || 'GET';
      const startTime = Date.now();

      try {
        const response = await originalFetch.apply(this, arguments);
        const duration = Date.now() - startTime;

        addBreadcrumb({
          type: 'http',
          category: 'fetch',
          message: `${method} ${url}`,
          data: {
            method,
            url,
            status_code: response.status,
            duration,
          },
          level: response.status >= 400 ? 'error' : 'info',
        });

        return response;
      } catch (error) {
        addBreadcrumb({
          type: 'http',
          category: 'fetch',
          message: `${method} ${url} - Failed`,
          data: {
            method,
            url,
            error: error.message,
          },
          level: 'error',
        });
        throw error;
      }
    };
  }

  /**
   * Initialize the SDK
   */
  function init(options) {
    if (isInitialized) {
      console.warn('[OffCall] SDK already initialized');
      return;
    }

    if (!options.apiKey) {
      console.error('[OffCall] API key is required');
      return;
    }

    // Merge config
    config = { ...config, ...options };

    // Store original handlers
    originalOnError = window.onerror;
    originalOnUnhandledRejection = window.onunhandledrejection;

    // Setup global error handlers
    window.onerror = handleGlobalError;
    window.addEventListener('unhandledrejection', handleUnhandledRejection);

    // Setup breadcrumb collection
    setupBreadcrumbCollection();

    isInitialized = true;

    if (config.debug) {
      console.log('[OffCall] SDK initialized', config);
    }

    // Add init breadcrumb
    addBreadcrumb({
      type: 'default',
      category: 'sdk',
      message: 'OffCall SDK initialized',
      data: {
        version: SDK_VERSION,
        environment: config.environment,
      },
    });
  }

  /**
   * Set user context
   */
  function setUser(user) {
    userContext = {
      id: user?.id || null,
      email: user?.email || null,
      name: user?.name || user?.username || null,
    };

    addBreadcrumb({
      type: 'user',
      category: 'user',
      message: 'User context updated',
      data: { userId: user?.id },
    });
  }

  /**
   * Clear user context
   */
  function clearUser() {
    userContext = { id: null, email: null, name: null };
  }

  /**
   * Set tags
   */
  function setTags(tags) {
    tagsContext = { ...tagsContext, ...tags };
  }

  /**
   * Set tag
   */
  function setTag(key, value) {
    tagsContext[key] = value;
  }

  /**
   * Set extra context
   */
  function setExtra(key, value) {
    extraContext[key] = value;
  }

  /**
   * Set extras
   */
  function setExtras(extras) {
    extraContext = { ...extraContext, ...extras };
  }

  /**
   * Get current config
   */
  function getConfig() {
    return { ...config };
  }

  /**
   * Check if initialized
   */
  function isReady() {
    return isInitialized;
  }

  // Public API
  const OffCallErrors = {
    init,
    captureException,
    captureMessage,
    addBreadcrumb,
    setUser,
    clearUser,
    setTags,
    setTag,
    setExtra,
    setExtras,
    getConfig,
    isReady,
    SDK_VERSION,
  };

  // Export for different environments
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = OffCallErrors;
  } else if (typeof define === 'function' && define.amd) {
    define([], function() { return OffCallErrors; });
  } else {
    global.OffCallErrors = OffCallErrors;
  }

})(typeof globalThis !== 'undefined' ? globalThis : typeof window !== 'undefined' ? window : this);

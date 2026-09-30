/**
 * OffCall AI - Node.js Error Tracking SDK
 *
 * Usage:
 * const OffCall = require('@offcallai/errors/node');
 *
 * OffCall.init({
 *   apiKey: 'ofc_your_api_key',
 *   environment: 'production',
 * });
 *
 * // Express middleware
 * app.use(OffCall.Handlers.requestHandler());
 * app.use(OffCall.Handlers.errorHandler());
 */

'use strict';

const https = require('https');
const http = require('http');
const { URL } = require('url');

const SDK_NAME = 'offcall-node';
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
  sampleRate: 1.0,
  attachStacktrace: true,
};

// Context
let userContext = {};
let tagsContext = {};
let extraContext = {};
let breadcrumbs = [];
let isInitialized = false;

// Original handlers
let originalUncaughtException = null;
let originalUnhandledRejection = null;

/**
 * Parse stack trace into frames
 */
function parseStackTrace(stack) {
  if (!stack) return [];

  const frames = [];
  const lines = stack.split('\n');

  for (const line of lines) {
    // Node.js format: at functionName (file:line:column)
    let match = line.match(/at\s+(.+?)\s+\((.+?):(\d+):(\d+)\)/);
    if (match) {
      frames.push({
        function: match[1],
        filename: match[2],
        lineno: parseInt(match[3]),
        colno: parseInt(match[4]),
        in_app: !match[2].includes('node_modules') && !match[2].includes('internal/'),
      });
      continue;
    }

    // Anonymous: at file:line:column
    match = line.match(/at\s+(.+?):(\d+):(\d+)/);
    if (match) {
      frames.push({
        function: '<anonymous>',
        filename: match[1],
        lineno: parseInt(match[2]),
        colno: parseInt(match[3]),
        in_app: !match[1].includes('node_modules'),
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

  if (breadcrumbs.length > config.maxBreadcrumbs) {
    breadcrumbs.shift();
  }
}

/**
 * Should ignore error
 */
function shouldIgnoreError(error) {
  const message = error.message || '';

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
 * Should sample
 */
function shouldSample() {
  if (config.sampleRate >= 1.0) return true;
  if (config.sampleRate <= 0) return false;
  return Math.random() < config.sampleRate;
}

/**
 * Build payload
 */
function buildPayload(error, additionalData = {}) {
  const stackFrames = parseStackTrace(error.stack);

  return {
    name: error.name || 'Error',
    type: error.name || 'Error',
    message: error.message || 'Unknown error',
    stack: error.stack,
    stackFrames,

    service: config.service || process.env.SERVICE_NAME || 'node-app',
    environment: config.environment,
    release: config.release,

    user: Object.keys(userContext).length > 0 ? userContext : undefined,

    contexts: {
      runtime: {
        name: 'Node.js',
        version: process.version,
      },
      os: {
        name: process.platform,
        version: process.arch,
      },
      app: {
        app_memory: process.memoryUsage().heapUsed,
      },
    },

    request: additionalData.request || undefined,
    tags: { ...tagsContext, ...additionalData.tags },
    extra: { ...extraContext, ...additionalData.extra },
    breadcrumbs: [...breadcrumbs],

    sdk: {
      name: SDK_NAME,
      version: SDK_VERSION,
    },

    timestamp: new Date().toISOString(),
  };
}

/**
 * Send error to API
 */
function sendError(payload) {
  if (!config.enabled || !config.apiKey) {
    if (config.debug) {
      console.log('[OffCall] SDK disabled or no API key');
    }
    return Promise.resolve();
  }

  if (config.beforeSend) {
    payload = config.beforeSend(payload);
    if (!payload) {
      if (config.debug) {
        console.log('[OffCall] Event dropped by beforeSend');
      }
      return Promise.resolve();
    }
  }

  return new Promise((resolve, reject) => {
    const url = new URL(config.endpoint);
    const data = JSON.stringify(payload);
    const isHttps = url.protocol === 'https:';

    const options = {
      hostname: url.hostname,
      port: url.port || (isHttps ? 443 : 80),
      path: url.pathname + url.search,
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(data),
        'X-API-Key': config.apiKey,
      },
    };

    const req = (isHttps ? https : http).request(options, (res) => {
      let responseData = '';
      res.on('data', (chunk) => {
        responseData += chunk;
      });
      res.on('end', () => {
        if (config.debug) {
          console.log('[OffCall] Error reported:', res.statusCode);
        }
        resolve(responseData);
      });
    });

    req.on('error', (err) => {
      if (config.debug) {
        console.error('[OffCall] Failed to send error:', err);
      }
      resolve(); // Don't reject to avoid crashing
    });

    req.setTimeout(10000, () => {
      req.destroy();
      if (config.debug) {
        console.error('[OffCall] Request timeout');
      }
      resolve();
    });

    req.write(data);
    req.end();
  });
}

/**
 * Capture exception
 */
function captureException(error, additionalData = {}) {
  if (!isInitialized) {
    console.warn('[OffCall] SDK not initialized');
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

  if (!shouldSample()) {
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
  return sendError(payload);
}

/**
 * Capture message
 */
function captureMessage(message, level = 'info', additionalData = {}) {
  if (!isInitialized) {
    console.warn('[OffCall] SDK not initialized');
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
  return sendError(payload);
}

/**
 * Global error handlers
 */
function setupGlobalHandlers() {
  // Uncaught exceptions
  originalUncaughtException = process.listeners('uncaughtException').slice();
  process.removeAllListeners('uncaughtException');

  process.on('uncaughtException', (error) => {
    captureException(error, { tags: { mechanism: 'uncaughtException' } });

    // Call original handlers
    originalUncaughtException.forEach((handler) => handler(error));

    // Exit if no other handlers
    if (originalUncaughtException.length === 0) {
      console.error('Uncaught Exception:', error);
      process.exit(1);
    }
  });

  // Unhandled rejections
  originalUnhandledRejection = process.listeners('unhandledRejection').slice();
  process.removeAllListeners('unhandledRejection');

  process.on('unhandledRejection', (reason, promise) => {
    const error = reason instanceof Error ? reason : new Error(String(reason));
    error.name = 'UnhandledRejection';
    captureException(error, { tags: { mechanism: 'unhandledRejection' } });

    // Call original handlers
    originalUnhandledRejection.forEach((handler) => handler(reason, promise));
  });
}

/**
 * Initialize SDK
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

  config = { ...config, ...options };

  setupGlobalHandlers();

  isInitialized = true;

  if (config.debug) {
    console.log('[OffCall] Node.js SDK initialized', config);
  }

  addBreadcrumb({
    type: 'default',
    category: 'sdk',
    message: 'OffCall SDK initialized',
    data: { version: SDK_VERSION, environment: config.environment },
  });
}

/**
 * Set user context
 */
function setUser(user) {
  userContext = user || {};
  addBreadcrumb({
    type: 'user',
    category: 'user',
    message: 'User context updated',
    data: { userId: user?.id },
  });
}

function clearUser() {
  userContext = {};
}

function setTags(tags) {
  tagsContext = { ...tagsContext, ...tags };
}

function setTag(key, value) {
  tagsContext[key] = value;
}

function setExtra(key, value) {
  extraContext[key] = value;
}

function setExtras(extras) {
  extraContext = { ...extraContext, ...extras };
}

function getConfig() {
  return { ...config };
}

function isReady() {
  return isInitialized;
}

/**
 * Express/Connect middleware handlers
 */
const Handlers = {
  /**
   * Request handler - adds request context to errors
   */
  requestHandler(options = {}) {
    return (req, res, next) => {
      // Add request breadcrumb
      addBreadcrumb({
        type: 'http',
        category: 'request',
        message: `${req.method} ${req.url}`,
        data: {
          method: req.method,
          url: req.url,
          headers: options.includeHeaders ? req.headers : undefined,
        },
      });

      // Store request on response for error handler
      res.__offcall_req = {
        method: req.method,
        url: req.url,
        headers: req.headers,
        query: req.query,
        body: options.includeBody ? req.body : undefined,
        ip: req.ip || req.connection?.remoteAddress,
      };

      next();
    };
  },

  /**
   * Error handler - captures errors
   */
  errorHandler(options = {}) {
    return (err, req, res, next) => {
      const request = res.__offcall_req || {
        method: req.method,
        url: req.url,
        headers: req.headers,
      };

      captureException(err, { request });

      if (options.shouldHandleError !== false) {
        next(err);
      } else {
        res.status(500).json({ error: 'Internal Server Error' });
      }
    };
  },
};

/**
 * Koa middleware
 */
function koaMiddleware(options = {}) {
  return async (ctx, next) => {
    addBreadcrumb({
      type: 'http',
      category: 'request',
      message: `${ctx.method} ${ctx.url}`,
      data: { method: ctx.method, url: ctx.url },
    });

    try {
      await next();
    } catch (err) {
      captureException(err, {
        request: {
          method: ctx.method,
          url: ctx.url,
          headers: ctx.headers,
          query: ctx.query,
        },
      });
      throw err;
    }
  };
}

/**
 * Fastify plugin
 */
function fastifyPlugin(fastify, options, done) {
  fastify.addHook('onRequest', async (request, reply) => {
    addBreadcrumb({
      type: 'http',
      category: 'request',
      message: `${request.method} ${request.url}`,
      data: { method: request.method, url: request.url },
    });
  });

  fastify.setErrorHandler(async (error, request, reply) => {
    await captureException(error, {
      request: {
        method: request.method,
        url: request.url,
        headers: request.headers,
        query: request.query,
      },
    });
    throw error;
  });

  done();
}

fastifyPlugin[Symbol.for('skip-override')] = true;

// Export
module.exports = {
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
  Handlers,
  koaMiddleware,
  fastifyPlugin,
  SDK_VERSION,
};

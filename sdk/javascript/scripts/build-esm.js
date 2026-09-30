/**
 * Build ESM version of OffCall SDK
 */
const fs = require('fs');
const path = require('path');

const inputPath = path.join(__dirname, '..', 'offcall-errors.js');
const outputPath = path.join(__dirname, '..', 'dist', 'offcall-errors.esm.js');

// Read the IIFE version
let code = fs.readFileSync(inputPath, 'utf8');

// Extract the OffCallErrors object definition
const esmCode = `/**
 * OffCall AI - JavaScript Error Tracking SDK (ESM)
 * @offcallai/errors
 */

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

let userContext = { id: null, email: null, name: null };
let tagsContext = {};
let extraContext = {};
let breadcrumbs = [];
let isInitialized = false;
let originalOnError = null;
let originalOnUnhandledRejection = null;

function getBrowserInfo() {
  const ua = navigator.userAgent;
  let browser = { name: 'Unknown', version: '0' };
  if (ua.indexOf('Firefox') > -1) {
    browser.name = 'Firefox';
    browser.version = ua.match(/Firefox\\/(\\d+)/)?.[1] || '0';
  } else if (ua.indexOf('Chrome') > -1 && ua.indexOf('Edg') === -1) {
    browser.name = 'Chrome';
    browser.version = ua.match(/Chrome\\/(\\d+)/)?.[1] || '0';
  } else if (ua.indexOf('Safari') > -1 && ua.indexOf('Chrome') === -1) {
    browser.name = 'Safari';
    browser.version = ua.match(/Version\\/(\\d+)/)?.[1] || '0';
  } else if (ua.indexOf('Edg') > -1) {
    browser.name = 'Edge';
    browser.version = ua.match(/Edg\\/(\\d+)/)?.[1] || '0';
  }
  return browser;
}

function getOSInfo() {
  const ua = navigator.userAgent;
  let os = { name: 'Unknown', version: '0' };
  if (ua.indexOf('Windows') > -1) {
    os.name = 'Windows';
  } else if (ua.indexOf('Mac') > -1) {
    os.name = 'macOS';
  } else if (ua.indexOf('Linux') > -1) {
    os.name = 'Linux';
  } else if (ua.indexOf('Android') > -1) {
    os.name = 'Android';
  } else if (ua.indexOf('iOS') > -1 || ua.indexOf('iPhone') > -1) {
    os.name = 'iOS';
  }
  return os;
}

function parseStackTrace(stack) {
  if (!stack) return [];
  const frames = [];
  const lines = stack.split('\\n');
  for (const line of lines) {
    let match = line.match(/at\\s+(.+?)\\s+\\((.+?):(\\d+):(\\d+)\\)/);
    if (match) {
      frames.push({
        function: match[1],
        filename: match[2],
        lineno: parseInt(match[3]),
        colno: parseInt(match[4]),
        in_app: !match[2].includes('node_modules')
      });
    }
  }
  return frames;
}

export function addBreadcrumb(crumb) {
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

function shouldIgnoreError(error) {
  const message = error.message || '';
  for (const pattern of config.ignoreErrors) {
    if (pattern instanceof RegExp && pattern.test(message)) return true;
    if (typeof pattern === 'string' && message.includes(pattern)) return true;
  }
  return false;
}

function shouldSampleError() {
  if (config.sampleRate >= 1.0) return true;
  if (config.sampleRate <= 0) return false;
  return Math.random() < config.sampleRate;
}

function buildPayload(error, additionalData = {}) {
  const browser = getBrowserInfo();
  const os = getOSInfo();
  const stackFrames = parseStackTrace(error.stack);
  return {
    name: error.name || 'Error',
    type: error.name || 'Error',
    message: error.message || 'Unknown error',
    stack: error.stack,
    stackFrames,
    url: window.location.href,
    service: config.service || window.location.hostname,
    environment: config.environment,
    release: config.release,
    user: userContext.id || userContext.email ? { ...userContext } : undefined,
    browser: { name: browser.name, version: browser.version },
    os: { name: os.name, version: os.version },
    request: { url: window.location.href, headers: { 'User-Agent': navigator.userAgent } },
    tags: { ...tagsContext, ...additionalData.tags },
    extra: { ...extraContext, ...additionalData.extra },
    breadcrumbs: [...breadcrumbs],
    sdk: { name: SDK_NAME, version: SDK_VERSION },
    timestamp: new Date().toISOString(),
  };
}

async function sendError(payload) {
  if (!config.enabled || !config.apiKey) return;
  if (config.beforeSend) {
    payload = config.beforeSend(payload);
    if (!payload) return;
  }
  try {
    await fetch(config.endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-API-Key': config.apiKey },
      body: JSON.stringify(payload),
    });
  } catch (err) {
    if (config.debug) console.error('[OffCall] Failed to send:', err);
  }
}

export function captureException(error, additionalData = {}) {
  if (!isInitialized) {
    console.warn('[OffCall] SDK not initialized');
    return;
  }
  if (!(error instanceof Error)) error = new Error(String(error));
  if (shouldIgnoreError(error) || !shouldSampleError()) return;
  addBreadcrumb({ type: 'error', category: 'exception', message: error.message, level: 'error' });
  const payload = buildPayload(error, additionalData);
  sendError(payload);
}

export function captureMessage(message, level = 'info', additionalData = {}) {
  if (!isInitialized) {
    console.warn('[OffCall] SDK not initialized');
    return;
  }
  const error = new Error(message);
  error.name = 'Message';
  addBreadcrumb({ type: 'info', category: 'message', message, level });
  const payload = buildPayload(error, additionalData);
  payload.level = level;
  sendError(payload);
}

function handleGlobalError(event) {
  const error = event.error || new Error(event.message);
  captureException(error, { extra: { filename: event.filename, lineno: event.lineno, colno: event.colno } });
  if (originalOnError) return originalOnError.apply(this, arguments);
}

function handleUnhandledRejection(event) {
  let error = event.reason instanceof Error ? event.reason : new Error(String(event.reason));
  error.name = 'UnhandledRejection';
  captureException(error, { tags: { mechanism: 'unhandledrejection' } });
  if (originalOnUnhandledRejection) return originalOnUnhandledRejection.apply(this, arguments);
}

export function init(options) {
  if (isInitialized) {
    console.warn('[OffCall] SDK already initialized');
    return;
  }
  if (!options.apiKey) {
    console.error('[OffCall] API key is required');
    return;
  }
  config = { ...config, ...options };
  originalOnError = window.onerror;
  originalOnUnhandledRejection = window.onunhandledrejection;
  window.onerror = handleGlobalError;
  window.addEventListener('unhandledrejection', handleUnhandledRejection);
  isInitialized = true;
  if (config.debug) console.log('[OffCall] SDK initialized', config);
  addBreadcrumb({ type: 'default', category: 'sdk', message: 'OffCall SDK initialized', data: { version: SDK_VERSION } });
}

export function setUser(user) {
  userContext = { id: user?.id || null, email: user?.email || null, name: user?.name || user?.username || null };
  addBreadcrumb({ type: 'user', category: 'user', message: 'User context updated', data: { userId: user?.id } });
}

export function clearUser() {
  userContext = { id: null, email: null, name: null };
}

export function setTags(tags) {
  tagsContext = { ...tagsContext, ...tags };
}

export function setTag(key, value) {
  tagsContext[key] = value;
}

export function setExtra(key, value) {
  extraContext[key] = value;
}

export function setExtras(extras) {
  extraContext = { ...extraContext, ...extras };
}

export function getConfig() {
  return { ...config };
}

export function isReady() {
  return isInitialized;
}

export { SDK_VERSION };

export default {
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
`;

// Write ESM version
fs.writeFileSync(outputPath, esmCode);
console.log('ESM build complete:', outputPath);

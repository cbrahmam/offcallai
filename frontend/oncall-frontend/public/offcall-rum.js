/**
 * OffCall AI - Browser RUM (Real User Monitoring) SDK
 * Lightweight SDK for capturing Core Web Vitals, page views, JS errors,
 * user sessions, and user actions.
 *
 * Usage:
 * <script src="/path/to/offcall-rum.js"></script>
 * <script>
 *   OffCallRUM.init({
 *     apiKey: 'rum_your_api_key',
 *     appName: 'my-app',
 *     endpoint: 'https://your-backend/api/v1/rum/ingest/batch',
 *     environment: 'production',
 *     sampleRate: 1.0,
 *     trackErrors: true,
 *     trackPerformance: true,
 *     trackActions: true
 *   });
 * </script>
 */

(function(global) {
  'use strict';

  var SDK_VERSION = '1.0.0';

  var config = {
    apiKey: null,
    appName: 'default',
    endpoint: '/api/v1/rum/ingest/batch',
    environment: 'production',
    sampleRate: 1.0,
    trackErrors: true,
    trackPerformance: true,
    trackActions: true,
    flushInterval: 5000,
    maxBatchSize: 25,
    debug: false
  };

  var sessionId = null;
  var eventQueue = [];
  var flushTimer = null;
  var initialized = false;
  var lastUrl = '';
  var pageEntryTime = 0;
  var vitals = {};

  // --- Utilities ---

  function generateId() {
    var chars = 'abcdef0123456789';
    var id = '';
    for (var i = 0; i < 32; i++) {
      id += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return id;
  }

  function getSessionId() {
    if (sessionId) return sessionId;
    try {
      sessionId = sessionStorage.getItem('offcall_rum_sid');
      if (!sessionId) {
        sessionId = generateId();
        sessionStorage.setItem('offcall_rum_sid', sessionId);
      }
    } catch (e) {
      sessionId = generateId();
    }
    return sessionId;
  }

  function log() {
    if (config.debug && typeof console !== 'undefined') {
      console.log.apply(console, ['[OffCallRUM]'].concat(Array.prototype.slice.call(arguments)));
    }
  }

  function shouldSample() {
    return Math.random() < config.sampleRate;
  }

  function now() {
    return new Date().toISOString();
  }

  function getUrlPath() {
    return location.pathname + location.search;
  }

  function getCssSelector(el) {
    if (!el || !el.tagName) return '';
    var parts = [];
    while (el && el.tagName) {
      var selector = el.tagName.toLowerCase();
      if (el.id) {
        selector += '#' + el.id;
        parts.unshift(selector);
        break;
      }
      if (el.className && typeof el.className === 'string') {
        selector += '.' + el.className.trim().split(/\s+/).join('.');
      }
      parts.unshift(selector);
      el = el.parentElement;
      if (parts.length > 4) break;
    }
    return parts.join(' > ');
  }

  // --- Event Queue ---

  function enqueue(type, data) {
    if (!initialized || !shouldSample()) return;
    eventQueue.push({ type: type, data: data });
    log('Queued', type, data);
    if (eventQueue.length >= config.maxBatchSize) {
      flush();
    }
  }

  function flush() {
    if (eventQueue.length === 0) return;
    var batch = eventQueue.splice(0, config.maxBatchSize);
    var payload = JSON.stringify({
      api_key: config.apiKey,
      session_id: getSessionId(),
      events: batch
    });

    log('Flushing', batch.length, 'events');

    try {
      if (typeof navigator !== 'undefined' && navigator.sendBeacon) {
        var blob = new Blob([payload], { type: 'application/json' });
        var sent = navigator.sendBeacon(config.endpoint, blob);
        if (!sent) sendXHR(payload);
      } else {
        sendXHR(payload);
      }
    } catch (e) {
      log('Flush error', e);
    }
  }

  function sendXHR(payload) {
    try {
      var xhr = new XMLHttpRequest();
      xhr.open('POST', config.endpoint, true);
      xhr.setRequestHeader('Content-Type', 'application/json');
      xhr.send(payload);
    } catch (e) {
      log('XHR error', e);
    }
  }

  // --- Page Views ---

  function trackPageView() {
    var currentUrl = location.href;
    if (currentUrl === lastUrl) return;

    // Record time-on-page for previous page
    if (lastUrl && pageEntryTime) {
      var timeOnPage = Date.now() - pageEntryTime;
      enqueue('pageview', {
        url: lastUrl,
        url_path: lastUrl.replace(location.origin, ''),
        page_title: document.title,
        timestamp: now(),
        time_on_page_ms: timeOnPage
      });
    }

    lastUrl = currentUrl;
    pageEntryTime = Date.now();

    // Send pageview for new page
    var data = {
      url: currentUrl,
      url_path: getUrlPath(),
      page_title: document.title,
      timestamp: now()
    };

    // Attach navigation timing on initial load
    if (typeof performance !== 'undefined' && performance.getEntriesByType) {
      var nav = performance.getEntriesByType('navigation');
      if (nav && nav.length > 0) {
        var t = nav[0];
        data.dns_lookup_ms = Math.round(t.domainLookupEnd - t.domainLookupStart);
        data.tcp_connect_ms = Math.round(t.connectEnd - t.connectStart);
        data.request_time_ms = Math.round(t.responseStart - t.requestStart);
        data.response_time_ms = Math.round(t.responseEnd - t.responseStart);
        data.dom_interactive_ms = Math.round(t.domInteractive);
        data.dom_complete_ms = Math.round(t.domComplete);
        data.load_event_ms = Math.round(t.loadEventEnd);
      }
    }

    enqueue('pageview', data);
  }

  function setupSPATracking() {
    // Listen for History API changes (pushState / replaceState)
    var origPushState = history.pushState;
    var origReplaceState = history.replaceState;

    history.pushState = function() {
      origPushState.apply(this, arguments);
      setTimeout(trackPageView, 0);
    };
    history.replaceState = function() {
      origReplaceState.apply(this, arguments);
      setTimeout(trackPageView, 0);
    };

    window.addEventListener('popstate', function() {
      setTimeout(trackPageView, 0);
    });
  }

  // --- Core Web Vitals ---

  function observeWebVitals() {
    if (typeof PerformanceObserver === 'undefined') return;

    // LCP
    try {
      new PerformanceObserver(function(list) {
        var entries = list.getEntries();
        var last = entries[entries.length - 1];
        if (last) vitals.lcp_ms = Math.round(last.startTime);
      }).observe({ type: 'largest-contentful-paint', buffered: true });
    } catch (e) {}

    // FID
    try {
      new PerformanceObserver(function(list) {
        var entry = list.getEntries()[0];
        if (entry) vitals.fid_ms = Math.round(entry.processingStart - entry.startTime);
      }).observe({ type: 'first-input', buffered: true });
    } catch (e) {}

    // CLS
    try {
      var clsValue = 0;
      new PerformanceObserver(function(list) {
        for (var i = 0; i < list.getEntries().length; i++) {
          var entry = list.getEntries()[i];
          if (!entry.hadRecentInput) {
            clsValue += entry.value;
          }
        }
        vitals.cls = Math.round(clsValue * 1000) / 1000;
      }).observe({ type: 'layout-shift', buffered: true });
    } catch (e) {}

    // FCP
    try {
      new PerformanceObserver(function(list) {
        var entries = list.getEntries();
        for (var i = 0; i < entries.length; i++) {
          if (entries[i].name === 'first-contentful-paint') {
            vitals.fcp_ms = Math.round(entries[i].startTime);
          }
        }
      }).observe({ type: 'paint', buffered: true });
    } catch (e) {}

    // INP (Interaction to Next Paint)
    try {
      var maxINP = 0;
      new PerformanceObserver(function(list) {
        for (var i = 0; i < list.getEntries().length; i++) {
          var dur = list.getEntries()[i].duration;
          if (dur > maxINP) maxINP = dur;
        }
        vitals.inp_ms = Math.round(maxINP);
      }).observe({ type: 'event', buffered: true, durationThreshold: 16 });
    } catch (e) {}

    // TTFB
    try {
      var nav = performance.getEntriesByType('navigation');
      if (nav && nav.length > 0) {
        vitals.ttfb_ms = Math.round(nav[0].responseStart);
      }
    } catch (e) {}
  }

  function sendVitals() {
    if (Object.keys(vitals).length === 0) return;
    var data = {
      url: location.href,
      url_path: getUrlPath(),
      page_title: document.title,
      timestamp: now()
    };
    for (var k in vitals) {
      data[k] = vitals[k];
    }
    enqueue('pageview', data);
  }

  // --- Error Tracking ---

  function setupErrorTracking() {
    window.addEventListener('error', function(event) {
      enqueue('error', {
        error_type: 'uncaught_exception',
        error_name: event.error ? event.error.name : 'Error',
        message: event.message || 'Unknown error',
        stack_trace: event.error ? event.error.stack : '',
        filename: event.filename || '',
        line_number: event.lineno || 0,
        column_number: event.colno || 0,
        url: location.href,
        url_path: getUrlPath(),
        timestamp: now(),
        is_handled: false
      });
    });

    window.addEventListener('unhandledrejection', function(event) {
      var reason = event.reason || {};
      enqueue('error', {
        error_type: 'unhandled_rejection',
        error_name: reason.name || 'UnhandledPromiseRejection',
        message: reason.message || String(reason),
        stack_trace: reason.stack || '',
        url: location.href,
        url_path: getUrlPath(),
        timestamp: now(),
        is_handled: false
      });
    });
  }

  // --- User Actions ---

  function setupActionTracking() {
    document.addEventListener('click', function(event) {
      var el = event.target;
      if (!el || !el.tagName) return;
      var tag = el.tagName.toLowerCase();
      // Only track meaningful clicks
      if (['a', 'button', 'input', 'select', 'textarea'].indexOf(tag) === -1 &&
          !el.getAttribute('role') && !el.closest('button, a, [role="button"]')) {
        return;
      }

      var text = (el.textContent || '').trim().substring(0, 100);

      enqueue('action', {
        action_type: 'click',
        action_name: text || tag,
        target_selector: getCssSelector(el),
        target_tag: tag,
        target_id: el.id || '',
        target_class: (typeof el.className === 'string' ? el.className : '').trim().substring(0, 200),
        target_text: text,
        url: location.href,
        url_path: getUrlPath(),
        page_x: event.pageX,
        page_y: event.pageY,
        timestamp: now()
      });
    }, true);
  }

  // --- Public API ---

  var OffCallRUM = {
    init: function(opts) {
      if (initialized) return;
      if (!opts || !opts.apiKey) {
        log('apiKey is required');
        return;
      }

      for (var key in opts) {
        if (opts.hasOwnProperty(key)) {
          config[key] = opts[key];
        }
      }

      initialized = true;
      getSessionId();

      // Track initial page view
      trackPageView();
      setupSPATracking();

      if (config.trackPerformance) {
        observeWebVitals();
      }

      if (config.trackErrors) {
        setupErrorTracking();
      }

      if (config.trackActions) {
        setupActionTracking();
      }

      // Periodic flush
      flushTimer = setInterval(flush, config.flushInterval);

      // Flush on page unload
      window.addEventListener('visibilitychange', function() {
        if (document.visibilityState === 'hidden') {
          sendVitals();
          flush();
        }
      });

      window.addEventListener('beforeunload', function() {
        sendVitals();
        flush();
      });

      log('Initialized', config.appName, 'v' + SDK_VERSION);
    },

    setUser: function(userId) {
      // Store user ID to attach to error events
      config._userId = userId;
    },

    trackError: function(error, context) {
      enqueue('error', {
        error_type: 'caught_exception',
        error_name: error.name || 'Error',
        message: error.message || String(error),
        stack_trace: error.stack || '',
        url: location.href,
        url_path: getUrlPath(),
        timestamp: now(),
        is_handled: true,
        context: context || {}
      });
    },

    trackAction: function(name, data) {
      enqueue('action', {
        action_type: 'custom',
        action_name: name,
        url: location.href,
        url_path: getUrlPath(),
        timestamp: now(),
        custom_data: data || {}
      });
    },

    flush: flush,

    getSessionId: getSessionId,

    version: SDK_VERSION
  };

  // Export
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = OffCallRUM;
  } else {
    global.OffCallRUM = OffCallRUM;
  }

})(typeof window !== 'undefined' ? window : this);

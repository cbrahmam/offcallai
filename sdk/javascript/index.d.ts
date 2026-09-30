/**
 * OffCall AI JavaScript Error Tracking SDK - TypeScript Definitions
 */

export interface OffCallConfig {
  /** Your OffCall API key (required) */
  apiKey: string;
  /** API endpoint URL */
  endpoint?: string;
  /** Environment name (e.g., 'production', 'staging') */
  environment?: string;
  /** Release/version string */
  release?: string;
  /** Service name */
  service?: string;
  /** Enable debug logging */
  debug?: boolean;
  /** Enable/disable error reporting */
  enabled?: boolean;
  /** Maximum number of breadcrumbs to keep */
  maxBreadcrumbs?: number;
  /** Callback to modify events before sending */
  beforeSend?: (event: ErrorEvent) => ErrorEvent | null;
  /** Error message patterns to ignore */
  ignoreErrors?: (string | RegExp)[];
  /** URL patterns to ignore */
  ignoreUrls?: (string | RegExp)[];
  /** URL patterns to deny */
  denyUrls?: (string | RegExp)[];
  /** URL patterns to allow */
  allowUrls?: (string | RegExp)[];
  /** Sample rate for errors (0.0 to 1.0) */
  sampleRate?: number;
}

export interface User {
  /** User ID */
  id?: string | number;
  /** User email */
  email?: string;
  /** User name */
  name?: string;
  /** Additional user properties */
  [key: string]: any;
}

export interface Breadcrumb {
  /** Timestamp in ISO format */
  timestamp?: string;
  /** Breadcrumb type */
  type?: 'default' | 'http' | 'navigation' | 'user' | 'console' | 'error';
  /** Category for grouping */
  category?: string;
  /** Human-readable message */
  message?: string;
  /** Additional data */
  data?: Record<string, any>;
  /** Severity level */
  level?: 'debug' | 'info' | 'warning' | 'error' | 'fatal';
}

export interface StackFrame {
  /** Function name */
  function?: string;
  /** Filename */
  filename?: string;
  /** Line number */
  lineno?: number;
  /** Column number */
  colno?: number;
  /** Whether this is application code */
  in_app?: boolean;
}

export interface ErrorEvent {
  /** Error name/type */
  name?: string;
  /** Error type */
  type?: string;
  /** Error message */
  message?: string;
  /** Raw stack trace string */
  stack?: string;
  /** Parsed stack frames */
  stackFrames?: StackFrame[];
  /** Current URL */
  url?: string;
  /** Service name */
  service?: string;
  /** Environment */
  environment?: string;
  /** Release version */
  release?: string;
  /** User context */
  user?: User;
  /** Browser info */
  browser?: { name: string; version: string };
  /** OS info */
  os?: { name: string; version: string };
  /** Request context */
  request?: Record<string, any>;
  /** Tags */
  tags?: Record<string, string>;
  /** Extra context */
  extra?: Record<string, any>;
  /** Breadcrumbs */
  breadcrumbs?: Breadcrumb[];
  /** SDK info */
  sdk?: { name: string; version: string };
  /** Timestamp in ISO format */
  timestamp?: string;
  /** Severity level */
  level?: string;
}

export interface AdditionalData {
  /** Tags to add */
  tags?: Record<string, string>;
  /** Extra context to add */
  extra?: Record<string, any>;
}

/**
 * Initialize the OffCall SDK
 * @param options Configuration options
 */
export function init(options: OffCallConfig): void;

/**
 * Capture an exception and send it to OffCall
 * @param error The error to capture
 * @param additionalData Additional context
 */
export function captureException(error: Error | string, additionalData?: AdditionalData): void;

/**
 * Capture a message and send it to OffCall
 * @param message The message to capture
 * @param level Severity level
 * @param additionalData Additional context
 */
export function captureMessage(
  message: string,
  level?: 'debug' | 'info' | 'warning' | 'error' | 'fatal',
  additionalData?: AdditionalData
): void;

/**
 * Add a breadcrumb
 * @param breadcrumb The breadcrumb to add
 */
export function addBreadcrumb(breadcrumb: Breadcrumb): void;

/**
 * Set user context
 * @param user User information
 */
export function setUser(user: User | null): void;

/**
 * Clear user context
 */
export function clearUser(): void;

/**
 * Set multiple tags
 * @param tags Tags to set
 */
export function setTags(tags: Record<string, string>): void;

/**
 * Set a single tag
 * @param key Tag key
 * @param value Tag value
 */
export function setTag(key: string, value: string): void;

/**
 * Set extra context value
 * @param key Context key
 * @param value Context value
 */
export function setExtra(key: string, value: any): void;

/**
 * Set multiple extra context values
 * @param extras Extra context to set
 */
export function setExtras(extras: Record<string, any>): void;

/**
 * Get current configuration
 */
export function getConfig(): OffCallConfig;

/**
 * Check if SDK is initialized
 */
export function isReady(): boolean;

/** SDK version */
export const SDK_VERSION: string;

declare const OffCallErrors: {
  init: typeof init;
  captureException: typeof captureException;
  captureMessage: typeof captureMessage;
  addBreadcrumb: typeof addBreadcrumb;
  setUser: typeof setUser;
  clearUser: typeof clearUser;
  setTags: typeof setTags;
  setTag: typeof setTag;
  setExtra: typeof setExtra;
  setExtras: typeof setExtras;
  getConfig: typeof getConfig;
  isReady: typeof isReady;
  SDK_VERSION: string;
};

export default OffCallErrors;

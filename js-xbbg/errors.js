'use strict';

/**
 * Base error class for all Bloomberg API errors.
 * All xbbg errors inherit from BlpError, allowing users to catch all
 * Bloomberg-related errors with a single except clause.
 */
class BlpError extends Error {
  constructor(message) {
    super(message);
    this.name = this.constructor.name;
  }
}

/**
 * Session lifecycle errors (start, connect, service open).
 */
class BlpSessionError extends BlpError {}

/**
 * Request-level errors from the Bloomberg API.
 * 
 * Attributes:
 *   service: The Bloomberg service URI (e.g., "//blp/refdata").
 *   operation: The request operation name (e.g., "ReferenceDataRequest").
 *   request_id: Optional correlation ID for debugging.
 *   code: Optional Bloomberg error code.
 */
class BlpRequestError extends BlpError {
  constructor(message, options = {}) {
    super(message);
    this.service = options.service;
    this.operation = options.operation;
    this.request_id = options.request_id;
    this.code = options.code;
  }
}

/**
 * Request validation errors.
 * 
 * Raised when request parameters fail validation against Bloomberg schemas.
 * Includes helpful suggestions for typos and invalid enum values.
 * 
 * Attributes:
 *   element: The element name that caused the error (if available).
 *   suggestion: Suggested correction for typos (if available).
 */
class BlpValidationError extends BlpError {
  constructor(message, options = {}) {
    super(message);
    this.element = options.element;
    this.suggestion = options.suggestion;
  }
}

/**
 * Request timeout.
 */
class BlpTimeoutError extends BlpError {}

/**
 * Internal errors (should not happen in normal operation).
 * If you encounter this error, please report it as a bug.
 */
class BlpInternalError extends BlpError {}

/**
 * Wraps a native NAPI error into the appropriate xbbg error class.
 * 
 * Pattern-matches on error message to determine the error type.
 * 
 * @param {Error} napiError - The native NAPI error to wrap
 * @returns {BlpError} - An instance of the appropriate error class
 */
function wrapError(napiError) {
  const msg = napiError.message || '';

  // Session errors
  if (msg.includes('Session start failed') || msg.includes('Failed to open service')) {
    return new BlpSessionError(msg);
  }

  // Request errors
  if (msg.includes('Request failed') || msg.includes('Subscription failed')) {
    const options = {};
    
    // Parse service and operation from "Request failed on {service}::{op}"
    const serviceOpMatch = msg.match(/on ([^:]+)::([^ (]+)/);
    if (serviceOpMatch) {
      options.service = serviceOpMatch[1];
      options.operation = serviceOpMatch[2];
    }
    
    return new BlpRequestError(msg, options);
  }

  // Validation errors
  if (
    msg.includes('Invalid argument') ||
    msg.includes('Configuration error') ||
    msg.includes('Operation not found') ||
    msg.includes('Schema element not found') ||
    msg.includes('Schema type mismatch') ||
    msg.includes('Unsupported schema') ||
    msg.includes('invalid extractor') ||
    msg.includes('(did you mean') // Validation with suggestion
  ) {
    const options = {};
    
    // Parse suggestion from "(did you mean 'xxx'?)" pattern
    const suggestionMatch = msg.match(/\(did you mean '([^']+)'\?\)/);
    if (suggestionMatch) {
      options.suggestion = suggestionMatch[1];
    }
    
    return new BlpValidationError(msg, options);
  }

  // Timeout errors
  if (msg.includes('Request timed out')) {
    return new BlpTimeoutError(msg);
  }

  // Internal errors
  if (
    msg.includes('Internal error') ||
    msg.includes('Channel closed') ||
    msg.includes('Stream buffer full') ||
    msg.includes('Request was cancelled')
  ) {
    return new BlpInternalError(msg);
  }

  // Default fallback
  return new BlpError(msg);
}

module.exports = {
  BlpError,
  BlpSessionError,
  BlpRequestError,
  BlpValidationError,
  BlpTimeoutError,
  BlpInternalError,
  wrapError,
};

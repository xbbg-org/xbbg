export interface BlpRequestErrorOptions {
  readonly service?: string;
  readonly operation?: string;
  readonly request_id?: string;
  readonly code?: string | number;
}

export interface BlpValidationErrorOptions {
  readonly element?: string;
  readonly suggestion?: string;
}

export class BlpError extends Error {
  public constructor(message: string) {
    super(message);
    this.name = new.target.name;
  }
}

export class BlpSessionError extends BlpError {}

export class BlpRequestError extends BlpError {
  public readonly service?: string;
  public readonly operation?: string;
  public readonly request_id?: string;
  public readonly code?: string | number;

  public constructor(message: string, options: BlpRequestErrorOptions = {}) {
    super(message);
    this.service = options.service;
    this.operation = options.operation;
    this.request_id = options.request_id;
    this.code = options.code;
  }
}

export class BlpValidationError extends BlpError {
  public readonly element?: string;
  public readonly suggestion?: string;

  public constructor(message: string, options: BlpValidationErrorOptions = {}) {
    super(message);
    this.element = options.element;
    this.suggestion = options.suggestion;
  }
}

export class BlpTimeoutError extends BlpError {}

export class BlpInternalError extends BlpError {}

export function wrapError(napiError: unknown): BlpError {
  if (napiError instanceof BlpError) {
    return napiError;
  }
  const msg =
    napiError instanceof Error ? napiError.message : typeof napiError === 'string' ? napiError : '';

  // Session errors
  if (
    msg.includes('Session start failed') ||
    msg.includes('session start failed') ||
    msg.includes('Failed to start session') ||
    msg.includes('Failed to open service') ||
    msg.includes('failed to spawn worker') ||
    msg.includes('connect event failed')
  ) {
    return new BlpSessionError(msg);
  }

  // Request errors
  if (msg.includes('Request failed') || msg.includes('Subscription failed')) {
    const options: BlpRequestErrorOptions = parseRequestOptions(msg);
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
    msg.includes('(did you mean')
  ) {
    const options: BlpValidationErrorOptions = parseValidationOptions(msg);
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

  return new BlpError(msg);
}

function parseRequestOptions(msg: string): BlpRequestErrorOptions {
  const options: {
    service?: string;
    operation?: string;
    request_id?: string;
    code?: string | number;
  } = {};
  const serviceOpMatch = /on ([^:]+)::([^ (]+)/u.exec(msg);
  if (serviceOpMatch !== null) {
    options.service = serviceOpMatch[1];
    options.operation = serviceOpMatch[2];
  }
  const requestIdMatch = /\[request_id=([^\]]+)\]/u.exec(msg);
  if (requestIdMatch !== null) {
    options.request_id = requestIdMatch[1];
  }
  return options;
}

function parseValidationOptions(msg: string): BlpValidationErrorOptions {
  const options: { element?: string; suggestion?: string } = {};
  const suggestionMatch = /\(did you mean '([^']+)'\?\)/u.exec(msg);
  if (suggestionMatch !== null) {
    options.suggestion = suggestionMatch[1];
  }
  return options;
}

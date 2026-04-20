import { describe, expect, it } from 'vitest';

import * as api from '../src/index';

const SESSION_HOST = process.env['XBBG_HOST'] ?? 'localhost';
const SESSION_PORT = Number(process.env['XBBG_PORT'] ?? 8194);

function nativeUnavailable(err: unknown): boolean {
  const message = err instanceof Error ? err.message : String(err);
  return (
    message.includes('Unable to load native napi-xbbg module') ||
    message.toLowerCase().includes('session start failed') ||
    message.toLowerCase().includes('failed to spawn worker')
  );
}

describe('@xbbg/core surface', () => {
  it('exposes all public exports', () => {
    const required = [
      'Engine',
      'Subscription',
      'connect',
      'configure',
      'blp',
      'ext',
      'Backend',
      'Format',
      'bdp',
      'bdh',
      'bds',
      'bdib',
      'bdtick',
      'subscribe',
      'abdp',
      'abdh',
      'abds',
      'abdib',
      'abdtick',
      'asubscribe',
      'BlpError',
      'BlpSessionError',
      'BlpRequestError',
      'BlpValidationError',
      'BlpTimeoutError',
      'BlpInternalError',
      'wrapError',
      'version',
      'setLogLevel',
      'getLogLevel',
    ] as const;
    for (const key of required) {
      expect(api, `Missing export: ${key}`).toHaveProperty(key);
    }
  });

  it('Backend enum is frozen with correct values', () => {
    expect(Object.isFrozen(api.Backend)).toBe(true);
    expect(api.Backend.ARROW).toBe('arrow');
    expect(api.Backend.JSON).toBe('json');
    expect(api.Backend.POLARS).toBe('polars');
    expect(Object.keys(api.Backend)).toHaveLength(3);
  });

  it('Format enum is frozen with correct values', () => {
    expect(Object.isFrozen(api.Format)).toBe(true);
    expect(api.Format.LONG).toBe('long');
    expect(api.Format.LONG_TYPED).toBe('long_typed');
    expect(api.Format.LONG_WITH_METADATA).toBe('long_with_metadata');
    expect(api.Format.SEMI_LONG).toBe('semi_long');
    expect(Object.keys(api.Format)).toHaveLength(4);
  });

  it('has a correct error class hierarchy', () => {
    expect(api.BlpError.prototype).toBeInstanceOf(Error);
    expect(api.BlpSessionError.prototype).toBeInstanceOf(api.BlpError);
    expect(api.BlpRequestError.prototype).toBeInstanceOf(api.BlpError);
    expect(api.BlpValidationError.prototype).toBeInstanceOf(api.BlpError);
    expect(api.BlpTimeoutError.prototype).toBeInstanceOf(api.BlpError);
    expect(api.BlpInternalError.prototype).toBeInstanceOf(api.BlpError);
  });

  it('sets the .name property on error instances', () => {
    expect(new api.BlpError('test').name).toBe('BlpError');
    expect(new api.BlpSessionError('test').name).toBe('BlpSessionError');
    expect(new api.BlpRequestError('test').name).toBe('BlpRequestError');
    expect(new api.BlpValidationError('test').name).toBe('BlpValidationError');
    expect(new api.BlpTimeoutError('test').name).toBe('BlpTimeoutError');
    expect(new api.BlpInternalError('test').name).toBe('BlpInternalError');
  });

  it('BlpRequestError carries optional properties', () => {
    const err = new api.BlpRequestError('test', {
      service: '//blp/refdata',
      operation: 'BDP',
      code: 123,
    });
    expect(err.service).toBe('//blp/refdata');
    expect(err.operation).toBe('BDP');
    expect(err.code).toBe(123);
  });

  it('BlpValidationError carries optional properties', () => {
    const err = new api.BlpValidationError('test', {
      element: 'field1',
      suggestion: 'PX_LAST',
    });
    expect(err.element).toBe('field1');
    expect(err.suggestion).toBe('PX_LAST');
  });

  it('wrapError maps NAPI error prefixes to correct classes', () => {
    const wrapCases: [string, new (...args: any[]) => Error][] = [
      ['Session start failed: x', api.BlpSessionError],
      ['Failed to open service: x', api.BlpSessionError],
      ['Request failed: x', api.BlpRequestError],
      ['Subscription failed: x', api.BlpRequestError],
      ['Invalid argument: x', api.BlpValidationError],
      ['Request timed out', api.BlpTimeoutError],
      ['Internal error: x', api.BlpInternalError],
      ['some unknown error', api.BlpError],
    ];
    for (const [msg, Cls] of wrapCases) {
      expect(api.wrapError(new Error(msg))).toBeInstanceOf(Cls);
    }
  });

  it('exposes version, connect, setLogLevel, getLogLevel as functions', () => {
    expect(typeof api.connect).toBe('function');
    expect(typeof api.version).toBe('function');
    expect(typeof api.setLogLevel).toBe('function');
    expect(typeof api.getLogLevel).toBe('function');
    expect(typeof api.version()).toBe('string');
    expect(api.version().length).toBeGreaterThan(0);
  });

  it('configure accepts both flat and nested config shapes', () => {
    expect(api.configure({ host: SESSION_HOST, port: SESSION_PORT })).toEqual({
      host: SESSION_HOST,
      port: SESSION_PORT,
    });
    const advanced = {
      servers: [
        { host: 'primary.example.com', port: 8194 },
        { host: 'secondary.example.com', port: 8196 },
      ],
      auth: { method: 'userapp' as const, appName: 'my-bpipe-app' },
      tls: {
        clientCredentials: '/secure/client.p12',
        trustMaterial: '/secure/trust.p7',
      },
      zfpRemote: '8194' as const,
      retryPolicy: {
        maxRetries: 2,
        initialDelayMs: 100,
        backoffFactor: 1.5,
        maxDelayMs: 1000,
      },
      socks5: { host: 'proxy.example.com', port: 1080 },
    };
    expect(api.configure(advanced)).toEqual(advanced);
    expect(api.configure(SESSION_HOST, SESSION_PORT)).toEqual({
      host: SESSION_HOST,
      port: SESSION_PORT,
    });
  });

  it('blp namespace exposes Python-style helpers', () => {
    const methods = [
      'bdp',
      'bdh',
      'bds',
      'bdib',
      'bdtick',
      'subscribe',
      'abdp',
      'abdh',
      'abds',
      'abdib',
      'abdtick',
      'asubscribe',
    ] as const;
    for (const m of methods) {
      expect(typeof api.blp[m]).toBe('function');
    }
  });

  it('ext.cdx namespace exposes acdx_* helpers', () => {
    for (const m of ['acdx_info', 'acdx_pricing', 'acdx_risk'] as const) {
      expect(typeof (api.ext.cdx as any)[m]).toBe('function');
    }
  });
});

describe('Engine instantiation', () => {
  it('new Engine(host, port) exposes expected methods', () => {
    try {
      const engine: any = new api.Engine(SESSION_HOST, SESSION_PORT);
      expect(engine).toBeInstanceOf(api.Engine);
      const asyncMethods = [
        'bdp',
        'bds',
        'bdh',
        'bdib',
        'bdtick',
        'bql',
        'beqs',
        'bsrch',
        'bta',
        'bflds',
        'blkp',
        'bport',
        'bcurves',
        'bgovts',
        'stream',
        'vwap',
        'mktbar',
        'depth',
        'chains',
        'bops',
        'bschema',
        'fieldInfo',
        'fieldSearch',
        'bqr',
        'yas',
        'preferreds',
        'corporateBonds',
        'futTicker',
        'activeFutures',
        'cdxTicker',
        'activeCdx',
        'dividend',
        'turnover',
        'etfHoldings',
        'currencyConversion',
        'subscribe',
        'subscribeWithOptions',
        'request',
        'requestRaw',
        'resolveFieldTypes',
      ];
      for (const method of asyncMethods) {
        expect(typeof engine[method]).toBe('function');
      }
      const syncMethods = [
        'getFieldInfo',
        'clearFieldCache',
        'saveFieldCache',
        'validateFields',
        'isFieldValidationEnabled',
        'getSchema',
        'getOperation',
        'listOperations',
        'getCachedSchema',
        'invalidateSchema',
        'clearSchemaCache',
        'listCachedSchemas',
        'getEnumValues',
        'listValidElements',
        'signalShutdown',
        'isAvailable',
      ];
      for (const method of syncMethods) {
        expect(typeof engine[method]).toBe('function');
      }
    } catch (err) {
      if (nativeUnavailable(err)) {
        console.warn('Engine instantiation skipped: native module or session unavailable');
        return;
      }
      throw err;
    }
  });

  it('Engine.withConfig returns an Engine', () => {
    try {
      const engine = api.Engine.withConfig({ host: SESSION_HOST, port: SESSION_PORT });
      expect(engine).toBeInstanceOf(api.Engine);
    } catch (err) {
      if (nativeUnavailable(err)) {
        console.warn('Engine.withConfig skipped: native module or session unavailable');
        return;
      }
      throw err;
    }
  });

  it('Subscription prototype exposes async iterator + methods', () => {
    const subProto = api.Subscription.prototype as any;
    expect(typeof subProto.next).toBe('function');
    expect(typeof subProto.add).toBe('function');
    expect(typeof subProto.remove).toBe('function');
    expect(typeof subProto.unsubscribe).toBe('function');
    expect(typeof subProto[Symbol.asyncIterator]).toBe('function');
  });
});

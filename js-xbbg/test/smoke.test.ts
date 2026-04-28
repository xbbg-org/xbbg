import { describe, expect, it } from 'vitest';

import type { NativeArrowZeroCopyBatch } from '../src/napi';
import { tableFromNativeArrowBatch } from '../src/arrow-zero-copy';
import type { RequestInput } from '../src/types';
import * as api from '../src/index';

const SESSION_HOST = process.env.XBBG_HOST ?? 'localhost';
const SESSION_PORT = Number(process.env.XBBG_PORT ?? 8194);

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

  it('wrapError preserves typed errors', () => {
    const err = new api.BlpValidationError('typed validation');
    expect(api.wrapError(err)).toBe(err);
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

describe('conflated market data options', () => {
  function fakeNativeSubscription(): any {
    return {
      add: async () => undefined,
      remove: async () => undefined,
      nextUpdate: async () => null,
      nextArrow: async () => null,
      unsubscribe: async () => [],
      unsubscribeArrow: async () => [],
      tickers: ['ES1 Index'],
      fields: ['BID', 'ASK'],
      isActive: true,
      stats: {
        messagesReceived: 0,
        droppedBatches: 0,
        batchesSent: 0,
        slowConsumer: false,
        dataLossEvents: 0,
        lastMessageUs: 0,
        lastDataLossUs: 0,
        effectiveOverflowPolicy: 'drop_newest',
      },
    };
  }

  function fakeEngine(captured: Record<string, unknown>): api.Engine {
    const engine = Object.create(api.Engine.prototype) as api.Engine;
    (engine as unknown as { _inner: unknown })._inner = {
      subscribe: async (tickers: readonly string[], fields: readonly string[], allFields?: boolean) => {
        captured.subscribe = { tickers, fields, allFields };
        return fakeNativeSubscription();
      },
      subscribeWithOptions: async (
        service: string,
        tickers: readonly string[],
        fields: readonly string[],
        options?: readonly string[],
        flushThreshold?: number,
        overflowPolicy?: string,
        streamCapacity?: number,
        allFields?: boolean,
      ) => {
        captured.subscribeWithOptions = {
          service,
          tickers,
          fields,
          options,
          flushThreshold,
          overflowPolicy,
          streamCapacity,
          allFields,
        };
        return fakeNativeSubscription();
      },
    };
    return engine;
  }

  it('adds the conflate Bloomberg option for mktdata subscriptions', async () => {
    const captured: Record<string, unknown> = {};
    await fakeEngine(captured).subscribe(['ES1 Index'], ['BID', 'ASK'], { conflate: true });

    expect(captured.subscribe).toBeUndefined();
    expect(captured.subscribeWithOptions).toMatchObject({
      service: '//blp/mktdata',
      tickers: ['ES1 Index'],
      fields: ['BID', 'ASK'],
      options: ['conflate'],
    });
  });

  it('normalizes ampersand conflate and avoids duplicates', async () => {
    const captured: Record<string, unknown> = {};
    await fakeEngine(captured).subscribe(['ES1 Index'], ['BID', 'ASK'], {
      options: ['&conflate'],
      conflate: true,
    });

    expect(captured.subscribeWithOptions).toMatchObject({
      options: ['conflate'],
    });
  });

  it('rejects conflate for non-mktdata helpers', async () => {
    await expect(
      fakeEngine({}).vwap(['IBM US Equity'], ['VWAP'], { conflate: true }),
    ).rejects.toBeInstanceOf(api.BlpValidationError);
  });

  it('rejects conflate with interval options', async () => {
    await expect(
      fakeEngine({}).subscribe(['ES1 Index'], ['BID', 'ASK'], {
        options: ['interval=5'],
        conflate: true,
      }),
    ).rejects.toBeInstanceOf(api.BlpValidationError);
  });
});


describe('native Arrow zero-copy table construction', () => {
  function typedBuffer(view: ArrayBufferView): Buffer {
    return Buffer.from(view.buffer, view.byteOffset, view.byteLength);
  }

  it('constructs an Arrow table from native buffer descriptors', () => {
    const prices = new Float64Array([50000.5, 0]);
    const sizes = new Int32Array([10, 20]);
    const offsets = new Int32Array([0, 13, 26]);
    const text = Buffer.from('XBTUSD CurncyIBM US Equity');
    const updateTime = new BigInt64Array([45_000_000_000n, 45_000_001_000n]);
    const quantities = new Uint32Array([1, 4_000_000_000]);
    const yields = new Float32Array([1.25, 2.5]);
    const tradeDates = new BigInt64Array([1_700_000_000_000n, 1_700_086_400_000n]);
    const binaryOffsets = new Int32Array([0, 2, 5]);
    const binaryValues = Buffer.from([0xde, 0xad, 0xbe, 0xef, 0x01]);
    const batch: NativeArrowZeroCopyBatch = {
      kind: 'zeroCopy',
      numRows: 2,
      columns: [
        {
          name: 'topic',
          type: 'utf8',
          nullable: false,
          length: 2,
          nullCount: 0,
          offsets: typedBuffer(offsets),
          data: text,
        },
        {
          name: 'LAST_PRICE',
          type: 'float64',
          nullable: true,
          length: 2,
          nullCount: 1,
          nullBitmap: Buffer.from([0b00000001]),
          data: typedBuffer(prices),
        },
        {
          name: 'SIZE',
          type: 'int32',
          nullable: false,
          length: 2,
          nullCount: 0,
          data: typedBuffer(sizes),
        },
        {
          name: 'UPDATE_TIME',
          type: 'time64_us',
          nullable: false,
          length: 2,
          nullCount: 0,
          data: typedBuffer(updateTime),
        },
        {
          name: 'QUANTITY',
          type: 'uint32',
          nullable: false,
          length: 2,
          nullCount: 0,
          data: typedBuffer(quantities),
        },
        {
          name: 'YIELD',
          type: 'float32',
          nullable: false,
          length: 2,
          nullCount: 0,
          data: typedBuffer(yields),
        },
        {
          name: 'TRADE_DATE',
          type: 'date64',
          nullable: false,
          length: 2,
          nullCount: 0,
          data: typedBuffer(tradeDates),
        },
        {
          name: 'PAYLOAD',
          type: 'binary',
          nullable: false,
          length: 2,
          nullCount: 0,
          offsets: typedBuffer(binaryOffsets),
          data: binaryValues,
        },
      ],
    };

    const table = tableFromNativeArrowBatch(batch);

    expect(table.numRows).toBe(2);
    expect(table.getChild('topic')?.get(0)).toBe('XBTUSD Curncy');
    expect(table.getChild('topic')?.get(1)).toBe('IBM US Equity');
    expect(table.getChild('LAST_PRICE')?.get(0)).toBe(50000.5);
    expect(table.getChild('LAST_PRICE')?.get(1)).toBeNull();
    expect(table.getChild('SIZE')?.get(1)).toBe(20);
    expect(table.getChild('UPDATE_TIME')?.get(0)).toBe(45_000_000_000n);
    expect(table.getChild('QUANTITY')?.get(1)).toBe(4_000_000_000);
    expect(table.getChild('YIELD')?.get(0)).toBeCloseTo(1.25);
    expect(table.getChild('TRADE_DATE')?.get(0)).toBe(1_700_000_000_000);
    expect(Array.from(table.getChild('PAYLOAD')?.get(1) ?? [])).toEqual([0xbe, 0xef, 0x01]);
  });

  it('Subscription.next uses native updates', async () => {
    const sub = new api.Subscription({
      nextUpdate: async () =>
        await Promise.resolve({
          kind: 'update',
          topic: 'XBTUSD Curncy',
          topicId: 1,
          timestampUs: 123,
          layoutVersion: 1,
          fields: ['answer'],
          values: [42],
          valueKinds: ['i32'],
        }),
      nextArrow: async () => await Promise.resolve(null),
      add: async () => {},
      remove: async () => {},
      unsubscribe: async () => await Promise.resolve(null),
      unsubscribeArrow: async () => await Promise.resolve(null),
      tickers: [],
      fields: [],
      isActive: true,
      stats: { messagesReceived: 0, droppedBatches: 0, batchesSent: 0, slowConsumer: false },
    });

    const result = await sub.next();

    expect(result.done).toBe(false);
    expect(result.value?.topic).toBe('XBTUSD Curncy');
    expect(result.value?.f64('answer')).toBe(42);
  });

  it('Subscription.arrow drains native zero-copy batches', async () => {
    const values = new Int32Array([7]);
    const batch: NativeArrowZeroCopyBatch = {
      kind: 'zeroCopy',
      numRows: 1,
      columns: [
        {
          name: 'answer',
          type: 'int32',
          nullable: false,
          length: 1,
          nullCount: 0,
          data: typedBuffer(values),
        },
      ],
    };
    const sub = new api.Subscription({
      nextUpdate: async () => await Promise.resolve(null),
      nextArrow: async () => await Promise.resolve(null),
      add: async () => {},
      remove: async () => {},
      unsubscribe: async () => await Promise.resolve(null),
      unsubscribeArrow: async (drain) => await Promise.resolve(drain ? [batch] : null),
      tickers: [],
      fields: [],
      isActive: true,
      stats: { messagesReceived: 0, droppedBatches: 0, batchesSent: 0, slowConsumer: false },
    });

    const drained = await sub.arrow().unsubscribe(true);

    expect(drained).toHaveLength(1);
    expect(drained[0]?.getChild('answer')?.get(0)).toBe(7);
  });
});

describe('Engine wrapper request plumbing', () => {
  function captureRequests(): api.Engine & { readonly calls: RequestInput[] } {
    const calls: RequestInput[] = [];
    const engine = Object.create(api.Engine.prototype) as api.Engine & {
      calls: RequestInput[];
      request(params: RequestInput): Promise<unknown>;
    };
    engine.calls = calls;
    engine.request = async (params: RequestInput): Promise<unknown> => {
      calls.push(params);
      return await Promise.resolve(params);
    };
    return engine;
  }

  it('forwards allFields to native subscriptions', async () => {
    const calls: { method: string; args: unknown[] }[] = [];
    const nativeSub = {
      nextArrow: async () => await Promise.resolve(null),
      add: async () => {},
      remove: async () => {},
      unsubscribeArrow: async () => await Promise.resolve(null),
      tickers: [],
      fields: [],
      isActive: true,
      stats: { messagesReceived: 0, droppedBatches: 0, batchesSent: 0, slowConsumer: false },
    };
    const engine = Object.create(api.Engine.prototype) as api.Engine;
    (engine as unknown as { _inner: unknown })._inner = {
      subscribe: async (...args: unknown[]) => {
        calls.push({ method: 'subscribe', args });
        return await Promise.resolve(nativeSub);
      },
      subscribeWithOptions: async (...args: unknown[]) => {
        calls.push({ method: 'subscribeWithOptions', args });
        return await Promise.resolve(nativeSub);
      },
    };

    await engine.subscribe(['XETUSD Curncy'], ['LAST_PRICE'], { allFields: true });
    await engine.stream(['XETUSD Curncy'], ['LAST_PRICE'], { allFields: true });
    await engine.vwap(['XETUSD Curncy'], ['LAST_PRICE'], { allFields: false });

    expect(calls[0]).toEqual({
      method: 'subscribe',
      args: [['XETUSD Curncy'], ['LAST_PRICE'], true],
    });
    expect(calls[1]).toEqual({
      method: 'subscribeWithOptions',
      args: [
        '//blp/mktdata',
        ['XETUSD Curncy'],
        ['LAST_PRICE'],
        undefined,
        undefined,
        undefined,
        undefined,
        true,
      ],
    });
    expect(calls[2]?.args.at(-1)).toBe(false);
  });

  it('forwards per-request validation toggles for reference and history wrappers', async () => {
    const engine = captureRequests();

    await engine.bdp(['IBM US Equity'], ['PX_LAST'], { validateFields: true });
    await engine.bds(['IBM US Equity'], ['DVD_HIST'], { validateFields: false });
    await engine.bdh(['IBM US Equity'], ['PX_LAST'], {
      start: '2024-01-01',
      end: '2024-01-02',
      validateFields: true,
    });

    expect(engine.calls[0]?.validateFields).toBe(true);
    expect(engine.calls[1]?.validateFields).toBe(false);
    expect(engine.calls[2]?.validateFields).toBe(true);
  });

  it('forwards intraday timezone controls and typed tick include options', async () => {
    const engine = captureRequests();

    await engine.bdib('IBM US Equity', {
      start: '2024-01-02T09:30:00',
      end: '2024-01-02T10:00:00',
      requestTz: 'NY',
      outputTz: 'exchange',
    });
    await engine.bdtick('IBM US Equity', {
      start: '2024-01-02T09:30:00',
      end: '2024-01-02T10:00:00',
      requestTz: 'NY',
      outputTz: 'NY',
      includeConditionCodes: true,
      includeExchangeCodes: true,
      kwargs: { customOption: 'customValue' },
    });

    expect(engine.calls[0]?.requestTz).toBe('NY');
    expect(engine.calls[0]?.outputTz).toBe('exchange');
    expect(engine.calls[1]?.requestTz).toBe('NY');
    expect(engine.calls[1]?.outputTz).toBe('NY');
    expect(engine.calls[1]?.kwargs).toEqual(
      expect.arrayContaining([
        { key: 'customOption', value: 'customValue' },
        { key: 'includeConditionCodes', value: 'true' },
        { key: 'includeExchangeCodes', value: 'true' },
      ]),
    );

    await engine.bdtick('IBM US Equity', {
      start: '2024-01-02T09:30:00',
      end: '2024-01-02T10:00:00',
      includeConditionCodes: false,
      kwargs: { includeConditionCodes: true },
    });
    expect(engine.calls[2]?.kwargs).toContainEqual({
      key: 'includeConditionCodes',
      value: 'false',
    });
  });

  it('rejects unknown backend strings instead of silently returning Arrow', async () => {
    const engine = Object.create(api.Engine.prototype);
    engine._inner = {
      request: async () => await Promise.resolve(Buffer.alloc(0)),
    };

    await expect(
      engine.request({ service: '//blp/refdata', operation: 'ReferenceDataRequest', backend: 'bogus' }),
    ).rejects.toThrow('Unsupported @xbbg/core backend');
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

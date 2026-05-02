import { expectTypeOf } from 'vitest';

import { tableFromNativeArrowBatch } from '../src/arrow-zero-copy';
import * as api from '../src/index';
import type { NativeArrowZeroCopyBatch } from '../src/napi';
import type { RequestInput } from '../src/types';

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

function fakeNativeSubscription(): any {
  return {
    add: async () => undefined,
    fields: ['BID', 'ASK'],
    isActive: true,
    nextArrow: async () => null,
    nextUpdate: async () => null,
    remove: async () => undefined,
    stats: {
      batchesSent: 0,
      dataLossEvents: 0,
      droppedBatches: 0,
      effectiveOverflowPolicy: 'drop_newest',
      lastDataLossUs: 0,
      lastMessageUs: 0,
      messagesReceived: 0,
      slowConsumer: false,
    },
    tickers: ['ES1 Index'],
    unsubscribe: async () => [],
    unsubscribeArrow: async () => [],
  };
}

function typedBuffer(view: ArrayBufferView): Buffer {
  return Buffer.from(view.buffer, view.byteOffset, view.byteLength);
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
      expect(api).toHaveProperty(key);
    }
  });

  it('backend enum is frozen with correct values', () => {
    expect(Object.isFrozen(api.Backend)).toBeTruthy();
    expect(api.Backend.ARROW).toBe('arrow');
    expect(api.Backend.JSON).toBe('json');
    expect(api.Backend.POLARS).toBe('polars');
    expect(Object.keys(api.Backend)).toHaveLength(3);
  });

  it('format enum is frozen with correct values', () => {
    expect(Object.isFrozen(api.Format)).toBeTruthy();
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

  it('blpRequestError carries optional properties', () => {
    const err = new api.BlpRequestError('test', {
      code: 123,
      operation: 'BDP',
      service: '//blp/refdata',
    });
    expect(err.service).toBe('//blp/refdata');
    expect(err.operation).toBe('BDP');
    expect(err.code).toBe(123);
  });

  it('blpValidationError carries optional properties', () => {
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
    expectTypeOf(api.connect).toBeFunction();
    expectTypeOf(api.version).toBeFunction();
    expectTypeOf(api.setLogLevel).toBeFunction();
    expectTypeOf(api.getLogLevel).toBeFunction();
    expectTypeOf(api.version()).toBeString();
    expect(api.version().length).toBeGreaterThan(0);
  });

  it('configure accepts both flat and nested config shapes', () => {
    expect(api.configure({ host: SESSION_HOST, port: SESSION_PORT })).toStrictEqual({
      host: SESSION_HOST,
      port: SESSION_PORT,
    });
    const advanced = {
      auth: { appName: 'my-bpipe-app', method: 'userapp' as const },
      retryPolicy: {
        backoffFactor: 1.5,
        initialDelayMs: 100,
        maxDelayMs: 1000,
        maxRetries: 2,
      },
      servers: [
        { host: 'primary.example.com', port: 8194 },
        { host: 'secondary.example.com', port: 8196 },
      ],
      socks5: { host: 'proxy.example.com', port: 1080 },
      tls: {
        clientCredentials: '/secure/client.p12',
        trustMaterial: '/secure/trust.p7',
      },
      zfpRemote: '8194' as const,
    };
    expect(api.configure(advanced)).toStrictEqual(advanced);
    expect(api.configure(SESSION_HOST, SESSION_PORT)).toStrictEqual({
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
      expectTypeOf(api.blp[m]).toBeFunction();
    }
  });

  it('ext.cdx namespace exposes acdx_* helpers', () => {
    for (const m of ['acdx_info', 'acdx_pricing', 'acdx_risk'] as const) {
      expect(typeof (api.ext.cdx as any)[m]).toBe('function');
    }
  });
});

describe('conflated market data options', () => {
  function fakeEngine(captured: Record<string, unknown>): api.Engine {
    const engine = Object.create(api.Engine.prototype) as api.Engine;
    (engine as unknown as { inner: unknown }).inner = {
      subscribe: async (
        tickers: readonly string[],
        fields: readonly string[],
        allFields?: boolean,
      ) => {
        captured.subscribe = { allFields, fields, tickers };
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
          allFields,
          fields,
          flushThreshold,
          options,
          overflowPolicy,
          service,
          streamCapacity,
          tickers,
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
      fields: ['BID', 'ASK'],
      options: ['conflate'],
      service: '//blp/mktdata',
      tickers: ['ES1 Index'],
    });
  });

  it('normalizes ampersand conflate and avoids duplicates', async () => {
    const captured: Record<string, unknown> = {};
    await fakeEngine(captured).subscribe(['ES1 Index'], ['BID', 'ASK'], {
      conflate: true,
      options: ['&conflate'],
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
        conflate: true,
        options: ['interval=5'],
      }),
    ).rejects.toBeInstanceOf(api.BlpValidationError);
  });
});

describe('native Arrow zero-copy table construction', () => {
  it('constructs an Arrow table from native buffer descriptors', () => {
    const prices = new Float64Array([50_000.5, 0]);
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
      kind: 'zeroCopy',
      numRows: 2,
    };

    const table = tableFromNativeArrowBatch(batch);

    expect(table.numRows).toBe(2);
    expect(table.getChild('topic')?.get(0)).toBe('XBTUSD Curncy');
    expect(table.getChild('topic')?.get(1)).toBe('IBM US Equity');
    expect(table.getChild('LAST_PRICE')?.get(0)).toBe(50_000.5);
    expect(table.getChild('LAST_PRICE')?.get(1)).toBeNull();
    expect(table.getChild('SIZE')?.get(1)).toBe(20);
    expect(table.getChild('UPDATE_TIME')?.get(0)).toBe(45_000_000_000n);
    expect(table.getChild('QUANTITY')?.get(1)).toBe(4_000_000_000);
    expect(table.getChild('YIELD')?.get(0)).toBeCloseTo(1.25);
    expect(table.getChild('TRADE_DATE')?.get(0)).toBe(1_700_000_000_000);
    expect([...(table.getChild('PAYLOAD')?.get(1) ?? [])]).toStrictEqual([0xbe, 0xef, 0x01]);
  });

  it('subscription.next uses native updates', async () => {
    const sub = new api.Subscription({
      add: async () => {},
      fields: [],
      isActive: true,
      nextArrow: async () => Promise.resolve(null),
      nextUpdate: async () =>
        Promise.resolve({
          kind: 'update',
          topic: 'XBTUSD Curncy',
          topicId: 1,
          timestampUs: 123,
          layoutVersion: 1,
          fields: ['answer'],
          values: [42],
          valueKinds: ['i32'],
        }),
      remove: async () => {},
      stats: { batchesSent: 0, droppedBatches: 0, messagesReceived: 0, slowConsumer: false },
      tickers: [],
      unsubscribe: async () => Promise.resolve(null),
      unsubscribeArrow: async () => Promise.resolve(null),
    });

    const result = await sub.next();

    expect(result.done).toBeFalsy();
    expect(result.value?.topic).toBe('XBTUSD Curncy');
    expect(result.value?.f64('answer')).toBe(42);
  });

  it('subscription.arrow drains native zero-copy batches', async () => {
    const values = new Int32Array([7]);
    const batch: NativeArrowZeroCopyBatch = {
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
      kind: 'zeroCopy',
      numRows: 1,
    };
    const sub = new api.Subscription({
      add: async () => {},
      fields: [],
      isActive: true,
      nextArrow: async () => Promise.resolve(null),
      nextUpdate: async () => Promise.resolve(null),
      remove: async () => {},
      stats: { batchesSent: 0, droppedBatches: 0, messagesReceived: 0, slowConsumer: false },
      tickers: [],
      unsubscribe: async () => Promise.resolve(null),
      unsubscribeArrow: async (drain) => Promise.resolve(drain ? [batch] : null),
    });

    const drained = await sub.arrow().unsubscribe(true);

    expect(drained).toHaveLength(1);
    expect(drained[0]?.getChild('answer')?.get(0)).toBe(7);
  });
});

describe('engine wrapper request plumbing', () => {
  function captureRequests(): api.Engine & { readonly calls: RequestInput[] } {
    const calls: RequestInput[] = [];
    const engine = Object.create(api.Engine.prototype) as api.Engine & {
      calls: RequestInput[];
      request(params: RequestInput): Promise<unknown>;
    };
    engine.calls = calls;
    engine.request = async (params: RequestInput): Promise<unknown> => {
      calls.push(params);
      return Promise.resolve(params);
    };
    return engine;
  }

  it('forwards allFields to native subscriptions', async () => {
    const calls: { method: string; args: unknown[] }[] = [];
    const nativeSub = {
      add: async () => {},
      fields: [],
      isActive: true,
      nextArrow: async () => Promise.resolve(null),
      remove: async () => {},
      stats: { batchesSent: 0, droppedBatches: 0, messagesReceived: 0, slowConsumer: false },
      tickers: [],
      unsubscribeArrow: async () => Promise.resolve(null),
    };
    const engine = Object.create(api.Engine.prototype) as api.Engine;
    (engine as unknown as { inner: unknown }).inner = {
      subscribe: async (...args: unknown[]) => {
        calls.push({ args, method: 'subscribe' });
        return Promise.resolve(nativeSub);
      },
      subscribeWithOptions: async (...args: unknown[]) => {
        calls.push({ args, method: 'subscribeWithOptions' });
        return Promise.resolve(nativeSub);
      },
    };

    await engine.subscribe(['XETUSD Curncy'], ['LAST_PRICE'], { allFields: true });
    await engine.stream(['XETUSD Curncy'], ['LAST_PRICE'], { allFields: true });
    await engine.vwap(['XETUSD Curncy'], ['LAST_PRICE'], { allFields: false });

    expect(calls[0]).toStrictEqual({
      args: [['XETUSD Curncy'], ['LAST_PRICE'], true],
      method: 'subscribe',
    });
    expect(calls[1]).toStrictEqual({
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
      method: 'subscribeWithOptions',
    });
    expect(calls[2]?.args.at(-1)).toBeFalsy();
  });

  it('forwards per-request validation toggles for reference and history wrappers', async () => {
    const engine = captureRequests();

    await engine.bdp(['IBM US Equity'], ['PX_LAST'], { validateFields: true });
    await engine.bds(['IBM US Equity'], ['DVD_HIST'], { validateFields: false });
    await engine.bdh(['IBM US Equity'], ['PX_LAST'], {
      end: '2024-01-02',
      start: '2024-01-01',
      validateFields: true,
    });

    expect(engine.calls[0]?.validateFields).toBeTruthy();
    expect(engine.calls[1]?.validateFields).toBeFalsy();
    expect(engine.calls[2]?.validateFields).toBeTruthy();
  });

  it('forwards intraday timezone controls and typed tick include options', async () => {
    const engine = captureRequests();

    await engine.bdib('IBM US Equity', {
      end: '2024-01-02T10:00:00',
      outputTz: 'exchange',
      requestTz: 'NY',
      start: '2024-01-02T09:30:00',
    });
    await engine.bdtick('IBM US Equity', {
      end: '2024-01-02T10:00:00',
      includeConditionCodes: true,
      includeExchangeCodes: true,
      kwargs: { customOption: 'customValue' },
      outputTz: 'NY',
      requestTz: 'NY',
      start: '2024-01-02T09:30:00',
    });

    expect(engine.calls[0]?.requestTz).toBe('NY');
    expect(engine.calls[0]?.outputTz).toBe('exchange');
    expect(engine.calls[1]?.requestTz).toBe('NY');
    expect(engine.calls[1]?.outputTz).toBe('NY');
    expect(engine.calls[1]?.kwargs).toStrictEqual(
      expect.arrayContaining([
        { key: 'customOption', value: 'customValue' },
        { key: 'includeConditionCodes', value: 'true' },
        { key: 'includeExchangeCodes', value: 'true' },
      ]),
    );

    await engine.bdtick('IBM US Equity', {
      end: '2024-01-02T10:00:00',
      includeConditionCodes: false,
      kwargs: { includeConditionCodes: true },
      start: '2024-01-02T09:30:00',
    });
    expect(engine.calls[2]?.kwargs).toContainEqual({
      key: 'includeConditionCodes',
      value: 'false',
    });
  });

  it('rejects unknown backend strings instead of silently returning Arrow', async () => {
    const engine = Object.create(api.Engine.prototype) as api.Engine;
    (engine as unknown as { inner: unknown }).inner = {
      request: async () => Promise.resolve(Buffer.alloc(0)),
    };

    const invalidRequest = {
      backend: 'bogus',
      operation: 'ReferenceDataRequest',
      service: '//blp/refdata',
    };
    const request = engine.request.bind(engine) as (params: unknown) => Promise<unknown>;
    await expect(request(invalidRequest)).rejects.toThrow('Unsupported @xbbg/core backend');
  });
});

describe('engine instantiation', () => {
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
    } catch (error) {
      if (nativeUnavailable(error)) {
        console.warn('Engine instantiation skipped: native module or session unavailable');
        return;
      }
      throw error;
    }
  });

  it('engine.withConfig returns an Engine', () => {
    try {
      const engine = api.Engine.withConfig({ host: SESSION_HOST, port: SESSION_PORT });
      expect(engine).toBeInstanceOf(api.Engine);
    } catch (error) {
      if (nativeUnavailable(error)) {
        console.warn('Engine.withConfig skipped: native module or session unavailable');
        return;
      }
      throw error;
    }
  });

  it('subscription prototype exposes async iterator + methods', () => {
    const subProto = api.Subscription.prototype as any;
    expect(typeof subProto.next).toBe('function');
    expect(typeof subProto.add).toBe('function');
    expect(typeof subProto.remove).toBe('function');
    expect(typeof subProto.unsubscribe).toBe('function');
    expect(typeof subProto[Symbol.asyncIterator]).toBe('function');
  });
});

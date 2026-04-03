const assert = require('node:assert');

try {
  const api = require('./index');
  const SESSION_HOST = process.env.XBBG_HOST || 'localhost';
  const SESSION_PORT = Number(process.env.XBBG_PORT || 8194);

  // Test 1: All exports exist
  const requiredExports = [
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
  ];
  for (const key of requiredExports) {
    assert(key in api, `Missing export: ${key}`);
  }
  console.log('PASS: all exports present');

  // Test 2: Backend enum is frozen with correct values
  assert(Object.isFrozen(api.Backend), 'Backend not frozen');
  assert.strictEqual(api.Backend.ARROW, 'arrow');
  assert.strictEqual(api.Backend.JSON, 'json');
  assert.strictEqual(api.Backend.POLARS, 'polars');
  assert.strictEqual(Object.keys(api.Backend).length, 3);
  console.log('PASS: Backend enum');

  // Test 3: Format enum is frozen with correct values
  assert(Object.isFrozen(api.Format), 'Format not frozen');
  assert.strictEqual(api.Format.LONG, 'long');
  assert.strictEqual(api.Format.LONG_TYPED, 'long_typed');
  assert.strictEqual(api.Format.LONG_WITH_METADATA, 'long_with_metadata');
  assert.strictEqual(api.Format.SEMI_LONG, 'semi_long');
  assert.strictEqual(Object.keys(api.Format).length, 4);
  console.log('PASS: Format enum');

  // Test 4: Error class hierarchy and properties
  assert(
    api.BlpError.prototype instanceof Error,
    'BlpError not instanceof Error',
  );
  assert(
    api.BlpSessionError.prototype instanceof api.BlpError,
    'BlpSessionError not instanceof BlpError',
  );
  assert(
    api.BlpRequestError.prototype instanceof api.BlpError,
    'BlpRequestError not instanceof BlpError',
  );
  assert(
    api.BlpValidationError.prototype instanceof api.BlpError,
    'BlpValidationError not instanceof BlpError',
  );
  assert(
    api.BlpTimeoutError.prototype instanceof api.BlpError,
    'BlpTimeoutError not instanceof BlpError',
  );
  assert(
    api.BlpInternalError.prototype instanceof api.BlpError,
    'BlpInternalError not instanceof BlpError',
  );
  console.log('PASS: error class hierarchy');

  // Test 5: Error instances have correct name property
  const err1 = new api.BlpError('test');
  assert.strictEqual(err1.name, 'BlpError');
  const err2 = new api.BlpSessionError('test');
  assert.strictEqual(err2.name, 'BlpSessionError');
  const err3 = new api.BlpRequestError('test');
  assert.strictEqual(err3.name, 'BlpRequestError');
  const err4 = new api.BlpValidationError('test');
  assert.strictEqual(err4.name, 'BlpValidationError');
  const err5 = new api.BlpTimeoutError('test');
  assert.strictEqual(err5.name, 'BlpTimeoutError');
  const err6 = new api.BlpInternalError('test');
  assert.strictEqual(err6.name, 'BlpInternalError');
  console.log('PASS: error instance names');

  // Test 6: BlpRequestError has optional properties
  const reqErr = new api.BlpRequestError('test', {
    service: '//blp/refdata',
    operation: 'BDP',
    code: 123,
  });
  assert.strictEqual(reqErr.service, '//blp/refdata');
  assert.strictEqual(reqErr.operation, 'BDP');
  assert.strictEqual(reqErr.code, 123);
  console.log('PASS: BlpRequestError properties');

  // Test 7: BlpValidationError has optional properties
  const valErr = new api.BlpValidationError('test', {
    element: 'field1',
    suggestion: 'PX_LAST',
  });
  assert.strictEqual(valErr.element, 'field1');
  assert.strictEqual(valErr.suggestion, 'PX_LAST');
  console.log('PASS: BlpValidationError properties');

  // Test 8: Engine constructor
  const engine = new api.Engine(SESSION_HOST, SESSION_PORT);
  assert(engine instanceof api.Engine);
  assert(engine._inner !== undefined);
  console.log('PASS: Engine constructor');

  // Test 9: Engine.withConfig static method
  const engineWithConfig = api.Engine.withConfig({
    host: SESSION_HOST,
    port: SESSION_PORT,
  });
  assert(engineWithConfig instanceof api.Engine);
  assert(engineWithConfig._inner !== undefined);
  console.log('PASS: Engine.withConfig');

  // Test 10: Engine async methods exist and are functions
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
    'subscribe',
    'subscribeWithOptions',
    'request',
    'resolveFieldTypes',
  ];
  for (const method of asyncMethods) {
    assert(
      typeof engine[method] === 'function',
      `Engine.${method} is not a function`,
    );
  }
  console.log('PASS: Engine async methods exist');

  // Test 11: Engine sync methods exist and are functions
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
    assert(
      typeof engine[method] === 'function',
      `Engine.${method} is not a function`,
    );
  }
  console.log('PASS: Engine sync methods exist');

  // Test 12: Subscription class exists and has expected methods
  assert(typeof api.Subscription === 'function');
  const subProto = api.Subscription.prototype;
  assert(typeof subProto.next === 'function');
  assert(typeof subProto.add === 'function');
  assert(typeof subProto.remove === 'function');
  assert(typeof subProto.unsubscribe === 'function');
  assert(
    Object.hasOwn(subProto, 'tickers') ||
      Object.getOwnPropertyDescriptor(subProto, 'tickers'),
  );
  assert(
    Object.hasOwn(subProto, 'fields') ||
      Object.getOwnPropertyDescriptor(subProto, 'fields'),
  );
  assert(
    Object.hasOwn(subProto, 'isActive') ||
      Object.getOwnPropertyDescriptor(subProto, 'isActive'),
  );
  assert(
    Object.hasOwn(subProto, 'stats') ||
      Object.getOwnPropertyDescriptor(subProto, 'stats'),
  );
  assert(typeof subProto[Symbol.asyncIterator] === 'function');
  console.log('PASS: Subscription class structure');

  // Test 13: connect function exists and is callable
  assert(typeof api.connect === 'function');
  console.log('PASS: connect function exists');

  // Test 14: configure accepts simple and nested engine config objects
  assert(typeof api.configure === 'function');
  assert.deepStrictEqual(
    api.configure({ host: SESSION_HOST, port: SESSION_PORT }),
    { host: SESSION_HOST, port: SESSION_PORT },
  );
  const advancedConfig = {
    servers: [
      { host: 'primary.example.com', port: 8194 },
      { host: 'secondary.example.com', port: 8196 },
    ],
    auth: { method: 'userapp', appName: 'my-bpipe-app' },
    tls: {
      clientCredentials: '/secure/client.p12',
      trustMaterial: '/secure/trust.p7',
    },
    zfpRemote: '8194',
    retryPolicy: {
      maxRetries: 2,
      initialDelayMs: 100,
      backoffFactor: 1.5,
      maxDelayMs: 1000,
    },
    socks5: { host: 'proxy.example.com', port: 1080 },
  };
  assert.deepStrictEqual(api.configure(advancedConfig), advancedConfig);
  assert.deepStrictEqual(api.configure(SESSION_HOST, SESSION_PORT), {
    host: SESSION_HOST,
    port: SESSION_PORT,
  });
  console.log('PASS: configure helper');

  // Test 15: top-level async wrappers exist
  const topLevelAsyncMethods = [
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
  ];
  for (const method of topLevelAsyncMethods) {
    assert(
      typeof api[method] === 'function',
      `Top-level ${method} is not a function`,
    );
  }
  console.log('PASS: top-level wrapper exports');

  // Test 16: blp namespace exposes Python-style async helpers
  assert.ok(api.blp && typeof api.blp === 'object');
  const blpMethods = [
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
  ];
  for (const method of blpMethods) {
    assert(
      typeof api.blp[method] === 'function',
      `blp.${method} is not a function`,
    );
  }
  console.log('PASS: blp namespace exports');

  // Test 17: ext.cdx namespace exposes requested async helpers
  assert.ok(api.ext && typeof api.ext === 'object');
  assert.ok(api.ext.cdx && typeof api.ext.cdx === 'object');
  for (const method of ['acdx_info', 'acdx_pricing', 'acdx_risk']) {
    assert(
      typeof api.ext.cdx[method] === 'function',
      `ext.cdx.${method} is not a function`,
    );
  }
  console.log('PASS: ext.cdx namespace exports');

  // Test 14: version is a function that returns a string
  assert(typeof api.version === 'function');
  const versionStr = api.version();
  assert(typeof versionStr === 'string');
  assert(versionStr.length > 0);
  console.log('PASS: version function');

  // Test 15: setLogLevel and getLogLevel are functions
  assert(typeof api.setLogLevel === 'function');
  assert(typeof api.getLogLevel === 'function');
  console.log('PASS: logging functions exist');

  // Test 16: requestRaw method exists
  assert(typeof engine.requestRaw === 'function');
  console.log('PASS: requestRaw method exists');

  // Test 17: wrapError maps NAPI error prefixes to correct classes
  const { wrapError } = require('./errors');
  const wrapCases = [
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
    const e = wrapError(new Error(msg));
    assert(
      e instanceof Cls,
      `wrapError('${msg}') → ${e.constructor.name}, expected ${Cls.name}`,
    );
  }
  console.log('PASS: wrapError prefix mapping');

  console.log('ALL TESTS PASSED');
} catch (error) {
  const message = String(error?.message ? error.message : error);
  if (message.includes('Unable to load native napi-xbbg module')) {
    console.log(
      'js-xbbg test skipped: native module not built in this environment',
    );
    process.exit(0);
  }
  if (
    message.toLowerCase().includes('session start failed') ||
    message.toLowerCase().includes('failed to spawn worker')
  ) {
    console.log(
      'js-xbbg test skipped: Bloomberg session is not available in this environment',
    );
    process.exit(0);
  }
  throw error;
}

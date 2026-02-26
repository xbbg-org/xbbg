'use strict';

const fs = require('node:fs');
const path = require('node:path');
const { tableFromIPC } = require('apache-arrow');
const { wrapError, BlpError, BlpSessionError, BlpRequestError, BlpValidationError, BlpTimeoutError, BlpInternalError } = require('./errors');

function loadNative() {
  const root = path.resolve(__dirname, '..');
  const candidates = [
    path.join(__dirname, 'napi_xbbg.node'),
    path.join(__dirname, 'napi-xbbg.node'),
    path.join(root, 'target', 'debug', 'napi_xbbg.node'),
    path.join(root, 'target', 'release', 'napi_xbbg.node'),
    path.join(root, 'target', 'debug', 'napi-xbbg.node'),
    path.join(root, 'target', 'release', 'napi-xbbg.node'),
  ];

  for (const candidate of candidates) {
    if (fs.existsSync(candidate)) {
      return require(candidate);
    }
  }

  throw new Error(
    'Unable to load native napi-xbbg module. Build it with "npm run build" from js-xbbg or "cargo build -p napi-xbbg" from repo root.'
  );
}

const native = loadNative();

const Backend = Object.freeze({
  ARROW: 'arrow',
  JSON: 'json',
  POLARS: 'polars',
});

const Format = Object.freeze({
  LONG: 'long',
  LONG_TYPED: 'long_typed',
  LONG_WITH_METADATA: 'long_with_metadata',
  SEMI_LONG: 'semi_long',
});

function toArrowTable(ipcBuffer) {
  return tableFromIPC(ipcBuffer);
}

function mapObjectToPairs(obj) {
  if (!obj) {
    return undefined;
  }
  return Object.entries(obj).map(([key, value]) => ({
    key: String(key),
    value: String(value),
  }));
}

class Subscription {
  constructor(inner) {
    this._inner = inner;
  }

  async next() {
    try {
      const batch = await this._inner.next();
      if (batch == null) {
        return { done: true, value: undefined };
      }
      return { done: false, value: toArrowTable(batch) };
    } catch (err) {
      throw wrapError(err);
    }
  }

  async add(tickers) {
    await this._inner.add(tickers);
  }

  async remove(tickers) {
    await this._inner.remove(tickers);
  }

  async unsubscribe(drain = false) {
    const drained = await this._inner.unsubscribe(Boolean(drain));
    if (!drained) {
      return [];
    }
    return drained.map(toArrowTable);
  }

  get tickers() {
    return this._inner.tickers;
  }

  get fields() {
    return this._inner.fields;
  }

  get isActive() {
    return this._inner.isActive;
  }

  get stats() {
    return this._inner.stats;
  }

  [Symbol.asyncIterator]() {
    return this;
  }
}

class Engine {
  constructor(host = 'localhost', port = 8194) {
    this._inner = new native.JsEngine(host, port);
  }

  static withConfig(config = {}) {
    const engine = Object.create(Engine.prototype);
    engine._inner = native.JsEngine.withConfig(config);
    return engine;
  }

  async request(params) {
    const backend = params.backend || Backend.ARROW;
    const { backend: _b, ...nativeParams } = params;
    try {
      const buffer = await this._inner.request(nativeParams);
      if (backend === Backend.JSON) {
        return Array.from(tableFromIPC(buffer));
      }
      if (backend === Backend.POLARS) {
        let pl;
        try { pl = require('nodejs-polars'); }
        catch { throw new Error('nodejs-polars is required for Polars backend. Install: npm install nodejs-polars'); }
        return pl.readIPC(buffer);
      }
      return tableFromIPC(buffer);
    } catch (err) {
      throw wrapError(err);
    }
  }

  async requestRaw(params) {
    return this._inner.request(params);
  }

  async bdp(tickers, fields, options = {}) {
    return this.request({
      service: '//blp/refdata',
      operation: 'ReferenceDataRequest',
      securities: tickers,
      fields,
      overrides: mapObjectToPairs(options.overrides),
      kwargs: mapObjectToPairs(options.kwargs),
      format: options.format,
      includeSecurityErrors: Boolean(options.includeSecurityErrors),
      extractor: 'refdata',
    });
  }

  async bds(tickers, fields, options = {}) {
    return this.request({
      service: '//blp/refdata',
      operation: 'ReferenceDataRequest',
      securities: tickers,
      fields,
      overrides: mapObjectToPairs(options.overrides),
      kwargs: mapObjectToPairs(options.kwargs),
      format: options.format,
      extractor: 'bulk',
    });
  }

  async bdh(tickers, fields, options = {}) {
    return this.request({
      service: '//blp/refdata',
      operation: 'HistoricalDataRequest',
      securities: tickers,
      fields,
      startDate: options.start,
      endDate: options.end,
      overrides: mapObjectToPairs(options.overrides),
      kwargs: mapObjectToPairs(options.kwargs),
      format: options.format,
      extractor: 'histdata',
    });
  }

  async bdib(ticker, options = {}) {
    return this.request({
      service: '//blp/refdata',
      operation: 'IntradayBarRequest',
      security: ticker,
      eventType: options.eventType || 'TRADE',
      interval: options.interval || 1,
      startDatetime: options.start,
      endDatetime: options.end,
      kwargs: mapObjectToPairs(options.kwargs),
      extractor: 'intraday_bar',
    });
  }

  async bdtick(ticker, options = {}) {
    return this.request({
      service: '//blp/refdata',
      operation: 'IntradayTickRequest',
      security: ticker,
      eventTypes: options.eventTypes || ['TRADE'],
      startDatetime: options.start,
      endDatetime: options.end,
      kwargs: mapObjectToPairs(options.kwargs),
      extractor: 'intraday_tick',
    });
  }

  async bql(query, options = {}) {
    return this.request({
      service: '//blp/bqlsvc',
      operation: 'sendQuery',
      elements: [{ key: 'expression', value: String(query) }],
      backend: options.backend,
      kwargs: mapObjectToPairs(options.kwargs),
      format: options.format,
      extractor: 'bql',
    });
  }

  async beqs(screen, options = {}) {
    const elements = [{ key: 'screenName', value: String(screen) }];
    if (options.asof) elements.push({ key: 'asOfDate', value: String(options.asof) });
    return this.request({
      service: '//blp/refdata',
      operation: 'BeqsRequest',
      elements,
      backend: options.backend,
      kwargs: mapObjectToPairs(options.kwargs),
      format: options.format,
    });
  }

  async bsrch(searchSpec, options = {}) {
    return this.request({
      service: '//blp/exrsvc',
      operation: 'ExcelGetGridRequest',
      searchSpec: String(searchSpec),
      backend: options.backend,
      overrides: mapObjectToPairs(options.overrides),
      kwargs: mapObjectToPairs(options.kwargs),
      format: options.format,
      extractor: 'bsrch',
    });
  }

  async bta(ticker, study, options = {}) {
    const studyObj = typeof study === 'string' ? { studyType: study, ...options.studyParams } : study;
    return this.request({
      service: '//blp/tasvc',
      operation: 'studyRequest',
      security: String(ticker),
      backend: options.backend,
      jsonElements: JSON.stringify(studyObj),
      kwargs: mapObjectToPairs(options.kwargs),
      format: options.format,
    });
  }

  async bflds(options = {}) {
    if (options.searchSpec) {
      return this.request({
        service: '//blp/apiflds',
        operation: 'FieldSearchRequest',
        searchSpec: String(options.searchSpec),
        backend: options.backend,
        kwargs: mapObjectToPairs(options.kwargs),
        format: options.format,
      });
    }
    const fields = Array.isArray(options.fields) ? options.fields : (options.fields ? [options.fields] : []);
    return this.request({
      service: '//blp/apiflds',
      operation: 'FieldInfoRequest',
      fieldIds: fields,
      backend: options.backend,
      kwargs: mapObjectToPairs(options.kwargs),
      format: options.format,
    });
  }

  async blkp(query, options = {}) {
    return this.request({
      service: '//blp/instruments',
      operation: 'instrumentListRequest',
      elements: [{ key: 'query', value: String(query) }],
      backend: options.backend,
      kwargs: mapObjectToPairs(options.kwargs),
      format: options.format,
    });
  }

  async bport(portfolio, fields, options = {}) {
    return this.request({
      service: '//blp/refdata',
      operation: 'PortfolioDataRequest',
      security: String(portfolio),
      fields: Array.isArray(fields) ? fields : [fields],
      backend: options.backend,
      overrides: mapObjectToPairs(options.overrides),
      kwargs: mapObjectToPairs(options.kwargs),
      format: options.format,
    });
  }

  async bcurves(ticker, options = {}) {
    return this.request({
      service: '//blp/instruments',
      operation: 'curveListRequest',
      elements: [{ key: 'query', value: String(ticker) }],
      backend: options.backend,
      kwargs: mapObjectToPairs(options.kwargs),
      format: options.format,
    });
  }

  async bgovts(ticker, options = {}) {
    return this.request({
      service: '//blp/instruments',
      operation: 'govtListRequest',
      elements: [{ key: 'query', value: String(ticker) }],
      backend: options.backend,
      kwargs: mapObjectToPairs(options.kwargs),
      format: options.format,
    });
  }

  async resolveFieldTypes(fields, overrides = undefined, defaultType = 'string') {
    const items = await this._inner.resolveFieldTypes(fields, mapObjectToPairs(overrides), defaultType);
    return Object.fromEntries(items.map((item) => [item.key, item.value]));
  }

  getFieldInfo(field) {
    return this._inner.getFieldInfo(field);
  }

  clearFieldCache() {
    this._inner.clearFieldCache();
  }

  saveFieldCache() {
    return this._inner.saveFieldCache();
  }

  validateFields(fields) {
    return this._inner.validateFields(fields);
  }

  isFieldValidationEnabled() {
    return this._inner.isFieldValidationEnabled();
  }

  getSchema(service) {
    return this._inner.getSchema(service).then((json) => JSON.parse(json));
  }

  getOperation(service, operation) {
    return this._inner.getOperation(service, operation).then((json) => JSON.parse(json));
  }

  listOperations(service) {
    return this._inner.listOperations(service);
  }

  getCachedSchema(service) {
    const json = this._inner.getCachedSchema(service);
    return json ? JSON.parse(json) : null;
  }

  invalidateSchema(service) {
    this._inner.invalidateSchema(service);
  }

  clearSchemaCache() {
    this._inner.clearSchemaCache();
  }

  listCachedSchemas() {
    return this._inner.listCachedSchemas();
  }

  getEnumValues(service, operation, element) {
    return this._inner.getEnumValues(service, operation, element);
  }

  listValidElements(service, operation) {
    return this._inner.listValidElements(service, operation);
  }

  async subscribe(tickers, fields) {
    try {
      const stream = await this._inner.subscribe(tickers, fields);
      return new Subscription(stream);
    } catch (err) {
      throw wrapError(err);
    }
  }

  async subscribeWithOptions(
    service,
    tickers,
    fields,
    options = undefined,
    flushThreshold = undefined,
    overflowPolicy = undefined,
    streamCapacity = undefined
  ) {
    try {
      const stream = await this._inner.subscribeWithOptions(
        service,
        tickers,
        fields,
        options,
        flushThreshold,
        overflowPolicy,
        streamCapacity
      );
      return new Subscription(stream);
    } catch (err) {
      throw wrapError(err);
    }
  }

  signalShutdown() {
    this._inner.signalShutdown();
  }

  isAvailable() {
    return this._inner.isAvailable();
  }

  async stream(tickers, fields, options = {}) {
    return this.subscribeWithOptions('//blp/mktdata', tickers, fields, options.options, options.flushThreshold, options.overflowPolicy, options.streamCapacity);
  }

  async vwap(tickers, fields, options = {}) {
    return this.subscribeWithOptions('//blp/mktvwap', tickers, fields, options.options, options.flushThreshold, options.overflowPolicy, options.streamCapacity);
  }

  async mktbar(ticker, options = {}) {
    return this.subscribeWithOptions('//blp/mktbar', [ticker], options.fields || [], options.options, options.flushThreshold, options.overflowPolicy, options.streamCapacity);
  }

  async depth(ticker, options = {}) {
    return this.subscribeWithOptions('//blp/mktdepthdata', [ticker], options.fields || [], options.options, options.flushThreshold, options.overflowPolicy, options.streamCapacity);
  }

  async chains(ticker, options = {}) {
    return this.subscribeWithOptions('//blp/mktlist', [ticker], options.fields || [], options.options, options.flushThreshold, options.overflowPolicy, options.streamCapacity);
  }

  async bops(service) {
    return this._inner.listOperations(service);
  }

  async bschema(service, operation) {
    if (operation) return this._inner.getOperation(service, operation).then(json => JSON.parse(json));
    return this._inner.getSchema(service).then(json => JSON.parse(json));
  }

  fieldInfo(fields, options = {}) {
    return this.bflds({ fields: Array.isArray(fields) ? fields : [fields], ...options });
  }

  fieldSearch(searchSpec, options = {}) {
    return this.bflds({ searchSpec: String(searchSpec), ...options });
  }

  _ipcToBackend(buffer, backend) {
    if (backend === Backend.JSON) {
      return Array.from(tableFromIPC(buffer));
    }
    if (backend === Backend.POLARS) {
      let pl;
      try { pl = require('nodejs-polars'); }
      catch { throw new Error('nodejs-polars is required for Polars backend. Install: npm install nodejs-polars'); }
      return pl.readIPC(buffer);
    }
    return tableFromIPC(buffer);
  }

  async bqr(ticker, options = {}) {
    try {
      const buffer = await this._inner.recipeBqr(
        String(ticker),
        options.startDatetime || undefined,
        options.endDatetime || undefined,
        options.eventTypes || null,
        options.includeBrokerCodes !== false,
      );
      return this._ipcToBackend(buffer, options.backend || Backend.ARROW);
    } catch (err) {
      throw wrapError(err);
    }
  }
}

async function connect(config = undefined) {
  if (!config) {
    return new Engine();
  }
  return Engine.withConfig(config);
}

module.exports = {
  Engine,
  Subscription,
  connect,
  Backend,
  Format,
  BlpError,
  BlpSessionError,
  BlpRequestError,
  BlpValidationError,
  BlpTimeoutError,
  BlpInternalError,
  wrapError,
  version: native.version,
  setLogLevel: native.setLogLevel,
  getLogLevel: native.getLogLevel,
};

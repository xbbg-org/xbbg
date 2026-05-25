import type { StructuredToolInterface } from "@langchain/core/tools";
import { AIMessage, ToolMessage } from "@langchain/core/messages";
import { ToolNode } from "@langchain/langgraph/prebuilt";

import {
  BLOOMBERG_TOOL_INSTRUCTIONS,
  createAllBloombergTools,
  createBloombergTools,
  getBloombergToolInstructions,
} from "../src";
import type { XbbgCoreLike, XbbgEngineLike } from "../src/core-loader";

type CoreSubscription = Awaited<ReturnType<XbbgEngineLike["stream"]>>;

function fakeSubscription(updates: readonly unknown[], error?: Error) {
  let index = 0;
  const subscription = {
    next: vi.fn(async () => {
      if (error !== undefined) {
        throw error;
      }
      if (index >= updates.length) {
        return { done: true, value: undefined } as IteratorResult<unknown>;
      }
      const value = updates[index];
      index += 1;
      return { done: false, value } as IteratorResult<unknown>;
    }),
    unsubscribe: vi.fn(async () => []),
  };
  return {
    next: subscription.next,
    subscription: subscription as unknown as CoreSubscription,
    unsubscribe: subscription.unsubscribe,
  };
}

function fakeEngine(): XbbgEngineLike {
  return {
    bdp: vi.fn(async () => [
      { ticker: "AAPL US Equity", field: "PX_LAST", value: "1234567890123456789012345" },
    ]),
    bdh: vi.fn(async () => [{ ticker: "AAPL US Equity", date: "20240102", value: 1 }]),
    bdib: vi.fn(async () => [{ time: "2024-01-02T09:30:00-05:00", close: 1 }]),
    bdtick: vi.fn(async () => [{ time: "2024-01-02T09:30:00-05:00", type: "TRADE", value: 1 }]),
    bds: vi.fn(async () => [{ member: "AAPL US Equity" }]),
    bflds: vi.fn(async () => [{ id: "PX_LAST" }]),
    bql: vi.fn(async () => [{ value: 1 }]),
    bsrch: vi.fn(async () => [{ security: "AAPL US Equity" }]),
    bqr: vi.fn(async () => [{ broker_buy: "DLR", event_type: "BID", price: 99 }]),
    beqs: vi.fn(async () => [{ security: "AAPL US Equity" }]),
    yas: vi.fn(async () => [{ field: "YAS_BOND_YLD", value: 5 }]),
    preferreds: vi.fn(async () => [{ ticker: "AAPL 4.5 Pfd" }]),
    corporateBonds: vi.fn(async () => [{ ticker: "AAPL 3.25 02/23/26 Corp" }]),
    indexMembers: vi.fn(async () => [{ member: "AAPL US Equity" }]),
    resolveIsins: vi.fn(async () => [{ isin: "US0378331005", security: "AAPL US Equity" }]),
    issuerIsins: vi.fn(async () => [{ issuer: "Apple Inc", isin: "US037833FB15" }]),
    etfHoldings: vi.fn(async () => [{ ticker: "AAPL US Equity", weight: 0.07 }]),
    stream: vi.fn(async () => fakeSubscription([]).subscription),
    mktbar: vi.fn(async () => fakeSubscription([]).subscription),
    depth: vi.fn(async () => fakeSubscription([]).subscription),
  };
}

function fakeCore(engine: XbbgEngineLike): XbbgCoreLike {
  return {
    connect: vi.fn(async () => engine),
    ext: {
      buildCorporateBondsQuery: vi.fn(() => "corp-bonds-query"),
      buildEarningHeaderRename: vi.fn(() => [{ key: "OLD", value: "NEW" }]),
      buildEtfHoldingsQuery: vi.fn(() => "etf-query"),
      buildFuturesTicker: vi.fn(() => "ESH4 Index"),
      buildFxPair: vi.fn(() => ({
        factor: 1,
        fromCcy: "USD",
        fxPair: "USDEUR Curncy",
        toCcy: "EUR",
      })),
      buildPreferredsQuery: vi.fn(() => "preferreds-query"),
      buildYasOverrides: vi.fn(() => [{ key: "YAS_BOND_PX", value: "99" }]),
      calculateLevelPercentages: vi.fn(() => [0.1, null]),
      cdx: {
        acdx_info: vi.fn(async () => []),
        acdx_pricing: vi.fn(async () => []),
        acdx_risk: vi.fn(async () => []),
      },
      cdxGenToSpecific: vi.fn(() => "CDX IG S40 5Y Corp"),
      clearExchangeOverride: vi.fn(),
      contractIndex: vi.fn(() => 1),
      currenciesNeedingConversion: vi.fn(() => ["EUR"]),
      defaultBqrDatetimes: vi.fn(() => ({
        end: "2024-01-02T10:00:00",
        start: "2024-01-02T09:30:00",
      })),
      defaultTurnoverDates: vi.fn(() => ({ end: "20240131", start: "20240101" })),
      deriveSessions: vi.fn(() => ({ day: { end: "16:00", start: "09:30" } })),
      filterCandidatesByCycle: vi.fn(() => [{ month: 3, ticker: "ESH4 Index", year: 2024 }]),
      filterEquityTickers: vi.fn(() => ["AAPL US Equity"]),
      filterValidContracts: vi.fn(() => ["ESH4 Index"]),
      fmtDate: vi.fn(() => "20240102"),
      generateFuturesCandidates: vi.fn(() => [{ month: 3, ticker: "ESH4 Index", year: 2024 }]),
      getDvdCols: vi.fn(() => [{ key: "dvd", value: "Dividend" }]),
      getDvdType: vi.fn(() => "Cash"),
      getDvdTypes: vi.fn(() => [{ key: "C", value: "Cash" }]),
      getEtfCols: vi.fn(() => [{ key: "ticker", value: "Ticker" }]),
      getExchangeOverride: vi.fn(() => null),
      getFuturesMonths: vi.fn(() => [{ key: "H", value: "March" }]),
      getMarketRule: vi.fn(() => ({ isContinuous: true, postMinutes: 0, preMinutes: 0 })),
      getMonthCode: vi.fn(() => "H"),
      getMonthName: vi.fn(() => "March"),
      inferTimezone: vi.fn(() => "America/New_York"),
      isLongFormat: vi.fn(() => false),
      isSpecificContract: vi.fn(() => true),
      listExchangeOverrides: vi.fn(() => []),
      normalizeTickers: vi.fn(() => ["AAPL US Equity"]),
      parseCdxTicker: vi.fn(() => ({
        asset: "Corp",
        index: "CDX IG",
        isGeneric: true,
        series: "S40",
        tenor: "5Y",
      })),
      parseDate: vi.fn(() => [2024, 1, 2]),
      parseTicker: vi.fn(() => ({ asset: "Equity", index: 0, prefix: "AAPL" })),
      pivotToWide: vi.fn((buffer: Buffer) => buffer),
      previousCdxSeries: vi.fn(() => "CDX IG S39 5Y Corp"),
      renameDividendColumns: vi.fn(() => [{ key: "DVD", value: "Dividend" }]),
      renameEtfColumns: vi.fn(() => [{ key: "ETF", value: "ETF" }]),
      sameCurrency: vi.fn(() => false),
      sessionTimesToUtc: vi.fn(() => ({ end: "21:00", start: "14:30" })),
      setExchangeOverride: vi.fn(),
      validateGenericTicker: vi.fn(),
    },
  } as unknown as XbbgCoreLike;
}

function byName(tools: readonly StructuredToolInterface[], name: string): StructuredToolInterface {
  const found = tools.find((entry) => entry.name === name);
  if (found === undefined) {
    throw new Error(`Missing tool ${name}`);
  }
  return found;
}

async function invokeArtifact(tool: StructuredToolInterface, input: unknown) {
  const result = await tool.invoke(input, {
    toolCall: { args: {}, id: `call_${tool.name}`, name: tool.name },
  });
  if (!ToolMessage.isInstance(result)) {
    throw new TypeError(`Expected ToolMessage from ${tool.name}`);
  }
  if (typeof result.content !== "string") {
    throw new TypeError(`Expected string content from ${tool.name}`);
  }
  return [result.content, result.artifact] as const;
}

async function invokeJson(tool: StructuredToolInterface, input: unknown) {
  const [, artifact] = await invokeArtifact(tool, input);
  return artifact as Record<string, any>;
}

describe("Bloomberg request tools", () => {
  it("creates tool objects without connecting to Bloomberg", () => {
    const engine = fakeEngine();
    const core = fakeCore(engine);

    const tools = createAllBloombergTools({ core });

    expect(tools.map((entry) => entry.name)).toContain("xbbg_bdp");
    expect(core.connect).not.toHaveBeenCalled();
  });

  it("honors disabledTools for request and recipe tools", () => {
    const engine = fakeEngine();
    const tools = createBloombergTools({
      core: fakeCore(engine),
      disabledTools: ["xbbg_beqs", "xbbg_etf_holdings", "xbbg_stream_snapshot"],
    });

    const names = tools.map((entry) => entry.name);
    expect(names).not.toContain("xbbg_beqs");
    expect(names).not.toContain("xbbg_etf_holdings");
    expect(names).not.toContain("xbbg_stream_snapshot");
    expect(names).toContain("xbbg_yas");
  });

  it("memoizes lazy engine creation across parallel tool calls", async () => {
    const engine = fakeEngine();
    let release!: () => void;
    const started = new Promise<void>((resolve) => {
      release = resolve;
    });
    const connect = vi.fn(async () => {
      await started;
      return engine;
    });
    const core = { ...fakeCore(engine), connect } as unknown as XbbgCoreLike;
    const tools = createBloombergTools({ core });

    const bdpPromise = byName(tools, "xbbg_bdp").invoke({
      fields: ["PX_LAST"],
      securities: ["AAPL US Equity"],
    });
    const bdhPromise = byName(tools, "xbbg_bdh").invoke({
      end: "2024-01-02",
      fields: ["PX_LAST"],
      securities: ["AAPL US Equity"],
      start: "2024-01-01",
    });

    release();
    await Promise.all([bdpPromise, bdhPromise]);
    expect(connect).toHaveBeenCalledTimes(1);
  });

  it("calls every request method with json backend and normalized inputs", async () => {
    const engine = fakeEngine();
    const core = fakeCore(engine);
    const tools = createBloombergTools({
      core,
      maxRows: 1,
      maxStringChars: 20,
      validateFields: true,
    });

    const bdp = await invokeJson(byName(tools, "xbbg_bdp"), {
      fields: [" PX_LAST "],
      overrides: { EQY_FUND_CRNCY: " USD " },
      securities: [" AAPL US Equity "],
    });
    expect(engine.bdp).toHaveBeenCalledWith(
      ["AAPL US Equity"],
      ["PX_LAST"],
      expect.objectContaining({ backend: "json", validateFields: true }),
    );
    expect(bdp).toMatchObject({ rowCount: 1, tool: "xbbg_bdp", truncated: true });
    expect(bdp.data[0].value).toContain("[truncated");

    await invokeJson(byName(tools, "xbbg_bdh"), {
      end: "2024-01-31",
      fields: ["PX_LAST"],
      securities: ["AAPL US Equity"],
      start: "20240101",
    });
    expect(engine.bdh).toHaveBeenCalledWith(
      ["AAPL US Equity"],
      ["PX_LAST"],
      expect.objectContaining({ backend: "json", end: "20240131", start: "20240101" }),
    );

    await invokeJson(byName(tools, "xbbg_bds"), {
      field: " INDX_MEMBERS ",
      securities: ["SPX Index"],
    });
    expect(engine.bds).toHaveBeenCalledWith(
      ["SPX Index"],
      ["INDX_MEMBERS"],
      expect.objectContaining({ backend: "json" }),
    );

    await invokeJson(byName(tools, "xbbg_bdib"), {
      end: "2024-01-02T16:00:00-05:00",
      interval: 5,
      start: "2024-01-02 09:30:00",
      ticker: "AAPL US Equity",
    });
    expect(engine.bdib).toHaveBeenCalledWith(
      "AAPL US Equity",
      expect.objectContaining({ backend: "json", interval: 5, start: "2024-01-02T09:30:00" }),
    );

    await invokeJson(byName(tools, "xbbg_bdtick"), {
      end: "2024-01-02T10:00:00-05:00",
      eventTypes: [" BID ", "ASK"],
      includeBrokerCodes: true,
      start: "2024-01-02T09:30:00-05:00",
      ticker: "AAPL US Equity",
    });
    expect(engine.bdtick).toHaveBeenCalledWith(
      "AAPL US Equity",
      expect.objectContaining({
        backend: "json",
        eventTypes: ["BID", "ASK"],
        includeBrokerCodes: true,
      }),
    );

    await invokeJson(byName(tools, "xbbg_bql"), { query: " get(px_last) for([AAPL US Equity]) " });
    expect(engine.bql).toHaveBeenCalledWith(
      "get(px_last) for([AAPL US Equity])",
      expect.objectContaining({ backend: "json" }),
    );

    await invokeJson(byName(tools, "xbbg_bsrch"), { searchSpec: " COMDTY:NG " });
    expect(engine.bsrch).toHaveBeenCalledWith(
      "COMDTY:NG",
      expect.objectContaining({ backend: "json" }),
    );

    await invokeJson(byName(tools, "xbbg_bqr"), {
      end: "2024-06-03T15:00:00",
      eventTypes: ["BID", "ASK"],
      start: "2024-06-03T14:30:00",
      ticker: "IBM US Equity@MSG1",
    });
    expect(engine.bqr).toHaveBeenCalledWith(
      "IBM US Equity@MSG1",
      expect.objectContaining({
        backend: "json",
        endDatetime: "2024-06-03T15:00:00",
        eventTypes: ["BID", "ASK"],
        startDatetime: "2024-06-03T14:30:00",
      }),
    );

    await invokeJson(byName(tools, "xbbg_bflds"), { fields: [" PX_LAST "] });
    expect(engine.bflds).toHaveBeenCalledWith(
      expect.objectContaining({ backend: "json", fields: ["PX_LAST"] }),
    );

    await invokeJson(byName(tools, "xbbg_beqs"), {
      asof: "2024-01-02",
      group: " General ",
      overrides: { LANG: " EN " },
      screen: " Capital Goods ",
      screenType: " PRIVATE ",
    });
    expect(engine.beqs).toHaveBeenCalledWith(
      "Capital Goods",
      expect.objectContaining({
        asof: "20240102",
        backend: "json",
        group: "General",
        overrides: { LANG: "EN" },
        screenType: "PRIVATE",
      }),
    );

    await invokeJson(byName(tools, "xbbg_yas"), {
      fields: [" YAS_BOND_YLD "],
      price: 99,
      settleDt: "2024-01-02",
      tickers: [" IBM Corp "],
    });
    expect(engine.yas).toHaveBeenCalledWith(
      ["IBM Corp"],
      ["YAS_BOND_YLD"],
      expect.objectContaining({ backend: "json", price: 99, settleDt: "20240102" }),
    );

    await invokeJson(byName(tools, "xbbg_preferreds"), {
      equityTicker: " AAPL US Equity ",
      fields: [" id "],
    });
    expect(engine.preferreds).toHaveBeenCalledWith(
      "AAPL US Equity",
      expect.objectContaining({ backend: "json", fields: ["id"] }),
    );

    await invokeJson(byName(tools, "xbbg_corporate_bonds"), {
      activeOnly: false,
      ccy: " USD ",
      fields: [" id "],
      ticker: " AAPL US Equity ",
    });
    expect(engine.corporateBonds).toHaveBeenCalledWith(
      "AAPL US Equity",
      expect.objectContaining({
        activeOnly: false,
        backend: "json",
        ccy: "USD",
        fields: ["id"],
      }),
    );

    await invokeJson(byName(tools, "xbbg_index_members"), {
      asof: "2024-01-31",
      field: "INDX_MEMBERS",
      index: " SPX Index ",
    });
    expect(engine.indexMembers).toHaveBeenCalledWith(
      "SPX Index",
      expect.objectContaining({ asof: "20240131", backend: "json", field: "INDX_MEMBERS" }),
    );

    await invokeJson(byName(tools, "xbbg_resolve_isins"), { isins: [" US0378331005 "] });
    expect(engine.resolveIsins).toHaveBeenCalledWith(
      ["US0378331005"],
      expect.objectContaining({ backend: "json" }),
    );

    await invokeJson(byName(tools, "xbbg_issuer_isins"), { bondIsins: [" US037833FB15 "] });
    expect(engine.issuerIsins).toHaveBeenCalledWith(
      ["US037833FB15"],
      expect.objectContaining({ backend: "json" }),
    );

    await invokeJson(byName(tools, "xbbg_etf_holdings"), {
      etfTicker: " SPY US Equity ",
      fields: [" id "],
    });
    expect(engine.etfHoldings).toHaveBeenCalledWith(
      "SPY US Equity",
      expect.objectContaining({ backend: "json", fields: ["id"] }),
    );
  });

  it("passes security identifiers unchanged and documents Bloomberg identifier syntax", async () => {
    const engine = fakeEngine();
    const tools = createBloombergTools({ core: fakeCore(engine) });

    expect(BLOOMBERG_TOOL_INSTRUCTIONS).toContain("/isin/{isin}");
    expect(BLOOMBERG_TOOL_INSTRUCTIONS).toContain("/cusip/{cusip}");
    expect(BLOOMBERG_TOOL_INSTRUCTIONS).toContain("/isin/US037833FB15@MSG1 Corp");
    expect(BLOOMBERG_TOOL_INSTRUCTIONS).toContain("xbbg_bdtick");
    expect(BLOOMBERG_TOOL_INSTRUCTIONS).toContain("xbbg_bqr");
    expect(BLOOMBERG_TOOL_INSTRUCTIONS).toContain("get(px_last) for('AAPL US Equity')");
    expect(BLOOMBERG_TOOL_INSTRUCTIONS).toContain("holdings('SPY US Equity')");
    expect(BLOOMBERG_TOOL_INSTRUCTIONS).toContain("members('SPX Index')");
    expect(BLOOMBERG_TOOL_INSTRUCTIONS).toContain("filter_valid_contracts");
    expect(BLOOMBERG_TOOL_INSTRUCTIONS).toContain("YAS_BOND_YLD");
    expect(BLOOMBERG_TOOL_INSTRUCTIONS).toContain("default_bqr_datetimes");
    expect(BLOOMBERG_TOOL_INSTRUCTIONS).toContain("## Core request tools");
    expect(BLOOMBERG_TOOL_INSTRUCTIONS).toContain("## Extension helper tools");
    expect(BLOOMBERG_TOOL_INSTRUCTIONS).toContain("rowCount");
    expect(BLOOMBERG_TOOL_INSTRUCTIONS).toContain("truncated");

    const requiredOnly = getBloombergToolInstructions({
      includeExtensionGuidance: false,
      includeLimitReminder: false,
    });
    expect(requiredOnly).toContain("## Core request tools");
    expect(requiredOnly).not.toContain("## Extension helper tools");
    expect(requiredOnly).not.toContain("## Request limits and inputs");

    await invokeJson(byName(tools, "xbbg_bdp"), {
      fields: ["PX_LAST"],
      securities: [" US0378331005 ", " /isin/US0378331005 "],
    });
    expect(engine.bdp).toHaveBeenCalledWith(
      ["US0378331005", "/isin/US0378331005"],
      ["PX_LAST"],
      expect.objectContaining({ backend: "json" }),
    );
  });

  it("returns compact content and structured artifacts", async () => {
    const engine = fakeEngine();
    const tools = createBloombergTools({ core: fakeCore(engine), maxStringChars: 20 });
    const bdp = byName(tools, "xbbg_bdp");

    expect((bdp as unknown as { readonly responseFormat?: string }).responseFormat).toBe(
      "content_and_artifact",
    );

    const [summary, artifact] = await invokeArtifact(bdp, {
      fields: ["PX_LAST"],
      securities: ["AAPL US Equity"],
    });

    expect(summary).toContain("xbbg_bdp: 1 row");
    expect(summary).toContain("truncated=true");
    expect(artifact).toMatchObject({ rowCount: 1, tool: "xbbg_bdp", truncated: true });

    const node = new ToolNode([bdp]);
    const result = (await node.invoke({
      messages: [
        new AIMessage({
          content: "",
          tool_calls: [
            {
              args: { fields: ["PX_LAST"], securities: ["AAPL US Equity"] },
              id: "call_bdp",
              name: "xbbg_bdp",
              type: "tool_call",
            },
          ],
        }),
      ],
    })) as { messages: unknown[] };

    const [message] = result.messages;
    expect(message).toBeInstanceOf(ToolMessage);
    expect((message as ToolMessage).content).toContain("xbbg_bdp: 1 row");
    expect((message as ToolMessage).content).not.toContain("12345678901234567890");
    expect((message as ToolMessage).artifact).toMatchObject({
      rowCount: 1,
      tool: "xbbg_bdp",
    });
  });

  it("collects bounded snapshot tools and always unsubscribes", async () => {
    const engine = fakeEngine();
    const tools = createBloombergTools({
      core: fakeCore(engine),
      maxStreamUpdates: 3,
      maxStreamWaitMs: 1_000,
    });

    const streamSub = fakeSubscription([
      { toObject: () => ({ LAST_PRICE: 123n, topic: "AAPL US Equity" }) },
      { toObject: () => ({ LAST_PRICE: 124, topic: "AAPL US Equity" }) },
    ]);
    vi.mocked(engine.stream).mockResolvedValueOnce(streamSub.subscription);

    const stream = await invokeJson(byName(tools, "xbbg_stream_snapshot"), {
      conflate: true,
      drain: true,
      fields: [" LAST_PRICE "],
      maxUpdates: 2,
      tickers: [" AAPL US Equity "],
      timeoutMs: 1_000,
    });

    expect(engine.stream).toHaveBeenCalledWith(
      ["AAPL US Equity"],
      ["LAST_PRICE"],
      expect.objectContaining({ conflate: true }),
    );
    expect(stream.data).toMatchObject({ reason: "max_updates", updateCount: 2 });
    expect(stream.data.updates[0].LAST_PRICE).toBe("123");
    expect(streamSub.unsubscribe).toHaveBeenCalledWith(true);

    const mktbarSub = fakeSubscription([
      { toArray: () => [{ close: 1n, time: new Date(Date.UTC(2024, 0, 2)) }] },
    ]);
    vi.mocked(engine.mktbar).mockResolvedValueOnce(mktbarSub.subscription);

    const mktbar = await invokeJson(byName(tools, "xbbg_mktbar_snapshot"), {
      fields: [" LAST_PRICE "],
      maxUpdates: 1,
      ticker: " AAPL US Equity ",
      timeoutMs: 1_000,
    });

    expect(engine.mktbar).toHaveBeenCalledWith(
      "AAPL US Equity",
      expect.objectContaining({ fields: ["LAST_PRICE"] }),
    );
    expect(mktbar.data.updates[0]).toEqual([{ close: "1", time: "2024-01-02T00:00:00.000Z" }]);
    expect(mktbarSub.unsubscribe).toHaveBeenCalledWith(false);

    const depthSub = fakeSubscription([{ toObject: () => ({ BID: 1, topic: "AAPL US Equity" }) }]);
    vi.mocked(engine.depth).mockResolvedValueOnce(depthSub.subscription);

    const depth = await invokeJson(byName(tools, "xbbg_depth_snapshot"), {
      maxUpdates: 2,
      ticker: " AAPL US Equity ",
      timeoutMs: 1_000,
    });

    expect(engine.depth).toHaveBeenCalledWith("AAPL US Equity", expect.objectContaining({}));
    expect(depth.data).toMatchObject({ reason: "done", updateCount: 1 });
    expect(depthSub.unsubscribe).toHaveBeenCalledWith(false);

    const failingSub = fakeSubscription([], new Error("boom"));
    vi.mocked(engine.depth).mockResolvedValueOnce(failingSub.subscription);

    await expect(
      byName(tools, "xbbg_depth_snapshot").invoke({
        maxUpdates: 1,
        ticker: "AAPL US Equity",
        timeoutMs: 1_000,
      }),
    ).rejects.toThrow(/xbbg_depth_snapshot failed: boom/u);
    expect(failingSub.unsubscribe).toHaveBeenCalledWith(false);
  });

  it("rejects unsafe or ambiguous request inputs", async () => {
    const tools = createBloombergTools({
      core: fakeCore(fakeEngine()),
      maxSecurities: 1,
      maxFields: 1,
      maxStreamUpdates: 1,
    });

    await expect(
      byName(tools, "xbbg_bdp").invoke({ fields: ["PX_LAST"], securities: ["A", "B"] }),
    ).rejects.toThrow(/at most 1/u);
    await expect(
      byName(tools, "xbbg_bdp").invoke({ fields: [""], securities: ["AAPL US Equity"] }),
    ).rejects.toThrow(/non-empty/u);
    await expect(
      byName(tools, "xbbg_bdp").invoke({
        fields: ["PX_LAST"],
        overrides: { bad: { nested: true } },
        securities: ["AAPL US Equity"],
      }),
    ).rejects.toThrow();
    await expect(
      byName(tools, "xbbg_bdh").invoke({
        end: "2024-01-01",
        fields: ["PX_LAST"],
        securities: ["AAPL US Equity"],
        start: "01/01/2024",
      }),
    ).rejects.toThrow();
    await expect(
      byName(tools, "xbbg_bdh").invoke({
        end: "2024-01-01",
        fields: ["PX_LAST"],
        securities: ["AAPL US Equity"],
        start: "2024-01-02",
      }),
    ).rejects.toThrow();
    await expect(
      byName(tools, "xbbg_bdib").invoke({
        end: "2024-01-02T10:00:00",
        interval: 0,
        start: "2024-01-02T09:30:00",
        ticker: "AAPL US Equity",
      }),
    ).rejects.toThrow(/greater than zero/u);
    await expect(
      byName(tools, "xbbg_bflds").invoke({ fields: ["PX_LAST"], searchSpec: "last price" }),
    ).rejects.toThrow(/exactly one/u);
    await expect(
      byName(tools, "xbbg_stream_snapshot").invoke({
        fields: ["PX"],
        maxUpdates: 2,
        tickers: ["A"],
      }),
    ).rejects.toThrow(/at most 1/u);
    await expect(
      byName(tools, "xbbg_stream_snapshot").invoke({
        fields: ["PX"],
        tickers: ["A"],
      }),
    ).rejects.toThrow();
  });

  it("does not mutate original results while truncating output", async () => {
    const original = [{ text: "1234567890" }, { text: "second" }];
    const engine = fakeEngine();
    vi.mocked(engine.bdp).mockResolvedValue(original);
    const tools = createBloombergTools({ core: fakeCore(engine), maxRows: 1, maxStringChars: 4 });

    const output = await invokeJson(byName(tools, "xbbg_bdp"), {
      fields: ["PX"],
      securities: ["A"],
    });

    expect(output).toMatchObject({ rowCount: 2, truncated: true });
    expect(output.data).toHaveLength(1);
    expect(output.data[0].text).toBe("1234…[truncated 6 chars]");
    expect(original).toEqual([{ text: "1234567890" }, { text: "second" }]);
  });
});

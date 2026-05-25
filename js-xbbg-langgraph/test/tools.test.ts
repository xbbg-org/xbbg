import type { StructuredToolInterface } from "@langchain/core/tools";

import { createAllBloombergTools, createBloombergTools } from "../src";
import type { XbbgCoreLike, XbbgEngineLike } from "../src/core-loader";

function fakeEngine(): XbbgEngineLike {
  return {
    bdp: vi.fn(async () => [
      { ticker: "AAPL US Equity", field: "PX_LAST", value: "1234567890123456789012345" },
    ]),
    bdh: vi.fn(async () => [{ ticker: "AAPL US Equity", date: "20240102", value: 1 }]),
    bdib: vi.fn(async () => [{ time: "2024-01-02T09:30:00-05:00", close: 1 }]),
    bds: vi.fn(async () => [{ member: "AAPL US Equity" }]),
    bflds: vi.fn(async () => [{ id: "PX_LAST" }]),
    bql: vi.fn(async () => [{ value: 1 }]),
    bsrch: vi.fn(async () => [{ security: "AAPL US Equity" }]),
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

async function invokeJson(tool: StructuredToolInterface, input: unknown) {
  return JSON.parse(String(await tool.invoke(input)));
}

describe("Bloomberg request tools", () => {
  it("creates tool objects without connecting to Bloomberg", () => {
    const engine = fakeEngine();
    const core = fakeCore(engine);

    const tools = createAllBloombergTools({ core });

    expect(tools.map((entry) => entry.name)).toContain("xbbg_bdp");
    expect(core.connect).not.toHaveBeenCalled();
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

    await invokeJson(byName(tools, "xbbg_bflds"), { fields: [" PX_LAST "] });
    expect(engine.bflds).toHaveBeenCalledWith(
      expect.objectContaining({ backend: "json", fields: ["PX_LAST"] }),
    );
  });

  it("rejects unsafe or ambiguous request inputs", async () => {
    const tools = createBloombergTools({
      core: fakeCore(fakeEngine()),
      maxSecurities: 1,
      maxFields: 1,
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

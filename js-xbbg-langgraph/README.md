# @xbbg/langgraph

LangChain/LangGraph-compatible Bloomberg tools backed by [`@xbbg/core`](../js-xbbg/README.md).

This package is a reusable tool adapter. It is not a chat app, HTTP server, MCP server, browser package, or agent framework.

## Prerequisites

Bloomberg connectivity is still provided by `@xbbg/core`: an installed Bloomberg Terminal/Desktop API, B-PIPE, SAPI, or ZFP setup plus Bloomberg SDK runtime libraries must be available on the server running the tools.

## Install

Tool package only:

```bash
npm install @xbbg/langgraph @xbbg/core @langchain/core
```

LangGraph app:

```bash
npm install @xbbg/langgraph @xbbg/core @langchain/core @langchain/langgraph
```

Current LangChain agent app:

```bash
npm install @xbbg/langgraph @xbbg/core @langchain/core langchain
```

## Agent guidance

Append the exported instructions to your system prompt:

```ts
import { BLOOMBERG_TOOL_INSTRUCTIONS } from "@xbbg/langgraph";
```

The instructions tell the model to ask clarifying questions for ambiguous tickers, fields, date ranges, currencies, periodicity, overrides, or universes; request `/isin/{isin}` for ISIN identifiers and `/cusip/{cusip}` for CUSIPs; use `xbbg_bflds` for unknown fields; prefer finite recipe tools for BEQS/YAS/universe workflows; use bounded snapshot tools instead of open subscriptions; keep requests bounded; and report empty, truncated, or errored responses directly.

## LangChain `createAgent` example

```ts
import { createAgent } from "langchain";
import { ChatOpenAI } from "@langchain/openai";
import { createAllBloombergTools, BLOOMBERG_TOOL_INSTRUCTIONS } from "@xbbg/langgraph";

const tools = createAllBloombergTools({
  maxSecurities: 10,
  maxFields: 10,
});

const agent = createAgent({
  model: new ChatOpenAI({ model: "gpt-4.1" }),
  tools,
  systemPrompt: BLOOMBERG_TOOL_INSTRUCTIONS,
});

const result = await agent.invoke({
  messages: [{ role: "user", content: "Get PX_LAST for AAPL US Equity." }],
});
```

## LangGraph example

`createReactAgent` from `@langchain/langgraph/prebuilt` is deprecated upstream in favor of `createAgent` from `langchain`, but it is still common in LangGraph examples and accepts these tools because they are normal LangChain tools.

```ts
import { createReactAgent } from "@langchain/langgraph/prebuilt";
import { ChatOpenAI } from "@langchain/openai";
import { createBloombergTools, BLOOMBERG_TOOL_INSTRUCTIONS } from "@xbbg/langgraph";

const agent = createReactAgent({
  llm: new ChatOpenAI({ model: "gpt-4.1" }),
  tools: createBloombergTools({ maxSecurities: 5, maxFields: 5 }),
  prompt: BLOOMBERG_TOOL_INSTRUCTIONS,
});
```

For custom graphs, pass the returned tools to LangGraph's `ToolNode`.

All tools use LangChain `responseFormat: "content_and_artifact"`. In `ToolNode`, the tool message content is a compact summary for the model, while `artifact` contains the bounded structured envelope for application code.

## Tool factories

Core Bloomberg request tools:

- `xbbg_bdp` - reference/current fields such as `PX_LAST`, `NAME`, `CUR_MKT_CAP`.
- `xbbg_bdh` - historical time series; requires explicit `start` and `end`.
- `xbbg_bds` - one Bloomberg bulk/table field such as index members.
- `xbbg_bdib` - intraday bars; requires explicit `start`, `end`, and `interval`.
- `xbbg_bdtick` - intraday ticks; requires explicit `start`, `end`, and event types when not using `TRADE`.
- `xbbg_bql` - BQL expressions only.
- `xbbg_bsrch` - Bloomberg search/grid requests, not normal security lookup.
- `xbbg_bqr` - Bloomberg Quote Request / fixed-income dealer quotes; prefer identifiers such as `/isin/US037833FB15@MSG1 Corp`.
- `xbbg_bflds` - field metadata/search; use first for uncertain mnemonics.
- `xbbg_beqs` - named Bloomberg BEQS equity screens.
- `xbbg_yas` - fixed-income YAS recipe fields such as `YAS_BOND_YLD`, `YAS_MOD_DUR`, `YAS_ZSPREAD`, and `YAS_BOND_PX`.
- `xbbg_preferreds` - preferred stock discovery for one equity ticker.
- `xbbg_corporate_bonds` - corporate bond universe query for one issuer/company ticker.
- `xbbg_index_members` - index constituents through the core index recipe.
- `xbbg_resolve_isins` - raw ISIN-to-security resolution; pass raw ISIN strings to this recipe only.
- `xbbg_issuer_isins` - issuer/bond ISIN workflow starting from known bond ISIN strings.
- `xbbg_etf_holdings` - ETF holdings for one ETF ticker.
- `xbbg_stream_snapshot` - bounded `//blp/mktdata` live observation that always unsubscribes.
- `xbbg_mktbar_snapshot` - bounded `//blp/mktbar` live bar observation for one ticker.
- `xbbg_depth_snapshot` - bounded `//blp/mktdepthdata` market-depth observation for one ticker.

For raw identifiers, ask for or pass Bloomberg's identifier syntax directly: `/isin/US0378331005` for ISINs and `/cusip/037833100` for CUSIPs.
BQL is passed as one complete expression string. Use shapes such as `get(px_last) for('AAPL US Equity')`, `get(px_last, volume) for(['IBM US Equity', 'AAPL US Equity'])`, `get(id_isin, weights) for(holdings('SPY US Equity'))`, or `get(px_last) for(members('SPX Index')) with(...)`. Prefer `xbbg_bdp`/`xbbg_bdh` for simple reference or historical requests.

Dealer quote / BQR workflows in xbbg use fixed-income identifiers with a quote source, for example `/isin/US037833FB15@MSG1 Corp`; use `xbbg_bqr` for that workflow and `xbbg_bdtick` for raw intraday ticks.

Streaming surfaces are intentionally exposed only as bounded snapshot tools. Each snapshot requires `maxUpdates`, applies the configured `maxStreamUpdates`/`maxStreamWaitMs` caps, stops on count, timeout, or stream completion, and calls `unsubscribe(false)` unless `drain: true` is explicitly provided. The package does not expose open-ended async subscription iterators as agent tools.

```ts
import { createBloombergTools, createBdpTool } from "@xbbg/langgraph";

const tools = createBloombergTools();
const bdpOnly = createBdpTool({ maxSecurities: 3 });
```

Extension helper tools:

- `xbbg_ext_ticker` - ticker hygiene before live requests: parse, normalize lists, filter equity tickers, check specific contracts, and validate generic futures tickers.
- `xbbg_ext_futures` - futures construction and selection: month-code lookup, build a specific contract, generate candidates from a generic, rank contracts, filter by cycle, and filter valid contracts for a date.
- `xbbg_ext_cdx` - CDX workflows: parse CDX tickers, roll to previous series, resolve generic to specific series, and run predefined CDX info/pricing/risk field bundles.
- `xbbg_ext_currency` - currency planning: build FX pair metadata, test same-currency requests, and identify currencies needing conversion to a target.
- `xbbg_ext_bql_builder` - BQL query builders for preferred stocks, corporate bonds, and ETF holdings; prefer these over hand-writing those query shapes.
- `xbbg_ext_market_session` - exchange sessions and timezones: derive sessions, infer timezone, convert local session times to UTC, fetch market rules, compute turnover/BQR default ranges, and inspect exchange overrides.
- `xbbg_ext_yas_overrides` - build flat YAS override maps for lower-level fixed-income BDP workflows. Prefer `xbbg_yas` when you want the actual YAS recipe result.
- `xbbg_ext_constants` - static constants and formatting helpers for dates, futures months, dividend types, and ETF/dividend columns.
- `xbbg_ext_columns` - rename helpers for dividend, ETF, and earnings-shaped Bloomberg responses.
- `xbbg_ext_calculate` - small numeric helper for level percentage calculations.

```ts
import { createBloombergExtTools, createAllBloombergTools } from "@xbbg/langgraph";

const helperTools = createBloombergExtTools();
const allTools = createAllBloombergTools({
  disabledTools: ["xbbg_bql", "xbbg_bsrch"],
});
```

## Engine handling

By default the first tool invocation lazily imports `@xbbg/core`, calls `connect(engineConfig)`, and reuses the resulting engine across the tool set. Parallel LangGraph tool calls share the same in-flight initialization promise.

```ts
import * as xbbg from "@xbbg/core";
import { createBloombergTools } from "@xbbg/langgraph";

const engine = await xbbg.connect({ host: "localhost", port: 8194 });
const tools = createBloombergTools({ engine });
```

## Limits and outputs

Defaults:

- `maxSecurities = 25`
- `maxFields = 25`
- `maxRows = 500`
- `maxStringChars = 2000`
- `maxStreamUpdates = 10`
- `maxStreamWaitMs = 15000`

Each tool uses `backend: "json"` for finite request results and LangChain `content_and_artifact` output. The model-facing content is a short summary, for example:

```text
xbbg_bdp: 1 row; truncated=false
```

The artifact is the bounded structured envelope:

```json
{ "tool": "xbbg_bdp", "rowCount": 1, "truncated": false, "data": [{ "ticker": "AAPL US Equity" }] }
```

When invoking tools outside an agent graph and you need the artifact, invoke with a tool-call id (or use LangGraph `ToolNode`) so LangChain returns a `ToolMessage` with `artifact`.

Use smaller factories or `disabledTools` when broad BQL/search helpers are not appropriate for a deployment.

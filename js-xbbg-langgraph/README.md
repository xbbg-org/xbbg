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

The instructions tell the model to ask clarifying questions for ambiguous tickers, fields, date ranges, currencies, or periodicity; use `xbbg_bflds` for unknown fields; use extension helpers before live Bloomberg calls; and keep requests bounded.

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

## Tool factories

Core Bloomberg request tools:

- `xbbg_bdp` - reference/current fields such as `PX_LAST`, `NAME`, `CUR_MKT_CAP`.
- `xbbg_bdh` - historical time series; requires explicit `start` and `end`.
- `xbbg_bds` - one Bloomberg bulk/table field such as index members.
- `xbbg_bdib` - intraday bars; requires explicit `start`, `end`, and `interval`.
- `xbbg_bql` - BQL expressions only.
- `xbbg_bsrch` - Bloomberg search/grid requests, not normal security lookup.
- `xbbg_bflds` - field metadata/search; use first for uncertain mnemonics.

```ts
import { createBloombergTools, createBdpTool } from "@xbbg/langgraph";

const tools = createBloombergTools();
const bdpOnly = createBdpTool({ maxSecurities: 3 });
```

Extension helper tools:

- `xbbg_ext_ticker`
- `xbbg_ext_futures`
- `xbbg_ext_cdx`
- `xbbg_ext_currency`
- `xbbg_ext_bql_builder`
- `xbbg_ext_market_session`
- `xbbg_ext_yas_overrides`
- `xbbg_ext_constants`
- `xbbg_ext_columns`
- `xbbg_ext_calculate`

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

Each request uses `backend: 'json'` and returns a JSON string envelope:

```json
{ "tool": "xbbg_bdp", "rowCount": 1, "truncated": false, "data": [{ "ticker": "AAPL US Equity" }] }
```

Use smaller factories or `disabledTools` when broad BQL/search helpers are not appropriate for a deployment.

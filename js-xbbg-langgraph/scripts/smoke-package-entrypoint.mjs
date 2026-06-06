import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const entrypoint = new URL("../dist/index.js", import.meta.url);

assert.ok(existsSync(entrypoint), "dist/index.js is missing; run npm run build first");

const xbbgLangGraph = require("../dist/index.js");

for (const exportName of [
  "BLOOMBERG_TOOL_INSTRUCTIONS",
  "BLOOMBERG_TOOL_NAMES",
  "BLOOMBERG_EXT_TOOL_NAMES",
]) {
  assert.ok(exportName in xbbgLangGraph, `Missing public export ${exportName}`);
}

for (const exportName of [
  "createAllBloombergTools",
  "createBloombergTools",
  "createBloombergExtTools",
  "createBdpTool",
  "getBloombergToolInstructions",
]) {
  assert.equal(typeof xbbgLangGraph[exportName], "function", `${exportName} should be a function`);
}

assert.ok(
  Array.isArray(xbbgLangGraph.BLOOMBERG_TOOL_NAMES),
  "BLOOMBERG_TOOL_NAMES should be an array",
);
assert.ok(
  xbbgLangGraph.BLOOMBERG_TOOL_NAMES.includes("xbbg_bdp"),
  "BLOOMBERG_TOOL_NAMES should include xbbg_bdp",
);
assert.ok(
  xbbgLangGraph.BLOOMBERG_EXT_TOOL_NAMES.includes("xbbg_ext_ticker"),
  "BLOOMBERG_EXT_TOOL_NAMES should include xbbg_ext_ticker",
);

const tools = xbbgLangGraph.createBloombergTools({ disabledTools: ["xbbg_bql"] });
assert.ok(
  tools.some((tool) => tool.name === "xbbg_bdp"),
  "createBloombergTools should expose xbbg_bdp",
);
assert.ok(!tools.some((tool) => tool.name === "xbbg_bql"), "disabledTools should remove xbbg_bql");

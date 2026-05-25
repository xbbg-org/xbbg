import { createCoreResolver } from "./core-loader";
import { createBloombergExtToolsForResolver } from "./ext-tools";
import type { BloombergToolsOptions } from "./options";
import { createBloombergToolsForResolver, type BloombergTool } from "./tools";

export {
  BLOOMBERG_TOOL_INSTRUCTIONS,
  getBloombergToolInstructions,
  type BloombergToolInstructionsOptions,
} from "./descriptions";
export {
  createBloombergExtTools,
  createExtBqlBuilderTool,
  createExtCalculateTool,
  createExtCdxTool,
  createExtColumnsTool,
  createExtConstantsTool,
  createExtCurrencyTool,
  createExtFuturesTool,
  createExtMarketSessionTool,
  createExtTickerTool,
  createExtYasOverridesTool,
} from "./ext-tools";
export {
  BLOOMBERG_TOOL_NAMES,
  type BloombergToolName,
  type BloombergToolsOptions,
  type NormalizedBloombergToolsOptions,
} from "./options";
export type { ToolEnvelope } from "./result-limits";
export {
  createBdhTool,
  createBdibTool,
  createBeqsTool,
  createBdtickTool,
  createBdpTool,
  createBdsTool,
  createBfldsTool,
  createCorporateBondsTool,
  createEtfHoldingsTool,
  createDepthSnapshotTool,
  createIndexMembersTool,
  createIssuerIsinsTool,
  createMktbarSnapshotTool,
  createPreferredsTool,
  createResolveIsinsTool,
  createStreamSnapshotTool,
  createYasTool,
  createBloombergTools,
  createBqlTool,
  createBsrchTool,
  createBqrTool,
  type BloombergTool,
} from "./tools";

export function createAllBloombergTools(options: BloombergToolsOptions = {}): BloombergTool[] {
  const resolver = createCoreResolver(options);
  return [
    ...createBloombergToolsForResolver(resolver),
    ...createBloombergExtToolsForResolver(resolver),
  ];
}

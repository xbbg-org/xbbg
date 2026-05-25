import { tool, type StructuredToolInterface } from "@langchain/core/tools";

import { createCoreResolver, type CoreResolver } from "./core-loader";
import {
  BDP_DESCRIPTION,
  BDH_DESCRIPTION,
  BDS_DESCRIPTION,
  BDIB_DESCRIPTION,
  BDTICK_DESCRIPTION,
  BFLDS_DESCRIPTION,
  BQL_DESCRIPTION,
  BSRCH_DESCRIPTION,
  BQR_DESCRIPTION,
} from "./descriptions";
import type { BloombergToolsOptions, BloombergToolName } from "./options";
import { isToolDisabled } from "./options";
import { stringifyToolResult, throwWithToolContext } from "./result-limits";
import {
  createBdhSchema,
  createBdibSchema,
  createBdtickSchema,
  createBdpSchema,
  createBdsSchema,
  createBfldsSchema,
  createBqlSchema,
  createBsrchSchema,
  createBqrSchema,
  type BdhInput,
  type BdibInput,
  type BdtickInput,
  type BdpInput,
  type BdsInput,
  type BfldsInput,
  type BqlInput,
  type BsrchInput,
  type BqrInput,
} from "./schemas";

export type BloombergTool = StructuredToolInterface;

type ToolCreator = (resolver: CoreResolver) => BloombergTool;

function resultString(resolver: CoreResolver, name: BloombergToolName, value: unknown): string {
  return stringifyToolResult(
    name,
    value,
    resolver.options.maxRows,
    resolver.options.maxStringChars,
  );
}

function validationSetting(
  resolver: CoreResolver,
  value: boolean | undefined,
): boolean | undefined {
  return value ?? resolver.options.validateFields;
}

function enabledTool(
  resolver: CoreResolver,
  name: BloombergToolName,
  creator: ToolCreator,
): BloombergTool[] {
  return isToolDisabled(resolver.options, name) ? [] : [creator(resolver)];
}

function bdpWithResolver(resolver: CoreResolver): BloombergTool {
  const name = "xbbg_bdp" satisfies BloombergToolName;
  return tool(
    async (input: BdpInput): Promise<string> => {
      try {
        const engine = await resolver.getEngine();
        const result = await engine.bdp(input.securities, input.fields, {
          backend: "json",
          format: input.format,
          includeSecurityErrors: input.includeSecurityErrors,
          kwargs: input.kwargs,
          overrides: input.overrides,
          validateFields: validationSetting(resolver, input.validateFields),
        });
        return resultString(resolver, name, result);
      } catch (error) {
        throwWithToolContext(name, error);
      }
    },
    {
      description: BDP_DESCRIPTION,
      name,
      schema: createBdpSchema(resolver.options),
    },
  );
}

function bdhWithResolver(resolver: CoreResolver): BloombergTool {
  const name = "xbbg_bdh" satisfies BloombergToolName;
  return tool(
    async (input: BdhInput): Promise<string> => {
      try {
        const engine = await resolver.getEngine();
        const result = await engine.bdh(input.securities, input.fields, {
          backend: "json",
          end: input.end,
          format: input.format,
          kwargs: input.kwargs,
          overrides: input.overrides,
          start: input.start,
          validateFields: validationSetting(resolver, input.validateFields),
        });
        return resultString(resolver, name, result);
      } catch (error) {
        throwWithToolContext(name, error);
      }
    },
    {
      description: BDH_DESCRIPTION,
      name,
      schema: createBdhSchema(resolver.options),
    },
  );
}

function bdsWithResolver(resolver: CoreResolver): BloombergTool {
  const name = "xbbg_bds" satisfies BloombergToolName;
  return tool(
    async (input: BdsInput): Promise<string> => {
      try {
        const engine = await resolver.getEngine();
        const result = await engine.bds(input.securities, [input.field], {
          backend: "json",
          format: input.format,
          kwargs: input.kwargs,
          overrides: input.overrides,
          validateFields: validationSetting(resolver, input.validateFields),
        });
        return resultString(resolver, name, result);
      } catch (error) {
        throwWithToolContext(name, error);
      }
    },
    {
      description: BDS_DESCRIPTION,
      name,
      schema: createBdsSchema(resolver.options),
    },
  );
}

function bdibWithResolver(resolver: CoreResolver): BloombergTool {
  const name = "xbbg_bdib" satisfies BloombergToolName;
  return tool(
    async (input: BdibInput): Promise<string> => {
      try {
        const engine = await resolver.getEngine();
        const result = await engine.bdib(input.ticker, {
          backend: "json",
          end: input.end,
          eventType: input.eventType,
          interval: input.interval,
          kwargs: input.kwargs,
          outputTz: input.outputTz,
          requestTz: input.requestTz,
          start: input.start,
        });
        return resultString(resolver, name, result);
      } catch (error) {
        throwWithToolContext(name, error);
      }
    },
    {
      description: BDIB_DESCRIPTION,
      name,
      schema: createBdibSchema(resolver.options),
    },
  );
}

function bdtickWithResolver(resolver: CoreResolver): BloombergTool {
  const name = "xbbg_bdtick" satisfies BloombergToolName;
  return tool(
    async (input: BdtickInput): Promise<string> => {
      try {
        const engine = await resolver.getEngine();
        const result = await engine.bdtick(input.ticker, {
          backend: "json",
          end: input.end,
          eventTypes: input.eventTypes,
          includeBicMicCodes: input.includeBicMicCodes,
          includeBloombergStandardConditionCodes: input.includeBloombergStandardConditionCodes,
          includeBrokerCodes: input.includeBrokerCodes,
          includeConditionCodes: input.includeConditionCodes,
          includeExchangeCodes: input.includeExchangeCodes,
          includeNonPlottableEvents: input.includeNonPlottableEvents,
          includeRpsCodes: input.includeRpsCodes,
          kwargs: input.kwargs,
          outputTz: input.outputTz,
          requestTz: input.requestTz,
          start: input.start,
        });
        return resultString(resolver, name, result);
      } catch (error) {
        throwWithToolContext(name, error);
      }
    },
    {
      description: BDTICK_DESCRIPTION,
      name,
      schema: createBdtickSchema(resolver.options),
    },
  );
}

function bqlWithResolver(resolver: CoreResolver): BloombergTool {
  const name = "xbbg_bql" satisfies BloombergToolName;
  return tool(
    async (input: BqlInput): Promise<string> => {
      try {
        const engine = await resolver.getEngine();
        const result = await engine.bql(input.query, {
          backend: "json",
          format: input.format,
          kwargs: input.kwargs,
        });
        return resultString(resolver, name, result);
      } catch (error) {
        throwWithToolContext(name, error);
      }
    },
    {
      description: BQL_DESCRIPTION,
      name,
      schema: createBqlSchema(resolver.options),
    },
  );
}

function bsrchWithResolver(resolver: CoreResolver): BloombergTool {
  const name = "xbbg_bsrch" satisfies BloombergToolName;
  return tool(
    async (input: BsrchInput): Promise<string> => {
      try {
        const engine = await resolver.getEngine();
        const result = await engine.bsrch(input.searchSpec, {
          backend: "json",
          format: input.format,
          kwargs: input.kwargs,
          overrides: input.overrides,
        });
        return resultString(resolver, name, result);
      } catch (error) {
        throwWithToolContext(name, error);
      }
    },
    {
      description: BSRCH_DESCRIPTION,
      name,
      schema: createBsrchSchema(resolver.options),
    },
  );
}

function bqrWithResolver(resolver: CoreResolver): BloombergTool {
  const name = "xbbg_bqr" satisfies BloombergToolName;
  return tool(
    async (input: BqrInput): Promise<string> => {
      try {
        const engine = await resolver.getEngine();
        const result = await engine.bqr(input.ticker, {
          backend: "json",
          endDatetime: input.end,
          eventTypes: input.eventTypes,
          includeBrokerCodes: input.includeBrokerCodes,
          startDatetime: input.start,
        });
        return resultString(resolver, name, result);
      } catch (error) {
        throwWithToolContext(name, error);
      }
    },
    {
      description: BQR_DESCRIPTION,
      name,
      schema: createBqrSchema(resolver.options),
    },
  );
}

function bfldsWithResolver(resolver: CoreResolver): BloombergTool {
  const name = "xbbg_bflds" satisfies BloombergToolName;
  return tool(
    async (input: BfldsInput): Promise<string> => {
      try {
        const engine = await resolver.getEngine();
        const result = await engine.bflds({
          backend: "json",
          fields: input.fields,
          format: input.format,
          kwargs: input.kwargs,
          searchSpec: input.searchSpec,
        });
        return resultString(resolver, name, result);
      } catch (error) {
        throwWithToolContext(name, error);
      }
    },
    {
      description: BFLDS_DESCRIPTION,
      name,
      schema: createBfldsSchema(resolver.options),
    },
  );
}

export function createBdpTool(options: BloombergToolsOptions = {}): BloombergTool {
  return bdpWithResolver(createCoreResolver(options));
}

export function createBdhTool(options: BloombergToolsOptions = {}): BloombergTool {
  return bdhWithResolver(createCoreResolver(options));
}

export function createBdsTool(options: BloombergToolsOptions = {}): BloombergTool {
  return bdsWithResolver(createCoreResolver(options));
}

export function createBdibTool(options: BloombergToolsOptions = {}): BloombergTool {
  return bdibWithResolver(createCoreResolver(options));
}

export function createBdtickTool(options: BloombergToolsOptions = {}): BloombergTool {
  return bdtickWithResolver(createCoreResolver(options));
}

export function createBqlTool(options: BloombergToolsOptions = {}): BloombergTool {
  return bqlWithResolver(createCoreResolver(options));
}

export function createBsrchTool(options: BloombergToolsOptions = {}): BloombergTool {
  return bsrchWithResolver(createCoreResolver(options));
}

export function createBqrTool(options: BloombergToolsOptions = {}): BloombergTool {
  return bqrWithResolver(createCoreResolver(options));
}

export function createBfldsTool(options: BloombergToolsOptions = {}): BloombergTool {
  return bfldsWithResolver(createCoreResolver(options));
}

export function createBloombergToolsForResolver(resolver: CoreResolver): BloombergTool[] {
  return [
    ...enabledTool(resolver, "xbbg_bdp", bdpWithResolver),
    ...enabledTool(resolver, "xbbg_bdh", bdhWithResolver),
    ...enabledTool(resolver, "xbbg_bds", bdsWithResolver),
    ...enabledTool(resolver, "xbbg_bdib", bdibWithResolver),
    ...enabledTool(resolver, "xbbg_bdtick", bdtickWithResolver),
    ...enabledTool(resolver, "xbbg_bql", bqlWithResolver),
    ...enabledTool(resolver, "xbbg_bsrch", bsrchWithResolver),
    ...enabledTool(resolver, "xbbg_bqr", bqrWithResolver),
    ...enabledTool(resolver, "xbbg_bflds", bfldsWithResolver),
  ];
}

export function createBloombergTools(options: BloombergToolsOptions = {}): BloombergTool[] {
  return createBloombergToolsForResolver(createCoreResolver(options));
}

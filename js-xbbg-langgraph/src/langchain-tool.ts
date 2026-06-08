import { tool, type StructuredToolInterface } from "@langchain/core/tools";
import { zodToJsonSchema } from "zod-to-json-schema";
import type * as z from "zod/v3";

import type { BloombergToolName } from "./options";
import type { ToolContentAndArtifact } from "./result-limits";

type ZodOutput<T> = z.ZodType<T, z.ZodTypeDef, unknown>;

interface BloombergStructuredToolFields<Input> {
  readonly description: string;
  readonly name: BloombergToolName;
  readonly responseFormat: "content_and_artifact";
  readonly schema: ZodOutput<Input>;
}

function inputJsonSchema(schema: ZodOutput<unknown>): Record<string, unknown> {
  const jsonSchema = zodToJsonSchema(schema, {
    $refStrategy: "none",
    effectStrategy: "input",
    pipeStrategy: "input",
  }) as Record<string, unknown>;
  delete jsonSchema.$schema;
  delete jsonSchema.definitions;
  return jsonSchema;
}

export function createBloombergStructuredTool<Input>(
  func: (input: Input) => Promise<ToolContentAndArtifact>,
  fields: BloombergStructuredToolFields<Input>,
): StructuredToolInterface {
  const providerToolDefinition = {
    type: "function",
    function: {
      description: fields.description,
      name: fields.name,
      parameters: inputJsonSchema(fields.schema),
    },
  };

  return tool(
    func as never,
    {
      ...fields,
      extras: { providerToolDefinition },
    } as never,
  ) as StructuredToolInterface;
}

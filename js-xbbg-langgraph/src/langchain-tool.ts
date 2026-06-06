import { tool, type StructuredToolInterface } from "@langchain/core/tools";
import * as z from "zod";

import type { BloombergToolName } from "./options";
import type { ToolContentAndArtifact } from "./result-limits";

interface BloombergStructuredToolFields<Input> {
  readonly description: string;
  readonly name: BloombergToolName;
  readonly responseFormat: "content_and_artifact";
  readonly schema: z.ZodType<Input>;
}

function inputJsonSchema(schema: z.ZodType): Record<string, unknown> {
  const jsonSchema = z.toJSONSchema(schema, {
    io: "input",
    unrepresentable: "any",
  }) as Record<string, unknown>;
  delete jsonSchema.$schema;
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

import type { BloombergToolName } from "./options";

interface LimitResult {
  readonly rowCount: number | null;
  readonly truncated: boolean;
  readonly value: unknown;
}

export interface ToolEnvelope {
  readonly tool: BloombergToolName;
  readonly rowCount: number | null;
  readonly truncated: boolean;
  readonly data: unknown;
}

interface LimitState {
  truncated: boolean;
}

function truncateString(value: string, maxStringChars: number, state: LimitState): string {
  if (value.length <= maxStringChars) {
    return value;
  }
  state.truncated = true;
  return `${value.slice(0, maxStringChars)}…[truncated ${value.length - maxStringChars} chars]`;
}

function limitValue(
  value: unknown,
  maxRows: number,
  maxStringChars: number,
  state: LimitState,
): unknown {
  if (typeof value === "string") {
    return truncateString(value, maxStringChars, state);
  }
  if (Array.isArray(value)) {
    const capped = value.length > maxRows ? value.slice(0, maxRows) : value;
    if (capped.length !== value.length) {
      state.truncated = true;
    }
    return capped.map((item) => limitValue(item, maxRows, maxStringChars, state));
  }
  if (typeof value === "object" && value !== null) {
    const output: Record<string, unknown> = {};
    for (const [key, entry] of Object.entries(value)) {
      output[key] = limitValue(entry, maxRows, maxStringChars, state);
    }
    return output;
  }
  return value;
}

export function limitResult(value: unknown, maxRows: number, maxStringChars: number): LimitResult {
  const state: LimitState = { truncated: false };
  const rowCount = Array.isArray(value) ? value.length : null;
  const limitedValue = limitValue(value, maxRows, maxStringChars, state);
  return {
    rowCount,
    truncated: state.truncated,
    value: limitedValue,
  };
}

export function stringifyToolResult(
  tool: BloombergToolName,
  value: unknown,
  maxRows: number,
  maxStringChars: number,
): string {
  const limited = limitResult(value, maxRows, maxStringChars);
  const envelope: ToolEnvelope = {
    tool,
    rowCount: limited.rowCount,
    truncated: limited.truncated,
    data: limited.value,
  };
  return JSON.stringify(envelope);
}

export function throwWithToolContext(tool: BloombergToolName, error: unknown): never {
  const prefix = `${tool} failed`;
  if (error instanceof Error) {
    if (!error.message.startsWith(prefix)) {
      Object.defineProperty(error, "message", {
        configurable: true,
        value: `${prefix}: ${error.message}`,
      });
    }
    throw error;
  }
  throw new Error(`${prefix}: ${String(error)}`);
}

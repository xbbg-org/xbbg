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

export type ToolContentAndArtifact = [string, ToolEnvelope];

interface LimitState {
  truncated: boolean;
}

const MAX_RESULT_DEPTH = 32;

function isPlainObject(value: object): value is Record<string, unknown> {
  const prototype: unknown = Object.getPrototypeOf(value);
  return prototype === Object.prototype || prototype === null;
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
  depth = 0,
  seen: WeakSet<object> = new WeakSet<object>(),
): unknown {
  if (typeof value === "string") {
    return truncateString(value, maxStringChars, state);
  }
  if (value instanceof Date) {
    return value.toISOString();
  }
  if (depth > MAX_RESULT_DEPTH) {
    state.truncated = true;
    return "[Max result depth exceeded]";
  }
  if (Array.isArray(value)) {
    if (seen.has(value)) {
      state.truncated = true;
      return "[Circular]";
    }
    seen.add(value);
    const capped = value.length > maxRows ? value.slice(0, maxRows) : value;
    if (capped.length !== value.length) {
      state.truncated = true;
    }
    return capped.map((item) => limitValue(item, maxRows, maxStringChars, state, depth + 1, seen));
  }
  if (typeof value === "object" && value !== null) {
    if (seen.has(value)) {
      state.truncated = true;
      return "[Circular]";
    }
    if (!isPlainObject(value)) {
      return value;
    }
    seen.add(value);
    const output: Record<string, unknown> = {};
    for (const [key, entry] of Object.entries(value)) {
      output[key] = limitValue(entry, maxRows, maxStringChars, state, depth + 1, seen);
    }
    return output;
  }
  return value;
}

function rowCountOf(value: unknown): number | null {
  if (Array.isArray(value)) {
    return value.length;
  }
  if (typeof value !== "object" || value === null) {
    return null;
  }
  const record = value as Record<string, unknown>;
  const rowCount = record.rowCount;
  if (typeof rowCount === "number" && Number.isInteger(rowCount) && rowCount >= 0) {
    return rowCount;
  }
  const updateCount = record.updateCount;
  if (typeof updateCount === "number" && Number.isInteger(updateCount) && updateCount >= 0) {
    return updateCount;
  }
  return null;
}

const ERROR_SHAPE_KEYS = new Set([
  "error",
  "errors",
  "fielderrors",
  "fieldexception",
  "fieldexceptions",
  "responseerror",
  "securityerror",
]);

function hasErrorShape(value: unknown): boolean {
  const pending: unknown[] = [value];
  const seen = new WeakSet<object>();

  while (pending.length > 0) {
    const entry = pending.pop();
    if (typeof entry !== "object" || entry === null) {
      continue;
    }
    if (seen.has(entry)) {
      continue;
    }
    seen.add(entry);

    if (Array.isArray(entry)) {
      for (const child of entry as readonly unknown[]) {
        pending.push(child);
      }
      continue;
    }

    for (const [key, child] of Object.entries(entry as Record<string, unknown>)) {
      if (ERROR_SHAPE_KEYS.has(key.toLowerCase()) && child !== undefined) {
        return true;
      }
      pending.push(child);
    }
  }

  return false;
}

export function limitResult(value: unknown, maxRows: number, maxStringChars: number): LimitResult {
  const state: LimitState = { truncated: false };
  const rowCount = rowCountOf(value);
  const limitedValue = limitValue(value, maxRows, maxStringChars, state);
  return {
    rowCount,
    truncated: state.truncated,
    value: limitedValue,
  };
}

function summarizeEnvelope(envelope: ToolEnvelope): string {
  const rowText =
    envelope.rowCount === null
      ? "row count unknown"
      : `${envelope.rowCount} row${envelope.rowCount === 1 ? "" : "s"}`;
  const notes: string[] = [];
  if (envelope.rowCount === 0) {
    notes.push("empty result");
  }
  if (envelope.truncated) {
    notes.push("artifact truncated to configured limits");
  }
  if (hasErrorShape(envelope.data)) {
    notes.push("inspect result payload for Bloomberg error details");
  }
  const noteText = notes.length === 0 ? "" : `; ${notes.join("; ")}`;
  return `${envelope.tool}: ${rowText}; truncated=${String(envelope.truncated)}${noteText}`;
}

function resultJsonReplacer(_key: string, value: unknown): unknown {
  if (typeof value === "bigint") {
    return value.toString();
  }
  return value;
}

function formatToolContent(envelope: ToolEnvelope): string {
  const payload = {
    tool: envelope.tool,
    rowCount: envelope.rowCount,
    truncated: envelope.truncated,
    data: envelope.data,
  };
  return `${summarizeEnvelope(envelope)}\n${JSON.stringify(payload, resultJsonReplacer)}`;
}

export function createToolResult(
  tool: BloombergToolName,
  value: unknown,
  maxRows: number,
  maxStringChars: number,
): ToolContentAndArtifact {
  const limited = limitResult(value, maxRows, maxStringChars);
  const envelope: ToolEnvelope = {
    tool,
    rowCount: limited.rowCount,
    truncated: limited.truncated,
    data: limited.value,
  };
  return [formatToolContent(envelope), envelope];
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

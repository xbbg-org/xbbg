/**
 * Date / datetime normalization helpers (issue #317).
 *
 * These helpers convert user-supplied date-like values into the wire formats
 * the Bloomberg engine expects:
 *
 * - {@link formatDate} -> Bloomberg-native ``YYYYMMDD`` (used by historical
 *   requests, override fields, recipe inputs).
 * - {@link formatDateTime} -> RFC 3339 / ISO 8601 with optional offset (used
 *   by intraday requests).
 *
 * They live in a dedicated module so the public surface in ``index.ts`` can
 * be tested without dragging in the native NAPI addon.
 */

import type { DateLike, DateTimeLike } from './types';

const ISO_DATE_RE = /^\d{4}[-/]\d{2}[-/]\d{2}$/;
const BBG_DATE_RE = /^\d{8}$/;
// Whole-string ambiguous (e.g. "01/17/2023") OR ambiguous prefix in a
// datetime string (e.g. "01/17/2023 10:30" / "01/17/2023T10:30"). Year-leading
// ISO is not flagged because ISO_DATE_RE matches it explicitly.
const AMBIGUOUS_DATE_RE = /^\d{1,2}[-/]\d{1,2}[-/]\d{2,4}([T \D]|$)/;

export function hasToJSDate(value: unknown): value is { toJSDate: () => Date } {
  return (
    typeof value === 'object' &&
    value !== null &&
    'toJSDate' in value &&
    typeof (value as { toJSDate?: unknown }).toJSDate === 'function'
  );
}

function rejectAmbiguousString(value: string): void {
  if (AMBIGUOUS_DATE_RE.test(value) && !ISO_DATE_RE.test(value.trim())) {
    throw new TypeError(
      `Ambiguous date format ${JSON.stringify(value)}: month/day order cannot be inferred. ` +
        `Use ISO 8601 (YYYY-MM-DD), Bloomberg-native (YYYYMMDD), or pass a Date / Luxon DateTime.`,
    );
  }
}

function dateLikeToJSDate(value: DateLike): Date {
  if (value instanceof Date) {
    return value;
  }
  if (typeof value === 'number') {
    return new Date(value);
  }
  if (hasToJSDate(value)) {
    return value.toJSDate();
  }
  if (typeof value === 'string') {
    const text = value.trim();
    rejectAmbiguousString(text);
    if (BBG_DATE_RE.test(text)) {
      const year = Number(text.slice(0, 4));
      const month = Number(text.slice(4, 6)) - 1;
      const day = Number(text.slice(6, 8));
      const dt = new Date(Date.UTC(year, month, day));
      if (Number.isNaN(dt.getTime())) {
        throw new TypeError(`Invalid Bloomberg-native date ${JSON.stringify(value)}`);
      }
      return dt;
    }
    // Replace the first separating space with 'T' so "2023-01-17 10:30" parses.
    const normalized = text.replace(' ', 'T');
    const dt = new Date(normalized);
    if (Number.isNaN(dt.getTime())) {
      throw new TypeError(
        `Cannot parse ${JSON.stringify(value)} as a date. Expected ISO 8601, ` +
          `Bloomberg-native YYYYMMDD, Date, epoch ms, or Luxon DateTime.`,
      );
    }
    return dt;
  }
  throw new TypeError(
    `Cannot convert ${typeof value} value ${String(value)} to a Date.`,
  );
}

/**
 * Format a date-like value to ``YYYYMMDD`` (Bloomberg-native).
 *
 * Accepts ``Date``, ISO 8601 / Bloomberg-native strings, epoch ms, and any
 * duck-typed Luxon-style ``{ toJSDate(): Date }``. Strict on ambiguous formats.
 */
export function formatDate(value: DateLike | undefined | null): string | undefined {
  if (value === undefined || value === null) {
    return undefined;
  }
  if (typeof value === 'string') {
    const text = value.trim();
    if (text.length === 0) {
      return undefined;
    }
    if (BBG_DATE_RE.test(text)) {
      return text;
    }
    rejectAmbiguousString(text);
    if (ISO_DATE_RE.test(text)) {
      return text.replace(/[-/]/g, '');
    }
  }
  const date = dateLikeToJSDate(value);
  const y = String(date.getUTCFullYear()).padStart(4, '0');
  const m = String(date.getUTCMonth() + 1).padStart(2, '0');
  const d = String(date.getUTCDate()).padStart(2, '0');
  return `${y}${m}${d}`;
}

/**
 * Format a datetime-like value to RFC 3339 (ISO 8601 with optional offset).
 *
 * Naive ISO strings without a tz suffix are returned as-is so the Rust engine
 * can apply the caller's ``request_tz``. Anything else (Date, epoch ms, Luxon
 * DateTime, or ISO with explicit tz) is converted to a tz-bearing ISO string.
 */
export function formatDateTime(
  value: DateTimeLike | undefined | null,
): string | undefined {
  if (value === undefined || value === null) {
    return undefined;
  }
  if (typeof value === 'string') {
    const text = value.trim();
    if (text.length === 0) {
      return undefined;
    }
    rejectAmbiguousString(text);
    if (BBG_DATE_RE.test(text)) {
      return `${text.slice(0, 4)}-${text.slice(4, 6)}-${text.slice(6, 8)}T00:00:00`;
    }
    // Preserve user-supplied naive strings; the Rust engine interprets them
    // according to ``request_tz``.
    return text.replace(' ', 'T');
  }
  const date = dateLikeToJSDate(value);
  return date.toISOString();
}

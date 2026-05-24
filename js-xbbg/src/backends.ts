import type { BackendKind, FormatKind } from './types';

export const Backend = Object.freeze({
  ARROW: 'arrow',
  JSON: 'json',
  POLARS: 'polars',
}) satisfies Readonly<Record<string, BackendKind>>;

export const Format = Object.freeze({
  LONG: 'long',
  LONG_TYPED: 'long_typed',
  LONG_WITH_METADATA: 'long_with_metadata',
  SEMI_LONG: 'semi_long',
}) satisfies Readonly<Record<string, FormatKind>>;

import type * as xbbg from "@xbbg/core";

import type { BloombergToolsOptions, NormalizedBloombergToolsOptions } from "./options";
import { normalizeBloombergToolsOptions } from "./options";

export type XbbgCoreModule = typeof xbbg;
export type XbbgEngineLike = Pick<
  Awaited<ReturnType<XbbgCoreModule["connect"]>>,
  | "bdp"
  | "bdh"
  | "bds"
  | "bdib"
  | "bdtick"
  | "bql"
  | "bsrch"
  | "bqr"
  | "bflds"
  | "beqs"
  | "yas"
  | "preferreds"
  | "corporateBonds"
  | "indexMembers"
  | "resolveIsins"
  | "issuerIsins"
  | "etfHoldings"
  | "stream"
  | "mktbar"
  | "depth"
>;
export type XbbgCoreLike = Pick<XbbgCoreModule, "connect" | "ext">;

export interface CoreResolver {
  readonly options: NormalizedBloombergToolsOptions;
  getCore(): Promise<XbbgCoreLike>;
  getEngine(): Promise<XbbgEngineLike>;
}

async function importCore(): Promise<XbbgCoreLike> {
  return await import("@xbbg/core");
}

export function createCoreResolver(options: BloombergToolsOptions = {}): CoreResolver {
  const normalized = normalizeBloombergToolsOptions(options);
  let corePromise: Promise<XbbgCoreLike> | undefined;
  let enginePromise: Promise<XbbgEngineLike> | undefined;

  async function getCore(): Promise<XbbgCoreLike> {
    if (normalized.core !== undefined) {
      return normalized.core;
    }
    corePromise ??= importCore();
    return await corePromise;
  }

  async function getEngine(): Promise<XbbgEngineLike> {
    if (normalized.engine !== undefined) {
      return normalized.engine;
    }
    enginePromise ??= (async (): Promise<XbbgEngineLike> => {
      const core = await getCore();
      return await core.connect(normalized.engineConfig);
    })();
    return await enginePromise;
  }

  return {
    getCore,
    getEngine,
    options: normalized,
  };
}

import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';

import { platformKey, platformPackages } from './platform-map';

const nodeRequire = createRequire(__filename);

interface NativePackageResolution {
  readonly binaryPath?: string;
}

export interface NativeAddonResolution {
  readonly key: string;
  readonly packageName: string | null;
  readonly binaryPath: string | null;
}

function exists(target: string): boolean {
  try {
    fs.accessSync(target);
    return true;
  } catch {
    return false;
  }
}

function isResolution(value: unknown): value is NativePackageResolution {
  return (
    typeof value === 'object' &&
    value !== null &&
    ('binaryPath' in value ? typeof value.binaryPath === 'string' : true)
  );
}

function requireLocalPackage(repoRoot: string, packageName: string): NativePackageResolution | null {
  const dirName = packageName.replace('@xbbg/', 'xbbg-');
  const localIndex = path.join(repoRoot, 'packages', dirName, 'index.js');
  if (!exists(localIndex)) {
    return null;
  }
  const resolved = nodeRequire(localIndex) as unknown;
  return isResolution(resolved) ? resolved : null;
}

function isOptionalPackageMissing(err: unknown, packageName: string): boolean {
  if (!(err instanceof Error)) {
    return false;
  }
  const code = 'code' in err ? (err as { readonly code?: unknown }).code : undefined;
  if (code !== 'MODULE_NOT_FOUND') {
    return false;
  }
  return (
    err.message.includes(`Cannot find module '${packageName}'`) ||
    err.message.includes(`Cannot find module "${packageName}"`) ||
    err.message.includes(`Cannot find package '${packageName}'`) ||
    err.message.includes(`Cannot find package "${packageName}"`)
  );
}

function requireOptionalPackage(packageName: string): NativePackageResolution | null {
  try {
    const resolved = nodeRequire(packageName) as unknown;
    if (!isResolution(resolved)) {
      throw new Error(`Invalid native package ${packageName}: expected an object with binaryPath`);
    }
    return resolved;
  } catch (err) {
    if (isOptionalPackageMissing(err, packageName)) {
      return null;
    }
    throw err;
  }
}

export function resolveNativeAddon(repoRoot: string): NativeAddonResolution {
  const key = platformKey();
  const packageName = (platformPackages as Readonly<Record<string, string>>)[key] ?? null;
  if (packageName === null) {
    return { key, packageName: null, binaryPath: null };
  }

  const installed = requireOptionalPackage(packageName);
  if (installed !== null) {
    if (installed.binaryPath === undefined) {
      throw new Error(`Invalid native package ${packageName}: missing binaryPath`);
    }
    if (!exists(installed.binaryPath)) {
      throw new Error(
        `Invalid native package ${packageName}: binaryPath does not exist: ${installed.binaryPath}`,
      );
    }
    return { key, packageName, binaryPath: installed.binaryPath };
  }

  const local = requireLocalPackage(repoRoot, packageName);
  if (local?.binaryPath !== undefined && exists(local.binaryPath)) {
    return { key, packageName, binaryPath: local.binaryPath };
  }

  return { key, packageName, binaryPath: null };
}

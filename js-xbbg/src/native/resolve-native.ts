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

function requireOptionalPackage(packageName: string): NativePackageResolution | null {
  try {
    const resolved = nodeRequire(packageName) as unknown;
    return isResolution(resolved) ? resolved : null;
  } catch {
    return null;
  }
}

export function resolveNativeAddon(repoRoot: string): NativeAddonResolution {
  const key = platformKey();
  const packageName = platformPackages[key as keyof typeof platformPackages] ?? null;
  if (packageName === null) {
    return { key, packageName: null, binaryPath: null };
  }

  const installed = requireOptionalPackage(packageName);
  if (installed?.binaryPath !== undefined && exists(installed.binaryPath)) {
    return { key, packageName, binaryPath: installed.binaryPath };
  }

  const local = requireLocalPackage(repoRoot, packageName);
  if (local?.binaryPath !== undefined && exists(local.binaryPath)) {
    return { key, packageName, binaryPath: local.binaryPath };
  }

  return { key, packageName, binaryPath: null };
}

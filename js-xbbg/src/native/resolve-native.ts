import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';

import { platformKey, platformPackages } from './platform-map';

const nodeRequire = createRequire(__filename);

interface NativePackageResolution {
  readonly binaryPath: string;
}

export interface NativeAddonResolution {
  readonly key: string;
  readonly packageName: string | null;
  readonly binaryPath: string | null;
}

export interface NativeResolverOptions {
  readonly key: string;
  readonly packageName: string | null;
  readonly repoRoot: string;
  readonly requirePackage: (id: string) => unknown;
  readonly exists: (target: string) => boolean;
}

function exists(target: string): boolean {
  try {
    fs.accessSync(target);
    return true;
  } catch {
    return false;
  }
}

function isResolutionObject(value: unknown): value is NativePackageResolution {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function validateNativePackage(packageName: string, resolved: unknown): NativePackageResolution {
  if (!isResolutionObject(resolved)) {
    throw new Error(`Invalid native package ${packageName}: expected an object with binaryPath`);
  }
  if (!('binaryPath' in resolved)) {
    throw new Error(`Invalid native package ${packageName}: missing binaryPath`);
  }
  if (typeof resolved.binaryPath !== 'string') {
    throw new Error(`Invalid native package ${packageName}: binaryPath must be a string`);
  }
  return resolved;
}

function localPackageIndex(repoRoot: string, packageName: string): string {
  const dirName = packageName.replace('@xbbg/', 'xbbg-');
  return path.join(repoRoot, 'packages', dirName, 'index.js');
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

function resolveInstalledPackage(
  packageName: string,
  requirePackage: (id: string) => unknown,
  existsFile: (target: string) => boolean,
): NativePackageResolution | null {
  try {
    const resolved = validateNativePackage(packageName, requirePackage(packageName));
    if (!existsFile(resolved.binaryPath)) {
      throw new Error(
        `Invalid native package ${packageName}: binaryPath does not exist: ${resolved.binaryPath}`,
      );
    }
    return resolved;
  } catch (err) {
    if (isOptionalPackageMissing(err, packageName)) {
      return null;
    }
    throw err;
  }
}

function resolveLocalPackage(
  repoRoot: string,
  packageName: string,
  requirePackage: (id: string) => unknown,
  existsFile: (target: string) => boolean,
): NativePackageResolution | null {
  const localIndex = localPackageIndex(repoRoot, packageName);
  if (!existsFile(localIndex)) {
    return null;
  }

  const resolved = validateNativePackage(packageName, requirePackage(localIndex));
  if (!existsFile(resolved.binaryPath)) {
    throw new Error(
      `Invalid native package ${packageName}: binaryPath does not exist: ${resolved.binaryPath}`,
    );
  }
  return resolved;
}

export function resolveNativeAddonCore(options: NativeResolverOptions): NativeAddonResolution {
  const { key, packageName, repoRoot, requirePackage, exists: existsFile } = options;
  if (packageName === null) {
    return { key, packageName: null, binaryPath: null };
  }

  const installed = resolveInstalledPackage(packageName, requirePackage, existsFile);
  if (installed !== null) {
    return { key, packageName, binaryPath: installed.binaryPath };
  }

  const local = resolveLocalPackage(repoRoot, packageName, requirePackage, existsFile);
  if (local !== null) {
    return { key, packageName, binaryPath: local.binaryPath };
  }

  return { key, packageName, binaryPath: null };
}

export function resolveNativeAddon(repoRoot: string): NativeAddonResolution {
  const key = platformKey();
  const packageName = (platformPackages as Readonly<Record<string, string>>)[key] ?? null;
  return resolveNativeAddonCore({
    key,
    packageName,
    repoRoot,
    requirePackage: (id: string): unknown => nodeRequire(id) as unknown,
    exists,
  });
}

import fs from 'node:fs';
import path from 'node:path';

export {
  nativeBinaryName,
  nativePackageForKey,
  platformKey,
  platformPackages,
} from '../src/native/platform-map';
export type { NativePackageDescriptor, PlatformKey } from '../src/native/platform-map';
import {
  nativeBinaryName,
  nativePackageForKey,
  platformPackages,
  type NativePackageDescriptor,
} from '../src/native/platform-map';

const packageDir = path.resolve(__dirname, '..');

interface NativePackageManifest {
  readonly cpu?: readonly string[];
  readonly files?: readonly string[];
  readonly name?: string;
  readonly os?: readonly string[];
}

export type NativePackageSpec = NativePackageDescriptor & {
  readonly binaryName: string;
  readonly cpu: string;
  readonly dirName: string;
  readonly expectedFiles: readonly string[];
  readonly os: string;
};

function readManifest(manifestPath: string): NativePackageManifest {
  return JSON.parse(fs.readFileSync(manifestPath, 'utf8')) as NativePackageManifest;
}

function singleManifestValue(
  manifest: NativePackageManifest,
  field: 'cpu' | 'os',
  packageName: string,
): string {
  const [value] = manifest[field] ?? [];
  if (value === undefined || manifest[field]?.length !== 1) {
    throw new Error(`${packageName}: package.json ${field} must contain exactly one value`);
  }
  return value;
}

function specForKey(key: string, packageName: string): NativePackageSpec {
  const descriptor = nativePackageForKey(key);
  if (descriptor === null) {
    throw new Error(`missing native package descriptor for ${key}`);
  }
  const manifestPath = path.join(packageDir, descriptor.packageDir, 'package.json');
  const manifest = readManifest(manifestPath);
  if (manifest.name !== packageName) {
    throw new Error(`${manifestPath}: expected package name ${packageName}, got ${manifest.name}`);
  }
  if (manifest.files === undefined || !manifest.files.includes(nativeBinaryName)) {
    throw new Error(`${packageName}: package.json files must include ${nativeBinaryName}`);
  }
  return Object.freeze({
    ...descriptor,
    binaryName: nativeBinaryName,
    cpu: singleManifestValue(manifest, 'cpu', packageName),
    dirName: path.basename(descriptor.packageDir),
    expectedFiles: Object.freeze([...manifest.files]),
    os: singleManifestValue(manifest, 'os', packageName),
  });
}

export const nativePackageSpecs = Object.freeze(
  Object.entries(platformPackages).map(([key, packageName]) => specForKey(key, packageName)),
);

export function nativePackageSpecForKey(key: string): NativePackageSpec | null {
  return nativePackageSpecs.find((spec) => spec.key === key) ?? null;
}

export function nativePackageSpecForPackageName(packageName: string): NativePackageSpec | null {
  return nativePackageSpecs.find((spec) => spec.packageName === packageName) ?? null;
}

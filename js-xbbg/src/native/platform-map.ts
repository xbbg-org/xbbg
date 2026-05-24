const EXPECTED_NATIVE_PACKAGE_FILES = Object.freeze([
  'index.js',
  'index.d.ts',
  'README.md',
  'LICENSE',
  'package.json',
  'napi_xbbg.node',
] as const);

export const nativeBinaryName = 'napi_xbbg.node';

export const nativePackageSpecs = Object.freeze([
  {
    key: 'darwin-arm64',
    packageName: '@xbbg/core-darwin-arm64',
    dirName: 'xbbg-core-darwin-arm64',
    packageDir: 'packages/xbbg-core-darwin-arm64',
    binaryName: nativeBinaryName,
    expectedFiles: EXPECTED_NATIVE_PACKAGE_FILES,
    os: 'darwin',
    cpu: 'arm64',
  },
  {
    key: 'linux-x64',
    packageName: '@xbbg/core-linux-x64',
    dirName: 'xbbg-core-linux-x64',
    packageDir: 'packages/xbbg-core-linux-x64',
    binaryName: nativeBinaryName,
    expectedFiles: EXPECTED_NATIVE_PACKAGE_FILES,
    os: 'linux',
    cpu: 'x64',
  },
  {
    key: 'win32-x64',
    packageName: '@xbbg/core-win32-x64',
    dirName: 'xbbg-core-win32-x64',
    packageDir: 'packages/xbbg-core-win32-x64',
    binaryName: nativeBinaryName,
    expectedFiles: EXPECTED_NATIVE_PACKAGE_FILES,
    os: 'win32',
    cpu: 'x64',
  },
] as const);

export type NativePackageSpec = (typeof nativePackageSpecs)[number];
export type PlatformKey = NativePackageSpec['key'];

function frozenSpecMap<Key extends string>(
  label: string,
  entries: readonly (readonly [Key, NativePackageSpec])[],
): Readonly<Record<Key, NativePackageSpec>> {
  const out: Partial<Record<Key, NativePackageSpec>> = {};
  for (const [key, spec] of entries) {
    if (out[key] !== undefined) {
      throw new Error(`duplicate native package ${label}: ${key}`);
    }
    out[key] = spec;
  }
  return Object.freeze(out as Record<Key, NativePackageSpec>);
}

export const nativePackageSpecByKey = frozenSpecMap(
  'platform key',
  nativePackageSpecs.map((spec) => [spec.key, spec] as const),
);

export const nativePackageSpecByPackageName = frozenSpecMap(
  'package name',
  nativePackageSpecs.map((spec) => [spec.packageName, spec] as const),
);

export const platformPackages = Object.freeze(
  Object.fromEntries(
    nativePackageSpecs.map((spec) => [spec.key, spec.packageName] as const),
  ) as Record<PlatformKey, NativePackageSpec['packageName']>,
);

export function nativePackageSpecForKey(key: string): NativePackageSpec | null {
  return (
    (nativePackageSpecByKey as Readonly<Record<string, NativePackageSpec | undefined>>)[key] ?? null
  );
}

export function nativePackageSpecForPackageName(packageName: string): NativePackageSpec | null {
  return (
    (nativePackageSpecByPackageName as Readonly<Record<string, NativePackageSpec | undefined>>)[
      packageName
    ] ?? null
  );
}

export function platformKey(
  platform: NodeJS.Platform = process.platform,
  arch: string = process.arch,
): string {
  return `${platform}-${arch}`;
}

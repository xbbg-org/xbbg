import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

import packageJson from '../package.json';
import {
  nativePackageSpecs as toolNativePackageSpecs,
  platformPackages as toolPlatformPackages,
} from '../scripts/platform-map';
import {
  nativeBinaryName,
  nativePackageSpecForKey,
  nativePackageSpecForPackageName,
  nativePackageSpecs,
  platformPackages,
} from '../src/native/platform-map';
import { resolveNativeAddonCore } from '../src/native/resolve-native';

const key = 'linux-x64';
const packageName = '@xbbg/core-linux-x64';

function moduleNotFound(message: string): Error {
  const err = new Error(message) as Error & { code: string };
  err.code = 'MODULE_NOT_FOUND';
  return err;
}

function withTempRepo(fn: (repoRoot: string) => void): void {
  const repoRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'xbbg-resolve-native-'));
  try {
    fn(repoRoot);
  } finally {
    fs.rmSync(repoRoot, { force: true, recursive: true });
  }
}

function localIndexPath(repoRoot: string): string {
  const spec = nativePackageSpecForKey(key);
  if (spec === null) {
    throw new Error(`missing test native package spec for ${key}`);
  }
  return path.join(repoRoot, spec.packageDir, 'index.js');
}

describe(resolveNativeAddonCore, () => {
  it('falls back when the target optional package is absent', () => {
    withTempRepo((repoRoot) => {
      const resolution = resolveNativeAddonCore({
        exists: () => false,
        key,
        packageName,
        repoRoot,
        requirePackage: (id) => {
          throw moduleNotFound(`Cannot find module '${id}'`);
        },
      });

      expect(resolution).toStrictEqual({ binaryPath: null, key, packageName });
    });
  });

  it('rethrows MODULE_NOT_FOUND from a nested dependency', () => {
    withTempRepo((repoRoot) => {
      const nested = moduleNotFound("Cannot find module 'nested-dependency'");

      expect(() =>
        resolveNativeAddonCore({
          exists: () => false,
          key,
          packageName,
          repoRoot,
          requirePackage: () => {
            throw nested;
          },
        }),
      ).toThrow(nested);
    });
  });

  it('throws for installed packages with invalid export shapes', () => {
    withTempRepo((repoRoot) => {
      expect(() =>
        resolveNativeAddonCore({
          exists: () => true,
          key,
          packageName,
          repoRoot,
          requirePackage: () => null,
        }),
      ).toThrow(`Invalid native package ${packageName}: expected an object with binaryPath`);
    });
  });

  it('throws for installed packages missing binaryPath', () => {
    withTempRepo((repoRoot) => {
      expect(() =>
        resolveNativeAddonCore({
          exists: () => true,
          key,
          packageName,
          repoRoot,
          requirePackage: () => ({}),
        }),
      ).toThrow(`Invalid native package ${packageName}: missing binaryPath`);
    });
  });

  it('throws for installed packages with nonexistent binaryPath', () => {
    withTempRepo((repoRoot) => {
      const missingBinary = path.join(repoRoot, 'missing.node');

      expect(() =>
        resolveNativeAddonCore({
          exists: () => false,
          key,
          packageName,
          repoRoot,
          requirePackage: () => ({ binaryPath: missingBinary }),
        }),
      ).toThrow(
        `Invalid native package ${packageName}: binaryPath does not exist: ${missingBinary}`,
      );
    });
  });

  it('treats an absent local package index as a benign fallback', () => {
    withTempRepo((repoRoot) => {
      const resolution = resolveNativeAddonCore({
        exists: () => false,
        key,
        packageName,
        repoRoot,
        requirePackage: (id) => {
          throw moduleNotFound(`Cannot find module '${id}'`);
        },
      });

      expect(resolution.binaryPath).toBeNull();
    });
  });

  it('throws for malformed local package exports once local index exists', () => {
    withTempRepo((repoRoot) => {
      expect(() =>
        resolveNativeAddonCore({
          exists: (target) => target === localIndexPath(repoRoot),
          key,
          packageName,
          repoRoot,
          requirePackage: (id) => {
            if (id === packageName) {
              throw moduleNotFound(`Cannot find module '${id}'`);
            }
            return 'not an object';
          },
        }),
      ).toThrow(`Invalid native package ${packageName}: expected an object with binaryPath`);
    });
  });

  it('throws for local package exports missing binaryPath once local index exists', () => {
    withTempRepo((repoRoot) => {
      expect(() =>
        resolveNativeAddonCore({
          exists: (target) => target === localIndexPath(repoRoot),
          key,
          packageName,
          repoRoot,
          requirePackage: (id) => {
            if (id === packageName) {
              throw moduleNotFound(`Cannot find module '${id}'`);
            }
            return {};
          },
        }),
      ).toThrow(`Invalid native package ${packageName}: missing binaryPath`);
    });
  });

  it('throws for local package exports with non-string binaryPath once local index exists', () => {
    withTempRepo((repoRoot) => {
      expect(() =>
        resolveNativeAddonCore({
          exists: (target) => target === localIndexPath(repoRoot),
          key,
          packageName,
          repoRoot,
          requirePackage: (id) => {
            if (id === packageName) {
              throw moduleNotFound(`Cannot find module '${id}'`);
            }
            return { binaryPath: 123 };
          },
        }),
      ).toThrow(`Invalid native package ${packageName}: binaryPath must be a string`);
    });
  });

  it('throws for local package exports with nonexistent binaryPath once local index exists', () => {
    withTempRepo((repoRoot) => {
      const missingBinary = path.join(repoRoot, 'missing.node');

      expect(() =>
        resolveNativeAddonCore({
          exists: (target) => target === localIndexPath(repoRoot),
          key,
          packageName,
          repoRoot,
          requirePackage: (id) => {
            if (id === packageName) {
              throw moduleNotFound(`Cannot find module '${id}'`);
            }
            return { binaryPath: missingBinary };
          },
        }),
      ).toThrow(
        `Invalid native package ${packageName}: binaryPath does not exist: ${missingBinary}`,
      );
    });
  });

  it('resolves a valid local binary after installed package fallback', () => {
    withTempRepo((repoRoot) => {
      const binaryPath = path.join(repoRoot, 'native.node');
      fs.writeFileSync(binaryPath, 'fake native binary');

      const resolution = resolveNativeAddonCore({
        exists: (target) => target === localIndexPath(repoRoot) || fs.existsSync(target),
        key,
        packageName,
        repoRoot,
        requirePackage: (id) => {
          if (id === packageName) {
            throw moduleNotFound(`Cannot find module '${id}'`);
          }
          return { binaryPath };
        },
      });

      expect(resolution).toStrictEqual({ binaryPath, key, packageName });
    });
  });

  it('prefers a valid installed package over a present local package', () => {
    withTempRepo((repoRoot) => {
      const installedBinary = path.join(repoRoot, 'installed.node');
      const localBinary = path.join(repoRoot, 'local.node');
      fs.writeFileSync(installedBinary, 'fake installed native binary');
      fs.writeFileSync(localBinary, 'fake local native binary');

      const resolution = resolveNativeAddonCore({
        exists: (target) => target === localIndexPath(repoRoot) || fs.existsSync(target),
        key,
        packageName,
        repoRoot,
        requirePackage: (id) => {
          if (id === packageName) {
            return { binaryPath: installedBinary };
          }
          throw new Error(`local package should not be required: ${id}`);
        },
      });

      expect(resolution).toStrictEqual({ binaryPath: installedBinary, key, packageName });
    });
  });
  it('resolves an explicit installed package before requiring a known platform spec', () => {
    withTempRepo((repoRoot) => {
      const binaryPath = path.join(repoRoot, 'custom.node');
      fs.writeFileSync(binaryPath, 'fake custom native binary');

      const resolution = resolveNativeAddonCore({
        exists: (target) => target === binaryPath,
        key: 'future-os-x64',
        packageName: '@xbbg/core-future-os-x64',
        repoRoot,
        requirePackage: () => ({ binaryPath }),
      });

      expect(resolution).toStrictEqual({
        binaryPath,
        key: 'future-os-x64',
        packageName: '@xbbg/core-future-os-x64',
      });
    });
  });

  it('returns a null package and binary for unsupported platforms', () => {
    const resolution = resolveNativeAddonCore({
      exists: () => false,
      key: 'freebsd-x64',
      packageName: null,
      repoRoot: os.tmpdir(),
      requirePackage: () => {
        throw new Error('should not require unsupported package');
      },
    });

    expect(resolution).toStrictEqual({ binaryPath: null, key: 'freebsd-x64', packageName: null });
  });
});

describe('platform map packaging metadata', () => {
  it('keeps source and script platform maps in sync', () => {
    expect(toolPlatformPackages).toStrictEqual(platformPackages);
  });
  it('keeps source and script native package specs in sync', () => {
    expect(toolNativePackageSpecs).toStrictEqual(nativePackageSpecs);
  });

  it('keeps optional dependency keys in sync with platform packages', () => {
    expect(Object.keys(packageJson.optionalDependencies).toSorted()).toStrictEqual(
      Object.values(platformPackages).toSorted(),
    );
  });

  it('defines one complete native package spec per optional dependency', () => {
    expect(nativePackageSpecs.map((spec) => spec.packageName).toSorted()).toStrictEqual(
      Object.keys(packageJson.optionalDependencies).toSorted(),
    );
    for (const spec of nativePackageSpecs) {
      expect(platformPackages[spec.key]).toBe(spec.packageName);
      expect(nativePackageSpecForKey(spec.key)).toBe(spec);
      expect(nativePackageSpecForPackageName(spec.packageName)).toBe(spec);
      expect(path.basename(spec.packageDir)).toBe(spec.dirName);
      expect(spec.binaryName).toBe(nativeBinaryName);
      expect(spec.expectedFiles).toContain(nativeBinaryName);
    }
  });

  it('keeps native package specs aligned with package manifests', () => {
    const jsPackageDir = path.resolve(__dirname, '..');

    for (const spec of nativePackageSpecs) {
      const packageDir = path.join(jsPackageDir, spec.packageDir);
      const manifestPath = path.join(packageDir, 'package.json');
      const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8')) as {
        cpu?: string[];
        files?: string[];
        name?: string;
        os?: string[];
      };

      expect(manifest.name).toBe(spec.packageName);
      expect(manifest.os).toStrictEqual([spec.os]);
      expect(manifest.cpu).toStrictEqual([spec.cpu]);
      expect(manifest.files).toStrictEqual([...spec.expectedFiles]);
      for (const expectedFile of spec.expectedFiles.filter((file) => file !== spec.binaryName)) {
        expect(fs.existsSync(path.join(packageDir, expectedFile))).toBeTruthy();
      }
    }
  });
});

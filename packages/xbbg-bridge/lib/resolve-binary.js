'use strict';

const fs = require('node:fs');
const path = require('node:path');
const { platformKey, platformPackages } = require('./platform-map');

function exists(target) {
  try {
    fs.accessSync(target);
    return true;
  } catch {
    return false;
  }
}

function requireLocalPackage(repoRoot, packageName) {
  const dirName = packageName.replace('@xbbg/', 'xbbg-');
  const localIndex = path.join(repoRoot, 'packages', dirName, 'index.js');
  if (!exists(localIndex)) {
    return null;
  }
  return require(localIndex);
}

function resolveBinary(repoRoot) {
  const key = platformKey();
  const packageName = platformPackages[key];
  if (!packageName) {
    throw new Error(`Unsupported platform for @xbbg/bridge: ${key}`);
  }

  try {
    const resolved = require(packageName);
    if (resolved && resolved.binaryPath && exists(resolved.binaryPath)) {
      return { packageName, binaryPath: resolved.binaryPath };
    }
  } catch (_) {
    // ignore and try local workspace fallback
  }

  const local = requireLocalPackage(repoRoot, packageName);
  if (local && local.binaryPath && exists(local.binaryPath)) {
    return { packageName, binaryPath: local.binaryPath };
  }

  throw new Error(
    `Missing packaged xbbg bridge binary for ${key}. Install ${packageName} or run npm --prefix packages/xbbg-bridge run build:binary.`
  );
}

module.exports = {
  resolveBinary,
};

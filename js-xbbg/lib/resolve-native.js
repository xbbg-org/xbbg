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

function resolveNativeAddon(repoRoot) {
  const key = platformKey();
  const packageName = platformPackages[key];
  if (!packageName) {
    return { key, packageName: null, binaryPath: null };
  }

  try {
    const resolved = require(packageName);
    if (resolved?.binaryPath && exists(resolved.binaryPath)) {
      return { key, packageName, binaryPath: resolved.binaryPath };
    }
  } catch {
    // Ignore and try local workspace fallback.
  }

  const local = requireLocalPackage(repoRoot, packageName);
  if (local?.binaryPath && exists(local.binaryPath)) {
    return { key, packageName, binaryPath: local.binaryPath };
  }

  return { key, packageName, binaryPath: null };
}

module.exports = {
  resolveNativeAddon,
};

'use strict';

const fs = require('node:fs');
const path = require('node:path');

function exists(target) {
  try {
    fs.accessSync(target);
    return true;
  } catch {
    return false;
  }
}

function resolveSdkRoot(repoRoot) {
  if (process.env.BLPAPI_ROOT) {
    return path.resolve(process.env.BLPAPI_ROOT);
  }

  if (process.env.XBBG_DEV_SDK_ROOT) {
    const resolved = path.isAbsolute(process.env.XBBG_DEV_SDK_ROOT)
      ? process.env.XBBG_DEV_SDK_ROOT
      : path.resolve(repoRoot, process.env.XBBG_DEV_SDK_ROOT);
    if (exists(resolved)) {
      return resolved;
    }
  }

  const vendorDir = path.join(repoRoot, 'vendor', 'blpapi-sdk');
  if (!exists(vendorDir)) {
    return null;
  }

  const candidates = fs
    .readdirSync(vendorDir, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => path.join(vendorDir, entry.name))
    .filter((dir) => exists(path.join(dir, 'include')) && exists(path.join(dir, 'lib')))
    .sort();

  return candidates.at(-1) || null;
}

function buildRuntimeEnv(repoRoot) {
  const env = { ...process.env };
  const sdkRoot = resolveSdkRoot(repoRoot);
  if (sdkRoot && !env.BLPAPI_ROOT) {
    env.BLPAPI_ROOT = sdkRoot;
  }
  if (process.platform === 'darwin' && sdkRoot) {
    const sdkLibDir = path.join(sdkRoot, 'lib');
    env.DYLD_FALLBACK_LIBRARY_PATH = env.DYLD_FALLBACK_LIBRARY_PATH
      ? `${sdkLibDir}:${env.DYLD_FALLBACK_LIBRARY_PATH}`
      : sdkLibDir;
  }
  return env;
}

module.exports = {
  buildRuntimeEnv,
  resolveSdkRoot,
};

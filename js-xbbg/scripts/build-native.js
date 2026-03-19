'use strict';

const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const packageDir = path.resolve(__dirname, '..');
const repoRoot = path.resolve(packageDir, '..');

function exists(target) {
  try {
    fs.accessSync(target);
    return true;
  } catch {
    return false;
  }
}

function resolveSdkRoot() {
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

  return candidates.at(-1) ?? null;
}

function resolveBuildArtifact(profile) {
  const ext = process.platform === 'darwin'
    ? 'dylib'
    : process.platform === 'win32'
      ? 'dll'
      : 'so';
  const prefix = process.platform === 'win32' ? '' : 'lib';
  return path.join(repoRoot, 'target', profile, `${prefix}napi_xbbg.${ext}`);
}

function fail(message) {
  console.error(`js-xbbg build failed: ${message}`);
  process.exit(1);
}

const profile = process.argv.includes('--release') ? 'release' : 'debug';
const artifactPath = resolveBuildArtifact(profile);
const outputPath = path.join(packageDir, 'napi_xbbg.node');

const sdkRoot = resolveSdkRoot();
if (!sdkRoot) {
  fail(
    'Could not find the Bloomberg SDK. Set BLPAPI_ROOT (or XBBG_DEV_SDK_ROOT) or vendor the SDK under vendor/blpapi-sdk/<version>.'
  );
}

const sdkLibDir = process.env.BLPAPI_LIB_DIR
  ? path.resolve(process.env.BLPAPI_LIB_DIR)
  : path.join(sdkRoot, 'lib');

if (!exists(sdkLibDir)) {
  fail(`Resolved Bloomberg SDK lib dir does not exist: ${sdkLibDir}`);
}

const extraRustFlags = [];
if (process.platform === 'darwin') {
  extraRustFlags.push(
    '-C link-arg=-Wl,-headerpad_max_install_names',
    `-C link-arg=-Wl,-rpath,${sdkLibDir}`
  );
}

const env = { ...process.env };
env.BLPAPI_ROOT = process.env.BLPAPI_ROOT || sdkRoot;
env.BLPAPI_LIB_DIR = process.env.BLPAPI_LIB_DIR || sdkLibDir;
env.RUSTFLAGS = [process.env.RUSTFLAGS, ...extraRustFlags].filter(Boolean).join(' ').trim();

const cargoArgs = ['build', '-p', 'napi-xbbg'];
if (profile === 'release') {
  cargoArgs.push('--release');
}

const result = spawnSync('cargo', cargoArgs, {
  cwd: repoRoot,
  env,
  stdio: 'inherit',
});

if (result.status !== 0) {
  process.exit(result.status ?? 1);
}

if (!exists(artifactPath)) {
  fail(`Expected build artifact was not produced: ${artifactPath}`);
}

fs.copyFileSync(artifactPath, outputPath);
fs.chmodSync(outputPath, 0o755);

console.log(`Copied ${path.relative(repoRoot, artifactPath)} -> ${path.relative(repoRoot, outputPath)}`);

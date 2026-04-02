#!/usr/bin/env node
'use strict';

const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { platformKey, platformPackages } = require('../lib/platform-map');
const { buildRuntimeEnv, resolveSdkRoot } = require('../lib/runtime-env');

const repoRoot = path.resolve(__dirname, '..', '..', '..');
const key = platformKey();
const packageName = platformPackages[key];
if (!packageName) {
  console.error(`Unsupported platform: ${key}`);
  process.exit(1);
}

const localPackageDir = path.join(repoRoot, 'packages', packageName.replace('@xbbg/', 'xbbg-'));
if (!fs.existsSync(localPackageDir)) {
  console.error(`Local platform package directory not found: ${localPackageDir}`);
  process.exit(1);
}

const sdkRoot = resolveSdkRoot(repoRoot);
if (!sdkRoot) {
  console.error('Unable to resolve Bloomberg SDK root. Set BLPAPI_ROOT or XBBG_DEV_SDK_ROOT.');
  process.exit(1);
}

const env = buildRuntimeEnv(repoRoot);
env.BLPAPI_ROOT = env.BLPAPI_ROOT || sdkRoot;

const args = ['build', '-p', 'xbbg-server', '--release'];
const result = spawnSync('cargo', args, { cwd: repoRoot, env, stdio: 'inherit' });
if (result.status !== 0) {
  process.exit(result.status || 1);
}

const binaryName = process.platform === 'win32' ? 'xbbg-server.exe' : 'xbbg-server';
const source = path.join(repoRoot, 'target', 'release', binaryName);
const destDir = path.join(localPackageDir, 'bin');
const dest = path.join(destDir, binaryName);
fs.mkdirSync(destDir, { recursive: true });
fs.copyFileSync(source, dest);
fs.chmodSync(dest, 0o755);
console.log(`Staged ${source} -> ${dest}`);

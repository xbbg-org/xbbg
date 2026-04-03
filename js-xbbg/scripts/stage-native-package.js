#!/usr/bin/env node

const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { platformKey, platformPackages } = require('../lib/platform-map');

const repoRoot = path.resolve(__dirname, '..', '..');
const packageDir = path.resolve(repoRoot, 'js-xbbg');
const sourceBinary = path.join(packageDir, 'napi_xbbg.node');

function fail(message) {
  console.error(`js-xbbg stage failed: ${message}`);
  process.exit(1);
}

function parseArgs(argv) {
  const parsed = { build: false, release: false, version: null };
  for (let index = 0; index < argv.length; index += 1) {
    const value = argv[index];
    switch (value) {
      case '--build':
        parsed.build = true;
        break;
      case '--release':
        parsed.release = true;
        break;
      case '--version':
        index += 1;
        parsed.version = argv[index] || null;
        break;
      default:
        fail(`unknown argument: ${value}`);
    }
  }
  return parsed;
}

function stagePackage(version = null) {
  const key = platformKey();
  const packageName = platformPackages[key];
  if (!packageName) {
    fail(`unsupported platform for packaged @xbbg/core native addon: ${key}`);
  }

  const localPackageDir = path.join(
    repoRoot,
    'packages',
    packageName.replace('@xbbg/', 'xbbg-'),
  );
  if (!fs.existsSync(localPackageDir)) {
    fail(`local platform package directory not found: ${localPackageDir}`);
  }
  if (!fs.existsSync(sourceBinary)) {
    fail(
      `expected built native addon at ${sourceBinary}; run npm --prefix js-xbbg run build first`,
    );
  }

  const destBinary = path.join(localPackageDir, 'napi_xbbg.node');
  fs.copyFileSync(sourceBinary, destBinary);

  if (version) {
    const normalizedVersion = version.replace(/^v/, '');
    const packageJsonPath = path.join(localPackageDir, 'package.json');
    const packageJson = JSON.parse(fs.readFileSync(packageJsonPath, 'utf8'));
    packageJson.version = normalizedVersion;
    fs.writeFileSync(
      packageJsonPath,
      `${JSON.stringify(packageJson, null, 2)}\n`,
    );
  }

  console.log(`Staged ${sourceBinary} -> ${destBinary}`);
  return { key, packageName, localPackageDir, destBinary };
}

function maybeBuild({ build, release }) {
  if (!build && fs.existsSync(sourceBinary)) {
    return;
  }
  const args = [path.join(packageDir, 'scripts', 'build-native.js')];
  if (release) {
    args.push('--release');
  }
  const result = spawnSync(process.execPath, args, {
    cwd: repoRoot,
    env: process.env,
    stdio: 'inherit',
  });
  if (result.status !== 0) {
    process.exit(result.status || 1);
  }
}

const options = parseArgs(process.argv.slice(2));
maybeBuild(options);
stagePackage(options.version);

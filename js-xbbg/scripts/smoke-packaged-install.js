#!/usr/bin/env node

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { platformKey, platformPackages } = require('./platform-map.cjs');

const repoRoot = path.resolve(__dirname, '..', '..');
const npmExecPath = process.env.npm_execpath;
const packedMode = process.argv.includes('--packed');

function fail(message) {
  console.error(`js-xbbg packaged-install smoke failed: ${message}`);
  process.exit(1);
}

function packageDirName(packageName) {
  return packageName.replace('@xbbg/', 'xbbg-');
}

function run(command, args, options = {}) {
  const result = spawnSync(command, args, {
    cwd: options.cwd,
    env: options.env,
    stdio: 'inherit',
    windowsHide: true,
  });
  if (result.error) {
    throw result.error;
  }
  if (result.status !== 0) {
    process.exit(result.status || 1);
  }
}

function runCapture(command, args, options = {}) {
  const result = spawnSync(command, args, {
    cwd: options.cwd,
    env: options.env,
    encoding: 'utf8',
    windowsHide: true,
  });
  if (result.error) {
    throw result.error;
  }
  if (result.status !== 0) {
    process.stderr.write(result.stderr || '');
    process.exit(result.status || 1);
  }
  const lines = (result.stdout || '')
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  return lines.at(-1) || '';
}

function npmCommand(args) {
  if (npmExecPath) {
    return { command: process.execPath, args: [npmExecPath, ...args] };
  }
  if (process.platform === 'win32') {
    return {
      command: process.env.ComSpec || 'cmd.exe',
      args: ['/d', '/s', '/c', 'npm.cmd', ...args],
    };
  }
  return { command: 'npm', args };
}

function runNpm(args, options = {}) {
  const invocation = npmCommand(args);
  run(invocation.command, invocation.args, options);
}

function runNpmCapture(args, options = {}) {
  const invocation = npmCommand(args);
  return runCapture(invocation.command, invocation.args, options);
}

function resolveVendoredSdkRoot() {
  const vendorDir = path.join(repoRoot, 'vendor', 'blpapi-sdk');
  if (!fs.existsSync(vendorDir)) {
    return null;
  }
  const candidates = fs
    .readdirSync(vendorDir, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => path.join(vendorDir, entry.name))
    .filter((dir) => fs.existsSync(path.join(dir, 'bin')) || fs.existsSync(path.join(dir, 'lib')))
    .sort();
  return candidates.at(-1) || null;
}

function smokeRuntimeEnv() {
  const env = { ...process.env };
  if (env.BLPAPI_ROOT && !path.isAbsolute(env.BLPAPI_ROOT)) {
    env.BLPAPI_ROOT = path.resolve(repoRoot, env.BLPAPI_ROOT);
  }
  if (env.XBBG_DEV_SDK_ROOT && !path.isAbsolute(env.XBBG_DEV_SDK_ROOT)) {
    env.XBBG_DEV_SDK_ROOT = path.resolve(repoRoot, env.XBBG_DEV_SDK_ROOT);
  }
  if (!env.BLPAPI_ROOT && !env.XBBG_DEV_SDK_ROOT) {
    const sdkRoot = resolveVendoredSdkRoot();
    if (sdkRoot) {
      env.BLPAPI_ROOT = sdkRoot;
    }
  }
  return env;
}

function smokeRequire(appDir) {
  run(
    process.execPath,
    [
      '-e',
      "const resolved = require.resolve('@xbbg/core'); if (!resolved.includes('dist')) throw new Error(`expected packaged dist entrypoint, got ${resolved}`); const core = require('@xbbg/core'); console.log(resolved, typeof core.connect, typeof core.version, core.version());",
    ],
    { cwd: appDir, env: smokeRuntimeEnv() },
  );
}

function smokeSourceInstall(jsPackageDir) {
  const appDir = fs.mkdtempSync(path.join(os.tmpdir(), 'xbbg-source-install-'));
  runNpm(['init', '-y'], { cwd: appDir, env: process.env });
  runNpm(['install', jsPackageDir], { cwd: appDir, env: process.env });
  smokeRequire(appDir);
}

function smokePackedInstall(jsPackageDir, platformPackageDir) {
  const packDir = fs.mkdtempSync(
    path.join(os.tmpdir(), 'xbbg-packaged-install-'),
  );
  const coreTarball = runNpmCapture(
    ['pack', jsPackageDir, '--pack-destination', packDir],
    {
      cwd: repoRoot,
      env: process.env,
    },
  );
  const platformTarball = runNpmCapture(
    ['pack', platformPackageDir, '--pack-destination', packDir],
    { cwd: repoRoot, env: process.env },
  );

  const appDir = fs.mkdtempSync(path.join(os.tmpdir(), 'xbbg-packed-install-'));
  runNpm(['init', '-y'], { cwd: appDir, env: process.env });
  runNpm(
    [
      'install',
      path.join(packDir, platformTarball),
      path.join(packDir, coreTarball),
    ],
    { cwd: appDir, env: process.env },
  );
  smokeRequire(appDir);
}

function main() {
  const currentKey = platformKey();
  const currentPackageName = platformPackages[currentKey];
  if (!currentPackageName) {
    fail(`unsupported platform for smoke test: ${currentKey}`);
  }

  const jsPackageDir = path.join(repoRoot, 'js-xbbg');
  const platformPackageDir = path.join(
    jsPackageDir,
    'packages',
    packageDirName(currentPackageName),
  );
  const stagedBinary = path.join(platformPackageDir, 'napi_xbbg.node');

  if (!fs.existsSync(stagedBinary)) {
    fail(
      `expected staged native package binary at ${stagedBinary}; run stage:native-package first`,
    );
  }

  if (packedMode) {
    smokePackedInstall(jsPackageDir, platformPackageDir);
    return;
  }

  smokeSourceInstall(jsPackageDir);
}

main();

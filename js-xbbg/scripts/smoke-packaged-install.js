#!/usr/bin/env node

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');
const { platformKey, platformPackages } = require('../lib/platform-map');

const repoRoot = path.resolve(__dirname, '..', '..');
const npmCmd = process.platform === 'win32' ? 'npm.cmd' : 'npm';
const packedMode = process.argv.includes('--packed');

function fail(message) {
  console.error(`js-xbbg packaged-install smoke failed: ${message}`);
  process.exit(1);
}

function packageDirName(packageName) {
  return packageName.replace('@xbbg/', 'xbbg-');
}

function run(command, args, options = {}) {
  const useShell =
    process.platform === 'win32' && command.toLowerCase().endsWith('.cmd');
  const result = spawnSync(command, args, {
    cwd: options.cwd,
    env: options.env,
    stdio: 'inherit',
    shell: useShell,
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
  const useShell =
    process.platform === 'win32' && command.toLowerCase().endsWith('.cmd');
  const result = spawnSync(command, args, {
    cwd: options.cwd,
    env: options.env,
    encoding: 'utf8',
    shell: useShell,
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

function smokeRequire(appDir) {
  run(
    process.execPath,
    [
      '-e',
      "const core = require('@xbbg/core'); console.log(typeof core.connect, typeof core.version, core.version());",
    ],
    { cwd: appDir, env: process.env },
  );
}

function smokeSourceInstall(jsPackageDir) {
  const appDir = fs.mkdtempSync(path.join(os.tmpdir(), 'xbbg-source-install-'));
  run(npmCmd, ['init', '-y'], { cwd: appDir, env: process.env });
  run(npmCmd, ['install', jsPackageDir], { cwd: appDir, env: process.env });
  smokeRequire(appDir);
}

function smokePackedInstall(jsPackageDir, platformPackageDir) {
  const packDir = fs.mkdtempSync(
    path.join(os.tmpdir(), 'xbbg-packaged-install-'),
  );
  const coreTarball = runCapture(
    npmCmd,
    ['pack', jsPackageDir, '--pack-destination', packDir],
    {
      cwd: repoRoot,
      env: process.env,
    },
  );
  const platformTarball = runCapture(
    npmCmd,
    ['pack', platformPackageDir, '--pack-destination', packDir],
    { cwd: repoRoot, env: process.env },
  );

  const appDir = fs.mkdtempSync(path.join(os.tmpdir(), 'xbbg-packed-install-'));
  run(npmCmd, ['init', '-y'], { cwd: appDir, env: process.env });
  run(
    npmCmd,
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
    repoRoot,
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

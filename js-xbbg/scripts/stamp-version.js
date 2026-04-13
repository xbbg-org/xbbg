#!/usr/bin/env node

const fs = require('node:fs');
const path = require('node:path');
const {
  platformPackages: corePlatformPackages,
} = require('../lib/platform-map');
const {
  platformPackages: bridgePlatformPackages,
} = require('../../packages/xbbg-bridge/lib/platform-map');

const repoRoot = path.resolve(__dirname, '..', '..');

function fail(message) {
  console.error(`js package version stamp failed: ${message}`);
  process.exit(1);
}

function packageDirName(packageName) {
  return packageName.replace('@xbbg/', 'xbbg-');
}

function readPackageJson(packageJsonPath) {
  return JSON.parse(fs.readFileSync(packageJsonPath, 'utf8'));
}

function writePackageJson(packageJsonPath, packageJson) {
  fs.writeFileSync(
    packageJsonPath,
    `${JSON.stringify(packageJson, null, 2)}\n`,
  );
}

function stampPackageFamily(wrapperPackageJsonPath, platformPackages, version) {
  const wrapperPackageJson = readPackageJson(wrapperPackageJsonPath);
  wrapperPackageJson.version = version;
  if (wrapperPackageJson.optionalDependencies) {
    wrapperPackageJson.optionalDependencies = Object.fromEntries(
      Object.keys(wrapperPackageJson.optionalDependencies).map(
        (packageName) => [packageName, version],
      ),
    );
  }
  writePackageJson(wrapperPackageJsonPath, wrapperPackageJson);

  for (const packageName of Object.values(platformPackages)) {
    const platformPackageJsonPath = path.join(
      repoRoot,
      'packages',
      packageDirName(packageName),
      'package.json',
    );
    const packageJson = readPackageJson(platformPackageJsonPath);
    packageJson.version = version;
    writePackageJson(platformPackageJsonPath, packageJson);
  }
}

const rawVersion = process.argv[2];
if (!rawVersion) {
  fail('usage: node ./scripts/stamp-version.js <version>');
}

const version = rawVersion.replace(/^js-v/, '').replace(/^v/, '');
if (!version) {
  fail('version must not be empty');
}

stampPackageFamily(
  path.join(repoRoot, 'js-xbbg', 'package.json'),
  corePlatformPackages,
  version,
);
stampPackageFamily(
  path.join(repoRoot, 'packages', 'xbbg-bridge', 'package.json'),
  bridgePlatformPackages,
  version,
);

console.log(`Stamped JS package versions with ${version}`);

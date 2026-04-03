#!/usr/bin/env node

const fs = require('node:fs');
const path = require('node:path');
const { platformPackages } = require('../lib/platform-map');

const repoRoot = path.resolve(__dirname, '..', '..');
const packageDir = path.resolve(repoRoot, 'js-xbbg');
const packageJsonPath = path.join(packageDir, 'package.json');

function fail(message) {
  console.error(`js-xbbg version stamp failed: ${message}`);
  process.exit(1);
}

function packageDirName(packageName) {
  return packageName.replace('@xbbg/', 'xbbg-');
}

const rawVersion = process.argv[2];
if (!rawVersion) {
  fail('usage: node ./scripts/stamp-version.js <version>');
}
const version = rawVersion.replace(/^v/, '');

const rootPackageJson = JSON.parse(fs.readFileSync(packageJsonPath, 'utf8'));
rootPackageJson.version = version;
rootPackageJson.optionalDependencies = Object.fromEntries(
  Object.values(platformPackages).map((packageName) => [packageName, version]),
);
fs.writeFileSync(
  packageJsonPath,
  `${JSON.stringify(rootPackageJson, null, 2)}\n`,
);

for (const packageName of Object.values(platformPackages)) {
  const platformPackageJsonPath = path.join(
    repoRoot,
    'packages',
    packageDirName(packageName),
    'package.json',
  );
  const packageJson = JSON.parse(
    fs.readFileSync(platformPackageJsonPath, 'utf8'),
  );
  packageJson.version = version;
  fs.writeFileSync(
    platformPackageJsonPath,
    `${JSON.stringify(packageJson, null, 2)}\n`,
  );
}

console.log(`Stamped js-xbbg packages with version ${version}`);

#!/usr/bin/env node

import fs from 'node:fs';
import path from 'node:path';

import { platformPackages as corePlatformPackages } from './platform-map';

interface PackageJson {
  optionalDependencies?: Record<string, unknown>;
  version?: string;
  [key: string]: unknown;
}

const repoRoot = path.resolve(__dirname, '..', '..');
const packageDir = path.join(repoRoot, 'js-xbbg');

function fail(message: string): never {
  console.error(`js package version stamp failed: ${message}`);
  process.exit(1);
}

function packageDirName(packageName: string): string {
  return packageName.replace('@xbbg/', 'xbbg-');
}

function isPackageJson(value: unknown): value is PackageJson {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function readPackageJson(packageJsonPath: string): PackageJson {
  const packageJson: unknown = JSON.parse(fs.readFileSync(packageJsonPath, 'utf8'));
  if (!isPackageJson(packageJson)) {
    throw new TypeError(`Expected package.json object: ${packageJsonPath}`);
  }
  return packageJson;
}

function writePackageJson(packageJsonPath: string, packageJson: PackageJson): void {
  fs.writeFileSync(packageJsonPath, `${JSON.stringify(packageJson, null, 2)}\n`);
}

function stampPackageFamily(
  wrapperPackageJsonPath: string,
  platformPackages: Readonly<Record<string, string>>,
  version: string,
): void {
  const wrapperPackageJson = readPackageJson(wrapperPackageJsonPath);
  wrapperPackageJson.version = version;
  if (wrapperPackageJson.optionalDependencies) {
    wrapperPackageJson.optionalDependencies = Object.fromEntries(
      Object.keys(wrapperPackageJson.optionalDependencies).map((packageName) => [
        packageName,
        version,
      ]),
    );
  }
  writePackageJson(wrapperPackageJsonPath, wrapperPackageJson);

  for (const packageName of Object.values(platformPackages)) {
    const platformPackageJsonPath = path.join(
      packageDir,
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
if (rawVersion === undefined || rawVersion.length === 0) {
  fail('usage: npm run stamp:version -- <version>');
}

const version = rawVersion.replace(/^js-v/, '').replace(/^v/, '');
if (version.length === 0) {
  fail('version must not be empty');
}

stampPackageFamily(path.join(packageDir, 'package.json'), corePlatformPackages, version);

console.log(`Stamped JS package versions with ${version}`);

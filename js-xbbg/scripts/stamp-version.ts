#!/usr/bin/env node

import fs from 'node:fs';
import path from 'node:path';

import { nativePackageSpecs } from './platform-map';

interface PackageJson {
  optionalDependencies?: Record<string, unknown>;
  dependencies?: Record<string, unknown>;
  version?: string;
  [key: string]: unknown;
}

const repoRoot = path.resolve(__dirname, '..', '..');
const packageDir = path.join(repoRoot, 'js-xbbg');
const langgraphPackageDir = path.join(repoRoot, 'js-xbbg-langgraph');

function fail(message: string): never {
  console.error(`js package version stamp failed: ${message}`);
  process.exit(1);
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

function stampPackageFamily(wrapperPackageJsonPath: string, version: string): void {
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

  for (const spec of nativePackageSpecs) {
    const platformPackageJsonPath = path.join(packageDir, spec.packageDir, 'package.json');
    const packageJson = readPackageJson(platformPackageJsonPath);
    packageJson.version = version;
    writePackageJson(platformPackageJsonPath, packageJson);
  }
}
function stampLanggraphPackage(packageJsonPath: string, version: string): void {
  const packageJson = readPackageJson(packageJsonPath);
  packageJson.version = version;
  packageJson.dependencies = {
    ...packageJson.dependencies,
    '@xbbg/core': version,
  };
  writePackageJson(packageJsonPath, packageJson);
}

const rawVersion = process.argv[2];
if (rawVersion === undefined || rawVersion.length === 0) {
  fail('usage: npm run stamp:version -- <version>');
}

const version = rawVersion.replace(/^js-v/u, '').replace(/^v/u, '');
if (version.length === 0) {
  fail('version must not be empty');
}

stampPackageFamily(path.join(packageDir, 'package.json'), version);
stampLanggraphPackage(path.join(langgraphPackageDir, 'package.json'), version);

console.log(`Stamped JS package versions with ${version}`);

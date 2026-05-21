#!/usr/bin/env node

import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

import { platformKey, platformPackages } from './platform-map';

const repoRoot = path.resolve(__dirname, '..', '..');
const packageDir = path.resolve(repoRoot, 'js-xbbg');
const sourceBinary = path.join(packageDir, 'napi_xbbg.node');

interface StageOptions {
  build: boolean;
  release: boolean;
  version: string | null;
}

interface StagePackageResult {
  readonly destBinary: string;
  readonly key: string;
  readonly localPackageDir: string;
  readonly packageName: string;
}

interface NpmInvocation {
  readonly command: string;
  readonly args: readonly string[];
}

const npmExecPath = process.env.npm_execpath;

function fail(message: string): never {
  console.error(`js-xbbg stage failed: ${message}`);
  process.exit(1);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function resolvePlatformPackageName(key: string): string | null {
  const match = Object.entries(platformPackages).find(([platformName]) => platformName === key);
  return match?.[1] ?? null;
}

function parseArgs(argv: readonly string[]): StageOptions {
  const parsed: StageOptions = { build: false, release: false, version: null };
  for (let index = 0; index < argv.length; index += 1) {
    const value = argv[index];
    if (value === undefined) {
      fail('encountered missing CLI argument while parsing stage options');
    }
    switch (value) {
      case '--build': {
        parsed.build = true;
        break;
      }
      case '--release': {
        parsed.release = true;
        break;
      }
      case '--version': {
        index += 1;
        parsed.version = argv[index] ?? null;
        break;
      }
      default: {
        fail(`unknown argument: ${value}`);
      }
    }
  }
  return parsed;
}

function runNpm(args: readonly string[]): void {
  const invocation = npmCommand(args);
  const result = spawnSync(invocation.command, invocation.args, {
    cwd: repoRoot,
    env: process.env,
    stdio: 'inherit',
    windowsHide: true,
  });
  if (result.error) {
    fail(`failed to run npm ${args.join(' ')}: ${result.error.message}`);
  }
  if (result.status !== 0) {
    process.exit(result.status ?? 1);
  }
}

function ensurePlatformLoader(localPackageDir: string): void {
  const loaderPath = path.join(localPackageDir, 'index.js');
  if (fs.existsSync(loaderPath)) {
    return;
  }
  runNpm(['--prefix', packageDir, 'run', 'build:ts']);
  if (!fs.existsSync(loaderPath)) {
    fail(`expected generated platform loader at ${loaderPath}; build:ts did not produce it`);
  }
}

function stagePackage(version: string | null = null): StagePackageResult {
  const key = platformKey();
  const packageName = resolvePlatformPackageName(key);
  if (packageName === null) {
    fail(`unsupported platform for packaged @xbbg/core native addon: ${key}`);
  }

  const localPackageDir = path.join(packageDir, 'packages', packageName.replace('@xbbg/', 'xbbg-'));
  if (!fs.existsSync(localPackageDir)) {
    fail(`local platform package directory not found: ${localPackageDir}`);
  }
  ensurePlatformLoader(localPackageDir);

  if (!fs.existsSync(sourceBinary)) {
    fail(
      `expected built native addon at ${sourceBinary}; run npm --prefix js-xbbg run build:native first or pass --build`,
    );
  }

  const destBinary = path.join(localPackageDir, 'napi_xbbg.node');
  fs.copyFileSync(sourceBinary, destBinary);

  if (version !== null) {
    const normalizedVersion = version.replace(/^v/u, '');
    const packageJsonPath = path.join(localPackageDir, 'package.json');
    const packageJson: unknown = JSON.parse(fs.readFileSync(packageJsonPath, 'utf8'));
    if (!isRecord(packageJson)) {
      fail(`expected package.json object at ${packageJsonPath}`);
    }
    packageJson.version = normalizedVersion;
    fs.writeFileSync(packageJsonPath, `${JSON.stringify(packageJson, null, 2)}\n`);
  }

  console.log(`Staged ${sourceBinary} -> ${destBinary}`);
  return { destBinary, key, localPackageDir, packageName };
}

function npmCommand(args: readonly string[]): NpmInvocation {
  if (npmExecPath !== undefined && npmExecPath.length > 0) {
    return { args: [npmExecPath, ...args], command: process.execPath };
  }
  if (process.platform === 'win32') {
    return {
      args: ['/d', '/s', '/c', 'npm.cmd', ...args],
      command: process.env.ComSpec ?? 'cmd.exe',
    };
  }
  return { args, command: 'npm' };
}

function maybeBuild({ build, release }: StageOptions): void {
  if (!build && fs.existsSync(sourceBinary)) {
    return;
  }
  runNpm(
    release
      ? ['--prefix', packageDir, 'run', 'build:native', '--', '--release']
      : ['--prefix', packageDir, 'run', 'build:native'],
  );
}

const options = parseArgs(process.argv.slice(2));
maybeBuild(options);
stagePackage(options.version);

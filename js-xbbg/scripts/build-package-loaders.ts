#!/usr/bin/env node

import fs from 'node:fs';
import path from 'node:path';
import ts from 'typescript';

import { nativePackageSpecs, type NativePackageSpec } from './platform-map';

const repoRoot = path.resolve(__dirname, '..', '..');
const packageDir = path.resolve(repoRoot, 'js-xbbg');

function fail(message: string): never {
  console.error(`js-xbbg package-loader build failed: ${message}`);
  process.exit(1);
}

function buildLoader(spec: NativePackageSpec): void {
  const dir = path.join(packageDir, spec.packageDir);
  const inputPath = path.join(dir, 'index.ts');
  const outputPath = path.join(dir, 'index.js');
  const outputTypesPath = path.join(dir, 'index.d.ts');

  if (!fs.existsSync(inputPath)) {
    fail(`expected platform loader source at ${inputPath}`);
  }

  const transpiled = ts.transpileModule(fs.readFileSync(inputPath, 'utf8'), {
    compilerOptions: {
      esModuleInterop: true,
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2022,
    },
    fileName: inputPath,
  });

  fs.writeFileSync(outputPath, transpiled.outputText);
  fs.writeFileSync(outputTypesPath, 'export declare const binaryPath: string;\n');
}

function removeLegacyOutput(spec: NativePackageSpec): void {
  const legacyDir = path.join(packageDir, spec.dirName);
  if (fs.existsSync(legacyDir)) {
    fs.rmSync(legacyDir, { force: true, recursive: true });
  }
}

for (const spec of nativePackageSpecs) {
  buildLoader(spec);
  removeLegacyOutput(spec);
}

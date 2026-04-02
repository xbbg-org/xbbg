#!/usr/bin/env node
'use strict';

const path = require('node:path');
const { spawn } = require('node:child_process');
const { resolveBinary } = require('../lib/resolve-binary');
const { buildRuntimeEnv } = require('../lib/runtime-env');

const repoRoot = path.resolve(__dirname, '..', '..', '..');
const args = process.argv.slice(2);
const { binaryPath } = resolveBinary(repoRoot);
const env = buildRuntimeEnv(repoRoot);

const child = spawn(binaryPath, args, {
  cwd: repoRoot,
  stdio: 'inherit',
  env,
});

child.on('exit', (code, signal) => {
  if (signal) {
    process.kill(process.pid, signal);
    return;
  }
  process.exit(code ?? 1);
});

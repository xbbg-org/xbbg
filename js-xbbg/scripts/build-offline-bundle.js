#!/usr/bin/env node
/*
 * Build an offline bundle zip for one @xbbg/core platform.
 *
 * Assumes the repo is checked out, `js-xbbg/` has been stamped (version
 * matches `js-xbbg/packages/xbbg-core-<label>/package.json`), and the platform
 * package has been staged with its prebuilt `napi_xbbg.node`.
 *
 * Output: <out-dir>/xbbg-offline-<label>-<version>.zip containing:
 *   bundle/            preinstalled node_modules tree + smoke test
 *   tarballs/          packed @xbbg/core and @xbbg/core-<label>
 *   README.txt         usage + Bloomberg runtime requirement
 *
 * Requires: node, npm, zip (on PATH). Intended to run on Linux in CI.
 */
'use strict';

const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

function parseArgs(argv) {
  const args = {};
  for (let i = 0; i < argv.length; i += 1) {
    const key = argv[i];
    if (key === '--label' || key === '--out-dir') {
      args[key.slice(2)] = argv[i + 1];
      i += 1;
    }
  }
  if (!args.label || !args['out-dir']) {
    console.error('Usage: build-offline-bundle.js --label <platform> --out-dir <dir>');
    process.exit(2);
  }
  return args;
}

function run(cmd, cmdArgs, opts = {}) {
  const result = spawnSync(cmd, cmdArgs, { stdio: 'inherit', ...opts });
  if (result.error) throw result.error;
  if (result.status !== 0) {
    throw new Error(`${cmd} ${cmdArgs.join(' ')} exited with status ${result.status}`);
  }
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  const { label } = args;
  const jsPackageDir = path.resolve(__dirname, '..');
  const repoRoot = path.resolve(jsPackageDir, '..');
  const outDir = path.resolve(args['out-dir']);
  const corePkgDir = path.join(jsPackageDir, 'packages', `xbbg-core-${label}`);

  const corePkg = JSON.parse(fs.readFileSync(path.join(jsPackageDir, 'package.json'), 'utf8'));
  const platPkg = JSON.parse(fs.readFileSync(path.join(corePkgDir, 'package.json'), 'utf8'));
  if (corePkg.version !== platPkg.version) {
    throw new Error(
      `Version mismatch: @xbbg/core is ${corePkg.version} but @xbbg/core-${label} is ${platPkg.version}`,
    );
  }
  const { version } = corePkg;

  fs.mkdirSync(outDir, { recursive: true });
  const work = fs.mkdtempSync(path.join(os.tmpdir(), 'xbbg-offline-'));
  const tarballs = path.join(work, 'tarballs');
  const bundle = path.join(work, 'bundle');
  fs.mkdirSync(tarballs, { recursive: true });
  fs.mkdirSync(bundle, { recursive: true });

  run('npm', ['pack', jsPackageDir, '--pack-destination', tarballs]);
  run('npm', ['pack', corePkgDir, '--pack-destination', tarballs]);

  const coreTgz = `xbbg-core-${version}.tgz`;
  const platTgz = `xbbg-core-${label}-${version}.tgz`;
  for (const name of [coreTgz, platTgz]) {
    if (!fs.existsSync(path.join(tarballs, name))) {
      throw new Error(`Expected tarball not produced: ${name}`);
    }
  }

  fs.writeFileSync(
    path.join(bundle, 'package.json'),
    `${JSON.stringify(
      {
        name: `xbbg-offline-${label}-bundle`,
        private: true,
        type: 'commonjs',
        dependencies: {
          '@xbbg/core': `file:../tarballs/${coreTgz}`,
          [`@xbbg/core-${label}`]: `file:../tarballs/${platTgz}`,
        },
      },
      null,
      2,
    )}\n`,
  );

  // --force bypasses npm's os/cpu check for @xbbg/core-<label> when
  // bundling cross-platform (e.g. assembling a win32-x64 bundle on a
  // Linux runner). The bundle is never executed on the install host.
  run(
    'npm',
    [
      'install',
      '--omit=optional',
      '--omit=dev',
      '--omit=peer',
      '--no-audit',
      '--no-fund',
      '--install-strategy=hoisted',
      '--force',
    ],
    { cwd: bundle },
  );

  fs.writeFileSync(
    path.join(bundle, 'test-load.js'),
    [
      'const xbbg = require("@xbbg/core");',
      'const version = typeof xbbg.version === "function" ? xbbg.version() : "unknown";',
      'console.log("@xbbg/core loaded; version:", version);',
      '',
    ].join('\n'),
  );

  const readme = [
    `xbbg offline ${label} bundle (version ${version})`,
    '='.repeat(60),
    '',
    'Contents',
    '--------',
    '- bundle/node_modules            preinstalled Node module tree',
    '- bundle/package.json            bundle manifest',
    '- bundle/test-load.js            minimal load smoke test',
    `- tarballs/${coreTgz}   @xbbg/core JS package`,
    `- tarballs/${platTgz}   prebuilt native N-API addon for ${label}`,
    '',
    'Usage',
    '-----',
    'Option A - copy node_modules into your project:',
    '  cp -r bundle/node_modules /path/to/your/project/',
    '',
    'Option B - install tarballs directly:',
    '  cd /path/to/your/project',
    `  npm install <path>/tarballs/${coreTgz} <path>/tarballs/${platTgz}`,
    '',
    'Bloomberg runtime requirement',
    '-----------------------------',
    "This bundle does NOT include Bloomberg's blpapi runtime library.",
    'On the target machine, install Bloomberg Terminal or the blpapi SDK',
    'and ensure blpapi3_64.dll / libblpapi3_64.so / libblpapi3.dylib is',
    'discoverable via one of:',
    '  - BLPAPI_LIB_DIR pointing to the folder containing the runtime',
    '  - BLPAPI_ROOT pointing to the SDK root',
    '  - PATH (Windows) / LD_LIBRARY_PATH (Linux) / DYLD_LIBRARY_PATH (macOS)',
    '',
    'Smoke test',
    '----------',
    '  cd bundle',
    '  node test-load.js',
    '',
  ].join('\n');
  fs.writeFileSync(path.join(work, 'README.txt'), readme);

  const zipName = `xbbg-offline-${label}-${version}.zip`;
  const zipPath = path.join(outDir, zipName);
  if (fs.existsSync(zipPath)) fs.unlinkSync(zipPath);
  run('zip', ['-r', '-q', zipPath, 'bundle', 'tarballs', 'README.txt'], { cwd: work });

  console.log(`Wrote ${zipPath}`);
}

main();

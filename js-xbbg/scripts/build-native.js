const fs = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const packageDir = path.resolve(__dirname, '..');
const repoRoot = path.resolve(packageDir, '..');

function exists(target) {
  try {
    fs.accessSync(target);
    return true;
  } catch {
    return false;
  }
}

function parseVersionParts(name) {
  const parts = name.split('.').map((part) => Number(part));
  return parts.every((part) => Number.isInteger(part) && part >= 0)
    ? parts
    : null;
}

function compareSdkRoots(left, right) {
  const leftParts = parseVersionParts(path.basename(left));
  const rightParts = parseVersionParts(path.basename(right));
  if (leftParts && rightParts) {
    const length = Math.max(leftParts.length, rightParts.length);
    for (let index = 0; index < length; index += 1) {
      const leftPart = leftParts[index] ?? 0;
      const rightPart = rightParts[index] ?? 0;
      if (leftPart !== rightPart) {
        return rightPart - leftPart;
      }
    }
  }
  if (leftParts) return -1;
  if (rightParts) return 1;
  return right.localeCompare(left);
}

function resolveSdkLibDir(sdkRoot) {
  const candidates =
    process.platform === 'darwin'
      ? [
          path.join(sdkRoot, 'Darwin'),
          path.join(sdkRoot, 'lib'),
          path.join(sdkRoot, 'lib64'),
        ]
      : process.platform === 'win32'
        ? [
            path.join(sdkRoot, 'lib'),
            path.join(sdkRoot, 'Lib'),
            path.join(sdkRoot, 'bin'),
          ]
        : [
            path.join(sdkRoot, 'Linux'),
            path.join(sdkRoot, 'lib64'),
            path.join(sdkRoot, 'lib'),
          ];

  return candidates.find((candidate) => exists(candidate)) ?? null;
}

function resolveSdkLayout(root) {
  if (!root || !exists(root)) {
    return null;
  }

  const candidates = [path.resolve(root)];
  for (const entry of fs.readdirSync(root, { withFileTypes: true })) {
    if (entry.isDirectory()) {
      candidates.push(path.join(root, entry.name));
    }
  }

  candidates.sort(compareSdkRoots);

  for (const candidate of candidates) {
    const includeDir = exists(path.join(candidate, 'include'))
      ? path.join(candidate, 'include')
      : exists(path.join(candidate, 'Include'))
        ? path.join(candidate, 'Include')
        : null;
    const libDir = resolveSdkLibDir(candidate);
    if (includeDir && libDir) {
      return { sdkRoot: candidate, sdkLibDir: libDir };
    }
  }

  return null;
}

function resolveSdkRoot() {
  if (process.env.BLPAPI_ROOT) {
    const layout = resolveSdkLayout(path.resolve(process.env.BLPAPI_ROOT));
    if (layout) {
      return layout;
    }
  }

  if (process.env.XBBG_DEV_SDK_ROOT) {
    const resolved = path.isAbsolute(process.env.XBBG_DEV_SDK_ROOT)
      ? process.env.XBBG_DEV_SDK_ROOT
      : path.resolve(repoRoot, process.env.XBBG_DEV_SDK_ROOT);
    const layout = resolveSdkLayout(resolved);
    if (layout) {
      return layout;
    }
  }

  return resolveSdkLayout(path.join(repoRoot, 'vendor', 'blpapi-sdk'));
}

function resolveBuildArtifact(profile) {
  const ext =
    process.platform === 'darwin'
      ? 'dylib'
      : process.platform === 'win32'
        ? 'dll'
        : 'so';
  const prefix = process.platform === 'win32' ? '' : 'lib';
  return path.join(repoRoot, 'target', profile, `${prefix}napi_xbbg.${ext}`);
}

function fail(message) {
  console.error(`js-xbbg build failed: ${message}`);
  process.exit(1);
}

const profile = process.argv.includes('--release') ? 'release' : 'debug';
const artifactPath = resolveBuildArtifact(profile);
const outputPath = path.join(packageDir, 'napi_xbbg.node');

const sdkLayout = resolveSdkRoot();
if (!sdkLayout) {
  fail(
    'Could not find the Bloomberg SDK. Set BLPAPI_ROOT (or XBBG_DEV_SDK_ROOT) or vendor the SDK under vendor/blpapi-sdk/<version>.',
  );
}

const sdkRoot = sdkLayout.sdkRoot;
const sdkLibDir = process.env.BLPAPI_LIB_DIR
  ? path.resolve(process.env.BLPAPI_LIB_DIR)
  : sdkLayout.sdkLibDir;
if (!exists(sdkLibDir)) {
  fail(`Resolved Bloomberg SDK lib dir does not exist: ${sdkLibDir}`);
}

const extraRustFlags = [];
if (process.platform === 'darwin') {
  extraRustFlags.push(
    '-C link-arg=-Wl,-headerpad_max_install_names',
    `-C link-arg=-Wl,-rpath,${sdkLibDir}`,
  );
}

const env = { ...process.env };
env.BLPAPI_ROOT = sdkRoot;
env.BLPAPI_LIB_DIR = sdkLibDir;
env.RUSTFLAGS = [process.env.RUSTFLAGS, ...extraRustFlags]
  .filter(Boolean)
  .join(' ')
  .trim();

const cargoArgs = ['build', '-p', 'napi-xbbg'];
if (profile === 'release') {
  cargoArgs.push('--release');
}

const result = spawnSync('cargo', cargoArgs, {
  cwd: repoRoot,
  env,
  stdio: 'inherit',
});

if (result.status !== 0) {
  process.exit(result.status ?? 1);
}

if (!exists(artifactPath)) {
  fail(`Expected build artifact was not produced: ${artifactPath}`);
}

fs.copyFileSync(artifactPath, outputPath);
fs.chmodSync(outputPath, 0o755);

console.log(
  `Copied ${path.relative(repoRoot, artifactPath)} -> ${path.relative(repoRoot, outputPath)}`,
);

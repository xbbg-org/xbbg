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

function runTool(command, args, context) {
  const result = spawnSync(command, args, { encoding: 'utf8' });
  if (result.error) {
    fail(`${context}: ${result.error.message}`);
  }
  if (result.status !== 0) {
    const output = [result.stdout, result.stderr]
      .filter((value) => value && value.length > 0)
      .join('\n')
      .trim();
    fail(
      `${context}: ${output || `${command} exited with status ${result.status ?? 'unknown'}`}`,
    );
  }
  return `${result.stdout ?? ''}${result.stderr ?? ''}`;
}

function stripOtoolPathSuffix(value) {
  return value.replace(/\s+\(offset \d+\)$/, '');
}

function parseDarwinRpaths(loadCommands) {
  const rpaths = new Set();
  let inRpath = false;

  for (const line of loadCommands.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (trimmed === 'cmd LC_RPATH') {
      inRpath = true;
      continue;
    }
    if (inRpath && trimmed.startsWith('path ')) {
      rpaths.add(stripOtoolPathSuffix(trimmed.slice('path '.length)));
      inRpath = false;
      continue;
    }
    if (inRpath && trimmed.startsWith('cmd ')) {
      inRpath = false;
    }
  }

  return rpaths;
}

function parseDarwinLinkedLibraries(output) {
  return output
    .split(/\r?\n/)
    .slice(1)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => line.replace(/\s+\([^)]*\).*$/, ''));
}

function readDarwinLoadCommands(binaryPath) {
  return runTool(
    'otool',
    ['-l', binaryPath],
    `Failed to inspect Mach-O load commands for ${binaryPath}`,
  );
}

function readDarwinLinkedLibraries(binaryPath) {
  return runTool(
    'otool',
    ['-L', binaryPath],
    `Failed to inspect Mach-O linked libraries for ${binaryPath}`,
  );
}

function installNameTool(args, context) {
  runTool('install_name_tool', args, context);
}

function startsWithPath(value, parent) {
  const normalizedValue = path.resolve(value);
  const normalizedParent = path.resolve(parent);
  return (
    normalizedValue === normalizedParent ||
    normalizedValue.startsWith(`${normalizedParent}${path.sep}`)
  );
}

function isSdkBlpapiLibrary(value, sdkLibDir) {
  return (
    path.isAbsolute(value) &&
    startsWithPath(value, sdkLibDir) &&
    /^libblpapi3(_64|_32)?\.(so|dylib)$/.test(path.basename(value))
  );
}

function isForbiddenDarwinPath(value) {
  if (!path.isAbsolute(value)) {
    return false;
  }
  if (value.startsWith('/usr/lib/') || value.startsWith('/System/Library/')) {
    return false;
  }
  return true;
}

function verifyDarwinPortableBinary(binaryPath) {
  const loadCommands = readDarwinLoadCommands(binaryPath);
  const linkedLibraries = parseDarwinLinkedLibraries(
    readDarwinLinkedLibraries(binaryPath),
  );
  const values = [
    ...parseDarwinRpaths(loadCommands),
    ...linkedLibraries,
  ];
  const forbidden = Array.from(
    new Set(values.filter((value) => isForbiddenDarwinPath(value))),
  );
  if (forbidden.length > 0) {
    fail(
      `Mach-O load commands for ${binaryPath} contain non-portable build paths: ${forbidden.join(', ')}`,
    );
  }
}

// Keep the published macOS addon relocatable; Bloomberg's runtime remains user-provided.
function patchDarwinNativeAddon(binaryPath, sdkLibDir) {
  if (process.platform !== 'darwin') {
    return;
  }

  installNameTool(
    ['-id', '@rpath/napi_xbbg.node', binaryPath],
    `Failed to set portable install name for ${binaryPath}`,
  );

  const linkedLibraries = parseDarwinLinkedLibraries(
    readDarwinLinkedLibraries(binaryPath),
  );
  for (const linkedLibrary of linkedLibraries) {
    if (!isSdkBlpapiLibrary(linkedLibrary, sdkLibDir)) {
      continue;
    }
    installNameTool(
      [
        '-change',
        linkedLibrary,
        `@rpath/${path.basename(linkedLibrary)}`,
        binaryPath,
      ],
      `Failed to rewrite Bloomberg SDK dependency for ${binaryPath}`,
    );
  }

  let rpaths = parseDarwinRpaths(readDarwinLoadCommands(binaryPath));
  for (const rpath of rpaths) {
    if (!isForbiddenDarwinPath(rpath)) {
      continue;
    }
    installNameTool(
      ['-delete_rpath', rpath, binaryPath],
      `Failed to delete non-portable rpath ${rpath} from ${binaryPath}`,
    );
  }

  rpaths = parseDarwinRpaths(readDarwinLoadCommands(binaryPath));
  for (const rpath of ['@loader_path', '@loader_path/lib']) {
    if (rpaths.has(rpath)) {
      continue;
    }
    installNameTool(
      ['-add_rpath', rpath, binaryPath],
      `Failed to add portable rpath ${rpath} to ${binaryPath}`,
    );
  }

  verifyDarwinPortableBinary(binaryPath);
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
  extraRustFlags.push('-C link-arg=-Wl,-headerpad_max_install_names');
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
patchDarwinNativeAddon(outputPath, sdkLibDir);

console.log(
  `Copied ${path.relative(repoRoot, artifactPath)} -> ${path.relative(repoRoot, outputPath)}`,
);

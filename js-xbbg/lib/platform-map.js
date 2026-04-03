const platformPackages = {
  'darwin-arm64': '@xbbg/core-darwin-arm64',
  'linux-x64': '@xbbg/core-linux-x64',
  'win32-x64': '@xbbg/core-win32-x64',
};

function platformKey(platform = process.platform, arch = process.arch) {
  return `${platform}-${arch}`;
}

module.exports = {
  platformKey,
  platformPackages,
};

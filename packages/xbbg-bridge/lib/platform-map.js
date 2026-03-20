'use strict';

const platformPackages = {
  'darwin-arm64': '@xbbg/bridge-darwin-arm64',
  'darwin-x64': '@xbbg/bridge-darwin-x64',
  'linux-x64': '@xbbg/bridge-linux-x64',
  'linux-arm64': '@xbbg/bridge-linux-arm64',
  'win32-x64': '@xbbg/bridge-win32-x64',
};

function platformKey(platform = process.platform, arch = process.arch) {
  return `${platform}-${arch}`;
}

module.exports = {
  platformKey,
  platformPackages,
};

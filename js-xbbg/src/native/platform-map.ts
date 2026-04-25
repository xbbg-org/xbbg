export const platformPackages = Object.freeze({
  'darwin-arm64': '@xbbg/core-darwin-arm64',
  'linux-x64': '@xbbg/core-linux-x64',
  'win32-x64': '@xbbg/core-win32-x64',
} as const);

export type PlatformKey = keyof typeof platformPackages;

export function platformKey(
  platform: NodeJS.Platform = process.platform,
  arch: string = process.arch,
): string {
  return `${platform}-${arch}`;
}

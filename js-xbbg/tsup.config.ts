import { defineConfig } from 'tsup';

export default defineConfig({
  entry: ['src/index.ts'],
  format: ['cjs'],
  dts: true,
  outDir: 'dist',
  clean: true,
  sourcemap: true,
  target: 'node20',
  splitting: false,
  shims: false,
  platform: 'node',
  treeshake: true,
});

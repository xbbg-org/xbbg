import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "node",
    globals: true,
    hookTimeout: 30000,
    include: ["test/**/*.test.ts"],
    pool: "forks",
    reporters: ["default"],
    testTimeout: 30000,
  },
});

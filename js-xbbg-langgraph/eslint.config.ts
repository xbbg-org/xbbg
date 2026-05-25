import eslint from "@eslint/js";
import nodePlugin from "eslint-plugin-n";
import globals from "globals";
import tseslint from "typescript-eslint";

const tsconfigRootDir = __dirname;

export default [
  {
    ignores: ["**/node_modules/", "dist/", "**/*.js", "**/*.cjs", "**/*.mjs", "**/*.d.ts"],
  },
  eslint.configs.recommended,
  ...tseslint.configs.strictTypeChecked,
  ...tseslint.configs.stylisticTypeChecked,
  nodePlugin.configs["flat/recommended-module"],
  {
    languageOptions: {
      globals: { ...globals.node, ...globals.vitest },
      parserOptions: {
        projectService: {
          allowDefaultProject: ["eslint.config.ts", "tsup.config.ts", "vitest.config.ts"],
        },
        tsconfigRootDir,
      },
    },
    rules: {
      "@typescript-eslint/no-explicit-any": "error",
      "@typescript-eslint/no-unsafe-argument": "error",
      "@typescript-eslint/no-unsafe-assignment": "error",
      "@typescript-eslint/no-unsafe-call": "error",
      "@typescript-eslint/no-unsafe-member-access": "error",
      "@typescript-eslint/no-unsafe-return": "error",
      "@typescript-eslint/no-unused-vars": [
        "error",
        {
          argsIgnorePattern: "^_",
          caughtErrorsIgnorePattern: "^_",
          varsIgnorePattern: "^_",
        },
      ],
      "@typescript-eslint/consistent-type-imports": [
        "error",
        { fixStyle: "inline-type-imports", prefer: "type-imports" },
      ],
      "@typescript-eslint/consistent-type-exports": [
        "error",
        { fixMixedExportsWithInlineTypeSpecifier: true },
      ],
      "@typescript-eslint/explicit-function-return-type": [
        "error",
        {
          allowDirectConstAssertionInArrowFunctions: true,
          allowExpressions: true,
          allowHigherOrderFunctions: true,
          allowTypedFunctionExpressions: true,
        },
      ],
      "@typescript-eslint/explicit-module-boundary-types": "error",
      "@typescript-eslint/no-import-type-side-effects": "error",
      "@typescript-eslint/strict-boolean-expressions": [
        "error",
        {
          allowAny: false,
          allowNullableBoolean: false,
          allowNullableNumber: false,
          allowNullableObject: true,
          allowNullableString: false,
          allowNumber: false,
          allowString: false,
        },
      ],
      "@typescript-eslint/switch-exhaustiveness-check": "error",
      "@typescript-eslint/no-confusing-void-expression": ["error", { ignoreArrowShorthand: true }],
      "@typescript-eslint/prefer-nullish-coalescing": "error",
      "@typescript-eslint/no-unnecessary-condition": "error",
      "@typescript-eslint/no-floating-promises": "error",
      "@typescript-eslint/require-await": "error",
      "@typescript-eslint/return-await": ["error", "always"],
      "@typescript-eslint/promise-function-async": "error",
      "@typescript-eslint/naming-convention": [
        "error",
        {
          format: ["camelCase", "UPPER_CASE", "PascalCase"],
          leadingUnderscore: "allow",
          selector: "variable",
        },
        {
          format: ["camelCase", "PascalCase"],
          selector: "function",
        },
        {
          format: ["PascalCase"],
          selector: "typeLike",
        },
        {
          format: ["PascalCase", "UPPER_CASE"],
          selector: "enumMember",
        },
      ],
      "no-console": ["warn", { allow: ["warn", "error"] }],
      eqeqeq: ["error", "always", { null: "ignore" }],
      "no-eval": "error",
      "no-implied-eval": "off",
      "@typescript-eslint/no-implied-eval": "error",
      "no-throw-literal": "off",
      "@typescript-eslint/only-throw-error": "error",
      "@typescript-eslint/prefer-readonly": "error",
      "@typescript-eslint/no-unnecessary-type-assertion": "error",
      "@typescript-eslint/no-redundant-type-constituents": "error",
      "@typescript-eslint/no-non-null-assertion": "error",
      "@typescript-eslint/unified-signatures": "error",
      "@typescript-eslint/restrict-template-expressions": ["error", { allowNumber: true }],
      "n/no-missing-import": "off",
      "n/no-unpublished-import": "off",
      "n/no-extraneous-import": "off",
      "n/no-process-exit": "off",
    },
  },
  {
    files: ["test/**/*.ts"],
    rules: {
      "@typescript-eslint/explicit-function-return-type": "off",
      "@typescript-eslint/explicit-module-boundary-types": "off",
      "@typescript-eslint/no-empty-function": "off",
      "@typescript-eslint/no-explicit-any": "off",
      "@typescript-eslint/no-floating-promises": "off",
      "@typescript-eslint/no-non-null-assertion": "off",
      "@typescript-eslint/no-unnecessary-condition": "off",
      "@typescript-eslint/no-unsafe-argument": "off",
      "@typescript-eslint/no-unsafe-assignment": "off",
      "@typescript-eslint/no-unsafe-call": "off",
      "@typescript-eslint/no-unsafe-member-access": "off",
      "@typescript-eslint/no-unsafe-return": "off",
      "@typescript-eslint/prefer-nullish-coalescing": "off",
      "@typescript-eslint/prefer-promise-reject-errors": "off",
      "@typescript-eslint/promise-function-async": "off",
      "@typescript-eslint/require-await": "off",
      "@typescript-eslint/return-await": "off",
      "@typescript-eslint/strict-boolean-expressions": "off",
      "@typescript-eslint/use-unknown-in-catch-callback-variable": "off",
      "no-console": "off",
    },
  },
];

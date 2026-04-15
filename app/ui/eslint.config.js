import globals from 'globals';
import pluginJs from '@eslint/js';
import tseslint from 'typescript-eslint';
import pluginReact from 'eslint-plugin-react';
import reactHooks from 'eslint-plugin-react-hooks';
import prettierPlugin from 'eslint-plugin-prettier';
import prettierConfig from 'eslint-config-prettier';

/** @type {import('eslint').Linter.Config[]} */
export default [
  {
    ignores: ['dist/**', 'node_modules/**', 'docs/generated/**', 'src/generated/**'],
  },
  { files: ['**/*.{js,mjs,cjs,ts,jsx,tsx}'] },
  { languageOptions: { globals: globals.browser } },
  pluginJs.configs.recommended,
  ...tseslint.configs.recommended,
  {
    ...pluginReact.configs.flat.recommended,
    settings: {
      react: {
        version: 'detect', // Automatically detect the React version
      },
    },
  },
  // Только rules-of-hooks + exhaustive-deps; полный recommended v7 тянет React Compiler rules.
  // Prettier configuration
  prettierConfig,
  {
    plugins: {
      prettier: prettierPlugin,
      'react-hooks': reactHooks,
    },
    rules: {
      'react-hooks/rules-of-hooks': 'error',
      'react-hooks/exhaustive-deps': 'error',
      'react/react-in-jsx-scope': 'off', // Disable 'React must be in scope when using JSX
      'react/prop-types': 'off', // Disable prop-types validation as we use TypeScript
      'prettier/prettier': 'warn', // Report Prettier issues as warnings
      'no-restricted-imports': [
        'error',
        {
          paths: [
            {
              name: '@mui/material',
              message:
                'Please use specific imports from @mui/material instead of importing the entire module.',
            },
            {
              name: '@mui/x-charts',
              message:
                'Please use specific imports from @mui/x-charts instead of importing the entire module.',
            },
            {
              name: '@mui/x-date-pickers',
              message:
                'Please use specific imports from @mui/x-date-pickers instead of importing the entire module.',
            },
            {
              name: '@mui/x-tree-view',
              message:
                'Please use specific imports from @mui/x-tree-view instead of importing the entire module.',
            },
          ],
          patterns: ['@mui/*/*/*'],
        },
      ],
    },
  },
];

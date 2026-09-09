import { defineConfig, globalIgnores } from 'eslint/config';
import nextVitals from 'eslint-config-next/core-web-vitals';

export default defineConfig([
  ...nextVitals,
  // React Compiler is not enabled in this project. Keep its migration
  // diagnostics visible without making them runtime correctness failures.
  { rules: {
    'react-hooks/set-state-in-effect': 'warn',
    'react-hooks/immutability': 'warn',
    'react-hooks/refs': 'warn',
    'react-hooks/purity': 'warn',
  } },
  globalIgnores(['.next/**', 'out/**', 'build/**', 'next-env.d.ts']),
]);

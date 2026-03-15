/**
 * Node 18: globalThis.crypto polyfill for serialize-javascript 7.x (used by workbox).
 * Node 19+ has it built-in.
 */
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
if (!globalThis.crypto) {
  const nodeCrypto = require('node:crypto');
  (globalThis as unknown as { crypto: Crypto }).crypto = nodeCrypto.webcrypto;
}

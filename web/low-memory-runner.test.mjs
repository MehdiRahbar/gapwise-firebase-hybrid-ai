import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

test('low-memory runner opens the real profile interactively without CDP flags', async () => {
  const fixturePath = resolve(dirname(fileURLToPath(import.meta.url)), 'fixtures', 'RUN_NANO4_LOW_MEMORY.contract.cmd');
  const script = await readFile(fixturePath, 'utf8');
  assert.doesNotMatch(script, /remote-debugging-(?:port|pipe)/i);
  assert.doesNotMatch(script, /Invoke-Cdp|json\/version|LanguageModel\.create/i);
  assert.match(script, /--profile-directory/i);
  assert.match(script, /--new-window/i);
  assert.match(script, /nano4_run=/i);
  assert.match(script, /__gapwise_evidence/i);
});

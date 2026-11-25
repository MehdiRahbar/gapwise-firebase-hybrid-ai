import test from 'node:test';
import assert from 'node:assert/strict';
import { buildLocalEvidenceEnvelope, isLocalEvidenceHost } from './evidence-bridge.mjs';

test('local evidence envelopes redact credentials and authentication material', () => {
  const envelope = buildLocalEvidenceEnvelope(
    'inference',
    {
      raw: 'real model output',
      firebaseConfig: { apiKey: 'secret-api-key', appId: 'secret-app-id' },
      appCheckKey: 'secret-site-key',
      otp: '123456',
      accessToken: 'secret-token',
      elapsedMs: 1234,
    },
    '20261123_220000',
    '2026-11-23T22:00:00.000Z'
  );

  assert.equal(envelope.runId, '20261123_220000');
  assert.equal(envelope.event, 'inference');
  assert.equal(envelope.payload.raw, 'real model output');
  assert.equal(envelope.payload.elapsedMs, 1234);
  assert.equal('firebaseConfig' in envelope.payload, false);
  assert.equal('appCheckKey' in envelope.payload, false);
  assert.equal('otp' in envelope.payload, false);
  assert.equal('accessToken' in envelope.payload, false);
});

test('evidence bridge is local-only', () => {
  assert.equal(isLocalEvidenceHost('127.0.0.1'), true);
  assert.equal(isLocalEvidenceHost('localhost'), true);
  assert.equal(isLocalEvidenceHost('gapwise-hybrid-2026.web.app'), false);
});

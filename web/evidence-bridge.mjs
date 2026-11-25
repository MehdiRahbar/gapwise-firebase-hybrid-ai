const SENSITIVE_KEY = /(api.?key|app.?check|access.?token|auth.?token|refresh.?token|authorization|credential|password|passcode|otp|one.?time|private.?key|secret|firebase.?config)/i;

function sanitize(value, depth = 0) {
  if (depth > 8 || value === null || value === undefined) return value;
  if (Array.isArray(value)) return value.slice(0, 80).map((item) => sanitize(item, depth + 1));
  if (typeof value !== 'object') return value;
  return Object.fromEntries(
    Object.entries(value)
      .filter(([key]) => !SENSITIVE_KEY.test(key))
      .slice(0, 120)
      .map(([key, item]) => [key, sanitize(item, depth + 1)])
  );
}

export function isLocalEvidenceHost(hostname) {
  return hostname === '127.0.0.1' || hostname === 'localhost' || hostname === '::1';
}

export function normalizeEvidenceRunId(runId) {
  const value = String(runId || '').trim();
  return /^[A-Za-z0-9_-]{1,64}$/.test(value) ? value : 'manual';
}

export function buildLocalEvidenceEnvelope(event, payload = {}, runId = 'manual', capturedAt = new Date().toISOString()) {
  return {
    schema: 'gapwise.local-evidence.v1',
    runId: normalizeEvidenceRunId(runId),
    event: String(event || 'unknown').replace(/[^A-Za-z0-9_-]/g, '_').slice(0, 48) || 'unknown',
    capturedAt,
    payload: sanitize(payload),
  };
}

export async function recordLocalEvidence(event, payload = {}) {
  if (!isLocalEvidenceHost(globalThis.location?.hostname || '')) return { sent: false, reason: 'non_local_host' };
  const params = new URLSearchParams(globalThis.location?.search || '');
  const envelope = buildLocalEvidenceEnvelope(event, payload, params.get('nano4_run') || 'manual');
  try {
    const response = await fetch('/__gapwise_evidence', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(envelope),
      keepalive: true,
    });
    return { sent: response.ok, status: response.status };
  } catch (error) {
    return { sent: false, reason: String(error?.message || error) };
  }
}

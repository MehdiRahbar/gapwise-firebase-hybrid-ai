/**
 * Real Firebase AI Logic hybrid integration (official npm Firebase JS SDK).
 * No dummy Gemini responses, no direct third-party API keys, no guessed source labels.
 * Single-turn text workflow preserves on-device compatibility.
 */
let instance = null;
let firebaseApp = null;
let modeName = 'PREFER_ON_DEVICE';
let deviceState = 'not-initialized';
let unsettledBackgroundRuns = 0;
const allowedModes = new Set(['PREFER_ON_DEVICE', 'ONLY_ON_DEVICE', 'PREFER_IN_CLOUD', 'ONLY_IN_CLOUD']);
const clock = () => (typeof performance !== 'undefined' ? performance.now() : Date.now());

export function createRequestCoordinator() {
  let caseEpoch = 0;
  let runSeq = 0;
  let activeRunId = null;
  let cancelledRunId = null;
  let activeController = null;
  let activeKind = null;

  const abortController = (reason) => {
    const had = Boolean(activeController);
    if (activeController) {
      try {
        const abortReason =
          reason === 'user_cancelled'
            ? new Error('User cancelled waiting for model inference.')
            : reason instanceof Error
            ? reason
            : new Error(String(reason || 'Request aborted.'));
        abortReason.name = 'AbortError';
        activeController.abort(abortReason);
      } catch {
        // Ignore custom AbortController edge cases
      }
      activeController = null;
    }
    return had;
  };

  return {
    getState() {
      return { caseEpoch, runSeq, activeRunId, cancelledRunId, activeKind };
    },
    beginRun({ kind = 'local', AbortCtor = globalThis.AbortController } = {}) {
      abortController('superseded_by_new_run');
      runSeq += 1;
      activeRunId = runSeq;
      cancelledRunId = null;
      activeKind = kind;
      activeController = AbortCtor ? new AbortCtor() : null;
      return {
        runId: activeRunId,
        epoch: caseEpoch,
        kind: activeKind,
        signal: activeController?.signal || null,
      };
    },
    cancelActive(reason = 'user_cancelled') {
      const kind = activeKind;
      const runId = activeRunId;
      cancelledRunId = runId;
      activeRunId = null;
      activeKind = null;
      const cancelled = abortController(reason);
      return { cancelled, runId, kind, epoch: caseEpoch };
    },
    invalidateCase(reason = 'case_changed') {
      caseEpoch += 1;
      const prevKind = activeKind;
      activeRunId = null;
      cancelledRunId = null;
      activeKind = null;
      const abortedPrevious = abortController(reason);
      return { epoch: caseEpoch, abortedPrevious, kind: prevKind, reason };
    },
    isCurrent(runId, epoch) {
      return runId != null && runId === activeRunId && epoch === caseEpoch;
    },
    canReportCancellation(runId, epoch) {
      return runId != null && runId === cancelledRunId && epoch === caseEpoch;
    },
    claimTerminalState(runId, epoch) {
      if (runId != null && runId === activeRunId && epoch === caseEpoch) {
        activeRunId = null;
        activeController = null;
        activeKind = null;
        return 'active';
      }
      if (runId != null && runId === cancelledRunId && epoch === caseEpoch) {
        cancelledRunId = null;
        return 'cancelled';
      }
      return 'stale';
    },
    completeRun(runId, epoch) {
      if (runId != null && runId === activeRunId && epoch === caseEpoch) {
        activeRunId = null;
        activeController = null;
        activeKind = null;
        return true;
      }
      return false;
    },
  };
}

export function envConfig() {
  const env = import.meta.env || {};
  const cfg = {
    apiKey: env.VITE_FIREBASE_API_KEY,
    authDomain: env.VITE_FIREBASE_AUTH_DOMAIN,
    projectId: env.VITE_FIREBASE_PROJECT_ID,
    appId: env.VITE_FIREBASE_APP_ID,
    messagingSenderId: env.VITE_FIREBASE_MESSAGING_SENDER_ID,
    storageBucket: env.VITE_FIREBASE_STORAGE_BUCKET,
  };
  return Object.fromEntries(Object.entries(cfg).filter(([, v]) => Boolean(v)));
}

export function envAppCheckKey() {
  return (import.meta.env?.VITE_APPCHECK_SITE_KEY || '').trim();
}

export function getHybridStatus() {
  const configuredModel = modeName === 'ONLY_ON_DEVICE' ? null : instance?.model || null;
  const activeAdapter = modeName === 'ONLY_ON_DEVICE' ? 'chrome-prompt-api-adapter' : configuredModel;
  return {
    connected: !!instance,
    mode: modeName,
    deviceState,
    activeAdapter,
    sdkConfiguredModel: configuredModel,
    backgroundLocalPending: unsettledBackgroundRuns > 0,
    unsettledBackgroundRuns,
  };
}

export function hybridReady() {
  return !!instance;
}

export function classifyInferenceError(err) {
  const msg = String(err?.message || err || '');
  const code = String(err?.code || '');
  const name = String(err?.name || '');
  if (name === 'AbortError' || /user[\s_-]?cancelled|abort/i.test(msg + ' ' + code)) return 'UserCancelledError';
  if (/consent|cloud fallback/i.test(msg)) return 'ConsentRequiredError';
  if (/401|app\s*check|recaptcha|forbidden|403/i.test(msg + ' ' + code)) return 'AppCheckOrAuthError';
  if (/429|quota|rate[- ]?limit|resource[- ]?exhausted/i.test(msg + ' ' + code)) return 'RateLimit429Error';
  if (/timeout|timed out/i.test(msg + ' ' + code)) return 'ModelTimeoutError';
  if (/failed to fetch|network|internet|offline|dns/i.test(msg + ' ' + code)) return 'NetworkFetchError';
  if (/unable to create a session|servicecrash|invalidstateerror/i.test(msg + ' ' + code)) return 'OnDeviceSessionError';
  if (/api-not-enabled|only_on_device|unavailable|languagemodel/i.test(msg + ' ' + code)) return 'OnDeviceUnavailableError';
  if (/malformed|json/i.test(msg)) return 'MalformedOutputError';
  return 'FirebaseAIError';
}

export async function probeDeviceAvailability() {
  const lm = globalThis.LanguageModel;
  if (!lm || typeof lm.availability !== 'function') return { supported: false, availability: 'unavailable' };
  try {
    const availability = await lm.availability({
      expectedInputs: [{ type: 'text', languages: ['en'] }],
      expectedOutputs: [{ type: 'text', languages: ['en'] }],
    });
    return { supported: availability !== 'unavailable', availability: String(availability || 'unavailable') };
  } catch {
    try {
      const availability = await lm.availability();
      return { supported: availability !== 'unavailable', availability: String(availability || 'unavailable') };
    } catch {
      return { supported: false, availability: 'unavailable' };
    }
  }
}

export async function connectHybrid(config, appCheckSiteKey = '', options = {}) {
  if (instance) throw new Error('Firebase already connected in this tab. Reload to change project or mode.');
  if (!config || !config.apiKey || !config.projectId || !config.appId) {
    throw new Error('Missing Firebase web app apiKey, projectId or appId.');
  }
  const mode = String(options.mode || 'PREFER_ON_DEVICE');
  if (!allowedModes.has(mode)) throw new Error('Invalid inference mode.');
  const dev = Boolean(import.meta.env?.DEV);
  const debug = dev && import.meta.env?.VITE_APPCHECK_DEBUG === 'true';
  if (!appCheckSiteKey && mode !== 'ONLY_ON_DEVICE') {
    throw new Error('A registered App Check site key is required for cloud-capable modes.');
  }
  const [{ initializeApp, getApps }, appCheck, aiSDK] = await Promise.all([
    import('firebase/app'),
    import('firebase/app-check'),
    import('firebase/ai'),
  ]);
  const { initializeAppCheck, ReCaptchaEnterpriseProvider, ReCaptchaV3Provider } = appCheck;
  const { getAI, getGenerativeModel, GoogleAIBackend, InferenceMode, Schema } = aiSDK;
  const app = getApps().find((x) => x.name === 'gapwise-hybrid') || initializeApp(config, 'gapwise-hybrid');
  if (debug) self.FIREBASE_APPCHECK_DEBUG_TOKEN = true;
  const appCheckProviderMode = String(options.appCheckProvider || import.meta.env?.VITE_APPCHECK_PROVIDER || 'enterprise').toLowerCase();
  const appCheckProvider = appCheckSiteKey
    ? appCheckProviderMode === 'v3'
      ? new ReCaptchaV3Provider(appCheckSiteKey)
      : new ReCaptchaEnterpriseProvider(appCheckSiteKey)
    : null;
  if (appCheckProvider) initializeAppCheck(app, { provider: appCheckProvider, isTokenAutoRefreshEnabled: true });
  const ai = getAI(app, { backend: new GoogleAIBackend() });
  const cloudSchema = Schema.object({
    properties: {
      suggested_checks: Schema.array({
        items: Schema.object({
          properties: {
            id: Schema.string(),
            label: Schema.string(),
            reason: Schema.string(),
            quote: Schema.string(),
          },
          optionalProperties: ['id', 'reason'],
        }),
      }),
      possible_missing_categories: Schema.array({ items: Schema.string() }),
      unsupported_assumptions: Schema.array({ items: Schema.string() }),
    },
    optionalProperties: ['possible_missing_categories', 'unsupported_assumptions'],
  });
  const onDeviceSchema = {
    type: 'object',
    properties: {
      suggested_checks: {
        type: 'array',
        items: {
          type: 'object',
          properties: {
            id: { type: 'string' },
            label: { type: 'string' },
            reason: { type: 'string' },
            quote: { type: 'string' },
          },
          required: ['label', 'quote'],
        },
      },
      possible_missing_categories: { type: 'array', items: { type: 'string' } },
      unsupported_assumptions: { type: 'array', items: { type: 'string' } },
    },
    required: ['suggested_checks'],
  };
  const model = getGenerativeModel(ai, {
    mode: InferenceMode[mode],
    onDeviceParams: {
      promptOptions: {
        responseConstraint: onDeviceSchema,
      },
    },
    inCloudParams: {
      model: 'gemini-3.5-flash-lite',
      generationConfig: {
        responseMimeType: 'application/json',
        responseSchema: cloudSchema,
      },
    },
  });
  firebaseApp = app;
  instance = model;
  modeName = mode;
  deviceState = mode === 'ONLY_IN_CLOUD' ? 'not-applicable' : 'not-initialized';
  return {
    connected: true,
    mode,
    appCheckConfigured: !!appCheckSiteKey,
    appCheckProvider: appCheckSiteKey ? appCheckProviderMode : 'none',
    appCheckDevDebug: debug,
    projectId: app.options.projectId,
  };
}

export function prepareDeviceModel(onProgress = () => {}, modelOverride = null) {
  const target = modelOverride || instance;
  if (!target) throw new Error('Connect Firebase first.');
  if (modeName === 'ONLY_IN_CLOUD' && !modelOverride) {
    deviceState = 'not-applicable';
    return Promise.resolve({ ready: false, availability: 'not_applicable' });
  }
  // Must be called synchronously during user activation click.
  deviceState = 'initializing';
  try {
    const task = target.initializeDeviceModel((v) => onProgress(Math.max(0, Math.min(1, Number(v) || 0))));
    return Promise.resolve(task)
      .then(async () => {
        const probe = await probeDeviceAvailability();
        if (!probe.supported) {
          deviceState = 'unavailable';
          if (modeName === 'ONLY_ON_DEVICE') {
            throw new Error(`On-device LanguageModel API is ${probe.availability}; ONLY_ON_DEVICE refuses cloud fallback.`);
          }
          return { ready: false, availability: probe.availability };
        }
        deviceState = 'ready';
        return { ready: true, availability: probe.availability };
      })
      .catch((err) => {
        deviceState = 'unavailable';
        throw err;
      });
  } catch (err) {
    deviceState = 'unavailable';
    throw err;
  }
}

function tryParseJsonObject(chunk) {
  try {
    return JSON.parse(chunk);
  } catch {
    // Some small on-device models emit a stray backslash before a closing string quote (e.g. "...?)\\","quote":).
    const repaired = chunk.replace(/(?<!\\)\\"(?=\s*[,}\]])/g, '\\\\"');
    try {
      return JSON.parse(repaired);
    } catch {
      return null;
    }
  }
}

function extractTopLevelJsonObjects(str) {
  const blocks = [];
  let depth = 0;
  let start = -1;
  let inString = false;
  let esc = false;
  let hasTrailingGarbage = false;
  for (let i = 0; i < str.length; i += 1) {
    const ch = str[i];
    if (esc) {
      esc = false;
      continue;
    }
    if (ch === '\\' && inString) {
      esc = true;
      continue;
    }
    if (ch === '"') {
      inString = !inString;
      continue;
    }
    if (inString) continue;
    if (ch === '{') {
      if (depth === 0) start = i;
      depth += 1;
    } else if (ch === '}') {
      if (depth > 0) {
        depth -= 1;
      } else {
        hasTrailingGarbage = true;
      }
      if (depth === 0 && start >= 0) {
        blocks.push(str.slice(start, i + 1));
        start = -1;
      }
    } else if (depth === 0 && !/\s/.test(ch)) {
      hasTrailingGarbage = true;
    }
  }
  const balanced = depth === 0 && !inString && !esc && !hasTrailingGarbage;
  return { blocks, balanced };
}

export function parseModelProposal(raw) {
  const text = String(raw ?? '').slice(0, 24000);
  // Strip optional code fences and escape only literal backslashes before a closing quote+delimiter.
  // Never guess or rewrite corrupted JSON delimiter quotes such as `"?","` — reject fail-closed.
  const cleaned = text
    .replace(/```(?:json)?/gi, '')
    .replace(/(?<!\\)\\"(?=\s*[,}\]])/g, '\\\\"')
    .trim();
  if (!cleaned.includes('{')) {
    return { suggested_checks: [], possible_missing_categories: [], unsupported_assumptions: [], parse_error: 'no_json_object' };
  }
  const { blocks, balanced } = extractTopLevelJsonObjects(cleaned);
  if (!blocks.length || !balanced) {
    return {
      suggested_checks: [],
      possible_missing_categories: [],
      unsupported_assumptions: [],
      parse_error: 'invalid_or_ambiguous_json',
    };
  }
  const parsedObjects = blocks.map(tryParseJsonObject);
  if (parsedObjects.some((d) => !d || typeof d !== 'object' || Array.isArray(d))) {
    return {
      suggested_checks: [],
      possible_missing_categories: [],
      unsupported_assumptions: [],
      parse_error: 'invalid_or_ambiguous_json',
    };
  }
  const hasChecksSchema = parsedObjects.some((d) => Array.isArray(d.suggested_checks));
  if (!hasChecksSchema) {
    return {
      suggested_checks: [],
      possible_missing_categories: [],
      unsupported_assumptions: [],
      parse_error: 'unexpected_schema',
    };
  }
  const cut = (s, n) => (typeof s === 'string' ? s.trim().slice(0, n) : '');
  const allowed = (a) => (Array.isArray(a) ? a.slice(0, 12) : []);
  const checks = [];
  const categories = [];
  const assumptions = [];
  for (const data of parsedObjects) {
    for (const x of allowed(data.suggested_checks)) {
      if (x && typeof x === 'object' && !Array.isArray(x)) {
        const item = { id: cut(x.id, 60), label: cut(x.label, 300), reason: cut(x.reason, 450), quote: cut(x.quote, 700) };
        if (item.label && checks.length < 12) checks.push(item);
      }
    }
    for (const c of allowed(data.possible_missing_categories)) {
      const val = cut(c, 160);
      if (val && categories.length < 12) categories.push(val);
    }
    for (const a of allowed(data.unsupported_assumptions)) {
      const val = cut(a, 160);
      if (val && assumptions.length < 12) assumptions.push(val);
    }
  }
  return {
    suggested_checks: checks,
    possible_missing_categories: categories,
    unsupported_assumptions: assumptions,
  };
}

export function resolveInferenceTimeoutMs(mode, currentDeviceState, overrideMs) {
  if (overrideMs !== undefined && overrideMs !== null && Number.isFinite(Number(overrideMs)) && Number(overrideMs) > 0) {
    return Math.max(1000, Math.min(240000, Number(overrideMs)));
  }
  if (mode === 'ONLY_ON_DEVICE' || (mode === 'PREFER_ON_DEVICE' && currentDeviceState === 'ready')) {
    return 150000;
  }
  return 25000;
}

export async function extractWithHybrid(prompt, options = {}) {
  if (!instance) throw new Error('Firebase AI Logic is not connected.');
  const timeoutMs = resolveInferenceTimeoutMs(modeName, deviceState, options.timeoutMs);
  const consentState = Boolean(options.consentState);
  const scopeRequest = options.scopeRequest || null;
  const signal = options.signal || null;
  if (signal?.aborted) {
    throw new Error('User cancelled waiting for model inference.');
  }
  if (modeName === 'ONLY_ON_DEVICE' && !globalThis.LanguageModel) {
    // @firebase/ai skips ChromeAdapter when global LanguageModel is absent; fail closed instead of falling back to cloud.
    throw new Error('ONLY_ON_DEVICE blocked: Chrome LanguageModel API is unavailable in this browser; no cloud request sent.');
  }
  const start = clock();
  let timerId = null;
  let onAbort = null;
  let genSettled = false;
  let rawResponseText = null;
  const reqOpts = signal ? { signal, timeout: timeoutMs } : { timeout: timeoutMs };
  const genPromise = Promise.resolve()
    .then(() => instance.generateContent(String(prompt).slice(0, 11500), reqOpts))
    .finally(() => {
      if (!genSettled) {
        genSettled = true;
      } else if (modeName !== 'ONLY_IN_CLOUD') {
        unsettledBackgroundRuns = Math.max(0, unsettledBackgroundRuns - 1);
      }
    });
  // Prevent unhandled rejection warnings when client aborts/times out early.
  genPromise.catch(() => {});

  try {
    const racers = [
      genPromise,
      new Promise((_, reject) => {
        timerId = setTimeout(() => reject(new Error(`Inference timed out after ${timeoutMs}ms.`)), timeoutMs);
      }),
    ];
    if (signal && typeof signal.addEventListener === 'function') {
      racers.push(
        new Promise((_, reject) => {
          onAbort = () => reject(new Error('User cancelled waiting for model inference.'));
          signal.addEventListener('abort', onAbort, { once: true });
        })
      );
    }
    const result = await Promise.race(racers);
    genSettled = true;
    const response = result?.response;
    const raw = response?.text?.() || '';
    rawResponseText = raw;
    const source = response?.inferenceSource || 'UNREPORTED';
    const parsed = parseModelProposal(raw);
    const sdkModelVersion = response?.modelVersion || response?.model || null;
    const adapterLabel =
      source === 'in_cloud'
        ? 'firebase-ai-cloud'
        : source === 'on_device'
        ? 'chrome-prompt-api-adapter'
        : 'UNREPORTED';
    const modelVersion =
      source === 'in_cloud'
        ? instance?.inCloudParams?.model || instance?.model || null
        : source === 'on_device'
        ? sdkModelVersion
        : null;
    const modelId =
      source === 'in_cloud'
        ? modelVersion || 'SDK-unspecified'
        : source === 'on_device'
        ? modelVersion
          ? `${adapterLabel}:${modelVersion}`
          : `${adapterLabel} (version unreported)`
        : 'UNREPORTED';
    const errorClass = parsed.parse_error ? 'MalformedOutputError' : 'none';
    return {
      raw,
      parsed,
      source,
      adapterLabel,
      modelVersion,
      modelId,
      elapsedMs: Math.round(clock() - start),
      timeoutMs,
      mode: modeName,
      deviceState,
      consentState,
      errorClass,
      scopeRequest,
    };
  } catch (err) {
    if (!genSettled) {
      genSettled = true;
      if (modeName !== 'ONLY_IN_CLOUD') {
        unsettledBackgroundRuns += 1;
      }
    }
    const errObj = err && typeof err === 'object' ? err : new Error(String(err || 'Inference failed.'));
    const errClass = signal?.aborted ? 'UserCancelledError' : classifyInferenceError(errObj);
    if (errClass === 'OnDeviceSessionError') deviceState = 'session-error';
    errObj.errorClass = errClass;
    errObj.elapsedMs = Math.round(clock() - start);
    errObj.timeoutMs = timeoutMs;
    if (rawResponseText !== null) errObj.raw = rawResponseText;
    if (errClass === 'UserCancelledError') {
      errObj.cancellationKind =
        modeName === 'ONLY_IN_CLOUD' ? 'real_transport_abort' : 'client_wait_abort_local_still_draining';
    }
    throw errObj;
  } finally {
    if (timerId) clearTimeout(timerId);
    if (signal && onAbort && typeof signal.removeEventListener === 'function') {
      signal.removeEventListener('abort', onAbort);
    }
  }
}

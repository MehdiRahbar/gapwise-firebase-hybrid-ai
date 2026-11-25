import { promises as fs } from 'node:fs';
import path from 'node:path';
import { defineConfig } from 'vite';

const evidenceRoot = path.resolve(process.env.GAPWISE_EVIDENCE_ROOT || 'evidence/nano4_low_memory/runs');

function localEvidencePlugin() {
  return {
    name: 'gapwise-local-evidence',
    configureServer(server) {
      server.middlewares.use('/__gapwise_evidence', (req, res, next) => {
        if (req.method !== 'POST') {
          next();
          return;
        }
        const chunks = [];
        let size = 0;
        req.on('data', (chunk) => {
          size += chunk.length;
          if (size <= 2_000_000) chunks.push(chunk);
        });
        req.on('end', async () => {
          try {
            if (size > 2_000_000) throw new Error('evidence payload exceeds 2 MB');
            const body = JSON.parse(Buffer.concat(chunks).toString('utf8'));
            const runId = String(body.runId || '');
            const event = String(body.event || 'unknown').replace(/[^A-Za-z0-9_-]/g, '_').slice(0, 48) || 'unknown';
            if (!/^[A-Za-z0-9_-]{1,64}$/.test(runId)) throw new Error('invalid evidence run id');
            if (!body || body.schema !== 'gapwise.local-evidence.v1') throw new Error('invalid evidence schema');
            const runDir = path.resolve(evidenceRoot, runId);
            if (!runDir.startsWith(`${evidenceRoot}${path.sep}`)) throw new Error('invalid evidence path');
            await fs.mkdir(runDir, { recursive: true });
            const filename = `app_${Date.now()}_${event}.json`;
            await fs.writeFile(path.join(runDir, filename), `${JSON.stringify({ ...body, serverCapturedAt: new Date().toISOString() }, null, 2)}\n`, 'utf8');
            res.statusCode = 201;
            res.setHeader('content-type', 'application/json; charset=utf-8');
            res.end(JSON.stringify({ ok: true, file: filename }));
          } catch (error) {
            res.statusCode = 400;
            res.setHeader('content-type', 'application/json; charset=utf-8');
            res.end(JSON.stringify({ ok: false, error: String(error?.message || error) }));
          }
        });
      });
    },
  };
}

export default defineConfig({
  root: 'web',
  envDir: '..',
  publicDir: 'public',
  plugins: [localEvidencePlugin()],
  build: { outDir: '../dist', emptyOutDir: true, target: 'es2022' },
  server: { host: '127.0.0.1' },
  preview: { host: '127.0.0.1' },
});

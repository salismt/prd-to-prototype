// Minimal static server + stateful fake backend. PROTOTYPE_MODE=1 enables the test-only reset endpoint.
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');

const PORT = Number(process.env.PORT || 4312);
const PROTOTYPE_MODE = process.env.PROTOTYPE_MODE === '1';
const SEED = { profile: { name: 'Ada Lovelace', revision: 1 }, actor: 'editor' };
let state = structuredClone(SEED);

const json = (res, status, body) => {
  res.writeHead(status, { 'content-type': 'application/json' });
  res.end(JSON.stringify(body));
};
const readJson = (req) => new Promise((resolve) => {
  let raw = '';
  req.on('data', (c) => (raw += c));
  req.on('end', () => { try { resolve(JSON.parse(raw || '{}')); } catch { resolve(null); } });
});

// Fake command boundary: every guard lives here, not only in the UI.
function updateName(body) {
  if (state.actor !== 'editor') return [403, { error: 'Viewers cannot edit the display name.' }];
  if (typeof body.name !== 'string' || !body.name.trim()) return [400, { error: 'Display name cannot be blank.' }];
  if (body.revision !== state.profile.revision) return [409, { error: 'Profile changed elsewhere. Your draft is kept.', profile: state.profile }];
  state.profile = { name: body.name.trim(), revision: state.profile.revision + 1 };
  return [200, state.profile];
}

http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://localhost:${PORT}`);
  if (url.pathname === '/api/session') return json(res, 200, { actor: state.actor });
  if (url.pathname === '/api/profile' && req.method === 'GET') return json(res, 200, state.profile);
  if (url.pathname === '/api/profile' && req.method === 'PUT') {
    const body = await readJson(req);
    return body ? json(res, ...updateName(body)) : json(res, 400, { error: 'Invalid JSON' });
  }
  if (PROTOTYPE_MODE && url.pathname === '/__test/reset' && req.method === 'POST') {
    const body = (await readJson(req)) || {};
    state = structuredClone(SEED);
    if (body.actor) state.actor = body.actor;
    if (body.profile) state.profile = { ...state.profile, ...body.profile };
    return json(res, 200, state);
  }
  const file = path.join(__dirname, 'public', url.pathname === '/' ? 'index.html' : url.pathname);
  if (!file.startsWith(path.join(__dirname, 'public')) || !fs.existsSync(file)) return json(res, 404, { error: 'Not found' });
  res.writeHead(200, { 'content-type': file.endsWith('.js') ? 'text/javascript' : 'text/html' });
  fs.createReadStream(file).pipe(res);
}).listen(PORT, () => console.log(`web-demo on http://localhost:${PORT} (prototype mode: ${PROTOTYPE_MODE})`));

// Vanilla hash router: #/ (S1 home) and #/profile (S2). All state lives behind /api/*.
const view = document.getElementById('view');
const api = (path, init) => fetch(path, { headers: { 'content-type': 'application/json' }, ...init }).then(async (r) => ({ ok: r.ok, body: await r.json() }));

async function home() {
  const { body: profile } = await api('/api/profile');
  view.innerHTML = `<h1>Home</h1><p>Welcome back, <strong data-testid="home-name">${esc(profile.name)}</strong>.</p>`;
}

async function profile() {
  const [{ body: session }, { body: current }] = await Promise.all([api('/api/session'), api('/api/profile')]);
  view.innerHTML = `
    <h1>Profile</h1>
    <p class="note">Signed in as <span data-testid="actor">${esc(session.actor)}</span>. Current name: <span data-testid="current-name">${esc(current.name)}</span> (rev ${current.revision}).</p>
    <form id="name-form">
      <label for="name">Display name</label>
      <input id="name" name="name" value="${esc(current.name)}" autocomplete="off">
      <button type="submit">Save</button>
    </form>
    <p id="message"></p>`;
  const input = document.getElementById('name');
  const message = document.getElementById('message');
  let revision = current.revision;
  document.getElementById('name-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const { ok, body } = await api('/api/profile', { method: 'PUT', body: JSON.stringify({ name: input.value, revision }) });
    message.setAttribute('role', ok ? 'status' : 'alert');
    if (ok) {
      revision = body.revision;
      document.querySelector('[data-testid=current-name]').textContent = body.name;
      message.textContent = `Saved as "${body.name}".`;
    } else {
      message.textContent = body.error; // draft in the input is left untouched on every rejection
    }
  });
}

const routes = { '#/': home, '#/profile': profile };
const render = () => (routes[location.hash || '#/'] || home)();
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);
addEventListener('hashchange', render);
render();

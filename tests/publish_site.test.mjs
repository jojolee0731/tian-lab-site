import assert from 'node:assert/strict';
import test from 'node:test';
import { createHandler } from '../supabase/functions/publish-site/handler.mjs';

const SESSION = 'test-session-that-is-at-least-twenty-characters';
const SECRET = 'server-only-publish-test-credential';
const config = { SUPABASE_URL: 'https://example.supabase.co', SUPABASE_ANON_KEY: 'public-test-key', GITHUB_PUBLISH_TOKEN: SECRET };
const json = (body, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
const request = (options = {}) => new Request('https://example.supabase.co/functions/v1/publish-site', {
  method: 'POST', headers: { Authorization: `Bearer ${SESSION}`, Origin: 'https://jojolee0731.github.io', 'Content-Type': 'application/json' }, ...options,
});
function harness(responses, overrides = {}) {
  const calls = [];
  const handler = createHandler({ env: key => ({ ...config, ...overrides })[key], fetchImpl: async (url, options) => {
    calls.push({ url, options });
    const response = responses.shift();
    if (response instanceof Error) throw response;
    assert.ok(response, 'unexpected outbound call');
    return response;
  } });
  return { handler, calls };
}

test('missing JWT and foreign origins cannot dispatch', async () => {
  const { handler, calls } = harness([]);
  assert.equal((await handler(request({ headers: {} }))).status, 401);
  assert.equal((await handler(request({ headers: { Authorization: `Bearer ${SESSION}`, Origin: 'https://untrusted.example' } }))).status, 403);
  assert.equal(calls.length, 0);
});
test('a forged/expired session is rejected by Auth before permission lookup', async () => {
  const { handler, calls } = harness([json({}, 401)]);
  assert.equal((await handler(request())).status, 401);
  assert.equal(calls.length, 1);
  assert.ok(calls[0].url.endsWith('/auth/v1/user'));
});
test('member role, disabled admin and revoked invitation never reach GitHub', async () => {
  for (const result of [json({ account: { role: 'member' } }), json({ account: { role: 'admin', enabled: false } }), json({}, 403)]) {
    const { handler, calls } = harness([json({ id: 'confirmed-user' }), result]);
    assert.equal((await handler(request({ body: JSON.stringify({ role: 'admin' }) }))).status, 403);
    assert.equal(calls.length, 2);
    assert.ok(calls.every(call => !call.url.includes('github')));
  }
});
test('a live administrator can only dispatch the fixed production workflow', async () => {
  const { handler, calls } = harness([json({ id: 'confirmed-user' }), json({ account: { role: 'admin' } }), new Response(null, { status: 204 })]);
  const response = await handler(request({ body: JSON.stringify({ repo: 'attacker/repo', ref: 'draft', workflow: 'exfiltrate.yml' }) }));
  assert.equal(response.status, 202);
  const body = await response.json();
  assert.equal(body.state, 'queued');
  assert.ok(!JSON.stringify(body).includes(SECRET));
  assert.equal(calls[2].url, 'https://api.github.com/repos/jojolee0731/tian-lab-site/actions/workflows/publish-members.yml/dispatches');
  assert.deepEqual(JSON.parse(calls[2].options.body), { ref: 'main' });
  assert.equal(calls[2].options.headers.Authorization, `Bearer ${SECRET}`);
  assert.equal(calls[1].options.headers.Authorization, `Bearer ${SESSION}`);
  assert.equal(calls[2].options.redirect, 'error');
});
test('missing configuration or failed dispatch never claims publication', async () => {
  const missing = harness([json({ id: 'user' }), json({ account: { role: 'admin' } })], { GITHUB_PUBLISH_TOKEN: '' });
  assert.equal((await missing.handler(request())).status, 503);
  assert.equal(missing.calls.length, 2);
  const denied = harness([json({ id: 'user' }), json({ account: { role: 'admin' } }), json({ error: SECRET }, 403)]);
  const response = await denied.handler(request());
  assert.equal(response.status, 502);
  assert.ok(!(await response.text()).includes(SECRET));
});

test('modern publishable configuration is separate from the verified user JWT', async () => {
  for (const keys of [{ default: 'sb_publishable_fixture' }, { default: 'sb_secret_not_public', secondary: 'sb_publishable_fixture' }]) {
    const { handler, calls } = harness([json({ id: 'user' }), json({ account: { role: 'admin' } }), new Response(null, { status: 204 })], {
      SUPABASE_PUBLISHABLE_KEYS: JSON.stringify(keys), SUPABASE_ANON_KEY: '',
    });
    assert.equal((await handler(request())).status, 202);
    assert.equal(calls[0].options.headers.apikey, 'sb_publishable_fixture');
    assert.equal(calls[0].options.headers.Authorization, `Bearer ${SESSION}`);
  }
});

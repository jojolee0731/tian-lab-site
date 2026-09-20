import assert from 'node:assert/strict';
import test from 'node:test';
import { EventEmitter } from 'node:events';
import { createHandler, createSmtpAdapter } from '../supabase/functions/review-notifications/handler.mjs';

const KEY = 'sb_secret_notification_fixture_1234567890123456';
const OTHER_KEY = 'sb_secret_rotation_fixture_1234567890123456';
const PASSWORD = 'smtp-test-secret-never-return-this';
const RECIPIENT = 'xiangm_chen@foxmail.com';
const PORTAL = 'https://jojolee0731.github.io/tian-lab-site/members/';
const baseConfig = { SUPABASE_URL: 'https://example.supabase.co', SUPABASE_SECRET_KEYS: JSON.stringify({ default: KEY }), REVIEW_SMTP_PASSWORD: PASSWORD };
const json = (value, status = 200) => new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } });
const request = (options = {}) => new Request('https://example.supabase.co/functions/v1/review-notifications', {
  method: 'POST', headers: { apikey: KEY, 'Content-Type': 'application/json' }, body: '{}', ...options,
});
const uuid = n => `00000000-0000-0000-0000-${String(n).padStart(12, '0')}`;
const item = (n = 1, changes = {}) => ({ id: uuid(n), submission_id: uuid(100 + n), member_name: '测试成员', created_at: '2026-09-20T08:30:00+00:00', lease_token: uuid(200 + n), attempts: 1, ...changes });
function harness(responses = [], { config = {}, send, verify, timeout = 1000 } = {}) {
  const calls = [], messages = [], signals = [], verifications = [];
  const handler = createHandler({
    env: name => ({ ...baseConfig, ...config })[name], smtpTimeoutMs: timeout,
    fetchImpl: async (url, options) => {
      calls.push({ url, options });
      const response = responses.shift();
      assert.ok(response, 'unexpected RPC');
      if (response instanceof Error) throw response;
      return response;
    },
    sendMail: async (message, options) => {
      messages.push(message); signals.push(options.signal);
      return send ? await send(message, options) : { accepted: [RECIPIENT] };
    },
    verifySmtp: async options => { verifications.push(options); return verify ? await verify(options) : true; },
  });
  return { handler, calls, messages, signals, verifications };
}

test('only POST without a browser Origin is accepted; no CORS is enabled', async () => {
  const h = harness();
  assert.equal((await h.handler(request({ method: 'GET', body: undefined }))).status, 405);
  assert.equal((await h.handler(request({ method: 'OPTIONS', body: undefined }))).status, 405);
  const response = await h.handler(request({ headers: { apikey: KEY, Origin: 'https://jojolee0731.github.io' } }));
  assert.equal(response.status, 403);
  assert.equal(response.headers.get('Access-Control-Allow-Origin'), null);
  assert.equal(h.calls.length + h.messages.length + h.verifications.length, 0);
});

test('missing, anon, user JWT, wrong and excessively long apikey cannot claim or verify SMTP', async () => {
  const jwt = ['eyJhbGciOiJIUzI1NiJ9', Buffer.from('{"role":"authenticated"}').toString('base64url'), 'signature'].join('.');
  for (const headers of [{}, { apikey: 'sb_publishable_public_fixture' }, { apikey: jwt }, { Authorization: `Bearer ${KEY}` }, { apikey: OTHER_KEY }, { apikey: 'x'.repeat(8200) }]) {
    const h = harness();
    assert.equal((await h.handler(request({ headers, body: '{"mode":"verify"}' }))).status, 401);
    assert.equal(h.calls.length + h.messages.length + h.verifications.length, 0);
  }
});

test('modern default and rotated named secret keys authenticate without sending a Bearer header', async () => {
  for (const key of [KEY, OTHER_KEY]) {
    const h = harness([json([])], { config: { SUPABASE_SECRET_KEYS: JSON.stringify({ default: KEY, rotated: OTHER_KEY }) } });
    assert.equal((await h.handler(request({ headers: { apikey: key } }))).status, 200);
    assert.equal(h.calls[0].options.headers.apikey, key);
    assert.equal(h.calls[0].options.headers.Authorization, undefined);
    assert.deepEqual(JSON.parse(h.calls[0].options.body), { p_limit: 5 });
    assert.equal(h.calls[0].options.redirect, 'error');
  }
});

test('legacy service-role fallback requires the exact configured key and adds its RPC Bearer header', async () => {
  const jwt = role => ['eyJhbGciOiJIUzI1NiJ9', Buffer.from(JSON.stringify({ role })).toString('base64url'), 'fixture_signature'].join('.');
  const legacy = jwt('service_role');
  const h = harness([json([])], { config: { SUPABASE_SECRET_KEYS: 'malformed', SUPABASE_SERVICE_ROLE_KEY: legacy } });
  assert.equal((await h.handler(request({ headers: { apikey: legacy } }))).status, 200);
  assert.equal(h.calls[0].options.headers.Authorization, `Bearer ${legacy}`);
  const bad = harness([], { config: { SUPABASE_SECRET_KEYS: '{}', SUPABASE_SERVICE_ROLE_KEY: jwt('anon') } });
  assert.equal((await bad.handler(request({ headers: { apikey: jwt('anon') } }))).status, 401);
  assert.equal(bad.calls.length, 0);
});

test('request body cannot override recipient, message, limit or any other content', async () => {
  for (const body of ['{"to":"attacker@example.test"}', '{"recipient":"attacker@example.test","mode":"verify"}', '{"html":"secret"}', '{"p_limit":100}', '{"mode":"send"}', 'null', '[]', '{', ' '.repeat(1025)]) {
    const h = harness();
    assert.equal((await h.handler(request({ body }))).status, 400);
    assert.equal(h.calls.length + h.messages.length + h.verifications.length, 0);
  }
});

test('SMTP verify authenticates but never claims, sends or finishes an outbox item', async () => {
  const h = harness();
  const response = await h.handler(request({ body: '{"mode":"verify"}' }));
  assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), { state: 'smtp_verified', sent: 0 });
  assert.equal(h.verifications.length, 1);
  assert.equal(h.calls.length + h.messages.length, 0);
});

test('verify failure never returns SMTP exception contents or credentials', async () => {
  const h = harness([], { verify: () => { throw Object.assign(new Error(`${KEY} ${PASSWORD}`), { code: PASSWORD, response: KEY, command: PASSWORD, cause: new Error(KEY) }); } });
  const response = await h.handler(request({ body: '{"mode":"verify"}' }));
  assert.equal(response.status, 502);
  const text = await response.text();
  assert.ok(!text.includes(KEY) && !text.includes(PASSWORD));
  assert.deepEqual(JSON.parse(text), { error: 'smtp_verification_failed', reason: 'smtp_failed', sent: 0 });
  assert.equal(h.calls.length + h.messages.length, 0);
});

test('authenticated verify failures expose only fixed SMTP reason categories', async () => {
  const cases = [
    ['smtp_timeout', 'smtp_timeout'], ['ETIMEDOUT', 'smtp_timeout'], ['ERR_TLS_HANDSHAKE_TIMEOUT', 'smtp_timeout'],
    ['EAUTH', 'smtp_auth_failed'], ['ETLS', 'smtp_tls_failed'], ['ERR_TLS_CERT_ALTNAME_INVALID', 'smtp_tls_failed'],
    ['CERT_HAS_EXPIRED', 'smtp_tls_failed'], ['ESOCKET', 'smtp_network_failed'], ['EDNS', 'smtp_network_failed'],
    ['ECONNREFUSED', 'smtp_network_failed'], ['ECONNRESET', 'smtp_network_failed'], ['ENOTFOUND', 'smtp_network_failed'],
    ['EAI_AGAIN', 'smtp_network_failed'], ['unrecognized', 'smtp_failed'], [undefined, 'smtp_failed'],
  ];
  for (const [code, reason] of cases) {
    const h = harness([], { verify: () => { throw Object.assign(new Error(PASSWORD), { code, response: KEY, command: PASSWORD }); } });
    const response = await h.handler(request({ body: '{"mode":"verify"}' }));
    assert.equal(response.status, 502);
    assert.deepEqual(await response.json(), { error: 'smtp_verification_failed', reason, sent: 0 });
    assert.equal(h.calls.length + h.messages.length, 0);
  }
});

test('verify deadline reports smtp_timeout and aborts without claiming or sending', async () => {
  let aborted = false;
  const h = harness([], { timeout: 5, verify: ({ signal }) => new Promise(() => { signal.addEventListener('abort', () => { aborted = true; }); }) });
  const response = await h.handler(request({ body: '{"mode":"verify"}' }));
  assert.equal(response.status, 502);
  assert.deepEqual(await response.json(), { error: 'smtp_verification_failed', reason: 'smtp_timeout', sent: 0 });
  assert.ok(aborted);
  assert.equal(h.calls.length + h.messages.length, 0);
});

test('verify diagnostics are unavailable without server authentication or with a browser Origin', async () => {
  for (const headers of [{}, { apikey: OTHER_KEY }, { apikey: KEY, Origin: 'https://jojolee0731.github.io' }]) {
    const h = harness([], { verify: () => { throw Object.assign(new Error(PASSWORD), { code: 'EAUTH' }); } });
    const response = await h.handler(request({ headers, body: '{"mode":"verify"}' }));
    assert.ok([401, 403].includes(response.status));
    assert.equal(Object.hasOwn(await response.json(), 'reason'), false);
    assert.equal(h.verifications.length + h.calls.length + h.messages.length, 0);
  }
});

test('missing SMTP password and non-HTTPS/base-path configuration fail before claiming', async () => {
  for (const config of [{ REVIEW_SMTP_PASSWORD: '' }, { SUPABASE_URL: 'http://example.test' }, { SUPABASE_URL: 'https://user:password@example.test' }, { SUPABASE_URL: 'https://example.test/private' }]) {
    const h = harness([], { config });
    assert.equal((await h.handler(request())).status, 503);
    assert.equal(h.calls.length + h.messages.length, 0);
  }
});

test('claim failures are sanitized and do not touch SMTP', async () => {
  for (const response of [json({ error: PASSWORD }, 500), new Error(KEY)]) {
    const h = harness([response]);
    const result = await h.handler(request());
    assert.equal(result.status, 502);
    assert.ok(!(await result.text()).includes(PASSWORD));
    assert.equal(h.messages.length, 0);
  }
});

test('empty outbox is a successful no-op', async () => {
  const h = harness([json([])]);
  assert.deepEqual(await (await h.handler(request())).json(), { state: 'processed', claimed: 0, sent: 0, retryScheduled: 0, completionUnconfirmed: 0 });
  assert.equal(h.messages.length, 0);
});

test('a valid alert has fixed recipient/envelope/subject/portal and no private payload', async () => {
  const h = harness([json([item(1, { payload: { bio: PASSWORD }, recipient: 'attacker@example.test' })]), json(true)]);
  const response = await h.handler(request());
  assert.equal(response.status, 200);
  const m = h.messages[0];
  assert.equal(m.to, RECIPIENT);
  assert.deepEqual(m.from, { name: 'TianLab 成员工作台', address: '71529983@qq.com' });
  assert.deepEqual(m.envelope, { from: '71529983@qq.com', to: [RECIPIENT] });
  assert.equal(m.subject, 'TianLab 成员资料待审核');
  assert.ok(m.text.includes('2026-09-20 16:30:00（北京时间）') && m.text.includes(PORTAL));
  assert.ok(!JSON.stringify(m).includes(PASSWORD) && !JSON.stringify(m).includes('attacker'));
  assert.deepEqual(JSON.parse(h.calls[1].options.body), { p_id: uuid(1), p_lease_token: uuid(201), p_sent: true, p_error_code: null });
});

test('name control characters are removed and HTML is escaped; name never enters headers', async () => {
  const h = harness([json([item(1, { member_name: '<img src=x onerror=1>\r\nBcc: injected & " \'\u0000' })]), json(true)]);
  await h.handler(request());
  const m = h.messages[0];
  assert.ok(!m.html.includes('<img') && m.html.includes('&lt;img') && m.html.includes('&amp;') && m.html.includes('&#39;'));
  assert.ok(!m.text.includes('\r') && !m.text.includes('\u0000'));
  assert.equal(m.subject, 'TianLab 成员资料待审核');
  assert.equal(m.to, RECIPIENT);
});

test('Message-ID is stable across leases/attempts for the same submission', async () => {
  const a = harness([json([item()]), json(true)]);
  const b = harness([json([item(1, { lease_token: uuid(999), attempts: 4 })]), json(true)]);
  await a.handler(request()); await b.handler(request());
  assert.equal(a.messages[0].messageId, b.messages[0].messageId);
  assert.equal(a.messages[0].messageId, `<tianlab-review-${uuid(101)}@jojolee0731.github.io>`);
});

test('at most five distinct items are mailed; larger or duplicate batches fail closed', async () => {
  const h = harness([json(Array.from({ length: 5 }, (_, n) => item(n + 1))), ...Array.from({ length: 5 }, () => json(true))]);
  assert.equal((await h.handler(request())).status, 200);
  assert.equal(h.messages.length, 5);
  for (const values of [Array.from({ length: 6 }, (_, n) => item(n + 1)), [item(), item()], [item(), item(2, { submission_id: uuid(101) })]]) {
    const invalid = harness([json(values)]);
    assert.equal((await invalid.handler(request())).status, 502);
    assert.equal(invalid.messages.length, 0);
  }
});

test('invalid IDs, lease tokens or attempts never produce a message', async () => {
  for (const patch of [{ id: '../secret' }, { lease_token: 'bad' }, { id: [uuid(1)] }, { attempts: 9 }, { attempts: 0 }]) {
    const h = harness([json([item(1, patch)])]);
    assert.equal((await h.handler(request())).status, 502);
    assert.equal(h.messages.length, 0);
  }
});

test('invalid name/time is finished with a safe retry error without sending', async () => {
  for (const patch of [{ member_name: { bio: PASSWORD } }, { created_at: 'invalid' }]) {
    const h = harness([json([item(1, patch)]), json(true)]);
    const result = await (await h.handler(request())).json();
    assert.equal(h.messages.length, 0);
    assert.equal(result.retryScheduled, 1);
    assert.equal(JSON.parse(h.calls[1].options.body).p_error_code, 'invalid_claim');
  }
});

test('SMTP failure is persisted once with a safe error code and no immediate resend', async () => {
  const h = harness([json([item()]), json(true)], { send: () => { throw new Error(`${PASSWORD} ${KEY}`); } });
  const response = await h.handler(request());
  assert.equal(response.status, 200);
  assert.equal(h.messages.length, 1);
  assert.deepEqual(JSON.parse(h.calls[1].options.body), { p_id: uuid(1), p_lease_token: uuid(201), p_sent: false, p_error_code: 'smtp_failed' });
  assert.ok(!(await response.text()).includes(PASSWORD));
});

test('delivery failures reuse diagnostic categories and distinguish local mail construction errors', async () => {
  const cases = [
    ['EAUTH', 'smtp_auth_failed'], ['ETLS', 'smtp_tls_failed'], ['ESOCKET', 'smtp_network_failed'],
    ['ETIMEDOUT', 'smtp_timeout'], ['EENVELOPE', 'smtp_envelope_failed'], ['ESECURITY', 'smtp_security_failed'],
    ['EMESSAGE', 'smtp_message_failed'], ['EPROTOCOL', 'smtp_protocol_failed'], ['ESTREAM', 'smtp_stream_failed'],
    ['ERR_STREAM_PREMATURE_CLOSE', 'smtp_stream_failed'], ['ERR_NOT_IMPLEMENTED', 'smtp_runtime_failed'],
    ['ERR_INVALID_ARG_TYPE', 'smtp_runtime_failed'], ['ENOTSUP', 'smtp_runtime_failed'], ['unrecognized', 'smtp_failed'],
  ];
  for (const [code, category] of cases) {
    const h = harness([json([item()]), json(true)], { send: () => { throw Object.assign(new Error(PASSWORD), { code, response: KEY, cause: new Error(KEY) }); } });
    const response = await h.handler(request());
    assert.equal(response.status, 200);
    const finished = JSON.parse(h.calls[1].options.body);
    assert.equal(finished.p_error_code, category);
    assert.equal(finished.p_sent, false);
    assert.equal(h.messages.length, 1);
    assert.ok(!JSON.stringify(finished).includes(PASSWORD) && !JSON.stringify(finished).includes(KEY));
  }
});

test('delivery stores only fixed SMTP command classes and numeric 4xx or 5xx status codes', async () => {
  const cases = [
    ['EAUTH', `AUTH PLAIN ${PASSWORD}`, 535, 'smtp_auth_failed_auth_535'],
    ['EENVELOPE', `MAIL FROM:<${PASSWORD}@example.test>`, 550, 'smtp_envelope_failed_mail_from_550'],
    ['EENVELOPE', `RCPT TO:<${PASSWORD}@example.test>`, 451, 'smtp_envelope_failed_rcpt_to_451'],
    ['EMESSAGE', 'DATA', 554, 'smtp_message_failed_data_554'],
    ['ESOCKET', 'CONN', 421, 'smtp_network_failed_connection_421'],
    ['ETLS', 'STARTTLS', 454, 'smtp_tls_failed_tls_454'],
    [PASSWORD, PASSWORD, PASSWORD, 'smtp_failed'],
    [PASSWORD, 'AUTHORIZATION', '535', 'smtp_failed'],
    [PASSWORD, 'DATA_SECRET', 250, 'smtp_failed'],
    [PASSWORD, `AUTH ${PASSWORD.repeat(40)}`, 600, 'smtp_failed'],
  ];
  for (const [code, command, responseCode, expected] of cases) {
    const h = harness([json([item()]), json(true)], { send: () => { throw Object.assign(new Error(PASSWORD), { code, command, responseCode, response: KEY }); } });
    const response = await h.handler(request());
    assert.equal(response.status, 200);
    const finished = JSON.parse(h.calls[1].options.body);
    assert.equal(finished.p_error_code, expected);
    assert.match(finished.p_error_code, /^[a-z][a-z0-9_]{0,63}$/);
    assert.ok(!JSON.stringify(finished).includes(PASSWORD) && !JSON.stringify(finished).includes(KEY));
    assert.equal(h.messages.length, 1);
    assert.equal(Object.hasOwn(await response.json(), 'reason'), false);
  }
});

test('SMTP not accepting the fixed recipient schedules retry', async () => {
  const h = harness([json([item()]), json(true)], { send: () => ({ accepted: [], rejected: [RECIPIENT] }) });
  await h.handler(request());
  assert.equal(JSON.parse(h.calls[1].options.body).p_error_code, 'smtp_rejected');
});

test('absolute SMTP deadline aborts the operation and persists smtp_timeout', async () => {
  let aborted = false;
  const h = harness([json([item()]), json(true)], { timeout: 5, send: (_message, { signal }) => new Promise(() => { signal.addEventListener('abort', () => { aborted = true; }); }) });
  const response = await h.handler(request());
  assert.equal(response.status, 200);
  assert.ok(aborted);
  assert.equal(h.messages.length, 1);
  assert.equal(JSON.parse(h.calls[1].options.body).p_error_code, 'smtp_timeout');
});

test('SMTP acceptance followed by finish failure or stale lease never resends or marks unsent', async () => {
  for (const finish of [json(false), json({ error: PASSWORD }, 500), new Error(KEY)]) {
    const h = harness([json([item()]), finish]);
    const response = await h.handler(request());
    assert.equal(response.status, 502);
    const body = await response.json();
    assert.equal(body.sent, 1); assert.equal(body.completionUnconfirmed, 1);
    assert.equal(h.messages.length, 1); assert.equal(h.calls.length, 2);
    assert.equal(JSON.parse(h.calls[1].options.body).p_sent, true);
    assert.ok(!JSON.stringify(body).includes(PASSWORD) && !JSON.stringify(body).includes(KEY));
  }
});

function adapterHarness({ lateSocket = false, verify = false } = {}) {
  const socket = new EventEmitter(); socket.destroyed = false; socket.destroy = () => { socket.destroyed = true; };
  let options, handedOff = 0, sends = 0, verifies = 0, closed = 0, connectOptions;
  const adapter = createSmtpAdapter({
    env: name => name === 'REVIEW_SMTP_PASSWORD' ? PASSWORD : undefined,
    connectTls: value => { connectOptions = value; if (!lateSocket) queueMicrotask(() => socket.emit('secureConnect')); return socket; },
    createTransport: value => {
      options = value;
      const operation = mode => new Promise((resolve, reject) => {
        if (mode === 'verify') verifies += 1; else sends += 1;
        options.getSocket({}, (error, result) => { if (error) reject(error); else { handedOff += 1; assert.equal(result.secured, true); resolve(mode === 'verify' ? true : { accepted: [RECIPIENT] }); } });
      });
      return { sendMail: () => operation('send'), verify: () => operation('verify'), close: () => { closed += 1; } };
    },
  });
  return { adapter, socket, snapshot: () => ({ options, handedOff, sends, verifies, closed, connectOptions }), run: signal => verify ? adapter.verifySmtp({ signal }) : adapter.sendMail({}, { signal }) };
}

test('SMTP adapter fixes QQ465 authenticated TLS, disables logging/content access, and closes sockets', async () => {
  const h = adapterHarness();
  await h.run(new AbortController().signal);
  const s = h.snapshot();
  assert.equal(s.options.host, 'smtp.qq.com'); assert.equal(s.options.port, 465); assert.equal(s.options.secure, true);
  assert.equal(s.options.auth.user, '71529983@qq.com');
  assert.equal(s.connectOptions.rejectUnauthorized, true); assert.equal(s.connectOptions.servername, 'smtp.qq.com');
  assert.equal(s.options.logger, false); assert.equal(s.options.debug, false);
  assert.equal(s.options.disableFileAccess, true); assert.equal(s.options.disableUrlAccess, true);
  assert.ok(h.socket.destroyed); assert.equal(s.closed, 1);
});

test('SMTP adapter verify invokes only verify and creates no message', async () => {
  const h = adapterHarness({ verify: true });
  assert.equal(await h.run(new AbortController().signal), true);
  assert.equal(h.snapshot().sends, 0); assert.equal(h.snapshot().verifies, 1);
});

test('aborted pending TLS connection is destroyed and a late secureConnect cannot send', async () => {
  const h = adapterHarness({ lateSocket: true });
  const controller = new AbortController();
  const pending = h.run(controller.signal);
  controller.abort();
  await assert.rejects(pending, error => error.code === 'smtp_timeout');
  assert.ok(h.socket.destroyed);
  h.socket.emit('secureConnect');
  assert.equal(h.snapshot().handedOff, 0);
  assert.equal(h.snapshot().closed, 1);
});

test('an already aborted operation never creates a TLS connection or transport', async () => {
  const h = adapterHarness(); const controller = new AbortController(); controller.abort();
  await assert.rejects(h.run(controller.signal), error => error.code === 'smtp_timeout');
  assert.equal(h.snapshot().options, undefined); assert.equal(h.snapshot().connectOptions, undefined);
});

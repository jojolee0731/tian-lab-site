const RECIPIENT = 'xiangm_chen@foxmail.com';
const SENDER = '71529983@qq.com';
const PORTAL = 'https://jojolee0731.github.io/tian-lab-site/members/';
const SMTP_HOST = 'smtp.qq.com';
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const SMTP_TIMEOUT_MS = 18000;
const MAX_BATCH = 5;
const encoder = new TextEncoder();

function safeError(code) { return Object.assign(new Error(code), { code }); }
function secretKeys(env) {
  let named = {};
  try { named = JSON.parse(env('SUPABASE_SECRET_KEYS') || '{}'); } catch { /* Legacy fallback remains available. */ }
  const modern = value => typeof value === 'string' && /^sb_secret_[A-Za-z0-9_-]{16,512}$/.test(value);
  const candidates = named && typeof named === 'object' && !Array.isArray(named)
    ? [named.default, ...Object.values(named)] : [];
  candidates.push(env('SUPABASE_SECRET_KEY'));
  const keys = candidates.filter(modern);
  const legacy = env('SUPABASE_SERVICE_ROLE_KEY');
  if (typeof legacy === 'string' && legacy.length <= 8192 && /^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$/.test(legacy)) {
    try {
      const value = legacy.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
      if (JSON.parse(atob(value.padEnd(Math.ceil(value.length / 4) * 4, '='))).role === 'service_role') keys.push(legacy);
    } catch { /* A misconfigured anon/user token must not become a worker secret. */ }
  }
  return [...new Set(keys)];
}

// Hashes have fixed length; compare every byte of every configured key without early exit.
async function matchingKey(supplied, keys) {
  if (!supplied || supplied.length > 8192) return null;
  const digest = async value => new Uint8Array(await crypto.subtle.digest('SHA-256', encoder.encode(value)));
  const input = await digest(supplied);
  const expected = await Promise.all(keys.map(digest));
  let match = -1;
  for (let i = 0; i < expected.length; i += 1) {
    let difference = 0;
    for (let j = 0; j < 32; j += 1) difference |= input[j] ^ expected[i][j];
    if (difference === 0) match = i;
  }
  return match < 0 ? null : keys[match];
}

async function requestMode(request) {
  const reader = request.body?.getReader();
  const chunks = [];
  let size = 0;
  if (reader) {
    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        size += value.byteLength;
        if (size > 1024) { await reader.cancel(); throw safeError('invalid_request'); }
        chunks.push(value);
      }
    } finally { reader.releaseLock(); }
  }
  const bytes = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
  const text = new TextDecoder('utf-8', { fatal: true }).decode(bytes).trim();
  const body = text ? JSON.parse(text) : {};
  if (!body || typeof body !== 'object' || Array.isArray(body) || Object.keys(body).some(key => key !== 'mode')) throw safeError('invalid_request');
  if (body.mode !== undefined && body.mode !== 'verify') throw safeError('invalid_request');
  return body.mode || 'deliver';
}

async function smtpDeadline(operation, timeoutMs) {
  const controller = new AbortController();
  let timer;
  try {
    return await Promise.race([
      Promise.resolve().then(() => operation(controller.signal)),
      new Promise((_, reject) => {
        timer = setTimeout(() => { controller.abort(); reject(safeError('smtp_timeout')); }, timeoutMs);
      }),
    ]);
  } finally {
    clearTimeout(timer);
    controller.abort();
  }
}

function messageFor(item) {
  if (typeof item.member_name !== 'string' || item.member_name.length > 1000 || typeof item.created_at !== 'string'
    || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$/.test(item.created_at)) throw safeError('invalid_claim');
  const time = Date.parse(item.created_at);
  if (!Number.isFinite(time)) throw safeError('invalid_claim');
  const name = item.member_name.replace(/[\u0000-\u001f\u007f-\u009f\u2028\u2029]/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 120) || '课题组成员';
  const submittedAt = new Date(time + 8 * 3600000).toISOString().slice(0, 19).replace('T', ' ') + '（北京时间）';
  const escape = value => value.replace(/[&<>"']/g, character => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[character]);
  return {
    from: { name: 'TianLab 成员工作台', address: SENDER },
    to: RECIPIENT,
    envelope: { from: SENDER, to: [RECIPIENT] },
    subject: 'TianLab 成员资料待审核',
    messageId: `<tianlab-review-${item.submission_id.toLowerCase()}@jojolee0731.github.io>`,
    text: `${name} 提交了成员资料，待审核。\n提交时间：${submittedAt}\n审核入口：${PORTAL}\n`,
    html: `<p>${escape(name)} 提交了成员资料，待审核。</p><p>提交时间：${escape(submittedAt)}</p><p><a href="${PORTAL}">打开成员工作台审核</a></p>`,
    disableFileAccess: true,
    disableUrlAccess: true,
  };
}

function deliveryError(error) {
  if (error?.code === 'invalid_claim') return 'invalid_claim';
  let category = verificationError(error);
  const codes = {
    smtp_rejected: 'smtp_rejected', EENVELOPE: 'smtp_envelope_failed', ESECURITY: 'smtp_security_failed',
    EMESSAGE: 'smtp_message_failed', EPROTOCOL: 'smtp_protocol_failed', ESTREAM: 'smtp_stream_failed',
    ERR_STREAM_PREMATURE_CLOSE: 'smtp_stream_failed', ERR_STREAM_DESTROYED: 'smtp_stream_failed',
    ERR_NOT_IMPLEMENTED: 'smtp_runtime_failed', ERR_METHOD_NOT_IMPLEMENTED: 'smtp_runtime_failed',
    ERR_INVALID_ARG_TYPE: 'smtp_runtime_failed', ERR_INVALID_ARG_VALUE: 'smtp_runtime_failed',
    ERR_INVALID_STATE: 'smtp_runtime_failed', ENOTSUP: 'smtp_runtime_failed', ENOSYS: 'smtp_runtime_failed',
  };
  if (typeof error?.code === 'string' && Object.hasOwn(codes, error.code)) category = codes[error.code];
  // Retain only a fixed command class and a numeric SMTP failure status. Commands
  // can contain mailbox addresses or AUTH credentials, so never persist their text.
  const command = typeof error?.command === 'string' && error.command.length <= 512 ? error.command.trim().toUpperCase() : '';
  const commands = [
    [/^AUTH(?:\s|$)/, 'auth'], [/^MAIL FROM(?:[:\s]|$)/, 'mail_from'], [/^RCPT TO(?:[:\s]|$)/, 'rcpt_to'],
    [/^DATA(?:\s|$)/, 'data'], [/^(?:CONN|EHLO|HELO)(?:\s|$)/, 'connection'],
    [/^STARTTLS(?:\s|$)/, 'tls'], [/^RSET(?:\s|$)/, 'reset'], [/^QUIT(?:\s|$)/, 'quit'],
  ];
  const commandClass = commands.find(([pattern]) => pattern.test(command))?.[1];
  const responseCode = Number.isInteger(error?.responseCode) && error.responseCode >= 400 && error.responseCode <= 599 ? error.responseCode : null;
  return [category, commandClass, responseCode].filter(value => value !== null && value !== undefined).join('_');
}

function verificationError(error) {
  // Shared fixed categories for delivery status and authenticated diagnostics.
  // Never return the original code, message, response, cause or SMTP configuration.
  if (['smtp_timeout', 'ETIMEDOUT', 'ERR_TLS_HANDSHAKE_TIMEOUT'].includes(error?.code) || error?.name === 'AbortError') return 'smtp_timeout';
  if (error?.code === 'EAUTH') return 'smtp_auth_failed';
  if (['ETLS', 'ERR_TLS_CERT_ALTNAME_INVALID', 'DEPTH_ZERO_SELF_SIGNED_CERT', 'SELF_SIGNED_CERT_IN_CHAIN',
    'UNABLE_TO_VERIFY_LEAF_SIGNATURE', 'CERT_HAS_EXPIRED', 'CERT_NOT_YET_VALID', 'UNABLE_TO_GET_ISSUER_CERT',
    'UNABLE_TO_GET_ISSUER_CERT_LOCALLY', 'ERR_SSL_WRONG_VERSION_NUMBER', 'ERR_SSL_TLSV1_ALERT_PROTOCOL_VERSION',
    'ERR_SSL_SSLV3_ALERT_HANDSHAKE_FAILURE', 'ERR_SSL_TLSV1_ALERT_INTERNAL_ERROR'].includes(error?.code)) return 'smtp_tls_failed';
  if (['ESOCKET', 'ECONNECTION', 'EDNS', 'ECONNREFUSED', 'ECONNRESET', 'ECONNABORTED', 'ENOTFOUND',
    'EAI_AGAIN', 'ENETUNREACH', 'EHOSTUNREACH', 'EPIPE'].includes(error?.code)) return 'smtp_network_failed';
  return 'smtp_failed';
}

export function createHandler({ env, fetchImpl = fetch, sendMail, verifySmtp, smtpTimeoutMs = SMTP_TIMEOUT_MS }) {
  // Injection can shorten tests, never extend the production SMTP budget.
  const timeoutMs = Number.isFinite(smtpTimeoutMs) ? Math.max(1, Math.min(SMTP_TIMEOUT_MS, smtpTimeoutMs)) : SMTP_TIMEOUT_MS;
  return async function reviewNotifications(request) {
    const headers = { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' };
    const reply = (status, value) => new Response(JSON.stringify(value), { status, headers });
    try {
      if (request.method !== 'POST') return reply(405, { error: 'post_required' });
      // No browser CORS surface, even if a server key was mistakenly supplied by a browser.
      if (request.headers.has('Origin')) return reply(403, { error: 'server_only' });
      const keys = secretKeys(env);
      const key = await matchingKey(request.headers.get('apikey'), keys);
      if (!key) return reply(401, { error: 'unauthorized' });
      let mode;
      try { mode = await requestMode(request); } catch { return reply(400, { error: 'invalid_request' }); }
      let base;
      try {
        const url = new URL(env('SUPABASE_URL'));
        if (url.protocol !== 'https:' || url.username || url.password || url.search || url.hash || !['', '/'].includes(url.pathname)) throw safeError('configuration');
        base = url.origin;
      } catch { return reply(503, { error: 'service_not_configured' }); }
      if (!env('REVIEW_SMTP_PASSWORD') || typeof sendMail !== 'function' || typeof verifySmtp !== 'function') return reply(503, { error: 'service_not_configured' });
      if (mode === 'verify') {
        try {
          if (await smtpDeadline(signal => verifySmtp({ signal }), timeoutMs) !== true) throw safeError('smtp_failed');
          return reply(200, { state: 'smtp_verified', sent: 0 });
        } catch (error) { return reply(502, { error: 'smtp_verification_failed', reason: verificationError(error), sent: 0 }); }
      }
      const rpcHeaders = { apikey: key, 'Content-Type': 'application/json' };
      if (!key.startsWith('sb_secret_')) rpcHeaders.Authorization = `Bearer ${key}`;
      const rpc = async (name, payload) => {
        const response = await fetchImpl(`${base}/rest/v1/rpc/${name}`, {
          method: 'POST', headers: rpcHeaders, body: JSON.stringify(payload), redirect: 'error', signal: AbortSignal.timeout(5000),
        });
        if (!response.ok) throw safeError('outbox_unavailable');
        return await response.json();
      };
      let items;
      try { items = await rpc('claim_review_notifications', { p_limit: MAX_BATCH }); }
      catch { return reply(502, { error: 'outbox_unavailable' }); }
      const seenIds = new Set();
      const seenSubmissions = new Set();
      if (!Array.isArray(items) || items.length > MAX_BATCH || items.some(item => {
        if (!item || typeof item.id !== 'string' || typeof item.submission_id !== 'string' || typeof item.lease_token !== 'string'
          || !UUID.test(item.id) || !UUID.test(item.submission_id) || !UUID.test(item.lease_token)
          || !Number.isInteger(item.attempts) || item.attempts < 1 || item.attempts > 8
          || seenIds.has(item.id.toLowerCase()) || seenSubmissions.has(item.submission_id.toLowerCase())) return true;
        seenIds.add(item.id.toLowerCase()); seenSubmissions.add(item.submission_id.toLowerCase()); return false;
      })) return reply(502, { error: 'invalid_claim_batch' });
      const counts = { claimed: items.length, sent: 0, retryScheduled: 0, completionUnconfirmed: 0 };
      for (const item of items) {
        let accepted = false;
        let errorCode = null;
        try {
          const message = messageFor(item);
          const result = await smtpDeadline(signal => sendMail(message, { signal }), timeoutMs);
          accepted = Array.isArray(result?.accepted) && result.accepted.some(value => (typeof value === 'string' ? value : value?.address)?.toLowerCase() === RECIPIENT);
          if (!accepted) throw safeError('smtp_rejected');
          counts.sent += 1;
        } catch (error) { errorCode = deliveryError(error); }
        try {
          const completed = await rpc('finish_review_notification', {
            p_id: item.id, p_lease_token: item.lease_token, p_sent: accepted, p_error_code: accepted ? null : errorCode,
          });
          if (completed !== true) throw safeError('completion_unconfirmed');
          if (!accepted) counts.retryScheduled += 1;
        } catch {
          // SMTP may already have accepted the message. Never send again or mark it
          // unsent in this invocation. A later lease retry is at-least-once delivery.
          counts.completionUnconfirmed += 1;
        }
      }
      return reply(counts.completionUnconfirmed ? 502 : 200, { state: counts.completionUnconfirmed ? 'completion_unconfirmed' : 'processed', ...counts });
    } catch {
      // Do not log or echo raw SMTP/PostgREST errors, request bodies, or credentials.
      return reply(502, { error: 'notification_service_unavailable' });
    }
  };
}

// Own the TLS socket so an absolute deadline actually destroys pending or active
// connections. Nodemailer's ordinary transport.close() alone does not do that.
export function createSmtpAdapter({ env, createTransport, connectTls }) {
  const execute = (mode, message, { signal }) => new Promise((resolve, reject) => {
    let socket;
    let transport;
    let settled = false;
    const cleanup = () => {
      signal.removeEventListener('abort', abort);
      try { socket?.destroy(); } catch { /* Cleanup cannot disclose transport details. */ }
      try { transport?.close(); } catch { /* Cleanup cannot disclose transport details. */ }
    };
    const finish = (error, result) => {
      if (settled) return;
      settled = true; cleanup();
      if (error) reject(error); else resolve(result);
    };
    const abort = () => finish(safeError('smtp_timeout'));
    signal.addEventListener('abort', abort, { once: true });
    if (signal.aborted) { abort(); return; }
    try {
      transport = createTransport({
        host: SMTP_HOST, port: 465, secure: true, pool: false,
        auth: { user: SENDER, pass: env('REVIEW_SMTP_PASSWORD') },
        tls: { servername: SMTP_HOST, rejectUnauthorized: true, minVersion: 'TLSv1.2' },
        connectionTimeout: 5000, greetingTimeout: 5000, socketTimeout: 10000, dnsTimeout: 5000,
        logger: false, debug: false, transactionLog: false,
        disableFileAccess: true, disableUrlAccess: true,
        getSocket(_options, callback) {
          if (settled || signal.aborted) { callback(safeError('smtp_timeout')); return; }
          let returned = false;
          const giveSocket = (error, value) => { if (!returned) { returned = true; callback(error, value); } };
          try {
            socket = connectTls({ host: SMTP_HOST, port: 465, servername: SMTP_HOST, rejectUnauthorized: true, minVersion: 'TLSv1.2' });
            socket.once('error', error => { giveSocket(error); finish(error); });
            socket.once('secureConnect', () => {
              if (settled || signal.aborted) { socket.destroy(); giveSocket(safeError('smtp_timeout')); return; }
              giveSocket(null, { connection: socket, secured: true });
            });
            // A timeout can fire between getSocket scheduling and its connector.
            if (settled || signal.aborted) { socket.destroy(); giveSocket(safeError('smtp_timeout')); }
          } catch (error) { giveSocket(error); finish(error); }
        },
      });
      const result = mode === 'verify' ? transport.verify() : transport.sendMail(message);
      Promise.resolve(result).then(value => finish(null, value), error => finish(error));
    } catch (error) { finish(error); }
  });
  return {
    sendMail: (message, options) => execute('deliver', message, options),
    verifySmtp: options => execute('verify', null, options),
  };
}

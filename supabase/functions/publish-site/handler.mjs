// The browser never receives the repository credential and cannot choose a ref.
const REPOSITORY = 'jojolee0731/tian-lab-site';
const WORKFLOW = 'publish-members.yml';
const REF = 'main';

export function createHandler({ env, fetchImpl = fetch }) {
  const allowedOrigins = (env('PORTAL_ALLOWED_ORIGINS') || 'https://jojolee0731.github.io')
    .split(',').map(value => value.trim()).filter(Boolean);
  return async function publishSite(request) {
    const origin = request.headers.get('Origin');
    const headers = { 'Content-Type': 'application/json', 'Cache-Control': 'no-store', 'Vary': 'Origin' };
    const reply = (status, body) => new Response(JSON.stringify(body), { status, headers });
    if (origin && !allowedOrigins.includes(origin)) return reply(403, { error: 'Origin is not allowed.' });
    if (origin) headers['Access-Control-Allow-Origin'] = origin;
    headers['Access-Control-Allow-Headers'] = 'authorization, x-client-info, apikey, content-type';
    headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS';
    if (request.method === 'OPTIONS') return new Response(null, { status: 204, headers });
    if (request.method !== 'POST') return reply(405, { error: 'Use POST.' });
    const authorization = request.headers.get('Authorization') || '';
    if (!/^Bearer [A-Za-z0-9._-]{20,8192}$/.test(authorization)) return reply(401, { error: 'An authenticated user session is required.' });
    const base = env('SUPABASE_URL') || '';
    let publicKey = '';
    try {
      const named = JSON.parse(env('SUPABASE_PUBLISHABLE_KEYS') || '{}');
      const isPublishable = value => typeof value === 'string' && /^sb_publishable_[A-Za-z0-9_-]+$/.test(value);
      publicKey = isPublishable(named?.default) ? named.default : Object.values(named || {}).find(isPublishable) || '';
    } catch { /* Missing or malformed new-key configuration falls back to legacy. */ }
    publicKey = publicKey || env('SUPABASE_ANON_KEY') || '';
    try {
      const parsed = new URL(base);
      if (parsed.protocol !== 'https:' || parsed.username || parsed.password || parsed.search || parsed.hash || !['', '/'].includes(parsed.pathname)) throw new Error();
    } catch {
      return reply(503, { error: 'The publishing service is not configured.' });
    }
    if (!publicKey) return reply(503, { error: 'The publishing service is not configured.' });
    const originUrl = base.replace(/\/$/, '');
    const authHeaders = { apikey: publicKey, Authorization: authorization };
    try {
      // Verify the JWT with Auth, even when the Edge gateway's JWT check changes.
      const verified = await fetchImpl(`${originUrl}/auth/v1/user`, {
        headers: authHeaders, redirect: 'error', signal: AbortSignal.timeout(15000),
      });
      if (!verified.ok) return reply(401, { error: 'Your session is invalid or expired.' });
      const user = await verified.json();
      if (!user || typeof user.id !== 'string' || !user.id) return reply(401, { error: 'Your session is invalid or expired.' });
      // portal_self checks the current verified email, invitation and enabled flag.
      // Do not trust role/member IDs supplied in request bodies or token metadata.
      const access = await fetchImpl(`${originUrl}/rest/v1/rpc/portal_self`, {
        method: 'POST', headers: { ...authHeaders, 'Content-Type': 'application/json' },
        body: '{}', redirect: 'error', signal: AbortSignal.timeout(15000),
      });
      if (!access.ok) return reply(403, { error: 'An active administrator account is required.' });
      const self = await access.json();
      if (self?.account?.role !== 'admin' || self.account.enabled === false) return reply(403, { error: 'An active administrator account is required.' });
      const token = env('GITHUB_PUBLISH_TOKEN');
      if (!token) return reply(503, { error: 'GitHub publishing is not activated. Approval remains saved.' });
      const dispatched = await fetchImpl(`https://api.github.com/repos/${REPOSITORY}/actions/workflows/${WORKFLOW}/dispatches`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, Accept: 'application/vnd.github+json', 'Content-Type': 'application/json', 'X-GitHub-Api-Version': '2022-11-28' },
        body: JSON.stringify({ ref: REF }), redirect: 'error', signal: AbortSignal.timeout(15000),
      });
      if (dispatched.status !== 204) return reply(502, { error: 'Publishing could not be queued. Approval remains saved; the live site is unchanged.' });
      return reply(202, {
        state: 'queued', workflow: WORKFLOW,
        message: 'Publication has been queued. The public website changes only after the build and checks succeed.',
        runsUrl: `https://github.com/${REPOSITORY}/actions/workflows/${WORKFLOW}`,
      });
    } catch {
      // Never forward Auth/GitHub response bodies, tokens or private profile data.
      return reply(502, { error: 'Publishing service unavailable. Approval remains saved; publication is not confirmed.' });
    }
  };
}

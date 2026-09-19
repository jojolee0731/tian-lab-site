# Member portal implementation contract

Existing public website remains static; private drafts and image originals live in Supabase. Never seed fabricated member research. The current roster contains 34 members and generates 102 personal pages plus 21 main pages. Registry membership does not grant portal access; initial access is administrator-only, with no bulk member invitations. As of 2026-09-19, all 3 cloud migrations and the signup allowlist Hook are configured, QQ SMTP and both OTP templates are saved, and the user has confirmed receiving/copying the email code. Local portal configuration is enabled; successful administrator login and the full review/publication flow remain unverified. See [操作说明](member-portal-guide.md).

The dedicated single-repository GitHub Actions token is stored in the Supabase Edge Secret, and Supabase URL/secret values are stored in GitHub Actions secrets. The GitHub token expires on **2027-09-19** and must be replaced in the Edge Secret before expiry. Secret values are never part of this contract.

## Public JSON
`data/member-profiles.json`: `{ "schemaVersion": 1, "profiles": { "member-15": { "version": "submission uuid", "publishedAt": "ISO timestamp with timezone", "content": <payload> } } }`. Initially profiles is empty; all current roster members still get standalone public pages using verified existing data. Public page path: `person-member-15.html` in each language directory. Team anchors remain compatible. `publishedAt` records backend approval/restore time, not successful website deployment time; the public `version` is the submission UUID used to compare the live website with the reviewed snapshot.

## Editable payload (plain text, no HTML)
`bio`, `bio_en`, `interests`, `interests_en`, `education`, `education_en`, `public_email`, `avatar_path` (private storage path or empty), `links`: [{label,url}], `projects`: [{id,title,title_en,question,question_en,approach,approach_en,contribution,contribution_en,progress,progress_en,image_path,image_caption,image_caption_en,image_source}], `papers`: [{doi,title,authors,journal,year,context,contribution,contribution_en}]. Chinese text primary; English optional; Spanish public UI can use supplied English else original Chinese tagged appropriately. `context` = in_lab | before_lab.

Limits: 3 projects, 30 papers, 5 links; long text 3000 characters; project titles/link labels 200; paper title 1000, journal 200, authors 2000, DOI 255. The database additionally limits a payload to 512 KiB and requires unique project IDs. DOI identifiers reject whitespace, query/fragment delimiters, backslashes, single/double quotes and angle brackets; save normalizes DOI case. The browser can normalize a DOI URL before submission. Crossref lookup fills an editable draft only; authorship and contribution still need review. Personal papers do not automatically enter the lab publication catalog or featured selection. The current editor accepts HTTPS academic links and a separate public-email field; the backend/public renderer also validates plain `mailto:` links without query/fragment parameters.

Images are JPEG/PNG/WebP up to 5 MiB. A project image requires at least one of `image_caption` / `image_caption_en` plus a nonempty `image_source`. Export verifies actual format, rejects animation and oversized dimensions (20 million pixels or a dimension above 10,000), fully decodes and re-encodes raster pixels without embedded metadata, and verifies the output size again.

## Browser API RPCs (authenticated)
- `portal_self()` -> `{account:{role,member_id,email}, member:<people.json item|null>, draft:{payload,revision}, published:<approved payload|null>, submission:<latest own submission|null>}`. Reject uninvited, disabled, unverified and inactive-registry accounts using the current confirmed Auth email. `submission` includes status and review note. Admin may have null member_id.
- `save_profile(p_payload, p_expected_revision)` -> `{payload,revision}` (owner only)
- `submit_profile(p_expected_revision)` -> submission object with `id,member_id,payload,status,created_at`; immutable snapshot.
- `list_submissions()` -> admin-only array of submissions including member name, payload, status, review note, created_at and `published` marker. This marker identifies the backend's selected approved snapshot, not the live website.
- `review_submission(p_submission_id,p_decision,p_note)` -> submission; decisions approve | reject. Approval copies immutable snapshot into approved publication table and increments release version. No member can approve.
- `restore_publication(p_submission_id)` -> approve a previously approved snapshot for same member, preserving history.
- `list_member_access()` -> admin array with email, member_id, member_name, role, enabled, invited and active; includes uninvited active registry rows with null email/role.
- `set_member_access(p_email,p_member_id,p_role,p_enabled)` -> access record. Admin only, protect last admin/current admin from lockout. role member|admin. This updates the allowlist only; it does not create an Auth user or send an invitation email.
- `export_public_profiles()` -> `{schemaVersion:1,profiles:{...}}` service_role only; approved content only. No reviewer/account emails in public output.

## Storage
Bucket `member-drafts`, private, immutable uploads at `${member_id}/${uuid}.${jpg|png|webp}`. Authenticated owner or admin can read; own member can insert; no overwrite/delete. Validate path in server schema on save/submit, and actual raster image bytes during public export. Exporter maps approved image paths to `assets/images/member-projects/<member-id>/<uuid>.<ext>`; JSON public payload replaces paths with local public asset paths. Existing identity fields/roles edited only through existing admin source process.

## Config
`members/config.json` currently has the configured project URL/public publishable key and `enabled: true`. Only public anon/publishable keys belong here; never secrets. An unconfigured portal clearly states that it is not activated. The frontend uses the vendored official Supabase JS 2.116.0 bundle. Auth tokens use sessionStorage; research drafts are saved through the backend RPC, not simulated local saves. Browser login requests an email OTP and then verifies it before loading portal data. Auth signup/email verification alone does not grant portal permission.

## Publishing
Admin invokes Supabase Edge Function `publish-site` with a user JWT. The function verifies the user with Auth and checks the live admin permission using `portal_self()` before dispatching the fixed `jojolee0731/tian-lab-site` repository, `publish-members.yml` workflow and `main` ref. The browser cannot choose these targets. PAT is the server secret `GITHUB_PUBLISH_TOKEN`, scoped only to target-repository Actions write. The function uses Supabase's public key for user verification, not a service key. Its default allowed origin is `https://jojolee0731.github.io`; use `PORTAL_ALLOWED_ORIGINS` only when adding confirmed origins.

On `workflow_dispatch`, the workflow fetches only approved data using Actions secrets `SUPABASE_URL` and preferably `SUPABASE_SECRET_KEY` (`sb_secret_…`); legacy `SUPABASE_SERVICE_ROLE_KEY` is a fallback. Modern secret keys use `apikey`, not Bearer JWT authorization. After downloading approved images privately, the workflow validates, builds, checks and commits only the explicit public catalog/assets/generated pages/sitemap allowlist. The Pages artifact is separately restricted to public static files and checked for missing dependencies and known server credentials. Private SQL, drafts, server sources and configuration secrets are not website artifacts. No automatic commit includes `members/config.json`.

Normal `main` pushes also build, check and deploy the public static artifact, but do not pull private backend data. Concurrency serializes publication runs; Pages must be configured for GitHub Actions. A failed export/build/check/push prevents deployment. Backend approval, a queued workflow, a successful Git commit and a successful live website update are distinct events. An approved snapshot may remain saved even if deployment fails; confirm both the Pages deployment result and the public profile version before reporting publication. Restore likewise requires another publication run.

## Team ownership
- Root: members editor HTML/CSS/JS, integration, config, browser QA, activation.
- people_data: scripts/build_site.py, standalone pages, public profile CSS separate file, sitemap, data/member-profiles.json; public page content validation module if needed. Do not edit root styles.css/script.js.
- publication_data: supabase/migrations, backend RPC/storage security and SQL tests; seed script SQL source generation, backend README.
- structural_qa: scripts/export_member_profiles.py, publish Edge Function, GitHub publish workflow, existing checker extension + targeted tests. Do not alter build_site.py.

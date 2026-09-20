# Private member portal backend

Implemented by `supabase/migrations/202609190001_member_portal.sql`, `202609190002_signup_allowlist.sql`, and `202609190003_encoded_email_controls.sql`. This document describes actual SQL behavior and activation steps; SQL installation and verified Auth Hook activation are separate states.

Current status (2026-09-20): real administrator OTP login is verified. All 34 current members were enabled through the live administrator UI; a reload confirmed each registered email maps to its own member ID, with enabled access. Following explicit user authorization, one assigned member was promoted to `admin`; the original independent administrator remains enabled. A fresh reload verified 33 ordinary members and 2 administrators, for 35 access records. The allowlist update created no Auth users and sent no invitation emails. The administrator clicked the actual publish button, which called Edge and triggered [run 35478645703](https://github.com/jojolee0731/tian-lab-site/actions/runs/35478645703); build and deploy both succeeded. The approved public profile catalog remains empty.

All 3 cloud migrations succeeded, the signup Hook is enabled, QQ SMTP and both `{{ .Token }}` templates are saved, and live portal configuration is `enabled: true`. Real member first login, draft save, upload, submit/review and nonempty publication still need verification during member use. Local fixture/SQL tests are not evidence that those cloud user flows passed. See the concise [member/admin guide](member-portal-guide.md).

Historical evidence (2026-09-19): the [first main push](https://github.com/jojolee0731/tian-lab-site/actions/runs/35452195446) and [direct PAT dispatch](https://github.com/jojolee0731/tian-lab-site/actions/runs/35452251756) succeeded with Pages `build_type: workflow`. The latter exported the real approved catalog, guarded and committed the public diff, and deployed Pages. Bot commit `ae2838b9d9f3efc681026d3feb3d5cbf8c0da273` only normalized the empty `data/member-profiles.json`.

Deployment evidence: application commit `6089557`; workflow initialization commit `55a842fb69770a5046e8ade6a775c59c351e0279`. Live HTTP/browser checks confirmed member-35 as “高级实验师 · 药理学博士”, member-31 as “博士后”, the agreed four role categories for student/postdoc records, and successful Logo loading. Direct requests for the backend document and migration files returned 404, consistent with the Pages artifact allowlist.

The dedicated single-repository GitHub Actions token is saved as the Supabase Edge Secret `GITHUB_PUBLISH_TOKEN`; GitHub Actions secrets contain `SUPABASE_URL` and `SUPABASE_SECRET_KEY`. The GitHub token expires on **2027-09-19** and must be replaced in the Edge Secret before expiry. No credential value is recorded here.

## Data separation

The `member_portal` schema is not a public content source. Registry, invitations, drafts, submission snapshots, review decisions, publication pointers and publication history all have RLS enabled and no direct table grants to anonymous or authenticated browser roles. RPCs run with a fixed empty search path and fully qualified application table/function references. Helper functions are not executable by browser users except the two boolean Storage policy checks.

`portal_self()` identifies an account using `auth.uid()` joined to the **current verified email in `auth.users`** and a currently enabled invitation. It does not trust editable user metadata, submitted member IDs, or a JWT email that may be stale. Uninvited, unverified, disabled and inactive-registry accounts are refused. No account is created or invited merely because it appears in `people.json`.

The response includes `account`, `member`, `draft`, `published`, and `submission`. `submission` is the latest submitted revision belonging to the current member, or null; it contains `status` (`submitted`, `approved`, or `rejected`) and `review_note`, so members can see their own feedback. An administrator without a member assignment receives null here and uses the separate admin-only review queue. `list_member_access()` returns an array with `email`, `member_id`, `member_name`, `role`, `enabled`, `invited`, and `active`; uninvited registry rows have null email/role.

`save_profile()` and `submit_profile()` accept no member ID. The target is taken from the verified live invitation. A registry row lock serializes operations for one member and an expected revision rejects stale saves/submissions with SQLSTATE40001. Members can edit only their assigned profile; administrators without a member assignment can review/manage access but cannot use the draft-save RPC to edit arbitrary members.

Submission payloads are append-only snapshots. Review decisions live in a separate append-only table. Approval updates a current-publication pointer to the original snapshot and increments a release counter. Subsequent draft edits cannot change a submission or published payload. Restore only accepts a previously approved snapshot and appends an immutable history event. Restoring history does not rewrite past reviews. Submitting an unchanged revision twice is refused.

`set_member_access()` is admin-only and serialized by a table lock. It prevents the current administrator from disabling/demoting itself and refuses removal of the last enabled administrator. One enabled account may be assigned to a member at a time. Access management updates the allowlist; it does **not** create an Auth user or send invitation email.

`export_public_profiles()` grants EXECUTE only to `service_role`; anonymous and authenticated roles cannot call it. It exports only currently approved snapshots for active registry members:

```json
{"schemaVersion":1,"profiles":{"member-01":{"version":"submission-uuid","publishedAt":"approval-time","content":{}}}}
```

No invitation email, reviewer identity, review note or draft is included. `content.public_email` is an explicitly editable public contact field and may legitimately appear. `publishedAt` is the backend approval/restore timestamp; it does not prove the static website has deployed. Backend approval and successful website publication remain separate operations.

## Payload and image validation

SQL enforces allowed object keys, JSON types, aggregate size512KiB, long-text length3000, project title/label/journal length200, paper title1000, authors2000, DOI255, maximum3 projects/30 papers/5 links, unique project IDs, allowed paper context (`in_lab` or `before_lab`), DOI syntax, public-email syntax and HTTPS/mailto links. DOI values reject query/fragment delimiters, backslashes, quotes, whitespace and angle brackets, and save normalizes them to lowercase. HTML tags and unsupported control characters are rejected; text still must be escaped by the public renderer. Numeric or string years1800–2099 are accepted. Unrecognized fields cannot smuggle a member ID, role or reviewer flag. Project images require a nonempty Chinese or English caption and an image-source description before saving/submitting. English text remains optional.

Migration003 aligns public-email and mailto validation with the export pipeline: all percent-encoded control bytes `%00`–`%1f` and `%7f` are rejected case-insensitively. Ordinary percent characters remain allowed where email syntax permits them. The original001 migration is preserved;003 replaces only the two relevant regexes in `member_portal.validate_payload`.

Avatar/project image references must match the current member’s path and an existing Storage object. Empty image references are allowed. The private `member-drafts` bucket accepts JPEG/PNG/WebP and is configured for5MiB maximum uploads:

```
member-01/01234567-89ab-cdef-0123-456789abcdef.jpg
```

Authenticated owners may insert their own UUID-named objects. Owners and live admins may read them. No browser update/delete is permitted. Restrictive policies also block a broad unrelated permissive Storage policy from accidentally exposing this bucket. Service credentials inherently bypass RLS and must remain server-only; application publishing uses them only to export/read approved data.

Bucket MIME declarations and database paths cannot authenticate image bytes. The publication exporter must decode/verify approved raster files, check size and map them into public assets. That boundary is implemented/tested separately in `scripts/export_member_profiles.py`. A browser should never mark an upload public or use an overwrite/upsert option.

## Activate with the actual administrator

1. Apply the migration to the chosen Supabase project using the normal migration workflow. Confirm the private bucket exists and no public bucket/policy has been substituted.
2. Generate private registry/bootstrap SQL **outside the public Git worktree**:

```sh
python3 scripts/seed_member_portal.py --admin-email 'ACTUAL_CONFIRMED_ADMIN_EMAIL' --output '/absolute/private/path/member-bootstrap.sql'
```

The administrator email is a required explicit parameter for bootstrap; there is no hardcoded email/default. The output is mode0600, is not executed automatically, and contains no fabricated biographies or projects. The script refuses an output path inside the public worktree. It does not send email. Execute the private SQL as the database owner, then retain it only in an appropriate private location or remove it after activation. Never commit it, print its contents into public logs, or publish it as a website file.

If an enabled admin already exists, one-time bootstrap refuses to replace it. Subsequent access invitations use the authenticated admin RPC. Registry-only updates omit `--admin-email`; they update current source identity fields and mark absent roster IDs inactive without deleting prior review history.

3. Configure Supabase Auth for email OTP sign-in and the exact allowed site/redirect URLs. QQ SMTP and both Token templates are saved, and real administrator sign-in succeeded on 2026-09-20. All 34 current members have explicit enabled allowlist entries; members request their own login codes. Keep the SMTP authorization code in service configuration only. Only a confirmed Auth email matching the live allowlist gains portal access; future public roster changes do not authorize access automatically.
4. Put only the public project URL and anon/publishable key into `members/config.json`. Never put service-role keys or GitHub tokens there.
   For the publishing workflow, store `SUPABASE_URL` and the recommended modern `SUPABASE_SECRET_KEY` (`sb_secret_…`) in GitHub Actions secrets. The exporter sends a modern key in the `apikey` header; it is not a Bearer JWT. The legacy `SUPABASE_SERVICE_ROLE_KEY` remains a supported fallback using its JWT headers. Both elevated key types resolve to the database `service_role` role, so the SQL export permission is unchanged. The Edge function separately verifies the administrator's own Auth JWT using a publishable key before dispatching; an API key alone never grants a browser administrator access.
5. During real member use, verify first login, draft save, image upload, submit/review, cross-member rejection and publication of a nonempty approved snapshot. Administrator login and the actual authenticated Edge publish button are already verified; these do not replace member data-flow checks.

`supabase/functions/publish-site` is deployed, its server-only `GITHUB_PUBLISH_TOKEN` is set, and GitHub Pages uses the checked Actions artifact. Direct PAT dispatch and the real administrator-button-to-Edge call have both completed successful deployments. The latter is recorded in run 35478645703, with an empty approved catalog. The function re-verifies the user JWT and live admin invitation; an `approved` database row or a `202 queued` response alone is not a deployment receipt. Confirm the workflow result and public profile version for each future member-content release.

## Reproducible real-PostgreSQL tests

```sh
python3 supabase/tests/run_local_sql.py --pg-bin /path/to/postgresql/bin
```

The runner creates a temporary native PostgreSQL cluster, listens on a private Unix socket only, applies the migration and runs `permissions.sql`. It stops the server and deletes the test cluster in `finally`. It creates no operating-system service. `fixture.sql` supplies minimal `auth.users`, `auth.uid()`, Storage tables and Supabase role names; it must never be applied to a real Supabase project.

The 2026-09-19 combined run passed 159 assertions on native PostgreSQL16.15. Tests execute as real database roles, not a mocked JavaScript RLS layer. Covered behavior includes unauthorized/disabled/unverified sessions, account-bound edits, stale revisions, immutable submissions/reviews, unauthorized approval/export/table reads, own review feedback, path and field validation, private uploads, overwrite/delete resistance even in the presence of broad Storage policies, approval export versus newer private drafts, restore history/version increments, signup allowlist checks, encoded email controls, and removal of inactive members from export.

This is an actual PostgreSQL RPC/privilege/RLS execution result. It does **not** verify hosted user sessions, real member Storage uploads or the member review workflow. Separate cloud evidence confirms email receipt, code deployment and direct PAT dispatch; the remaining user-flow checks are listed above.

## Live read-only check and invitation-only signup gate

On 2026-09-19, live REST requests using the privately stored project keys confirmed:

- Anonymous `portal_self`, `list_submissions`, `list_member_access`, and `export_public_profiles` returned HTTP401 / SQLSTATE42501.
- Anonymous attempts to read accounts/drafts through the default schema returned 404 / PGRST205; choosing the private schema returned406 / PGRST106 (not exposed).
- The service-role approved export returned HTTP200 with exactly `{"schemaVersion":1,"profiles":{}}`.
- Anonymous listing of the private bucket returned an empty array. With no test objects/users created, this is only a no-disclosure observation; live cross-member Storage access still needs an invited-user integration test.
- Public Auth settings reported `disable_signup:false`, `mailer_autoconfirm:false`, and email authentication enabled. No signup, OTP, invitation, user-creation or mutation request was made.

The portal's live allowlist blocks data access after authentication; it does not by itself prevent a new, uninvited address from reaching Auth's signup/email flow. The approved Before User Created hook is the formal migration `supabase/migrations/202609190002_signup_allowlist.sql`. On 2026-09-19 the main activation task confirmed that002 and003 each completed in the cloud with `Success. No rows returned`, and visually verified the Before User Created hook as **ENABLED**, selecting `public.portal_before_user_created`. SQL deployment and Hook UI activation are therefore verified. **A hosted registration-flow verification remains outstanding**; the UI observation does not prove a real signup was intercepted.

QQ SMTP and both Confirm Signup/Magic Link templates using `{{ .Token }}` are saved. Email receipt was confirmed on 2026-09-19; real administrator OTP login was separately completed on 2026-09-20. No SMTP password, authorization code or login code is stored in this document.

The hook allows only a normalized exact email in an enabled invitation, with an active registry member when assigned. It accepts the explicit administrator entry without a member assignment and rejects anonymous/malformed events. It returns a generic403 for denial, does not confirm email or grant portal roles, and retains `portal_self`'s live checks. It uses invoker privileges; only `supabase_auth_admin` receives the column-level allowlist/registry reads and RLS policies needed for the check. Browser roles cannot execute the hook or query the allowlist through it.

After SQL deployment, activation requires separately selecting `public.portal_before_user_created` in Authentication → Hooks → Before User Created (URI `pg-functions://postgres/public/portal_before_user_created`). Keep email confirmation enabled. Add new invitations through the administrator flow **before** the invited person signs in for the first time. Until this hook or an equivalent server signup restriction is active, do not describe the UI's invitation-only statement as a pre-email signup gate.

This hook prevents uninvited **new-account creation**. It does not control every email request involving an already existing Auth account, so retain Auth email/IP rate limits and use CAPTCHA if unwanted requests appear. Closing all signups and pre-creating each Auth user is an alternative, but changes the current administrator allowlist-only onboarding flow and should not be substituted silently. Do not add an anonymous browser allowlist RPC; it would expose membership enumeration and remain bypassable by calling Auth directly.

The local suite includes all 3 migrations and runs without cloud access:

```sh
python3 supabase/tests/run_local_sql.py
```

After adding003, the combined suite passed 159 assertions on native PostgreSQL16.15: the original 80, 13 hook assertions, and 66 encoded-control checks. The unchanged local result is retained; no tests were repeated for this documentation update. Separate cloud evidence now confirms administrator OTP login, all 34 member allowlist mappings and the authenticated Edge publish button through successful deployment. Real member first login, draft/upload/submit/review, cross-member access and nonempty content publication remain to be verified during use.

## Official technical references

- [Supabase Database Functions](https://supabase.com/docs/guides/database/functions): security-definer search-path discipline and explicit function privileges.
- [Supabase Row Level Security](https://supabase.com/docs/guides/database/postgres/row-level-security): role-based access and service-key boundaries.
- [Supabase Storage Access Control](https://supabase.com/docs/guides/storage/security/access-control): Storage authorization through `storage.objects` RLS.
- [Supabase API Keys](https://supabase.com/docs/guides/getting-started/api-keys): modern publishable/secret keys and their database roles; modern keys are not JWTs.
- [Before User Created Hook](https://supabase.com/docs/guides/auth/auth-hooks/before-user-created-hook): reject new-account creation with a server-side signup rule.
- [Auth Hooks security model](https://supabase.com/docs/guides/auth/auth-hooks): dedicated Auth role grants and invoker-function guidance.
- [General Auth configuration](https://supabase.com/docs/guides/auth/general-configuration): signup and email-confirmation settings.

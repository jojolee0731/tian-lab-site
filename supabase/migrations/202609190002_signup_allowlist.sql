-- Invitation-only registration gate. SQL installation does not activate Auth Hooks.
-- Explicitly select this function under Before User Created after deployment.
-- Ref: https://supabase.com/docs/guides/auth/auth-hooks/before-user-created-hook
-- Invoker privileges keep the hook limited to allowlist checks.
grant usage on schema public, member_portal to supabase_auth_admin;
grant select(email,member_id,enabled) on member_portal.accounts to supabase_auth_admin;
grant select(member_id,active) on member_portal.registry to supabase_auth_admin;
create policy portal_auth_signup_accounts on member_portal.accounts
 for select to supabase_auth_admin using (true);
create policy portal_auth_signup_registry on member_portal.registry
 for select to supabase_auth_admin using (true);

create function public.portal_before_user_created(event jsonb)
returns jsonb language plpgsql security invoker set search_path='' as $$
declare requested_email text;
begin
 if jsonb_typeof(event->'user'->'email')='string'
 and coalesce(event->'user'->>'is_anonymous','false')<>'true' then
  requested_email:=lower(btrim(event->'user'->>'email'));
  if exists(
   select 1 from member_portal.accounts a
   where a.email=requested_email and a.enabled
   and (a.member_id is null or exists(
    select 1 from member_portal.registry r where r.member_id=a.member_id and r.active
   ))
  ) then return '{}'::jsonb; end if;
 end if;
 return jsonb_build_object('error',jsonb_build_object(
  'http_code',403,'message','Registration is available only to invited members.'
 ));
end $$;
revoke all on function public.portal_before_user_created(jsonb) from public,anon,authenticated,service_role;
grant execute on function public.portal_before_user_created(jsonb) to supabase_auth_admin;

-- Activation is separate: Authentication > Hooks > Before User Created.
-- URI: pg-functions://postgres/public/portal_before_user_created
-- Keep email confirmation enabled. This hook does not confirm email, assign roles,
-- create accounts, send mail, or replace live account checks in portal_self().

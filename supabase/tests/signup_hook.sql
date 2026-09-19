\set ON_ERROR_STOP on
begin;
create function public.test_assert(ok boolean,label text) returns void language plpgsql as $$begin if not coalesce(ok,false) then raise exception 'ASSERTION FAILED: %',label; end if; raise notice 'PASS %',label; end$$;
create function public.test_denied(query text,expected_state text,label text) returns void language plpgsql as $$
declare got text;
begin
 begin execute query; exception when others then get stacked diagnostics got=returned_sqlstate; end;
 if got is distinct from expected_state then raise exception 'ASSERTION FAILED: %, expected %, got %',label,expected_state,coalesce(got,'success'); end if;
 raise notice 'PASS % [%]',label,got;
end$$;
insert into member_portal.registry(member_id,member,active) values
 ('member-hook-active','{}',true),('member-hook-disabled','{}',true),('member-hook-inactive','{}',false);
insert into member_portal.accounts(email,member_id,role,enabled) values
 ('allowed@example.test','member-hook-active','member',true),
 ('disabled@example.test','member-hook-disabled','member',false),
 ('inactive@example.test','member-hook-inactive','member',true),
 ('admin@example.test',null,'admin',true);
set role supabase_auth_admin;
select public.test_assert(public.portal_before_user_created('{"user":{"email":"Allowed@EXAMPLE.test"}}')='{}'::jsonb,'hook permits exact invited member with case normalization');
select public.test_assert(public.portal_before_user_created('{"user":{"email":"admin@example.test"}}')='{}'::jsonb,'hook permits explicit admin without member assignment');
select public.test_assert(public.portal_before_user_created('{"user":{"email":"unknown@example.test"}}')->'error'->>'http_code'='403','hook rejects uninvited email');
select public.test_assert(public.portal_before_user_created('{"user":{"email":"disabled@example.test"}}')->'error'->>'http_code'='403','hook rejects disabled invitation');
select public.test_assert(public.portal_before_user_created('{"user":{"email":"inactive@example.test"}}')->'error'->>'http_code'='403','hook rejects inactive registry');
select public.test_assert(public.portal_before_user_created('{"user":{"email":"allowed@example.test","is_anonymous":true}}')->'error'->>'http_code'='403','hook rejects anonymous identity');
select public.test_assert(public.portal_before_user_created('{}')->'error'->>'http_code'='403','hook fails closed on missing email');
select public.test_assert(public.portal_before_user_created('{"user":{"email":["allowed@example.test"]}}')->'error'->>'http_code'='403','hook fails closed on malformed email');
select public.test_denied('select * from member_portal.accounts','42501','hook role cannot read non-granted account columns');
select public.test_denied('update member_portal.accounts set enabled=true','42501','hook role has no account mutation grant');
select public.test_denied('select * from member_portal.drafts','42501','hook role cannot read member drafts');
set role anon;
select public.test_denied($q$select public.portal_before_user_created('{"user":{"email":"allowed@example.test"}}')$q$,'42501','anonymous cannot query signup allowlist hook');
set role authenticated;
select public.test_denied($q$select public.portal_before_user_created('{"user":{"email":"allowed@example.test"}}')$q$,'42501','members cannot query signup allowlist hook');
reset role;
rollback;

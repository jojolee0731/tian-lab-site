-- Private member drafts. Public access is through these explicitly granted RPCs only.
begin;
create schema if not exists member_portal;
revoke all on schema member_portal from public, anon, authenticated;
create table member_portal.registry (
  member_id text primary key check (member_id ~ '^member-[a-z0-9-]{1,50}$'),
  member jsonb not null check (jsonb_typeof(member) = 'object'),
  active boolean not null default true
);
create table member_portal.accounts (
  email text primary key check (email = lower(btrim(email)) and length(email) <= 254 and email ~ '^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$'),
  member_id text references member_portal.registry(member_id),
  role text not null check (role in ('member','admin')),
  enabled boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (role = 'admin' or member_id is not null)
);
create unique index accounts_one_active_member on member_portal.accounts(member_id) where enabled and member_id is not null;
create table member_portal.drafts (
 member_id text primary key references member_portal.registry(member_id),
 payload jsonb not null default '{}'::jsonb,
 revision bigint not null default 0 check (revision >= 0),
 updated_at timestamptz not null default now()
);
create table member_portal.submissions (
 id uuid primary key default gen_random_uuid(),
 member_id text not null references member_portal.registry(member_id),
 payload jsonb not null,
 revision bigint not null,
 created_at timestamptz not null default now(),
 submitted_by uuid not null,
 unique(member_id,revision)
);
create table member_portal.reviews (
 submission_id uuid primary key references member_portal.submissions(id),
 decision text not null check (decision in ('approve','reject')),
 note text not null default '',
 reviewer uuid not null,
 created_at timestamptz not null default now()
);
create table member_portal.release_state (
 singleton boolean primary key default true check(singleton),
 version bigint not null default 0
);
insert into member_portal.release_state(singleton,version) values(true,0);
create table member_portal.publications (
 member_id text primary key references member_portal.registry(member_id),
 submission_id uuid not null references member_portal.submissions(id),
 approved_at timestamptz not null default now(),
 release_version bigint not null
);
create table member_portal.publication_history (
 id bigint generated always as identity primary key,
 member_id text not null references member_portal.registry(member_id),
 submission_id uuid not null references member_portal.submissions(id),
 action text not null check (action in ('approve','restore')),
 actor uuid not null,
 created_at timestamptz not null default now(),
 release_version bigint not null unique
);
alter table member_portal.registry enable row level security;
alter table member_portal.accounts enable row level security;
alter table member_portal.drafts enable row level security;
alter table member_portal.submissions enable row level security;
alter table member_portal.reviews enable row level security;
alter table member_portal.release_state enable row level security;
alter table member_portal.publications enable row level security;
alter table member_portal.publication_history enable row level security;
revoke all on all tables in schema member_portal from public,anon,authenticated;
revoke all on all sequences in schema member_portal from public,anon,authenticated;

create function member_portal.immutable_row() returns trigger language plpgsql set search_path='' as $$
begin raise exception using errcode='42501',message='immutable_snapshot'; end $$;
create trigger submissions_immutable before update or delete on member_portal.submissions for each row execute function member_portal.immutable_row();
create trigger reviews_immutable before update or delete on member_portal.reviews for each row execute function member_portal.immutable_row();
create trigger history_immutable before update or delete on member_portal.publication_history for each row execute function member_portal.immutable_row();

-- Email is taken from the current verified auth.users row, not an editable profile or stale JWT email.
create function member_portal.actor() returns member_portal.accounts
language plpgsql security definer set search_path='' as $$
declare a member_portal.accounts;
begin
 if auth.uid() is null then raise exception using errcode='42501',message='authentication_required'; end if;
 select p.* into a from member_portal.accounts p join auth.users u on lower(u.email)=p.email
 where u.id=auth.uid() and u.email_confirmed_at is not null and p.enabled
 and (p.member_id is null or exists(select 1 from member_portal.registry r where r.member_id=p.member_id and r.active));
 if not found then raise exception using errcode='42501',message='invitation_required_or_disabled'; end if;
 return a;
end $$;
create function member_portal.require_admin() returns member_portal.accounts
language plpgsql security definer set search_path='' as $$
declare a member_portal.accounts;
begin a:=member_portal.actor(); if a.role<>'admin' then raise exception using errcode='42501',message='admin_required'; end if; return a; end $$;
create function member_portal.require_owner() returns text
language plpgsql security definer set search_path='' as $$
declare a member_portal.accounts;
begin a:=member_portal.actor(); if a.member_id is null then raise exception using errcode='42501',message='member_profile_required'; end if; return a.member_id; end $$;

create function member_portal.check_text(v jsonb, max_chars integer, field_name text) returns void
language plpgsql set search_path='' as $$
declare t text;
begin
 if v is null then return; end if;
 if jsonb_typeof(v)<>'string' then raise exception using errcode='22023',message='invalid_text:'||field_name; end if;
 t:=v#>>'{}';
 if char_length(t)>max_chars or regexp_replace(t,E'[\n\r\t]','','g') ~ '[[:cntrl:]]' or t ~ '<[[:space:]]*/?[[:alpha:]!][^>]*>' then
 raise exception using errcode='22023',message='invalid_text:'||field_name; end if;
end $$;
create function member_portal.check_path(v text, owner_id text) returns void
language plpgsql security definer set search_path='' as $$
begin
 if coalesce(v,'')='' then return; end if;
 if v !~ ('^'||owner_id||'/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.(jpg|png|webp)$') then
 raise exception using errcode='22023',message='invalid_private_image_path'; end if;
 if not exists(select 1 from storage.objects o where o.bucket_id='member-drafts' and o.name=v) then
 raise exception using errcode='22023',message='image_not_uploaded'; end if;
end $$;
create function member_portal.validate_payload(payload jsonb, owner_id text) returns void
language plpgsql security definer set search_path='' as $$
declare k text; v jsonb; e jsonb; z jsonb; field text; lim integer; ids text[]:=array[]::text[];
begin
 if payload is null or jsonb_typeof(payload)<>'object' or octet_length(payload::text)>524288 then raise exception using errcode='22023',message='invalid_payload'; end if;
 for k,v in select * from jsonb_each(payload) loop
  if not k=any(array['bio','bio_en','interests','interests_en','education','education_en','public_email','avatar_path','links','projects','papers']) then raise exception using errcode='22023',message='unknown_field:'||k; end if;
  if not k=any(array['links','projects','papers']) then perform member_portal.check_text(v,case when k='public_email' then 254 when k='avatar_path' then 150 else 3000 end,k); end if;
 end loop;
 if coalesce(payload->>'public_email','')<>'' and (payload->>'public_email' !~ '^[A-Za-z0-9.!#$%&''*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,63}$' or payload->>'public_email' ~* '%0[ad]') then raise exception using errcode='22023',message='invalid_public_email'; end if;
 perform member_portal.check_path(payload->>'avatar_path',owner_id);
 foreach field in array array['links','projects','papers'] loop
  if not payload?field then continue; end if;
  if jsonb_typeof(payload->field)<>'array' then raise exception using errcode='22023',message='invalid_array:'||field; end if;
  lim:=case field when 'links' then 5 when 'projects' then 3 else 30 end;
  if jsonb_array_length(payload->field)>lim then raise exception using errcode='22023',message='too_many:'||field; end if;
  for e in select * from jsonb_array_elements(payload->field) loop
   if jsonb_typeof(e)<>'object' then raise exception using errcode='22023',message='invalid_item:'||field; end if;
   for k,v in select * from jsonb_each(e) loop
    if (field='links' and not k=any(array['label','url'])) or (field='projects' and not k=any(array['id','title','title_en','question','question_en','approach','approach_en','contribution','contribution_en','progress','progress_en','image_path','image_caption','image_caption_en','image_source'])) or (field='papers' and not k=any(array['doi','title','authors','journal','year','context','contribution','contribution_en'])) then raise exception using errcode='22023',message='unknown_item_field:'||k; end if;
    if field='papers' and k='year' then
     if jsonb_typeof(v) not in ('string','number') or v#>>'{}' !~ '^(18|19|20)[0-9]{2}$' then raise exception using errcode='22023',message='invalid_paper_year'; end if;
    else
     lim:=case when field='papers' and k='title' then 1000 when k=any(array['title','title_en','journal','label']) then 200 when k='authors' then 2000 when k='doi' then 255 when k='url' then 2048 when k=any(array['image_path','id','context']) then 150 else 3000 end;
     perform member_portal.check_text(v,lim,field||'.'||k);
    end if;
   end loop;
   if field='links' then
    if coalesce(e->>'label','')='' or coalesce(e->>'url','')='' or (e->>'url' !~ '^https://[A-Za-z0-9][A-Za-z0-9.-]*(:[0-9]{1,5})?([/?#][^[:space:]<>]*)?$' and e->>'url' !~ '^mailto:[A-Za-z0-9.!#$%&''*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,63}$') then raise exception using errcode='22023',message='invalid_external_link'; end if;
    if e->>'url' ~* '^mailto:' and e->>'url' ~* '%0[ad]' then raise exception using errcode='22023',message='invalid_external_link'; end if;
   elsif field='projects' then
    if coalesce(e->>'id','') !~ '^[A-Za-z0-9_-]{1,80}$' or coalesce(e->>'title','')='' or e->>'id'=any(ids) then raise exception using errcode='22023',message='invalid_project_identity'; end if;
    ids:=array_append(ids,e->>'id'); perform member_portal.check_path(e->>'image_path',owner_id);
    if coalesce(e->>'image_path','')<>'' and ((btrim(coalesce(e->>'image_caption',''))='' and btrim(coalesce(e->>'image_caption_en',''))='') or btrim(coalesce(e->>'image_source',''))='') then raise exception using errcode='22023',message='project_image_caption_and_source_required'; end if;
   else
    if coalesce(e->>'title','')='' or coalesce(e->>'context','') not in ('in_lab','before_lab') then raise exception using errcode='22023',message='invalid_paper_identity'; end if;
    if coalesce(e->>'doi','')<>'' and (e->>'doi' !~ '^10\.[0-9]{4,9}/[^[:space:]<>]{1,240}$' or e->>'doi' ~ '[?#"'']' or position(chr(92) in e->>'doi')>0) then raise exception using errcode='22023',message='invalid_doi'; end if;
   end if;
  end loop;
 end loop;
end $$;

create function member_portal.submission_json(sid uuid) returns jsonb language sql security definer set search_path='' as $$
 select jsonb_build_object('id',s.id,'member_id',s.member_id,'member_name',r.member->>'name','payload',s.payload,'revision',s.revision,'status',case v.decision when 'approve' then 'approved' when 'reject' then 'rejected' else 'submitted' end,'review_note',coalesce(v.note,''),'created_at',s.created_at,'published',coalesce(p.submission_id=s.id,false))
 from member_portal.submissions s join member_portal.registry r using(member_id)
 left join member_portal.reviews v on v.submission_id=s.id left join member_portal.publications p using(member_id) where s.id=sid
$$;
create function public.portal_self() returns jsonb language plpgsql security definer set search_path='' as $$
declare a member_portal.accounts; m jsonb; d jsonb; p jsonb; latest jsonb;
begin
 a:=member_portal.actor();
 if a.member_id is not null then
  select r.member into m from member_portal.registry r where r.member_id=a.member_id;
  select jsonb_build_object('payload',x.payload,'revision',x.revision) into d from member_portal.drafts x where x.member_id=a.member_id;
  select s.payload into p from member_portal.publications x join member_portal.submissions s on s.id=x.submission_id where x.member_id=a.member_id;
  select member_portal.submission_json(s.id) into latest from member_portal.submissions s where s.member_id=a.member_id order by s.revision desc limit 1;
 end if;
 return jsonb_build_object('account',jsonb_build_object('role',a.role,'member_id',a.member_id,'email',a.email),'member',m,'draft',coalesce(d,jsonb_build_object('payload','{}'::jsonb,'revision',0)),'published',p,'submission',latest);
end $$;
create function public.save_profile(p_payload jsonb,p_expected_revision bigint) returns jsonb language plpgsql security definer set search_path='' as $$
declare mid text; rev bigint; normalized_papers jsonb;
begin
 mid:=member_portal.require_owner(); perform 1 from member_portal.registry where member_id=mid for update;
 select revision into rev from member_portal.drafts where member_id=mid; rev:=coalesce(rev,0);
 if p_expected_revision is null or p_expected_revision<>rev then raise exception using errcode='40001',message='revision_conflict'; end if;
 perform member_portal.validate_payload(p_payload,mid);
 if p_payload ? 'papers' then
  select coalesce(jsonb_agg(case when x.value ? 'doi' then jsonb_set(x.value,'{doi}',to_jsonb(lower(x.value->>'doi'))) else x.value end order by x.ordinality),'[]'::jsonb) into normalized_papers from jsonb_array_elements(p_payload->'papers') with ordinality as x(value,ordinality);
  p_payload:=jsonb_set(p_payload,'{papers}',normalized_papers);
 end if;
 insert into member_portal.drafts(member_id,payload,revision) values(mid,p_payload,rev+1) on conflict(member_id) do update set payload=excluded.payload,revision=excluded.revision,updated_at=now();
 return jsonb_build_object('payload',p_payload,'revision',rev+1);
end $$;
create function public.submit_profile(p_expected_revision bigint) returns jsonb language plpgsql security definer set search_path='' as $$
declare mid text; d member_portal.drafts; sid uuid;
begin
 mid:=member_portal.require_owner(); perform 1 from member_portal.registry where member_id=mid for update;
 select * into d from member_portal.drafts where member_id=mid;
 if not found then raise exception using errcode='22023',message='draft_required'; end if;
 if p_expected_revision is null or d.revision<>p_expected_revision then raise exception using errcode='40001',message='revision_conflict'; end if;
 perform member_portal.validate_payload(d.payload,mid);
 if exists(select 1 from member_portal.submissions where member_id=mid and revision=d.revision) then raise exception using errcode='22023',message='revision_already_submitted'; end if;
 insert into member_portal.submissions(member_id,payload,revision,submitted_by) values(mid,d.payload,d.revision,auth.uid()) returning id into sid;
 return member_portal.submission_json(sid);
end $$;
create function public.list_submissions() returns jsonb language plpgsql security definer set search_path='' as $$
declare a member_portal.accounts; result jsonb;
begin a:=member_portal.require_admin(); select coalesce(jsonb_agg(member_portal.submission_json(s.id) order by s.created_at desc),'[]') into result from member_portal.submissions s; return result; end $$;
create function member_portal.publish_snapshot(sid uuid,kind text) returns void language plpgsql security definer set search_path='' as $$
declare mid text; rel bigint;
begin
 select member_id into mid from member_portal.submissions where id=sid;
 if not exists(select 1 from member_portal.registry r where r.member_id=mid and r.active) then raise exception using errcode='22023',message='inactive_member'; end if;
 update member_portal.release_state set version=version+1 where singleton returning version into rel;
 insert into member_portal.publications(member_id,submission_id,release_version) values(mid,sid,rel) on conflict(member_id) do update set submission_id=excluded.submission_id,approved_at=now(),release_version=excluded.release_version;
 insert into member_portal.publication_history(member_id,submission_id,action,actor,release_version) values(mid,sid,kind,auth.uid(),rel);
end $$;
create function public.review_submission(p_submission_id uuid,p_decision text,p_note text) returns jsonb language plpgsql security definer set search_path='' as $$
declare a member_portal.accounts; s member_portal.submissions;
begin
 a:=member_portal.require_admin();
 if p_decision is null or p_decision not in ('approve','reject') then raise exception using errcode='22023',message='invalid_review_decision'; end if;
 perform member_portal.check_text(to_jsonb(coalesce(p_note,'')),3000,'review_note');
 select * into s from member_portal.submissions where id=p_submission_id for update;
 if not found then raise exception using errcode='22023',message='submission_not_found'; end if;
 if exists(select 1 from member_portal.reviews where submission_id=s.id) then raise exception using errcode='22023',message='submission_already_reviewed'; end if;
 if p_decision='approve' then perform member_portal.validate_payload(s.payload,s.member_id); end if;
 insert into member_portal.reviews(submission_id,decision,note,reviewer) values(s.id,p_decision,coalesce(p_note,''),auth.uid());
 if p_decision='approve' then perform member_portal.publish_snapshot(s.id,'approve'); end if;
 return member_portal.submission_json(s.id);
end $$;
create function public.restore_publication(p_submission_id uuid) returns jsonb language plpgsql security definer set search_path='' as $$
declare a member_portal.accounts; s member_portal.submissions;
begin
 a:=member_portal.require_admin(); select * into s from member_portal.submissions where id=p_submission_id for update;
 if not found or not exists(select 1 from member_portal.reviews where submission_id=p_submission_id and decision='approve') then raise exception using errcode='22023',message='approved_snapshot_required'; end if;
 perform member_portal.validate_payload(s.payload,s.member_id); perform member_portal.publish_snapshot(s.id,'restore');
 return member_portal.submission_json(s.id);
end $$;
create function public.list_member_access() returns jsonb language plpgsql security definer set search_path='' as $$
declare a member_portal.accounts; result jsonb;
begin
 a:=member_portal.require_admin();
 select coalesce(jsonb_agg(x.item order by x.member_id,x.email),'[]') into result from (
  select r.member_id,p.email,jsonb_build_object('member_id',r.member_id,'member_name',r.member->>'name','email',p.email,'role',p.role,'enabled',coalesce(p.enabled,false),'invited',p.email is not null,'active',r.active) as item
  from member_portal.registry r left join member_portal.accounts p using(member_id) where r.active
  union all select p.member_id,p.email,jsonb_build_object('member_id',p.member_id,'member_name',null,'email',p.email,'role',p.role,'enabled',p.enabled,'invited',true,'active',true) from member_portal.accounts p where p.member_id is null
 ) x;
 return result;
end $$;
create function public.set_member_access(p_email text,p_member_id text,p_role text,p_enabled boolean) returns jsonb language plpgsql security definer set search_path='' as $$
declare a member_portal.accounts; target member_portal.accounts; em text;
begin
 a:=member_portal.require_admin(); lock table member_portal.accounts in share row exclusive mode;
 -- Re-check after lock: a concurrent revocation must take effect before this mutation.
 a:=member_portal.require_admin(); em:=lower(btrim(p_email));
 if em is null or length(em)>254 or em !~ '^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$' or p_role is null or p_role not in ('member','admin') or p_enabled is null or (p_role='member' and p_member_id is null) then raise exception using errcode='22023',message='invalid_access_record'; end if;
 if p_member_id is not null and not exists(select 1 from member_portal.registry where member_id=p_member_id and active) then raise exception using errcode='22023',message='invalid_member'; end if;
 select * into target from member_portal.accounts where email=em;
 if em=a.email and (not p_enabled or p_role<>'admin') then raise exception using errcode='42501',message='cannot_lock_out_current_admin'; end if;
 if target.role='admin' and target.enabled and (not p_enabled or p_role<>'admin') and (select count(*) from member_portal.accounts where role='admin' and enabled)<=1 then raise exception using errcode='42501',message='last_admin_required'; end if;
 insert into member_portal.accounts(email,member_id,role,enabled) values(em,p_member_id,p_role,p_enabled) on conflict(email) do update set member_id=excluded.member_id,role=excluded.role,enabled=excluded.enabled,updated_at=now();
 return jsonb_build_object('email',em,'member_id',p_member_id,'role',p_role,'enabled',p_enabled);
end $$;
-- Service role is granted EXECUTE alone; auth/anon cannot call even with forged RPC arguments.
create function public.export_public_profiles() returns jsonb language sql security definer set search_path='' as $$
 select jsonb_build_object('schemaVersion',1,'profiles',coalesce(jsonb_object_agg(p.member_id,jsonb_build_object('version',s.id,'publishedAt',p.approved_at,'content',s.payload)),'{}'::jsonb))
 from member_portal.publications p join member_portal.submissions s on s.id=p.submission_id and s.member_id=p.member_id join member_portal.reviews v on v.submission_id=s.id and v.decision='approve' join member_portal.registry r on r.member_id=p.member_id and r.active
$$;

-- Storage RLS helpers return booleans without revealing accounts or drafts.
create function member_portal.can_read_object(object_name text) returns boolean language plpgsql security definer set search_path='' as $$
declare a member_portal.accounts;
begin a:=member_portal.actor(); return a.role='admin' or split_part(object_name,'/',1)=a.member_id; exception when insufficient_privilege then return false; end $$;
create function member_portal.can_insert_object(object_name text) returns boolean language plpgsql security definer set search_path='' as $$
declare a member_portal.accounts;
begin a:=member_portal.actor(); return a.member_id is not null and object_name ~ ('^'||a.member_id||'/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.(jpg|png|webp)$'); exception when insufficient_privilege then return false; end $$;
insert into storage.buckets(id,name,public,file_size_limit,allowed_mime_types) values('member-drafts','member-drafts',false,5242880,array['image/jpeg','image/png','image/webp']) on conflict(id) do update set public=false,file_size_limit=excluded.file_size_limit,allowed_mime_types=excluded.allowed_mime_types;
create policy member_drafts_read on storage.objects for select to authenticated using(bucket_id='member-drafts' and member_portal.can_read_object(name));
create policy member_drafts_insert on storage.objects for insert to authenticated with check(bucket_id='member-drafts' and member_portal.can_insert_object(name));
-- Restrictive policies ensure an unrelated permissive policy cannot accidentally enable overwrite/delete in this bucket.
create policy member_drafts_no_update on storage.objects as restrictive for update to public using(bucket_id<>'member-drafts') with check(bucket_id<>'member-drafts');
create policy member_drafts_no_delete on storage.objects as restrictive for delete to public using(bucket_id<>'member-drafts');
create policy member_drafts_read_guard on storage.objects as restrictive for select to public using(bucket_id<>'member-drafts' or member_portal.can_read_object(name));
create policy member_drafts_insert_guard on storage.objects as restrictive for insert to public with check(bucket_id<>'member-drafts' or member_portal.can_insert_object(name));

revoke all on all functions in schema member_portal from public,anon,authenticated;
grant usage on schema member_portal to authenticated,anon;
grant execute on function member_portal.can_read_object(text),member_portal.can_insert_object(text) to authenticated,anon;
revoke all on function public.portal_self(),public.save_profile(jsonb,bigint),public.submit_profile(bigint),public.list_submissions(),public.review_submission(uuid,text,text),public.restore_publication(uuid),public.list_member_access(),public.set_member_access(text,text,text,boolean),public.export_public_profiles() from public,anon,authenticated;
grant execute on function public.portal_self(),public.save_profile(jsonb,bigint),public.submit_profile(bigint),public.list_submissions(),public.review_submission(uuid,text,text),public.restore_publication(uuid),public.list_member_access(),public.set_member_access(text,text,text,boolean) to authenticated;
grant execute on function public.export_public_profiles() to service_role;
commit;

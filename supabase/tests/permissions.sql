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
insert into auth.users values
('00000000-0000-0000-0000-000000000001','member1@example.test',now()),
('00000000-0000-0000-0000-000000000002','member2@example.test',now()),
('00000000-0000-0000-0000-000000000003','admin@example.test',now()),
('00000000-0000-0000-0000-000000000004','outsider@example.test',now()),
('00000000-0000-0000-0000-000000000005','unverified@example.test',null),
('00000000-0000-0000-0000-000000000006','disabled@example.test',now()),
('00000000-0000-0000-0000-000000000007','admin2@example.test',now());
insert into member_portal.registry values('member-01','{"id":"member-01","name":"Member One"}',true),('member-02','{"id":"member-02","name":"Member Two"}',true);
insert into member_portal.accounts(email,member_id,role,enabled) values
('member1@example.test','member-01','member',true),('member2@example.test','member-02','member',true),
('admin@example.test',null,'admin',true),('unverified@example.test',null,'admin',true),('disabled@example.test',null,'admin',false);
-- Deliberately broad unrelated storage policies must not weaken this bucket.
create policy test_broad_storage_select on storage.objects for select to anon,authenticated using(true);
create policy test_broad_storage_insert on storage.objects for insert to anon,authenticated with check(true);
create policy test_broad_storage_update on storage.objects for update to anon,authenticated using(true) with check(true);
create policy test_broad_storage_delete on storage.objects for delete to anon,authenticated using(true);
set role anon;
select public.test_denied('select public.portal_self()','42501','anon cannot call self');
select public.test_denied('select public.export_public_profiles()','42501','anon cannot export');
select public.test_denied('select * from member_portal.accounts','42501','anon cannot read accounts');
select public.test_denied($q$insert into storage.objects(bucket_id,name) values('member-drafts','member-01/11111111-1111-1111-1111-111111111111.png')$q$,'42501','anon cannot upload even with permissive unrelated policy');
set role authenticated;
select set_config('request.jwt.claim.sub','00000000-0000-0000-0000-000000000004',true);
select public.test_denied('select public.portal_self()','42501','uninvited account rejected');
select set_config('request.jwt.claim.sub','00000000-0000-0000-0000-000000000005',true);
select public.test_denied('select public.portal_self()','42501','unverified invited email rejected');
select set_config('request.jwt.claim.sub','00000000-0000-0000-0000-000000000006',true);
select public.test_denied('select public.portal_self()','42501','disabled account rejected');
select set_config('request.jwt.claim.sub','00000000-0000-0000-0000-000000000001',true);
select public.test_assert(public.portal_self()->'account'->>'member_id'='member-01','member identity bound to verified account');
select public.test_assert((public.portal_self()->'draft'->>'revision')::integer=0,'initial revision0');
select public.test_denied('select public.list_submissions()','42501','member cannot read review queue');
select public.test_denied('select public.list_member_access()','42501','member cannot list invitations');
select public.test_denied('select public.export_public_profiles()','42501','member cannot export');
select public.test_denied($q$select public.set_member_access('evil@example.test',null,'admin',true)$q$,'42501','member cannot self-promote');
select public.test_denied('select member_portal.actor()','42501','private actor helper not exposed');
select public.test_denied('select * from member_portal.drafts','42501','direct draft reads blocked');
select public.test_denied($q$insert into member_portal.publications values('member-01','00000000-0000-0000-0000-000000000010',now(),1)$q$,'42501','direct publication writes blocked');
insert into storage.objects(bucket_id,name) values('member-drafts','member-01/11111111-1111-1111-1111-111111111111.png');
select public.test_denied($q$insert into storage.objects(bucket_id,name) values('member-drafts','member-02/11111111-1111-1111-1111-111111111111.png')$q$,'42501','cross-member upload blocked');
select public.test_denied($q$insert into storage.objects(bucket_id,name) values('member-drafts','member-01/../../bad.svg')$q$,'42501','path traversal and SVG upload blocked');
select public.test_denied($q$insert into storage.objects(bucket_id,name) values('member-drafts','member-01/11111111-1111-1111-1111-111111111111.png')$q$,'23505','duplicate immutable object insert blocked');
update storage.objects set name='member-01/22222222-2222-2222-2222-222222222222.png';
delete from storage.objects;
select public.test_assert((select count(*)=1 from storage.objects where name='member-01/11111111-1111-1111-1111-111111111111.png'),'storage update/delete preserve immutable original');
select public.test_denied($q$select public.save_profile('{"member_id":"member-02"}',0)$q$,'22023','payload cannot change identity');
select public.test_denied($q$select public.save_profile('{"bio":"<script>alert(1)</script>"}',0)$q$,'22023','HTML payload rejected');
select public.test_denied($q$select public.save_profile(jsonb_build_object('bio',repeat('a',3001)),0)$q$,'22023','long biography rejected');
select public.test_denied($q$select public.save_profile('{"bio":null}',0)$q$,'22023','null field type rejected');
select public.test_denied($q$select public.save_profile('{"projects":{}}',0)$q$,'22023','invalid array rejected');
select public.test_denied($q$select public.save_profile(jsonb_build_object('links',(select jsonb_agg(jsonb_build_object('label','x','url','https://example.test')) from generate_series(1,6))),0)$q$,'22023','more than5 links rejected');
select public.test_denied($q$select public.save_profile(jsonb_build_object('projects',(select jsonb_agg(jsonb_build_object('id','p'||g,'title','x')) from generate_series(1,4)g)),0)$q$,'22023','more than3 projects rejected');
select public.test_denied($q$select public.save_profile(jsonb_build_object('papers',(select jsonb_agg(jsonb_build_object('title','x','context','in_lab')) from generate_series(1,31))),0)$q$,'22023','more than30 papers rejected');

select public.test_denied($q$select public.save_profile('{"links":[{"label":"x","url":"javascript:alert(1)"}]}',0)$q$,'22023','javascript URL rejected');
select public.test_denied($q$select public.save_profile('{"links":[{"label":"x","url":"https://a@b.example"}]}',0)$q$,'22023','URL credentials rejected');
select public.test_denied($q$select public.save_profile('{"public_email":"a%0d%0abcc@example.test"}',0)$q$,'22023','public email encoded CRLF rejected');
select public.test_denied($q$select public.save_profile('{"links":[{"label":"Contact","url":"mailto:a%0Abcc@example.test"}]}',0)$q$,'22023','mailto encoded CRLF rejected');
select public.test_denied(format('select public.save_profile(%L::jsonb,0)',jsonb_build_object('public_email','a%'||upper(lpad(to_hex(n),2,'0'))||'b@example.test')),'22023','public email encoded control byte rejected') from (select generate_series(0,31) as n union all select 127) as controls;
select public.test_denied(format('select public.save_profile(%L::jsonb,0)',jsonb_build_object('links',jsonb_build_array(jsonb_build_object('label','Contact','url','mailto:a%'||upper(lpad(to_hex(n),2,'0'))||'b@example.test')))),'22023','mailto encoded control byte rejected') from (select generate_series(0,31) as n union all select 127) as controls;
select public.test_denied($q$select public.save_profile('{"projects":[{"id":"one","title":"one"},{"id":"one","title":"two"}]}',0)$q$,'22023','duplicate project IDs rejected');
select public.test_denied($q$select public.save_profile('{"papers":[{"title":"x","year":2026,"context":"secret"}]}',0)$q$,'22023','paper context rejected');
select public.test_denied(format('select public.save_profile(%L::jsonb,0)',jsonb_build_object('papers',jsonb_build_array(jsonb_build_object('title','x','context','in_lab','doi','10.1234/a'||c||'b')))),'22023','DOI forbidden character rejected') from unnest(array['?','#',chr(92),chr(34),chr(39),' ','<','>']) as c;
select public.test_denied($q$select public.save_profile(jsonb_build_object('papers',jsonb_build_array(jsonb_build_object('title',repeat('a',1001),'context','in_lab'))),0)$q$,'22023','paper title over1000 rejected');
select public.test_denied($q$select public.save_profile('{"projects":[{"id":"p1","title":"Example","image_path":"member-01/11111111-1111-1111-1111-111111111111.png","image_source":"Member supplied"}]}',0)$q$,'22023','project image missing caption rejected');
select public.test_denied($q$select public.save_profile('{"projects":[{"id":"p1","title":"Example","image_path":"member-01/11111111-1111-1111-1111-111111111111.png","image_caption":"Example image"}]}',0)$q$,'22023','project image missing source rejected');
select public.test_denied($q$select public.save_profile('{"avatar_path":"member-02/11111111-1111-1111-1111-111111111111.png"}',0)$q$,'22023','foreign image path rejected');
select public.test_denied($q$select public.save_profile('{"avatar_path":"member-01/22222222-2222-2222-2222-222222222222.png"}',0)$q$,'22023','missing object reference rejected');
select public.test_assert((public.save_profile('{"bio":"Version one","public_email":"public-contact@example.test","avatar_path":"member-01/11111111-1111-1111-1111-111111111111.png","papers":[{"title":"Example","year":2026,"context":"in_lab","doi":"10.1234/test"}],"links":[{"label":"DOI","url":"https://doi.org/10.1234/test"}]}',0)->>'revision')::integer=1,'owner saves revision1');
select public.test_denied($q$select public.save_profile('{"bio":"stale"}',0)$q$,'40001','stale save fails optimistic lock');
select public.test_denied('select public.submit_profile(0)','40001','stale submit fails optimistic lock');
select public.submit_profile(1)->>'id' as sid1 \gset
select public.test_assert(public.portal_self()->'submission'->>'status'='submitted','self exposes submitted status matching frontend contract');
select public.test_denied('select public.submit_profile(1)','22023','same revision cannot be submitted twice');
select public.save_profile('{"bio":"Version two"}',1);
select public.test_assert(public.portal_self()->'published'='null'::jsonb,'submit does not auto-publish');
select set_config('request.jwt.claim.sub','00000000-0000-0000-0000-000000000002',true);
select public.test_assert((select count(*)=0 from storage.objects where bucket_id='member-drafts'),'member cannot read foreign image');
select public.test_assert(public.portal_self()->'draft'->'payload'='{}'::jsonb,'other member sees only own empty draft');
select public.test_assert(public.portal_self()->'submission'='null'::jsonb,'other member cannot read foreign submission or review note');
select public.save_profile(jsonb_build_object('bio','Member two','papers',jsonb_build_array(jsonb_build_object('title',repeat('a',1000),'context','in_lab','doi','10.1234/MIXEDcase'))),0);
select public.test_assert(public.portal_self()->'draft'->'payload'->'papers'->0->>'doi'='10.1234/mixedcase','long paper title accepted and DOI normalized lowercase');
select set_config('request.jwt.claim.sub','00000000-0000-0000-0000-000000000003',true);
select public.test_assert(public.portal_self()->'account'->>'role'='admin','live admin verified');
select public.test_assert(public.portal_self()->'submission'='null'::jsonb,'unassigned administrator self has no member submission');
select public.test_assert(jsonb_array_length(public.list_member_access())>=2,'admin sees registry invitation choices');
select public.test_assert((select count(*)=1 from storage.objects where bucket_id='member-drafts'),'admin reads private images');
select public.test_assert(public.list_submissions()->0->'payload'->>'bio'='Version one','submission remains original snapshot after edit');
select public.review_submission(:'sid1','approve','internal-review-note');
select public.test_denied(format('select public.review_submission(%L,%L,%L)',:'sid1','reject','changed'),'22023','review decisions are final');
select public.test_denied($q$select public.set_member_access('admin@example.test',null,'admin',false)$q$,'42501','current admin cannot disable itself');
select public.test_denied($q$select public.set_member_access('admin@example.test','member-01','member',true)$q$,'42501','current admin cannot demote itself');
select public.set_member_access('admin2@example.test',null,'admin',true);
select public.set_member_access('member2@example.test','member-02','member',false);
select set_config('request.jwt.claim.sub','00000000-0000-0000-0000-000000000002',true);
select public.test_denied('select public.portal_self()','42501','live disabled invitation immediately rejects existing session');
set role service_role;
select public.test_assert(public.export_public_profiles()->'profiles'->'member-01'->'content'->>'bio'='Version one','service exports approved snapshot not current draft');
select public.test_assert(not (public.export_public_profiles()->'profiles' ? 'member-02'),'unapproved profile never exported');
select public.test_assert(public.export_public_profiles()::text not like '%admin@example%' and public.export_public_profiles()::text not like '%member1@example%' and public.export_public_profiles()::text not like '%internal-review-note%','export omits account emails and review notes');
set role authenticated;
select set_config('request.jwt.claim.sub','00000000-0000-0000-0000-000000000001',true);
select public.submit_profile(2)->>'id' as sid2 \gset
select set_config('request.jwt.claim.sub','00000000-0000-0000-0000-000000000003',true);
select public.review_submission(:'sid2','approve','approved second');
select public.restore_publication(:'sid1');
select set_config('request.jwt.claim.sub','00000000-0000-0000-0000-000000000001',true);
select public.save_profile('{"bio":"Rejected version"}',2);
select public.submit_profile(3)->>'id' as sid3 \gset
select public.test_denied(format('select public.review_submission(%L,%L,%L)',:'sid3','approve','self'),'42501','member cannot approve own submission');
select set_config('request.jwt.claim.sub','00000000-0000-0000-0000-000000000003',true);
select public.review_submission(:'sid3','reject','Needs evidence');
select public.test_denied(format('select public.restore_publication(%L)',:'sid3'),'22023','rejected snapshot cannot be restored');
select set_config('request.jwt.claim.sub','00000000-0000-0000-0000-000000000001',true);
select public.test_assert(public.portal_self()->'submission'->>'id'=:'sid3' and public.portal_self()->'submission'->>'status'='rejected' and public.portal_self()->'submission'->>'review_note'='Needs evidence','member sees latest rejection and own reviewer feedback');

set role service_role;
select public.test_assert(public.export_public_profiles()->'profiles'->'member-01'->>'version'=:'sid1','rollback restores previously approved immutable snapshot');
reset role;
select public.test_assert((select count(*)=3 from member_portal.publication_history),'approval and rollback history preserved');
select public.test_assert((select version=3 from member_portal.release_state),'release version increments on approvals and rollback');
select public.test_denied(format('update member_portal.submissions set payload=%L::jsonb where id=%L','{}',:'sid1'),'42501','immutable snapshot trigger blocks even privileged direct update');
select public.test_denied(format('delete from member_portal.reviews where submission_id=%L',:'sid1'),'42501','review-history trigger blocks deletion');
update member_portal.registry set active=false where member_id='member-01';
set role service_role;
select public.test_assert(public.export_public_profiles()->'profiles'='{}'::jsonb,'inactive registry member excluded from export');
set role authenticated;
select set_config('request.jwt.claim.sub','00000000-0000-0000-0000-000000000001',true);
select public.test_denied('select public.portal_self()','42501','inactive registry member loses portal access');
reset role;
select public.test_assert((select not public and file_size_limit=5242880 and allowed_mime_types=array['image/jpeg','image/png','image/webp'] from storage.buckets where id='member-drafts'),'private raster bucket configured with5MB limit');
rollback;

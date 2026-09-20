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
 ('20000000-0000-0000-0000-000000000001','member-notify@example.test',now()),
 ('20000000-0000-0000-0000-000000000002','xiangm_chen@foxmail.com',now()),
 ('20000000-0000-0000-0000-000000000003','other-admin@example.test',now());
insert into member_portal.registry(member_id,member) values
 ('member-notify','{"name":"Notification Member"}');
insert into member_portal.accounts(email,member_id,role) values
 ('member-notify@example.test','member-notify','member'),
 ('xiangm_chen@foxmail.com',null,'admin'),
 ('other-admin@example.test',null,'admin');

set role anon;
select public.test_denied('select public.claim_review_notifications()','42501','anonymous cannot claim notifications');
select public.test_denied('select public.review_notification_status()','42501','anonymous cannot read notification counts');
set role authenticated;
select set_config('request.jwt.claim.sub','20000000-0000-0000-0000-000000000001',true);
select public.test_denied('select public.claim_review_notifications()','42501','member cannot invoke mail worker');
select public.test_denied('select * from member_portal.review_notifications','42501','member cannot read notification queue');
select public.test_denied('select public.review_notification_status()','42501','member cannot read admin notification status');
select public.test_denied($q$select public.finish_review_notification('00000000-0000-0000-0000-000000000000','00000000-0000-0000-0000-000000000000',true)$q$,'42501','member cannot mark notification sent');
select public.test_denied($q$select public.retry_review_notification('00000000-0000-0000-0000-000000000000')$q$,'42501','member cannot reset retries');
select public.save_profile('{"bio":"Private draft text never belongs in email."}',0);
select public.save_profile('{"bio":"Private draft text never belongs in email."}',1);
reset role;
select public.test_assert((select count(*)=0 from member_portal.review_notifications),'repeated draft saves do not enqueue');
set role authenticated;
select public.submit_profile(2)->>'id' as first_sid \gset
select public.test_denied('select public.submit_profile(2)','22023','same submitted revision keeps established rejection');
select public.save_profile('{"bio":"Private draft text never belongs in email."}',2);
select public.test_assert(public.submit_profile(3)->>'id'=:'first_sid','new revision with identical pending payload returns original submission');
reset role;
select public.test_assert((select count(*)=1 from member_portal.review_notifications),'duplicate submit produces only one notification');
select public.test_assert((select count(*)=1 from member_portal.submissions),'duplicate submit produces only one immutable snapshot');
select public.test_assert((select recipient='xiangm_chen@foxmail.com' from member_portal.review_notifications),'recipient is the one designated administrator');
select public.test_denied(format('insert into member_portal.review_notifications(submission_id) values(%L)',:'first_sid'),'23505','outbox submission ID is unique');
select public.test_denied($q$update member_portal.review_notifications set recipient='other-admin@example.test'$q$,'23514','even privileged accidental recipient substitution fails check');

-- The submission and its queue entry commit or roll back together.
savepoint atomic_submission;
set role authenticated;
select public.save_profile('{"bio":"A different pending snapshot"}',3);
select public.submit_profile(4);
reset role;
select public.test_assert((select count(*)=2 from member_portal.review_notifications),'new submission creates queue entry within transaction');
rollback to savepoint atomic_submission;
select public.test_assert((select count(*)=1 from member_portal.review_notifications),'transaction rollback removes its queue entry');
select public.test_assert((select count(*)=1 from member_portal.submissions),'transaction rollback removes its submission');

-- Only the designated active administrator can be the delivery target.
update member_portal.accounts set enabled=false where email='xiangm_chen@foxmail.com';
set role service_role;
select public.test_assert(public.claim_review_notifications()='[]'::jsonb,'disabled designated admin holds queue without redirecting to other admin');
select public.test_denied('select * from member_portal.review_notifications','42501','worker uses narrow RPC instead of direct table access');
reset role;
update member_portal.accounts set enabled=true where email='xiangm_chen@foxmail.com';
set role service_role;
select public.test_denied('select public.claim_review_notifications(0)','22023','zero claim limit rejected');
select public.test_denied('select public.claim_review_notifications(21)','22023','oversized claim limit rejected');
select public.claim_review_notifications()->0 as first_claim \gset
select public.test_assert((:'first_claim'::jsonb->>'submission_id')=:'first_sid','first claim maps to submitted snapshot');
select public.test_assert((select array_agg(k order by k)=array['attempts','created_at','id','lease_token','member_name','submission_id'] from jsonb_object_keys(:'first_claim'::jsonb) k),'claim metadata excludes payload, email and credentials');
select public.test_assert((:'first_claim'::jsonb->>'attempts')::integer=1,'claim counts first attempt');
select public.test_assert(public.claim_review_notifications()='[]'::jsonb,'active lease prevents second worker claiming same notification');
select public.test_assert(not public.finish_review_notification((:'first_claim'::jsonb->>'id')::uuid,'00000000-0000-0000-0000-000000000000',true),'incorrect lease cannot mark sent');
select public.test_assert(public.finish_review_notification((:'first_claim'::jsonb->>'id')::uuid,(:'first_claim'::jsonb->>'lease_token')::uuid,false,'smtp_failed'),'SMTP failure is recorded separately from submission');
select public.test_assert(public.claim_review_notifications()='[]'::jsonb,'failed delivery is not retried before backoff');
reset role;
select public.test_assert((select count(*)=1 from member_portal.submissions),'SMTP failure leaves submission committed and reviewable');
select public.test_assert((select state='pending' and attempts=1 and next_attempt_at=now()+interval '1 minute' and last_error_code='smtp_failed' from member_portal.review_notifications),'first failure has one minute backoff');
update member_portal.review_notifications set next_attempt_at=now();
set role service_role;
select public.claim_review_notifications()->0 as second_claim \gset
select public.test_assert(public.finish_review_notification((:'second_claim'::jsonb->>'id')::uuid,(:'second_claim'::jsonb->>'lease_token')::uuid,false,'raw secret or SMTP response'),'unsafe error text replaced by generic code');
reset role;
select public.test_assert((select next_attempt_at=now()+interval '5 minutes' and last_error_code='delivery_failed' from member_portal.review_notifications),'second failure waits five minutes and does not preserve raw error');
update member_portal.review_notifications set next_attempt_at=now();
set role service_role;
select public.claim_review_notifications()->0 as third_claim \gset
select public.test_assert(public.finish_review_notification((:'third_claim'::jsonb->>'id')::uuid,(:'third_claim'::jsonb->>'lease_token')::uuid,false,'smtp_timeout'),'third failed attempt recorded');
reset role;
select public.test_assert((select next_attempt_at=now()+interval '15 minutes' from member_portal.review_notifications),'third failure waits fifteen minutes');
update member_portal.review_notifications set next_attempt_at=now();
set role service_role;
select public.claim_review_notifications()->0 as fourth_claim \gset
select public.test_assert(public.finish_review_notification((:'fourth_claim'::jsonb->>'id')::uuid,(:'fourth_claim'::jsonb->>'lease_token')::uuid,false,'smtp_timeout'),'fourth failed attempt recorded');
reset role;
select public.test_assert((select next_attempt_at=now()+interval '60 minutes' from member_portal.review_notifications),'later failure waits sixty minutes');

-- Expired workers cannot acknowledge a replacement worker's lease.
update member_portal.review_notifications set next_attempt_at=now();
set role service_role;
select public.claim_review_notifications()->0 as expired_claim \gset
reset role;
update member_portal.review_notifications set lease_until=now()-interval '1 second';
set role service_role;
select public.test_assert(not public.finish_review_notification((:'expired_claim'::jsonb->>'id')::uuid,(:'expired_claim'::jsonb->>'lease_token')::uuid,true),'expired lease cannot acknowledge delivery');
select public.claim_review_notifications()->0 as renewed_claim \gset
select public.test_assert(:'renewed_claim'::jsonb->>'lease_token'<>:'expired_claim'::jsonb->>'lease_token','expired job gets a new fencing token');
select public.test_assert(not public.finish_review_notification((:'expired_claim'::jsonb->>'id')::uuid,(:'expired_claim'::jsonb->>'lease_token')::uuid,true),'old worker cannot overwrite replacement lease');
select public.test_assert(public.finish_review_notification((:'renewed_claim'::jsonb->>'id')::uuid,(:'renewed_claim'::jsonb->>'lease_token')::uuid,true),'current worker can mark notification sent');
select public.test_assert(public.claim_review_notifications()='[]'::jsonb,'sent notification is never automatically claimed again');
select public.test_assert(not public.retry_review_notification((:'renewed_claim'::jsonb->>'id')::uuid),'manual retry cannot resend a successful notification');
set role authenticated;
select set_config('request.jwt.claim.sub','20000000-0000-0000-0000-000000000002',true);
select public.test_assert(public.review_notification_status()=jsonb_build_object('pending',0,'sending',0,'failed',0,'last_sent_at',now()),'admin status returns only counts and last success');
select public.review_submission(:'first_sid','reject','Please revise.');
select set_config('request.jwt.claim.sub','20000000-0000-0000-0000-000000000001',true);
select public.save_profile('{"bio":"Private draft text never belongs in email."}',3);
select public.submit_profile(4)->>'id' as resubmit_sid \gset
select public.test_assert(:'resubmit_sid'<>:'first_sid','resubmitting identical content after rejection creates a new event');
reset role;
select public.test_assert((select count(*)=2 from member_portal.review_notifications),'resubmission after rejection creates a new notification');

-- A newer request supersedes an old unsent reminder; reviewed/inactive requests
-- are skipped without sending any stale private-review notice.
set role authenticated;
select public.save_profile('{"bio":"A changed submission"}',4);
select public.submit_profile(5)->>'id' as changed_sid \gset
set role service_role;
select public.claim_review_notifications()->0 as changed_claim \gset
select public.test_assert(:'changed_claim'::jsonb->>'submission_id'=:'changed_sid','worker chooses the latest actionable submission');
reset role;
select public.test_assert((select state='skipped' from member_portal.review_notifications where submission_id=:'resubmit_sid'),'superseded unsent reminder is skipped');
update member_portal.review_notifications set lease_until=now()-interval '1 second' where submission_id=:'changed_sid';
set role authenticated;
select set_config('request.jwt.claim.sub','20000000-0000-0000-0000-000000000002',true);
select public.review_submission(:'changed_sid','reject','Review completed before retry.');
set role service_role;
select public.test_assert(public.claim_review_notifications()='[]'::jsonb,'reviewed request is not retried');
reset role;
select public.test_assert((select state='skipped' from member_portal.review_notifications where submission_id=:'changed_sid'),'reviewed request reminder marked skipped');
set role authenticated;
select set_config('request.jwt.claim.sub','20000000-0000-0000-0000-000000000001',true);
select public.save_profile('{"bio":"New request before inactivity"}',5);
select public.submit_profile(6)->>'id' as inactive_sid \gset
reset role;
update member_portal.registry set active=false where member_id='member-notify';
set role service_role;
select public.test_assert(public.claim_review_notifications()='[]'::jsonb,'inactive member request is not sent');
reset role;
select public.test_assert((select state='skipped' from member_portal.review_notifications where submission_id=:'inactive_sid'),'inactive member reminder marked skipped');
update member_portal.registry set active=true where member_id='member-notify';

-- A worker outage or repeated SMTP failure stops after eight automatic attempts.
set role authenticated;
select public.save_profile('{"bio":"New request for retry limit"}',6);
select public.submit_profile(7)->>'id' as capped_sid \gset
reset role;
update member_portal.review_notifications set attempts=7 where submission_id=:'capped_sid';
set role service_role;
select public.claim_review_notifications()->0 as capped_claim \gset
select public.test_assert((:'capped_claim'::jsonb->>'attempts')::integer=8,'eighth automatic attempt is last');
select public.test_assert(public.finish_review_notification((:'capped_claim'::jsonb->>'id')::uuid,(:'capped_claim'::jsonb->>'lease_token')::uuid,false,'smtp_failed'),'eighth failure is recorded');
select public.test_assert(public.claim_review_notifications()='[]'::jsonb,'failed job is not automatically retried a ninth time');
set role authenticated;
select set_config('request.jwt.claim.sub','20000000-0000-0000-0000-000000000002',true);
select public.test_assert((public.review_notification_status()->>'failed')::integer=1,'administrator sees failed notification count');
set role service_role;
select public.test_assert(public.retry_review_notification((:'capped_claim'::jsonb->>'id')::uuid),'explicit service-role retry resets failed job');
select public.claim_review_notifications()->0 as retried_claim \gset
select public.test_assert((:'retried_claim'::jsonb->>'attempts')::integer=1,'manual retry starts a fresh bounded attempt series');
reset role;
update member_portal.review_notifications set attempts=8,lease_until=now()-interval '1 second' where submission_id=:'capped_sid';
set role service_role;
select public.test_assert(public.claim_review_notifications()='[]'::jsonb,'worker crash on eighth lease also stops automatic retry');
reset role;
select public.test_assert((select state='failed' and last_error_code='delivery_lease_expired' from member_portal.review_notifications where submission_id=:'capped_sid'),'exhausted expired lease is reported failed');
set role authenticated;
select set_config('request.jwt.claim.sub','20000000-0000-0000-0000-000000000002',true);
select public.review_submission(:'capped_sid','reject','Reviewed despite notification failure.');
set role service_role;
select public.test_assert(public.claim_review_notifications()='[]'::jsonb,'resolved failed reminder is not sent');
reset role;
select public.test_assert((select state='skipped' from member_portal.review_notifications where submission_id=:'capped_sid'),'resolved failed reminder no longer appears as delivery failure');
select public.test_assert((select relrowsecurity from pg_class where oid='member_portal.review_notifications'::regclass),'notification outbox has RLS enabled');
rollback;

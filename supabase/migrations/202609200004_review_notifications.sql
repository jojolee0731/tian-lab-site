-- Queue only successfully submitted snapshots. Delivery is deliberately outside
-- the submission transaction, so SMTP outages cannot undo a member's submission.
begin;

create table member_portal.review_notifications (
 id uuid primary key default gen_random_uuid(),
 submission_id uuid not null unique references member_portal.submissions(id),
 recipient text not null default 'xiangm_chen@foxmail.com'
   check (recipient='xiangm_chen@foxmail.com'),
 state text not null default 'pending' check (state in ('pending','sending','sent','skipped','failed')),
 attempts integer not null default 0 check (attempts between 0 and 8),
 created_at timestamptz not null default now(),
 next_attempt_at timestamptz not null default now(),
 lease_token uuid,
 lease_until timestamptz,
 sent_at timestamptz,
 last_error_code text check (last_error_code is null or last_error_code ~ '^[a-z][a-z0-9_]{0,63}$'),
 check ((state='sending' and lease_token is not null and lease_until is not null)
     or (state<>'sending' and lease_token is null and lease_until is null))
);
create index review_notifications_due on member_portal.review_notifications(state,next_attempt_at,created_at)
 where state in ('pending','sending');
alter table member_portal.review_notifications enable row level security;
revoke all on member_portal.review_notifications from public,anon,authenticated,service_role;

create function member_portal.enqueue_review_notification() returns trigger
language plpgsql security definer set search_path='' as $$
begin
 insert into member_portal.review_notifications(submission_id) values(new.id)
 on conflict(submission_id) do nothing;
 return new;
end $$;
revoke all on function member_portal.enqueue_review_notification() from public,anon,authenticated,service_role;
create trigger submission_review_notification after insert on member_portal.submissions
 for each row execute function member_portal.enqueue_review_notification();

-- Keep the established error on an already-submitted revision. A later save of
-- unchanged content is idempotent while the latest snapshot still awaits review.
create or replace function public.submit_profile(p_expected_revision bigint) returns jsonb
language plpgsql security definer set search_path='' as $$
declare mid text; d member_portal.drafts; latest member_portal.submissions; sid uuid;
begin
 mid:=member_portal.require_owner();
 perform 1 from member_portal.registry where member_id=mid for update;
 select * into d from member_portal.drafts where member_id=mid;
 if not found then raise exception using errcode='22023',message='draft_required'; end if;
 if p_expected_revision is null or d.revision<>p_expected_revision then
  raise exception using errcode='40001',message='revision_conflict';
 end if;
 perform member_portal.validate_payload(d.payload,mid);
 if exists(select 1 from member_portal.submissions where member_id=mid and revision=d.revision) then
  raise exception using errcode='22023',message='revision_already_submitted';
 end if;
 select * into latest from member_portal.submissions where member_id=mid order by revision desc limit 1 for update;
 if found and latest.payload=d.payload and not exists(
   select 1 from member_portal.reviews where submission_id=latest.id
 ) then return member_portal.submission_json(latest.id); end if;
 insert into member_portal.submissions(member_id,payload,revision,submitted_by)
 values(mid,d.payload,d.revision,auth.uid()) returning id into sid;
 return member_portal.submission_json(sid);
end $$;

-- Returns only notification metadata; never private draft/profile content.
create function public.claim_review_notifications(p_limit integer default 5) returns jsonb
language plpgsql security definer set search_path='' as $$
declare claimed jsonb;
begin
 if p_limit is null or p_limit<1 or p_limit>20 then
  raise exception using errcode='22023',message='invalid_notification_limit';
 end if;
 -- Do not silently redirect the user's chosen recipient to any other admin.
 if not exists(
  select 1 from member_portal.accounts a
  where a.email='xiangm_chen@foxmail.com' and a.enabled and a.role='admin'
  and (a.member_id is null or exists(
   select 1 from member_portal.registry r where r.member_id=a.member_id and r.active
  ))
 ) then return '[]'::jsonb; end if;

 -- A worker can die after claiming. Exhausted leases stop at the same retry cap.
 update member_portal.review_notifications n
 set state='failed',lease_token=null,lease_until=null,last_error_code='delivery_lease_expired'
 where n.state='sending' and n.lease_until<=now() and n.attempts>=8;

 -- Only the latest actionable request needs a review reminder. Never interrupt
 -- an active worker lease; that lease's result is fenced by its unique token.
 update member_portal.review_notifications n
 set state='skipped',lease_token=null,lease_until=null,last_error_code=null
 from member_portal.submissions s
 where n.submission_id=s.id
 and (n.state in ('pending','failed') or (n.state='sending' and n.lease_until<=now()))
 and (
  exists(select 1 from member_portal.reviews v where v.submission_id=s.id)
  or not exists(select 1 from member_portal.registry r where r.member_id=s.member_id and r.active)
  or exists(select 1 from member_portal.submissions newer where newer.member_id=s.member_id and newer.revision>s.revision)
 );

 with due as (
  select n.id from member_portal.review_notifications n
  where n.attempts<8 and (
   (n.state='pending' and n.next_attempt_at<=now())
   or (n.state='sending' and n.lease_until<=now())
  )
  order by n.created_at,n.id for update skip locked limit p_limit
 ), leased as (
  update member_portal.review_notifications n
  set state='sending',attempts=n.attempts+1,lease_token=gen_random_uuid(),lease_until=now()+interval '5 minutes'
  from due where n.id=due.id
  returning n.id,n.submission_id,n.lease_token,n.attempts
 )
 select coalesce(jsonb_agg(jsonb_build_object(
  'id',n.id,'submission_id',n.submission_id,'member_name',r.member->>'name',
  'created_at',s.created_at,'lease_token',n.lease_token,'attempts',n.attempts
 ) order by s.created_at,n.id),'[]'::jsonb) into claimed
 from leased n join member_portal.submissions s on s.id=n.submission_id
 join member_portal.registry r on r.member_id=s.member_id;
 return claimed;
end $$;

create function public.finish_review_notification(
 p_id uuid,p_lease_token uuid,p_sent boolean,p_error_code text default null
) returns boolean language plpgsql security definer set search_path='' as $$
declare affected integer;
begin
 if p_sent is null then raise exception using errcode='22023',message='notification_result_required'; end if;
 update member_portal.review_notifications n set
  state=case when p_sent then 'sent' when n.attempts>=8 then 'failed' else 'pending' end,
  sent_at=case when p_sent then now() else n.sent_at end,
  next_attempt_at=case when p_sent then n.next_attempt_at else now()+case
   when n.attempts=1 then interval '1 minute'
   when n.attempts=2 then interval '5 minutes'
   when n.attempts=3 then interval '15 minutes'
   else interval '60 minutes' end end,
  lease_token=null,lease_until=null,
  last_error_code=case when p_sent then null
   when p_error_code ~ '^[a-z][a-z0-9_]{0,63}$' then p_error_code else 'delivery_failed' end
 where n.id=p_id and n.state='sending' and n.lease_token=p_lease_token and n.lease_until>now();
 get diagnostics affected=row_count;
 return affected=1;
end $$;

-- Deliberate operator recovery only; the automatic worker never resets attempts.
create function public.retry_review_notification(p_id uuid) returns boolean
language plpgsql security definer set search_path='' as $$
declare affected integer;
begin
 update member_portal.review_notifications set
  state='pending',attempts=0,next_attempt_at=now(),last_error_code=null
 where id=p_id and state='failed';
 get diagnostics affected=row_count;
 return affected=1;
end $$;

create function public.review_notification_status() returns jsonb
language plpgsql security definer set search_path='' as $$
declare result jsonb;
begin
 perform member_portal.require_admin();
 select jsonb_build_object(
  'pending',count(*) filter(where state='pending'),
  'sending',count(*) filter(where state='sending'),
  'failed',count(*) filter(where state='failed'),
  'last_sent_at',max(sent_at)
 ) into result from member_portal.review_notifications;
 return result;
end $$;

revoke all on function public.claim_review_notifications(integer),
 public.finish_review_notification(uuid,uuid,boolean,text),public.retry_review_notification(uuid)
 from public,anon,authenticated;
grant execute on function public.claim_review_notifications(integer),
 public.finish_review_notification(uuid,uuid,boolean,text),public.retry_review_notification(uuid)
 to service_role;
revoke all on function public.review_notification_status() from public,anon,authenticated;
grant execute on function public.review_notification_status() to authenticated;
-- CREATE OR REPLACE keeps these grants, stated explicitly for a readable boundary.
revoke all on function public.submit_profile(bigint) from public,anon;
grant execute on function public.submit_profile(bigint) to authenticated;
commit;

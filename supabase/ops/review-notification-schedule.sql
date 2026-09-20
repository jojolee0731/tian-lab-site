-- Hosted Supabase only; the portable migration has no extension dependency.
-- Store the existing project server key in Vault as tianlab_review_worker_key
-- through a private owner session. Never substitute a browser publishable key.
-- REVIEW_SMTP_PASSWORD must be configured and SMTP verify must pass before
-- activating this job. This script always leaves this one job paused.
-- QQ SMTP verified from Tokyo; automatic routing to Mumbai failed verification.
-- Pin the tested region. During a regional outage, retries remain queued.
begin;
create extension if not exists pg_cron with schema pg_catalog;
create extension if not exists pg_net;

create or replace function member_portal.dispatch_review_notifications()
returns bigint language plpgsql security definer set search_path='' as $$
declare worker_key text; request_id bigint;
begin
 if not exists(select 1 from member_portal.accounts a
  where a.email='xiangm_chen@foxmail.com' and a.enabled and a.role='admin'
  and (a.member_id is null or exists(select 1 from member_portal.registry r
    where r.member_id=a.member_id and r.active))) then return null; end if;
 if not exists(select 1 from member_portal.review_notifications n
  where (n.state='pending' and n.next_attempt_at<=now())
     or (n.state='sending' and n.lease_until<=now())) then return null; end if;
 select decrypted_secret into worker_key from vault.decrypted_secrets
  where name='tianlab_review_worker_key';
 if worker_key is null or length(worker_key)<20 then return null; end if;
 select net.http_post(
  url:='https://bxhjuilxsdxdsjsiirgk.supabase.co/functions/v1/review-notifications',
  headers:=jsonb_build_object('Content-Type','application/json','apikey',worker_key,'x-region','ap-northeast-1'),
  body:='{}'::jsonb,timeout_milliseconds:=120000
 ) into request_id;
 return request_id;
end $$;
revoke all on function member_portal.dispatch_review_notifications()
 from public,anon,authenticated,service_role;

select cron.schedule('tianlab-review-notifications','* * * * *',
 'select member_portal.dispatch_review_notifications();');
select cron.alter_job((select jobid from cron.job where jobname='tianlab-review-notifications'),active:=false);
commit;

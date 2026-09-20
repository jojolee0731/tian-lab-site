#!/usr/bin/env python3
"""Run backend permission tests in a disposable real PostgreSQL cluster; no cloud access."""
import argparse
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--pg-bin',type=Path,default=Path('/opt/homebrew/opt/postgresql@16/bin'))
    p.add_argument('--with-signup-hook',action='store_true',help='Compatibility flag; signup hook migration and tests now always run.')
    a=p.parse_args(); root=Path(__file__).resolve().parents[2]
    pg=a.pg_bin
    for executable in ('initdb','pg_ctl','psql'):
        if not (pg/executable).exists():p.error(f'Missing {pg/executable}')
    temp=Path(tempfile.mkdtemp(prefix='tianlab-portal-pg-'))
    env=dict(os.environ,LC_ALL='C',LANG='C')
    def run(cmd,**kw):return subprocess.run([str(x) for x in cmd],env=env,check=True,**kw)
    started=False
    try:
        run([pg/'initdb','-D',temp/'data','-A','trust','--no-locale','-E','UTF8'],stdout=subprocess.DEVNULL)
        # Unix socket only; no TCP listener, no persistent launch agent or Homebrew service.
        run([pg/'pg_ctl','-D',temp/'data','-l',temp/'postgres.log','-o',f"-k {temp} -p 55439 -h ''",'-w','start'],stdout=subprocess.DEVNULL)
        started=True
        psql=[pg/'psql','-X','-h',temp,'-p','55439','-d','postgres','-v','ON_ERROR_STOP=1']
        run(psql+['-f',root/'supabase/tests/fixture.sql'],stdout=subprocess.DEVNULL)
        for migration in sorted((root/'supabase/migrations').glob('*.sql')):
            run(psql+['-f',migration],stdout=subprocess.DEVNULL)
        run(psql+['-f',root/'supabase/tests/permissions.sql'])
        run(psql+['-f',root/'supabase/tests/signup_hook.sql'])
        run(psql+['-f',root/'supabase/tests/review_notifications.sql'])
        # Two real database sessions race for one due notification. Keep each
        # transaction open briefly so SKIP LOCKED is exercised, not just leases.
        run(psql+['-c', """
            insert into member_portal.registry(member_id,member)
              values('member-notify-race','{"name":"Concurrent test member"}');
            insert into member_portal.accounts(email,role)
              values('xiangm_chen@foxmail.com','admin');
            insert into member_portal.submissions(member_id,payload,revision,submitted_by)
              values('member-notify-race','{}',1,'20000000-0000-0000-0000-000000000099');
        """],stdout=subprocess.DEVNULL)
        claim_sql="""begin; set role service_role;
            select jsonb_array_length(public.claim_review_notifications(1));
            select pg_sleep(1); commit;"""
        workers=[subprocess.Popen([str(x) for x in psql+['-A','-t','-q','-c',claim_sql]],
                                 env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
                 for _ in range(2)]
        counts=[]
        for worker in workers:
            out,err=worker.communicate(timeout=10)
            if worker.returncode:raise RuntimeError('Concurrent notification claim failed: '+err)
            counts.append(int(out.strip()))
        if sorted(counts)!=[0,1]:raise AssertionError(f'Concurrent workers claimed {counts}; expected one winner')
        print('PASS: concurrent PostgreSQL workers claimed one notification exactly once.')
        print('PASS: isolated native PostgreSQL RPC/permission/RLS suite. Supabase hosted integration is not implied.')
    finally:
        if started:run([pg/'pg_ctl','-D',temp/'data','-m','immediate','-w','stop'],stdout=subprocess.DEVNULL)
        shutil.rmtree(temp)

if __name__=='__main__':main()

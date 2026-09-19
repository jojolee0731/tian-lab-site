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
        print('PASS: isolated native PostgreSQL RPC/permission/RLS suite. Supabase hosted integration is not implied.')
    finally:
        if started:run([pg/'pg_ctl','-D',temp/'data','-m','immediate','-w','stop'],stdout=subprocess.DEVNULL)
        shutil.rmtree(temp)

if __name__=='__main__':main()

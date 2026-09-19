#!/usr/bin/env python3
"""Generate private registry SQL and optional one-time admin bootstrap; never send invitations."""
import argparse
import json
import os
import re
from pathlib import Path


def sql_literal(value):
    return "'" + value.replace("'", "''") + "'"


def render_seed(people, admin_email=None):
    items = people.get('items', [])
    if not items or len({m.get('id') for m in items}) != len(items):
        raise ValueError('Roster must contain unique member IDs.')
    lines = ['-- PRIVATE activation SQL. No Auth users are created and no email is sent.', 'begin;', 'set local standard_conforming_strings=on;']
    for member in items:
        mid = member.get('id', '')
        if not re.fullmatch(r'member-[a-z0-9-]{1,50}', mid):
            raise ValueError('Invalid member ID: ' + mid)
        value = json.dumps(member, ensure_ascii=False, separators=(',', ':'))
        lines.append(f'insert into member_portal.registry(member_id,member,active) values({sql_literal(mid)},{sql_literal(value)}::jsonb,true) on conflict(member_id) do update set member=excluded.member,active=true;')
    ids = ','.join(sql_literal(m['id']) for m in items)
    lines.append(f'update member_portal.registry set active=false where member_id not in ({ids});')
    if admin_email:
        email = admin_email.strip().lower()
        if len(email)>254 or not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
            raise ValueError('Invalid administrator email.')
        # Only a database owner can execute this SQL. Existing admins must use audited/live admin RPC.
        lines += ["lock table member_portal.accounts in share row exclusive mode;", "do $bootstrap$ begin", "if exists(select 1 from member_portal.accounts where role='admin' and enabled) then raise exception 'Administrator already exists; use set_member_access with an authenticated administrator'; end if;", f"insert into member_portal.accounts(email,member_id,role,enabled) values({sql_literal(email)},null,'admin',true);", "end $bootstrap$;"]
    lines += ['commit;', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--people', type=Path, default=Path(__file__).resolve().parents[1]/'data/people.json')
    parser.add_argument('--admin-email', help='Explicit one-time admin allowlist entry; no default.')
    parser.add_argument('--output', type=Path, required=True, help='Private SQL output; preferably outside the Git worktree.')
    args = parser.parse_args()
    content = render_seed(json.loads(args.people.read_text()), args.admin_email)
    out = args.output.expanduser().resolve()
    # Do not let a bootstrap email or generated private registry enter the public repository accidentally.
    repo = Path(__file__).resolve().parents[1]
    if out == repo or repo in out.parents:
        parser.error('--output must be outside the public website Git worktree')
    out.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(out, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as f:
        f.write(content)
    print(f'Private SQL generated: {out} (mode0600; not executed; no email sent).')


if __name__ == '__main__':
    main()

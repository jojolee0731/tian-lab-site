#!/usr/bin/env python3
"""Limit automatic commits and Pages artifacts to explicitly public files."""
from __future__ import annotations
import argparse
import base64
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from urllib.parse import urlsplit, unquote

from check_site import Document, SITE_PATH

ROOT = Path(__file__).resolve().parents[1]
PAGES = ('index', 'research', 'publications', 'people', 'join', 'collaborate', 'news')
LANGS = ('', 'zh/', 'es/')
IMAGE = re.compile(r'assets/images/member-projects/(member-\d{2,})/[0-9a-f-]{36}\.(jpg|png|webp)')


def roster_ids(root):
    records = json.loads((root / 'data/people.json').read_text())['items']
    ids = {record['id'] for record in records}
    if len(ids) != len(records) or any(not re.fullmatch(r'member-\d{2,}', value) for value in ids):
        raise ValueError('Current member registry contains unsafe or duplicate IDs')
    return ids


def rendered_paths(root):
    names = list(PAGES) + ['person-' + value for value in sorted(roster_ids(root))]
    return {prefix + name + '.html' for prefix in LANGS for name in names}


def allowed_commit_paths(root, manifest):
    members = roster_ids(root)
    if not isinstance(manifest, list) or len(manifest) != len(set(manifest)) or 'data/member-profiles.json' not in manifest:
        raise ValueError('Exporter must provide a unique public-file manifest including the profile catalog')
    for relative in manifest:
        if relative == 'data/member-profiles.json':
            continue
        match = IMAGE.fullmatch(relative) if isinstance(relative, str) else None
        if not match or match.group(1) not in members:
            raise ValueError('Exporter manifest contains a non-public or unowned path')
    return rendered_paths(root) | set(manifest) | {'sitemap.xml'}


def checked_file(root, relative):
    path = root / relative
    if path.resolve() != path or not path.is_file() or not path.resolve().is_relative_to(root):
        raise ValueError('Public output must be a regular file inside the site, with no symlinks')
    for key in ('SUPABASE_SECRET_KEY', 'SUPABASE_SERVICE_ROLE_KEY', 'GITHUB_PUBLISH_TOKEN', 'GH_TOKEN', 'GITHUB_TOKEN'):
        secret = os.environ.get(key, '')
        if len(secret) >= 16 and secret.encode() in path.read_bytes():
            raise ValueError('A server credential was detected in a proposed public output')
    return path


def git_paths(root, arguments):
    output = subprocess.check_output(['git', *arguments, '-z'], cwd=root)
    return {item.decode('utf-8') for item in output.split(b'\0') if item}


def stage_public_changes(root, manifest):
    permitted = allowed_commit_paths(root, manifest)
    tracked = git_paths(root, ['diff', '--name-only', 'HEAD', '--no-renames'])
    untracked = git_paths(root, ['ls-files', '--others', '--exclude-standard'])
    changed = tracked | untracked
    if changed - permitted:
        # Only file names are reported, never contents or secret values.
        raise ValueError('Refusing automatic commit of non-public changes: ' + ', '.join(sorted(changed - permitted)))
    for relative in changed:
        checked_file(root, relative)  # Automatic deletion is deliberately excluded.
    if changed:
        subprocess.run(['git', 'add', '--', *sorted(changed)], cwd=root, check=True)
    staged = git_paths(root, ['diff', '--cached', '--name-only', '--no-renames'])
    if staged - permitted or staged != changed:
        raise ValueError('The staged commit does not match the checked public outputs')
    return len(staged)


def validate_public_config(path):
    data = json.loads(path.read_text())
    required = {'supabaseUrl', 'supabaseAnonKey', 'enabled'}
    allowed = required | {'reviewNotificationsEnabled'}
    if not isinstance(data, dict) or not required <= set(data) <= allowed or not isinstance(data['enabled'], bool):
        raise ValueError('Portal configuration may contain only the approved public configuration fields')
    if 'reviewNotificationsEnabled' in data and not isinstance(data['reviewNotificationsEnabled'], bool):
        raise ValueError('The review notification flag must be a boolean')
    url, key = data['supabaseUrl'], data['supabaseAnonKey']
    if not isinstance(url, str) or not isinstance(key, str):
        raise ValueError('Portal URL and public key must be strings')
    if key:
        if key.startswith('sb_publishable_'):
            if not re.fullmatch(r'sb_publishable_[A-Za-z0-9_-]+', key):
                raise ValueError('Invalid public Supabase key')
        else:
            try:
                parts = key.split('.')
                if len(parts) != 3:
                    raise ValueError()
                claims = json.loads(base64.urlsafe_b64decode(parts[1] + '=' * (-len(parts[1]) % 4)))
                if claims.get('role') != 'anon':
                    raise ValueError()
            except (ValueError, UnicodeError, TypeError):
                raise ValueError('Only a publishable or legacy anon key may be exposed; never a service key') from None
    if url:
        parsed = urlsplit(url)
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('', '/'):
            raise ValueError('Portal configuration requires an HTTPS origin')
    if data['enabled'] and (not url or not key):
        raise ValueError('Enabled portal configuration requires its URL and public key')


def package_public_site(root, destination):
    root, destination = root.resolve(), destination.resolve()
    if destination.exists() or destination.resolve().is_relative_to(root):
        raise ValueError('Pages artifact must be a new directory outside the repository')
    files = rendered_paths(root) | {
        'styles.css', 'script.js', 'member-profile.css', 'sitemap.xml', 'robots.txt',
        'assets/favicon.svg', 'assets/logo-mark.svg',
        'data/people.json', 'data/contact.json', 'data/publications.json', 'data/member-profiles.json',
        'members/index.html', 'members/app.js', 'members/model.mjs',
        'members/workbench.css', 'members/config.json', 'members/vendor/supabase.js',
    }
    files |= {str(path.relative_to(root)) for path in (root / 'assets/images').rglob('*') if path.is_file() and path.suffix.lower() in ('.jpg', '.jpeg', '.png', '.webp', '.svg', '.ico')}
    files |= {path.name for path in root.glob('google*.html') if re.fullmatch(r'google[0-9a-f]+\.html', path.name)}
    validate_public_config(root / 'members/config.json')
    # Check the full allowlist before creating an uploadable artifact.
    checked = [(relative, checked_file(root, relative)) for relative in sorted(files)]
    destination.mkdir(parents=True)
    for relative, source in checked:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    (destination / '.nojekyll').write_text('')
    # Validate the actual upload artifact, not only the larger source checkout.
    # An omitted dependency must fail before upload/deployment can begin.
    for page in destination.rglob('*.html'):
        for node in Document(page).nodes:
            for attribute in ('href', 'src'):
                url = urlsplit(node.attrs.get(attribute, ''))
                if url.scheme or url.netloc or not url.path:
                    continue
                if url.path.startswith(SITE_PATH):
                    target = destination / unquote(url.path[len(SITE_PATH):])
                else:
                    target = page.parent / unquote(url.path)
                target = target.resolve()
                if target.is_dir():
                    target = target / 'index.html'
                if not target.is_relative_to(destination) or not target.is_file():
                    raise ValueError(f'Public artifact omits a local dependency linked by {page.relative_to(destination)}')
    return len(checked)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--manifest', type=Path)
    parser.add_argument('--stage', action='store_true')
    parser.add_argument('--package', type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        if args.stage:
            if not args.manifest:
                parser.error('--stage requires the exporter manifest')
            count = stage_public_changes(root, json.loads(args.manifest.read_text()))
            print(f'Checked and staged {count} public output files.')
        if args.package:
            count = package_public_site(root, args.package.resolve())
            print(f'Packaged {count} explicitly public files for Pages.')
        if not args.stage and not args.package:
            parser.error('Choose --stage or --package')
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f'Public-output guard failed: {exc}\n')


if __name__ == '__main__':
    main()

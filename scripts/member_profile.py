"""Validate approved public member content before static rendering.

This module accepts local, exported assets only. It does not fetch remote URLs,
interpret HTML, or turn private draft storage paths into public URLs.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
from datetime import datetime
from uuid import UUID
from urllib.parse import urlsplit, unquote

MEMBER_ID = re.compile(r'member-\d{2,}')
DOI = re.compile(r"10\.\d{4,9}/[^\s?#<>\"'\\]+", re.I)
EMAIL = re.compile(r'[^\s@<>"\x00-\x1f\x7f]+@[^\s@<>"\x00-\x1f\x7f]+\.[^\s@<>"\x00-\x1f\x7f]+')
LONG_FIELDS = ('bio', 'bio_en', 'interests', 'interests_en', 'education', 'education_en')
PROJECT_FIELDS = ('id', 'title', 'title_en', 'question', 'question_en', 'approach', 'approach_en', 'contribution', 'contribution_en', 'progress', 'progress_en', 'image_path', 'image_caption', 'image_caption_en', 'image_source')
PAPER_FIELDS = ('doi', 'title', 'authors', 'journal', 'year', 'context', 'contribution', 'contribution_en')


def plain(value, label, limit=3000):
    if not isinstance(value, str):
        raise ValueError(f'{label}: expected plain text')
    if len(value) > limit or re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', value):
        raise ValueError(f'{label}: text exceeds limit or contains control characters')
    return value.strip()


def public_email(value):
    address = plain(value, 'public_email', 254)
    if address and (not EMAIL.fullmatch(address) or re.search(r'[\x00-\x1f\x7f]', unquote(address))):
        raise ValueError('public_email: invalid email address')
    return address


def safe_link(value):
    if isinstance(value, str) and re.search(r'[\s\\]', value):
        raise ValueError('link URL: whitespace or backslash is not permitted')
    url = plain(value, 'link URL', 2048)
    if re.search(r'[\s\\]', url):
        raise ValueError('link URL: whitespace or backslash is not permitted')
    parsed = urlsplit(url)
    if parsed.scheme == 'mailto':
        if parsed.query or parsed.fragment or not EMAIL.fullmatch(parsed.path) or re.search(r'[\x00-\x1f\x7f]', unquote(parsed.path)):
            raise ValueError('link URL: mailto must contain one plain email address')
    elif parsed.scheme == 'https':
        if not parsed.hostname or parsed.username or parsed.password:
            raise ValueError('link URL: HTTPS host is required; credentials are not permitted')
        try:
            parsed.port
        except ValueError as exc:
            raise ValueError('link URL: invalid port') from exc
    else:
        raise ValueError('link URL: only HTTPS or mailto is permitted')
    return url


def public_image(value, member_id, root):
    path = plain(value, 'image path', 400).removeprefix('./')
    if not path:
        return ''
    pattern = r'assets/images/member-projects/' + re.escape(member_id) + r'/[A-Za-z0-9_-]+\.(?:jpg|jpeg|png|webp)'
    if not re.fullmatch(pattern, path, re.I):
        raise ValueError(f'{member_id}: image must be an exported member asset')
    resolved = (root / path).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f'{member_id}: image escapes the site directory') from exc
    if not resolved.is_file():
        raise ValueError(f'{member_id}: exported image does not exist: {path}')
    return path


def payload(value, member_id, root):
    if not isinstance(value, dict):
        raise ValueError(f'{member_id}: content must be an object')
    allowed = set(LONG_FIELDS) | {'public_email', 'avatar_path', 'links', 'projects', 'papers'}
    if set(value) - allowed:
        raise ValueError(f'{member_id}: unknown profile fields: {sorted(set(value)-allowed)}')
    out = {key: plain(value.get(key, ''), key) for key in LONG_FIELDS}
    out['public_email'] = public_email(value.get('public_email', ''))
    out['avatar_path'] = public_image(value.get('avatar_path', ''), member_id, root)
    for key, maximum in [('links', 5), ('projects', 3), ('papers', 30)]:
        records = value.get(key, [])
        if not isinstance(records, list) or len(records) > maximum:
            raise ValueError(f'{member_id}: {key} must be a list of at most {maximum} items')
        out[key] = []
        for item in records:
            if not isinstance(item, dict):
                raise ValueError(f'{member_id}: {key} item must be an object')
            if key == 'links':
                if set(item) - {'label', 'url'}:
                    raise ValueError(f'{member_id}: unknown link fields')
                label = plain(item.get('label', ''), 'link label', 200)
                if not label:
                    raise ValueError(f'{member_id}: link label is required')
                out[key].append({'label': label, 'url': safe_link(item.get('url', ''))})
            elif key == 'projects':
                if set(item) - set(PROJECT_FIELDS):
                    raise ValueError(f'{member_id}: unknown project fields')
                project = {field: plain(item.get(field, ''), field, 200 if field in ('id', 'title', 'title_en') else 3000) for field in PROJECT_FIELDS}
                if not (project['title'] or project['title_en']):
                    raise ValueError(f'{member_id}: project title is required')
                project['image_path'] = public_image(project['image_path'], member_id, root)
                if project['image_path'] and (not (project['image_caption'] or project['image_caption_en']) or not project['image_source']):
                    raise ValueError(f'{member_id}: project image requires a caption and source')
                out[key].append(project)
            else:
                if set(item) - set(PAPER_FIELDS):
                    raise ValueError(f'{member_id}: unknown paper fields')
                paper = {field: plain(str(item.get(field, '')) if field == 'year' and isinstance(item.get(field), int) else item.get(field, ''), field, {'title':1000,'journal':200,'authors':2000,'doi':255}.get(field,3000)) for field in PAPER_FIELDS}
                if not paper['title']:
                    raise ValueError(f'{member_id}: paper title is required')
                if paper['doi'] and not DOI.fullmatch(paper['doi']):
                    raise ValueError(f'{member_id}: DOI must be a DOI identifier, not a URL')
                if paper['context'] not in ('in_lab', 'before_lab'):
                    raise ValueError(f'{member_id}: paper context must be in_lab or before_lab')
                if paper['year'] and not re.fullmatch(r'\d{4}', paper['year']):
                    raise ValueError(f'{member_id}: paper year must contain four digits')
                out[key].append(paper)
    return out


def load_profiles(root: Path, members):
    data = json.loads((root / 'data/member-profiles.json').read_text(encoding='utf-8'))
    if not isinstance(data, dict) or set(data) != {'schemaVersion', 'profiles'} or data.get('schemaVersion') != 1 or not isinstance(data.get('profiles'), dict):
        raise ValueError('member-profiles.json: expected schemaVersion 1 and a profiles object')
    valid_ids = {person['id'] for person in members}
    out = {}
    for member_id, record in data['profiles'].items():
        if member_id not in valid_ids or not MEMBER_ID.fullmatch(member_id):
            raise ValueError(f'Public profile is not in the current roster: {member_id}')
        if not isinstance(record, dict) or set(record) != {'version', 'publishedAt', 'content'}:
            raise ValueError(f'{member_id}: profile record must contain version, publishedAt and content')
        try:
            UUID(plain(record.get('version', ''), 'version', 200))
            published = datetime.fromisoformat(plain(record.get('publishedAt', ''), 'publishedAt', 200).replace('Z', '+00:00'))
            if published.tzinfo is None:
                raise ValueError('timestamp must include a timezone')
        except ValueError as exc:
            raise ValueError(f'{member_id}: invalid publication version or timestamp') from exc
        out[member_id] = {'version': record.get('version', ''), 'publishedAt': record.get('publishedAt', ''), 'content': payload(record.get('content', {}), member_id, root)}
    return out

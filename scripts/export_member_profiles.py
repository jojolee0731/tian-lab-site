#!/usr/bin/env python3
"""Export approved member snapshots, never drafts, into public static assets.

Requires SUPABASE_URL and SUPABASE_SECRET_KEY in the server environment.
Legacy SUPABASE_SERVICE_ROLE_KEY is accepted as a migration fallback.
Private images are fetched from the fixed member-drafts bucket, fully decoded,
checked and re-encoded without metadata before any public catalog is replaced.
The exporter does not grant approval: export_public_profiles() is a service-only
RPC that returns the backend's immutable, administrator-approved snapshots.
"""
from __future__ import annotations

import argparse
from datetime import datetime
from io import BytesIO
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import UUID
import warnings

from member_profile import payload as validate_public_payload

ROOT = Path(__file__).resolve().parents[1]
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_EXPORT_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000
IMAGE_PATH = re.compile(r'(member-\d{2,})/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\.(jpg|png|webp)')


class ExportError(ValueError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Do not forward a service-role credential to a redirect target.
        return None


def service_url(value):
    if not isinstance(value, str) or re.search(r'[\s\\]', value):
        raise ExportError('SUPABASE_URL is missing or invalid')
    parsed = urlsplit(value)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('', '/'):
        raise ExportError('SUPABASE_URL must be an HTTPS origin without credentials or a path')
    try:
        parsed.port
    except ValueError as exc:
        raise ExportError('SUPABASE_URL has an invalid port') from exc
    return value.rstrip('/')


class SupabaseSource:
    def __init__(self, url, key):
        self.url = service_url(url)
        if not isinstance(key, str) or not key or re.search(r'\s', key):
            raise ExportError('The server-side Supabase secret key is not configured')
        if key.startswith('sb_publishable_'):
            raise ExportError('The exporter requires a server-only secret key, not a public key')
        self.headers = {'apikey': key}
        # New secret keys are not JWTs. Only legacy keys use Bearer authorization.
        if not key.startswith('sb_secret_'):
            self.headers['Authorization'] = 'Bearer ' + key
        self.opener = build_opener(NoRedirect)

    def request(self, suffix, maximum, post=False):
        headers = dict(self.headers)
        if post:
            headers['Content-Type'] = 'application/json'
        request = Request(self.url + suffix, data=b'{}' if post else None, headers=headers, method='POST' if post else 'GET')
        try:
            with self.opener.open(request, timeout=30) as response:
                size = response.headers.get('Content-Length')
                if size is not None and (not size.isdigit() or int(size) > maximum):
                    raise ExportError('Approved export response exceeds the allowed size')
                result = response.read(maximum + 1)
        except HTTPError as exc:
            raise ExportError(f'Approved export service returned HTTP {exc.code}; no public update was applied') from None
        except (URLError, TimeoutError) as exc:
            raise ExportError('Approved export service is unavailable; no public update was applied') from None
        if len(result) > maximum:
            raise ExportError('Approved export response exceeds the allowed size')
        return result

    def profiles(self):
        raw = self.request('/rest/v1/rpc/export_public_profiles', MAX_EXPORT_BYTES, post=True)
        try:
            return json.loads(raw)
        except (UnicodeError, ValueError):
            raise ExportError('Approved export service returned invalid JSON') from None

    def image(self, path):
        # Paths were validated against an owning member before this method runs.
        if not IMAGE_PATH.fullmatch(path):
            raise ExportError('Invalid private image path')
        return self.request('/storage/v1/object/authenticated/member-drafts/' + quote(path, safe='/'), MAX_IMAGE_BYTES)


def checked_image_path(value, member_id):
    if not isinstance(value, str):
        raise ExportError('Image path must be text')
    if not value:
        return ''
    match = IMAGE_PATH.fullmatch(value)
    if not match or match.group(1) != member_id:
        raise ExportError(f'{member_id}: image path must reference this member’s immutable upload')
    return value


def sanitize_image(data, extension):
    from PIL import Image, ImageOps, UnidentifiedImageError
    if not isinstance(data, bytes) or not data or len(data) > MAX_IMAGE_BYTES:
        raise ExportError('Image must contain at most 5 MB of raster data')
    expected = {'jpg': 'JPEG', 'png': 'PNG', 'webp': 'WEBP'}[extension]
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(data), formats=['JPEG', 'PNG', 'WEBP']) as probe:
                if probe.format != expected:
                    raise ExportError('Image extension does not match its decoded format')
                if probe.width * probe.height > MAX_IMAGE_PIXELS or max(probe.size) > 10000:
                    raise ExportError('Image dimensions exceed the public upload limit')
                if getattr(probe, 'n_frames', 1) != 1:
                    raise ExportError('Animated images are not accepted')
                probe.verify()
            with Image.open(BytesIO(data), formats=[expected]) as source:
                source.load()
                oriented = ImageOps.exif_transpose(source)
                mode = 'RGBA' if expected != 'JPEG' and ('A' in oriented.getbands() or 'transparency' in oriented.info) else 'RGB'
                pixels = oriented.convert(mode)
                # Fresh pixels remove EXIF, comments, GPS and embedded private data.
                clean = Image.frombytes(mode, pixels.size, pixels.tobytes())
                result = BytesIO()
                options = {'quality': 95, 'optimize': True} if expected == 'JPEG' else {'lossless': True} if expected == 'WEBP' else {'optimize': True}
                clean.save(result, format=expected, **options)
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ExportError('Image could not be decoded safely as JPEG, PNG or WebP') from None
    output = result.getvalue()
    if len(output) > MAX_IMAGE_BYTES:
        raise ExportError('Decoded public image exceeds 5 MB; a smaller upload is required')
    return output


def safe_destination(root, relative):
    root = root.resolve()
    target = root / relative
    if not target.resolve().is_relative_to(root) or target.resolve() != target:
        raise ExportError('Public destination must not escape the site or traverse symlinks')
    return target


def prepare_export(raw, member_ids, fetch_image, stage):
    """Validate everything in an isolated staging directory before publishing files."""
    if not isinstance(raw, dict) or set(raw) != {'schemaVersion', 'profiles'} or type(raw['schemaVersion']) is not int or raw['schemaVersion'] != 1 or not isinstance(raw['profiles'], dict):
        raise ExportError('Approved RPC must return only schemaVersion 1 and profiles')
    public = {'schemaVersion': 1, 'profiles': {}}
    images = {}
    for member_id, record in raw['profiles'].items():
        if member_id not in member_ids or not re.fullmatch(r'member-\d{2,}', member_id):
            raise ExportError('Approved profile does not belong to the current public roster')
        if not isinstance(record, dict) or set(record) != {'version', 'publishedAt', 'content'}:
            raise ExportError(f'{member_id}: approved record has unexpected or missing metadata')
        try:
            version = str(UUID(record['version']))
            published = datetime.fromisoformat(record['publishedAt'].replace('Z', '+00:00'))
            if published.tzinfo is None:
                raise ValueError('timezone required')
        except (ValueError, TypeError, AttributeError):
            raise ExportError(f'{member_id}: approved version or timestamp is invalid') from None
        if not isinstance(record['content'], dict):
            raise ExportError(f'{member_id}: approved content must be an object')
        # Copy JSON fields only; no reference to a live draft object is retained.
        content = json.loads(json.dumps(record['content']))
        projects = content.get('projects', [])
        if not isinstance(projects, list) or len(projects) > 3 or any(not isinstance(p, dict) for p in projects):
            raise ExportError(f'{member_id}: at most three project objects are permitted')
        image_fields = [(content, 'avatar_path')] + [(project, 'image_path') for project in projects]
        for parent, field in image_fields:
            private = checked_image_path(parent.get(field, ''), member_id)
            if not private:
                parent[field] = ''
                continue
            relative = 'assets/images/member-projects/' + private
            if relative not in images:
                data = sanitize_image(fetch_image(private), private.rsplit('.', 1)[1])
                destination = safe_destination(stage, relative)
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(data)
                images[relative] = data
            parent[field] = relative
        content = validate_public_payload(content, member_id, stage)
        public['profiles'][member_id] = {'version': version, 'publishedAt': record['publishedAt'], 'content': content}
    return public, images


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(prefix='.' + path.name + '-', dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data)
        os.replace(temporary, path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def export_profiles(root, raw, fetch_image):
    roster = json.loads((root / 'data/people.json').read_text(encoding='utf-8'))['items']
    members = {person['id'] for person in roster}
    with tempfile.TemporaryDirectory(prefix='tianlab-approved-public-') as directory:
        public, images = prepare_export(raw, members, fetch_image, Path(directory))
        # Validate all final destinations before making the first public write.
        for relative in [*images, 'data/member-profiles.json']:
            safe_destination(root, relative)
        for relative, data in images.items():
            atomic_write(safe_destination(root, relative), data)
        encoded = (json.dumps(public, ensure_ascii=False, indent=2, sort_keys=True) + '\n').encode('utf-8')
        atomic_write(safe_destination(root, 'data/member-profiles.json'), encoded)
    return public, ['data/member-profiles.json', *sorted(images)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--manifest', type=Path, help='Write public file paths to a runner-temporary manifest, never to the site')
    args = parser.parse_args()
    root = args.root.resolve()
    if args.manifest and args.manifest.resolve().is_relative_to(root):
        parser.error('--manifest must be outside the public repository')
    try:
        source = SupabaseSource(os.environ.get('SUPABASE_URL', ''), os.environ.get('SUPABASE_SECRET_KEY') or os.environ.get('SUPABASE_SERVICE_ROLE_KEY', ''))
        public, paths = export_profiles(root, source.profiles(), source.image)
        if args.manifest:
            atomic_write(args.manifest.resolve(), (json.dumps(paths) + '\n').encode())
        print(f'Exported {len(public["profiles"])} approved profiles and {len(paths) - 1} validated public images.')
    except (ValueError, OSError, KeyError, ImportError) as exc:
        print(f'Export failed: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())

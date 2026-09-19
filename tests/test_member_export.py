"""Security and failure-boundary tests use temporary fixtures, never site data."""
from __future__ import annotations
import base64
from copy import deepcopy
from io import BytesIO
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import export_member_profiles as exporter
import member_publish_guard as guard
import check_site
from PIL import Image, PngImagePlugin

MEMBER = 'member-15'
UUID = '00000000-0000-4000-8000-000000000001'
PRIVATE = MEMBER + '/' + UUID + '.png'
PUBLIC = 'assets/images/member-projects/' + PRIVATE


def raster(fmt='PNG', **options):
    output = BytesIO()
    Image.new('RGB', (4, 4), 'white').save(output, format=fmt, **options)
    return output.getvalue()


def approved(content=None):
    return {'schemaVersion': 1, 'profiles': {MEMBER: {
        'version': UUID, 'publishedAt': '2026-09-19T10:00:00+00:00',
        'content': content or {'bio': 'An approved public description.', 'avatar_path': PRIVATE},
    }}}


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='member-export-test-')
        self.root = Path(self.temporary.name).resolve()
        (self.root / 'data').mkdir()
        (self.root / 'data/people.json').write_text(json.dumps({'items': [{'id': MEMBER}]}))
        self.catalog = self.root / 'data/member-profiles.json'
        self.catalog.write_text('{"schemaVersion":1,"profiles":{}}\n')

    def tearDown(self):
        self.temporary.cleanup()

    def export(self, value, image=None):
        return exporter.export_profiles(self.root, value, lambda path: raster() if image is None else image)

    def test_only_approved_whitelisted_content_and_real_image_are_exported(self):
        metadata = PngImagePlugin.PngInfo()
        metadata.add_text('private-location', 'This must not be published')
        document, manifest = self.export(approved(), raster(pnginfo=metadata))
        self.assertEqual(manifest, ['data/member-profiles.json', PUBLIC])
        self.assertEqual(document['profiles'][MEMBER]['content']['avatar_path'], PUBLIC)
        with Image.open(self.root / PUBLIC) as image:
            self.assertEqual(image.format, 'PNG')
            self.assertEqual(image.size, (4, 4))
            self.assertNotIn('private-location', image.info)
        self.assertNotIn('member-drafts', self.catalog.read_text())

    def test_unknown_private_fields_do_not_leak_and_failure_preserves_site(self):
        for mutate in (
            lambda doc: doc.update({'drafts': ['private']}),
            lambda doc: doc['profiles'][MEMBER].update({'reviewer_email': 'private@example.com'}),
            lambda doc: doc['profiles'][MEMBER]['content'].update({'account_email': 'private@example.com'}),
        ):
            document = approved(); mutate(document)
            before = self.catalog.read_bytes()
            with self.assertRaises(ValueError): self.export(document)
            self.assertEqual(self.catalog.read_bytes(), before)
            self.assertFalse((self.root / PUBLIC).exists())

    def test_cross_member_paths_traversal_and_non_roster_members_are_rejected(self):
        for path in ('member-16/' + UUID + '.png', '../secrets.png', MEMBER + '/%2e%2e/file.png', 'https://example.com/a.png'):
            with self.assertRaises(ValueError): self.export(approved({'avatar_path': path}))
        document = approved(); document['profiles']['member-99'] = document['profiles'].pop(MEMBER)
        with self.assertRaises(ValueError): self.export(document)

    def test_svg_disguise_mismatched_extension_and_size_limits(self):
        for data in (b'<svg><script>alert(1)</script></svg>', raster('JPEG'), b'x' * (exporter.MAX_IMAGE_BYTES + 1)):
            with self.assertRaises(ValueError): self.export(approved(), data)
        with patch.object(exporter, 'MAX_IMAGE_PIXELS', 8):
            with self.assertRaises(ValueError): self.export(approved())

    def test_https_mailto_and_doi_scope(self):
        for url in ('javascript:alert(1)', 'http://example.com', 'https://user:secret@example.com', 'mailto:person@example.com?bcc=other@example.com', 'mailto:person%0d%0aBCC:other@example.com'):
            with self.assertRaises(ValueError): self.export(approved({'links': [{'label': 'link', 'url': url}]}))
        for doi in ('https://doi.org/10.1000/test', '10.1000/test\nprivate', '10.1000/<script>', '10.1000/a?x', '10.1000/a#x', '10.1000/a\\b', '10.1000/a"b', "10.1000/a'b"):
            with self.assertRaises(ValueError): self.export(approved({'papers': [{'title': 'A paper', 'doi': doi, 'context': 'in_lab'}]}))
        doc, _ = self.export(approved({'links': [{'label': 'Profile', 'url': 'https://example.com/profile'}], 'papers': [{'title': 'A paper', 'doi': '10.1000/test', 'context': 'before_lab', 'year': 2025}]}))
        self.assertEqual(doc['profiles'][MEMBER]['content']['papers'][0]['context'], 'before_lab')

    def test_paper_limits_and_project_image_provenance(self):
        paper = {'title': 'T' * 1000, 'journal': 'J' * 200, 'authors': 'A' * 2000, 'doi': '10.1000/' + 'x' * 247, 'context': 'in_lab'}
        self.export(approved({'papers': [paper]}))
        for field in ('title', 'journal', 'authors', 'doi'):
            too_long = dict(paper); too_long[field] += 'x'
            with self.assertRaises(ValueError): self.export(approved({'papers': [too_long]}))
        project = {'title': 'An approved project', 'image_path': PRIVATE, 'image_caption_en': 'Approved diagram', 'image_source': 'Original author-provided diagram.'}
        self.export(approved({'projects': [project]}))
        for missing in ('image_caption_en', 'image_source'):
            incomplete = dict(project); incomplete.pop(missing)
            with self.assertRaises(ValueError): self.export(approved({'projects': [incomplete]}))

    def test_modern_secret_uses_apikey_without_forged_bearer(self):
        modern = exporter.SupabaseSource('https://example.supabase.co', 'sb_secret_fixture')
        self.assertEqual(modern.headers, {'apikey': 'sb_secret_fixture'})
        legacy = exporter.SupabaseSource('https://example.supabase.co', 'legacy.jwt.fixture')
        self.assertEqual(legacy.headers['Authorization'], 'Bearer legacy.jwt.fixture')
        with self.assertRaises(ValueError): exporter.SupabaseSource('https://example.supabase.co', 'sb_publishable_fixture')

    def test_unconfigured_service_and_symlink_destinations_fail(self):
        for url in ('', 'http://localhost', 'https://user:password@project.supabase.co', 'https://project.supabase.co/path'):
            with self.assertRaises(ValueError): exporter.SupabaseSource(url, 'test')
        with self.assertRaises(ValueError): exporter.SupabaseSource('https://project.supabase.co', '')
        outside = self.root / 'other'; outside.mkdir()
        (self.root / 'assets').symlink_to(outside, target_is_directory=True)
        with self.assertRaises(ValueError): self.export(approved())

    def test_commit_scope_excludes_configuration_drafts_and_other_member_assets(self):
        allowed = guard.allowed_commit_paths(self.root, ['data/member-profiles.json', PUBLIC])
        self.assertIn('zh/person-member-15.html', allowed)
        for path in ('members/config.json', 'data/site.json', 'supabase/config.toml', '.env', 'data/drafts.json'):
            self.assertNotIn(path, allowed)
            with self.assertRaises(ValueError): guard.allowed_commit_paths(self.root, ['data/member-profiles.json', path])
        with self.assertRaises(ValueError): guard.allowed_commit_paths(self.root, ['data/member-profiles.json', PUBLIC.replace(MEMBER, 'member-99')])

    def test_actual_git_guard_stages_only_explicit_outputs(self):
        def git(*args):
            return subprocess.run(['git', *args], cwd=self.root, check=True, capture_output=True)
        git('init', '-q'); git('config', 'user.name', 'fixture'); git('config', 'user.email', 'fixture@example.com')
        git('add', 'data'); git('commit', '-qm', 'fixture')
        self.catalog.write_text('{"schemaVersion":1,"profiles":{}}\n ')
        (self.root / '.env').write_text('PRIVATE=fixture-not-a-real-secret')
        with self.assertRaises(ValueError): guard.stage_public_changes(self.root, ['data/member-profiles.json'])
        self.assertEqual(git('diff', '--cached', '--name-only').stdout, b'')
        (self.root / '.env').unlink()
        self.assertEqual(guard.stage_public_changes(self.root, ['data/member-profiles.json']), 1)
        self.assertEqual(git('diff', '--cached', '--name-only').stdout.strip(), b'data/member-profiles.json')

    def test_public_configuration_rejects_service_keys(self):
        path = self.root / 'config.json'
        def config(key, **extra):
            path.write_text(json.dumps({'enabled': True, 'supabaseUrl': 'https://example.supabase.co', 'supabaseAnonKey': key, **extra}))
        for role in ('service_role', 'authenticated'):
            claims = base64.urlsafe_b64encode(json.dumps({'role': role}).encode()).decode().rstrip('=')
            config('header.' + claims + '.signature')
            with self.assertRaises(ValueError): guard.validate_public_config(path)
        config('sb_secret_not_allowed')
        with self.assertRaises(ValueError): guard.validate_public_config(path)
        config('sb_publishable_example', serviceKey='private')
        with self.assertRaises(ValueError): guard.validate_public_config(path)
        config('sb_publishable_example'); guard.validate_public_config(path)

    def test_exact_person_and_publication_decisions_preserve_everything_else(self):
        baseline = {'people': [{'name': 'Original member'}], 'publications': [{'doi': '10.1000/original'}]}
        datasets = {'people': [{'id': 'member-01', 'name': 'Original member'}, {'id': 'member-35', 'name': 'New member'}], 'publications': [{'doi': '10.1000/original'}, {'doi': '10.1000/selected'}]}
        decisions = {'addedPeople': [{'id': 'member-35', 'name': 'New member', 'reason': 'Explicit user request'}]}
        selection = {'chosenDOIs': ['10.1000/selected']}
        def issues(data=datasets, choice=decisions):
            errors = []; check_site.check_preservation(baseline, data, choice, selection, errors.append)
            return errors
        self.assertEqual(issues(), [])
        changed = deepcopy(datasets); changed['people'][1]['name'] = 'Different person'
        self.assertTrue(issues(changed))
        changed = deepcopy(datasets); changed['people'].pop(0)
        self.assertTrue(issues(changed))
        changed = deepcopy(datasets); changed['people'].append({'id': 'member-36', 'name': 'Unapproved person'})
        self.assertTrue(issues(changed))
        changed = deepcopy(datasets); changed['publications'].append({'doi': '10.1000/unselected'})
        self.assertTrue(issues(changed))
        changed = deepcopy(datasets); changed['publications'].pop(0)
        self.assertTrue(issues(changed))
        reused = {'addedPeople': [{'id': 'member-01', 'name': 'Replacement', 'reason': 'Not a valid new ID'}]}
        self.assertTrue(issues(choice=reused))


if __name__ == '__main__':
    unittest.main()

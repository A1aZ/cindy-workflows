"""Behavior checks: real HTTP reads, consistent pages, no failed-export writes, upgrades."""
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import unittest
from urllib.parse import parse_qs, urlsplit
import zipfile

SOURCE = Path(__file__).resolve().parents[1] / 'skills/sausage-man-monitor'
sys.path.insert(0, str(SOURCE / 'scripts'))
import query
import package_skill as package


class WorkbenchFixture(BaseHTTPRequestHandler):
    flip = False
    empty = False
    changed = False
    bad_export = False
    requests = []

    def log_message(self, *args):
        pass

    def do_GET(self):
        cls = type(self)
        cls.requests.append(self.path)
        url = urlsplit(self.path)
        args = parse_qs(url.query)
        sha = 'b' * 64 if cls.changed else 'a' * 64
        if url.path == '/api/workflow/feedback/batches':
            data = {'current_snapshot': sha, 'batches': [
                {'id': 'current', 'snapshot': sha, 'current': True, 'source_count': 21, 'feedback_count': 21},
                {'id': 'old', 'snapshot': 'c' * 64, 'current': False}]}
        elif url.path == '/api/snapshot':
            data = {'publication': {'release_id': 'fixture', 'snapshot': {'sha256': sha}}, 'meta': {'known_limits': []}}
        elif url.path == '/api/workflow/state':
            data = {'schema': 'project.workflow.state.v1', 'contract': 'project.report.v1', 'reports': [{'id': 'published'}]}
        elif url.path == '/api/workflow/feedback/search':
            page = int(args['page'][0])
            total = 0 if cls.empty else 21
            data = {'batch': args['batch'][0], 'page': page, 'page_size': 20, 'total': total,
                    'sources': [{'id': str(i), 'text': 'synthetic fixture'} for i in range(page * 20, min(total, (page + 1) * 20))]}
            if cls.flip:
                cls.changed = True
        elif url.path == '/api/workflow/feedback/originals':
            data = {'snapshot_sha256': sha, 'sources': {i: {'text': 'synthetic fixture'} for i in args['ids'][0].split(',')}}
        elif url.path == '/api/export/manifest':
            data = {'sha256': 'wrong' if cls.bad_export else hashlib.sha256(b'{"fixture":true}').hexdigest()}
        elif url.path == '/api/export':
            return self.send_bytes(b'{"fixture":true}')
        elif url.path == '/reports/download/published/REPORT.md':
            return self.send_bytes(b'# synthetic fixture\n')
        else:
            self.send_response(404)
            self.end_headers()
            return
        self.send_bytes(json.dumps(data).encode())

    def send_bytes(self, raw):
        self.send_response(200)
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


class QueryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), WorkbenchFixture)
        cls.thread = threading.Thread(target=cls.server.serve_forever, kwargs={'poll_interval': 0.01}, daemon=True)
        cls.thread.start()
        cls.base = 'http://127.0.0.1:' + str(cls.server.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def setUp(self):
        WorkbenchFixture.flip = WorkbenchFixture.empty = WorkbenchFixture.changed = WorkbenchFixture.bad_export = False
        WorkbenchFixture.requests = []
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.config = Path(self.temp.name) / 'config.json'
        self.config.write_text(json.dumps({'base_url': self.base, 'timeout': 2}))

    def args(self, *args):
        return query.parser().parse_args(['--config', str(self.config), *args])

    def test_complete_search_pins_pages_and_preserves_count_meaning(self):
        value = query.run(self.args('search', '--all'))
        self.assertEqual((value['returned'], value['pages_read'], value['complete']), (21, 2, True))
        self.assertEqual(value['snapshot_sha256'], 'a' * 64)
        self.assertIn('索引', value['count_note'])
        self.assertEqual(len({s['id'] for s in value['sources']}), 21)

    def test_changed_release_does_not_return_mixed_pages(self):
        WorkbenchFixture.flip = True
        with self.assertRaisesRegex(query.WorkbenchError, '发布在读取期间'):
            query.run(self.args('search', '--all'))

    def test_page_limit_is_not_successful_partial_export(self):
        with self.assertRaisesRegex(query.WorkbenchError, 'max-pages'):
            query.run(self.args('search', '--all', '--max-pages', '1'))

    def test_empty_and_historical_batch(self):
        WorkbenchFixture.empty = True
        value = query.run(self.args('search', '--batch', 'old', '--all'))
        self.assertEqual(value['snapshot_sha256'], 'c' * 64)
        self.assertEqual(value['returned'], 0)
        self.assertTrue(value['complete'])

    def test_historical_originals_are_not_replaced_with_current(self):
        with self.assertRaisesRegex(query.WorkbenchError, '仅支持当前快照'):
            query.run(self.args('originals', '--ids', '1', '--snapshot', 'c' * 64))
        self.assertFalse(any('/originals' in path for path in WorkbenchFixture.requests))

    def test_export_hash_failure_writes_nothing(self):
        WorkbenchFixture.bad_export = True
        output = Path(self.temp.name) / 'export.json'
        with self.assertRaisesRegex(query.WorkbenchError, '哈希不一致'):
            query.run(self.args('export', '--output', str(output)))
        self.assertFalse(output.exists())

    def test_report_download_and_external_rejection(self):
        result = query.run(self.args('reports'))
        link = result['reports'][0]['downloads']['markdown']
        output = Path(self.temp.name) / 'report.md'
        saved = query.run(self.args('download', '--url', link, '--output', str(output)))
        self.assertEqual(saved['sha256'], hashlib.sha256(output.read_bytes()).hexdigest())
        with self.assertRaises(query.WorkbenchError):
            query.run(self.args('download', '--url', 'https://example.invalid/media/x', '--output', str(output)))

    def test_doctor_checks_live_identity(self):
        result = query.run(self.args('doctor'))
        self.assertTrue(result['ok'])
        self.assertEqual(result['release_id'], 'fixture')

    def test_configure_preserves_existing_settings(self):
        self.config.write_text(json.dumps({'base_url': self.base, 'timeout': 2, 'project_root': '/example/project'}))
        query.run(self.args('configure', '--base-url', self.base))
        saved = json.loads(self.config.read_text())
        self.assertEqual(saved['project_root'], '/example/project')


class DistributionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source'
        shutil.copytree(SOURCE, self.source)
        self.target = self.root / 'installed' / package.NAME

    def test_preview_has_no_writes_then_update_and_rollback_preserve_local_files(self):
        package.install(self.source, self.target)
        self.assertFalse(self.target.parent.exists())
        package.install(self.source, self.target, apply=True)
        (self.target / 'personal.local.json').write_text('{"keep":1}')
        old_version = package.verify(self.target)['version']
        package.seal(self.source, '1.0.1')
        updated = package.install(self.source, self.target, apply=True)
        self.assertEqual(package.verify(self.target)['version'], '1.0.1')
        (self.target / 'personal.local.json').write_text('{"keep":2}')
        package.rollback(self.target, updated['backup'], apply=True)
        self.assertEqual(package.verify(self.target)['version'], old_version)
        self.assertEqual(json.loads((self.target / 'personal.local.json').read_text())['keep'], 2)

    def test_local_edit_conflict_and_idempotent_install(self):
        package.install(self.source, self.target, apply=True)
        self.assertFalse(package.install(self.source, self.target, apply=True)['changed'])
        path = self.target / 'SKILL.md'
        changed = path.read_text(encoding='utf-8') + '\nlocal edit\n'
        path.write_text(changed, encoding='utf-8')
        with self.assertRaisesRegex(ValueError, '本地修改'):
            package.install(self.source, self.target, apply=True)
        self.assertEqual(path.read_text(encoding='utf-8'), changed)

    def test_legacy_adoption_and_rollback(self):
        self.target.mkdir(parents=True)
        (self.target / 'SKILL.md').write_text('legacy')
        with self.assertRaisesRegex(ValueError, 'adopt-existing'):
            package.install(self.source, self.target, apply=True)
        result = package.install(self.source, self.target, apply=True, adopt=True)
        package.rollback(self.target, result['backup'], apply=True)
        self.assertEqual((self.target / 'SKILL.md').read_text(), 'legacy')
        self.assertFalse((self.target / 'PACKAGE.json').exists())

    def test_removed_old_package_file_restores_on_rollback(self):
        package.install(self.source, self.target, apply=True)
        (self.target / 'obsolete.txt').write_text('old')
        manifest = package.read(self.target / 'PACKAGE.json')
        manifest['files']['obsolete.txt'] = package.digest(self.target / 'obsolete.txt')
        package.write(self.target / 'PACKAGE.json', manifest)
        result = package.install(self.source, self.target, apply=True)
        self.assertFalse((self.target / 'obsolete.txt').exists())
        package.rollback(self.target, result['backup'], apply=True)
        self.assertEqual((self.target / 'obsolete.txt').read_text(), 'old')

    def test_archive_only_contains_manifest_files_and_is_reproducible(self):
        (self.source / 'private.local.json').write_text('{"runtime":true}')
        a, b = self.root / 'a.zip', self.root / 'b.zip'
        package.pack(self.source, a)
        package.pack(self.source, b)
        self.assertEqual(package.digest(a), package.digest(b))
        with zipfile.ZipFile(a) as archive:
            self.assertEqual(set(archive.namelist()), {package.NAME + '/' + p for p in (*package.FILES, 'PACKAGE.json')})


if __name__ == '__main__':
    unittest.main()

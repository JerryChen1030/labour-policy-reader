import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('probe', ROOT / 'tools/rss_health_probe.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
SOURCE = {'id': 'synthetic', 'url': 'https://example.org/feed', 'allowed_hosts': ['example.org'], 'enabled': False}
BODY = b'<rss><channel><item><title>PRIVATE-NAME</title><description>private@example.org</description><link>https://example.org/a</link><pubDate>Mon, 05 Oct 2026 10:00:00 GMT</pubDate></item></channel></rss>'

class ProbeTests(unittest.TestCase):
    def test_metadata_only(self):
        r = p.probe(SOURCE, lambda *_: (BODY, SOURCE['url']))
        self.assertEqual(r['http_status'], 200)
        self.assertEqual(r['items'], 1)
        self.assertEqual(r['date_field_coverage']['published_parsed'], 1)
        self.assertEqual(r['last_date'], '2026-10-05T10:00:00Z')
        self.assertNotIn('PRIVATE-NAME', json.dumps(r))
        self.assertNotIn('private@example.org', json.dumps(r))
        self.assertFalse(SOURCE['enabled'])
    def test_unrecognized_dates_unknown(self):
        body = BODY.replace(b'pubDate', b'DateTime')
        r = p.probe(SOURCE, lambda *_: (body, SOURCE['url']))
        self.assertIsNone(r['last_date'])
        self.assertEqual(r['date_field_coverage']['published_raw'], 0)
    def test_parse_error_not_empty_success(self):
        r = p.probe(SOURCE, lambda *_: (b'<bad PRIVATE-NAME', SOURCE['url']))
        self.assertEqual(r['status'], 'error')
        self.assertEqual(r['http_status'], 200)
        self.assertIsNone(r['items'])
        self.assertNotIn('PRIVATE-NAME', json.dumps(r))
    def test_fetch_error_redacted(self):
        def fail(*_):
            raise RuntimeError('PRIVATE-NAME private@example.org')
        r = p.probe(SOURCE, fail)
        self.assertEqual(r['error'], 'probe_error')
        self.assertIsNone(r['http_status'])
        self.assertIsNone(r['items'])
    def test_http_error(self):
        def fail(*_):
            raise p.collector.FetchError('http_503')
        r = p.probe(SOURCE, fail)
        self.assertEqual(r['http_status'], 503)
        self.assertEqual(r['error'], 'http_503')
    def test_partial_links(self):
        body = BODY.replace(b'https://example.org/a', b'https://outside.example/a')
        r = p.probe(SOURCE, lambda *_: (body, SOURCE['url']))
        self.assertEqual((r['status'], r['items'], r['skipped_items']), ('partial', 0, 1))
    def test_workflow_manual_read_only(self):
        w = (ROOT / '.github/workflows/manual-rss-health.yml').read_text()
        self.assertIn('  workflow_dispatch:\n', w)
        for banned in ('schedule:', 'push:', 'pull_request:', 'secrets.', 'upload-artifact', 'contents: write', 'git push'):
            self.assertNotIn(banned, w)
        self.assertIn('runs-on: ubuntu-latest', w)
        self.assertIn('timeout-minutes: 5', w)
        self.assertIn('persist-credentials: false', w)
    def test_sources_remain_disabled(self):
        sources = json.loads((ROOT / 'collector/sources.json').read_text())['sources']
        self.assertEqual(tuple(s['id'] for s in sources), p.SOURCE_IDS)
        self.assertTrue(all(s['enabled'] is False for s in sources))

if __name__ == '__main__':
    unittest.main()

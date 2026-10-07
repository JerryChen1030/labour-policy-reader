"""Synthetic payloads only; public health receipts must not expose source text."""
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('diagnostic_probe', ROOT / 'tools/rss_health_probe.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
SOURCE = {'id': 'tw-wda-news', 'url': 'https://example.org/feed', 'allowed_hosts': ['example.org']}


class SourceDiagnosticTests(unittest.TestCase):
    def test_wda_local_date_coverage_is_not_utc(self):
        body = (ROOT / 'collector/tests/fixtures/wda-local-date.xml').read_bytes()
        result = p.probe(SOURCE, lambda *_: (body, SOURCE['url']))
        self.assertEqual(result['status'], 'ok')
        self.assertEqual(result['date_field_coverage']['published_local'], 1)
        self.assertEqual(result['date_field_coverage']['published_parsed'], 0)
        self.assertEqual(result['date_status'], 'source_local_timezone_unknown')
        self.assertIsNone(result['last_date'])
        self.assertEqual(result['last_source_local_date'], '2024-02-29')
        self.assertNotIn('Synthetic', json.dumps(result))
        self.assertNotIn('20240229T110500', json.dumps(result))

    def test_reason_codes_preserve_security_checks(self):
        cases = [(b'<html><body>PRIVATE-CANARY</body></html>', 'not_feed'),
                 (b'<!DOCTYPE html><html>PRIVATE-CANARY</html>', 'xml_dtd_or_entities_forbidden'),
                 (b'<!DOCTYPE rss [<!ENTITY e "PRIVATE-CANARY">]><rss/>', 'xml_dtd_or_entities_forbidden'),
                 ('<rss>PRIVATE-CANARY</rss>'.encode('utf-16'), 'xml_nul_encoding_forbidden'),
                 (b'<rss/>', 'rss_channel_missing')]
        for body, expected in cases:
            with self.subTest(expected=expected):
                result = p.probe(SOURCE, lambda *_: (body, SOURCE['url']))
                self.assertEqual(result['status'], 'error')
                self.assertEqual(result['error'], expected)
                self.assertIsNone(result['items'])
                self.assertNotIn('PRIVATE-CANARY', json.dumps(result))

    def test_arbitrary_parse_exception_code_redacted(self):
        def fail(*_):
            raise p.collector.FeedParseError('PRIVATE-CANARY')
        result = p.probe(SOURCE, fail)
        self.assertEqual(result['error'], 'feed_parse_error')
        self.assertNotIn('PRIVATE-CANARY', json.dumps(result))

    def test_default_fetch_collects_only_allowlisted_mime(self):
        body = b'<rss><channel/></rss>'
        def fetch(url, hosts, metadata=None):
            metadata['content_type'] = 'text/xml'
            return body, url
        with patch.object(p.collector, 'fetch', fetch):
            result = p.probe(SOURCE)
        self.assertEqual(result['content_type'], 'text/xml')
        self.assertEqual(result['date_status'], 'empty_feed')

    def test_transport_header_is_allowlisted_before_logging(self):
        class Response:
            status = 200
            body = b'<rss><channel/></rss>'
            def getheader(self, name, default=None):
                return 'PRIVATE-CANARY; private@example.org' if name == 'Content-Type' else default
            def read1(self, size):
                value, self.body = self.body[:size], self.body[size:]
                return value
        class Connection:
            def __init__(self, *args): pass
            def request(self, *args, **kwargs): pass
            def getresponse(self): return Response()
            def close(self): pass
        with patch.object(p.collector, 'PinnedHTTPS', Connection), \
             patch.object(p.collector, 'addresses', return_value=['8.8.8.8']):
            result = p.probe(SOURCE)
        self.assertEqual(result['content_type'], 'other_or_missing')
        self.assertNotIn('PRIVATE-CANARY', json.dumps(result))
        self.assertNotIn('private@example.org', json.dumps(result))

    def test_missing_dates_are_explicitly_incomplete(self):
        body = b'<rss><channel><item><link>https://example.org/a</link></item></channel></rss>'
        result = p.probe(SOURCE, lambda *_: (body, SOURCE['url']))
        self.assertEqual(result['date_status'], 'incomplete_or_unknown')
        self.assertIsNone(result['last_date'])
        self.assertIsNone(result['last_source_local_date'])


if __name__ == '__main__':
    unittest.main()

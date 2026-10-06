"""Offline tests; every feed/example is synthetic, not policy evidence."""
import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import collector as c

HERE = Path(__file__).parent
SOURCE = {'id':'synthetic','url':'https://example.org/feed','allowed_hosts':['example.org'],'enabled':True}
NOW = '2026-10-05T09:00:00Z'
RSS = (HERE/'fixtures/rss.xml').read_bytes()
ATOM = (HERE/'fixtures/atom.xml').read_bytes()


class ParserTests(unittest.TestCase):
    def rows(self, body=RSS):
        return c.parse_feed(body, SOURCE, NOW)[0]

    def test_rss_happy(self):
        row = self.rows()[0]
        self.assertEqual(row['canonical_url'], 'https://example.org/policy?id=1')
        self.assertEqual(row['published_at'], '2026-10-05T08:00:00Z')
        self.assertEqual(row['summary'], 'Synthetic text only')
        self.assertEqual(row['status'], 'pending')

    def test_atom_separate_dates(self):
        row = self.rows(ATOM)[0]
        self.assertEqual(row['published_at'], '2026-10-01T01:00:00Z')
        self.assertEqual(row['updated_at'], '2026-10-05T01:00:00Z')

    def test_rdf(self):
        body = b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns="http://purl.org/rss/1.0/" xmlns:dc="http://purl.org/dc/elements/1.1/"><item><title>Synthetic RDF</title><link>https://example.org/rdf</link><dc:date>2026-10-01T00:00:00Z</dc:date></item></rdf:RDF>'
        self.assertEqual(self.rows(body)[0]['published_at'], '2026-10-01T00:00:00Z')

    def test_empty_valid_feed(self):
        self.assertEqual(self.rows(b'<rss><channel/></rss>'), [])

    def test_missing_channel(self):
        with self.assertRaises(ValueError): self.rows(b'<rss/>')

    def test_change_beyond_summary_limit(self):
        prefix = b'x' * 2100
        first = self.rows(RSS.replace(b'Synthetic text only', prefix+b'first'))[0]
        second = self.rows(RSS.replace(b'Synthetic text only', prefix+b'second'))[0]
        self.assertEqual(first['summary'], second['summary'])
        self.assertNotEqual(first['content_hash'], second['content_hash'])

    def test_unknown_date_not_fetch_date(self):
        self.assertIsNone(self.rows(RSS.replace(b'Mon, 05 Oct 2026 08:00:00 GMT', b'unknown'))[0]['published_at'])

    def test_datetime_offset_overflow_is_unknown(self):
        for raw in ['0001-01-01T00:00:00+01:00', '9999-12-31T23:59:59-01:00']:
            with self.subTest(raw=raw): self.assertIsNone(c.date(raw))

    def test_timezone_required(self):
        self.assertIsNone(c.date('2026-10-05'))
        self.assertIsNone(c.date('2026-10-05T01:00:00'))

    def test_malformed(self):
        with self.assertRaises(c.ET.ParseError): self.rows(b'<rss>')

    def test_html_is_error_not_empty_feed(self):
        with self.assertRaises(ValueError): self.rows(b'<html/>')

    def test_entity_rejected(self):
        with self.assertRaises(ValueError): self.rows(b'<!DOCTYPE rss [<!ENTITY e "text">]><rss/>')

    def test_null_encoding_rejected(self):
        with self.assertRaises(ValueError): self.rows('<rss/>'.encode('utf-16'))

    def test_size_limit(self):
        with self.assertRaises(ValueError): self.rows(b'x'*(c.MAX_BYTES+1))

    def test_unapproved_item_host_skipped(self):
        rows, skipped = c.parse_feed(RSS.replace(b'example.org/policy', b'evil.example/policy'), SOURCE, NOW)
        self.assertEqual((rows, skipped), ([], 1))

    def test_dedup(self):
        rows, dropped = c.merge(self.rows(), self.rows(), NOW)
        self.assertEqual(len(rows), 1)
        self.assertEqual(dropped, 0)

    def test_changed_content_retains_versions(self):
        changed = self.rows(RSS.replace(b'Synthetic text only', b'Synthetic revised text'))
        rows, _ = c.merge(self.rows(), changed, NOW)
        self.assertEqual(len(rows), 2)
        self.assertEqual(len({r['document_id'] for r in rows}), 1)
        self.assertEqual(len({r['content_hash'] for r in rows}), 2)

    def test_refresh_never_approves(self):
        old = self.rows(); old[0]['status'] = 'approved'
        rows, _ = c.merge(old, self.rows(), NOW)
        self.assertEqual(rows[0]['status'], 'pending')

    def test_retention(self):
        old = self.rows(); old[0]['last_seen_at'] = '2025-01-01T00:00:00Z'
        self.assertEqual(c.merge(old, [], NOW), ([], 1))

    def test_queue_cap(self):
        rows = [dict(self.rows()[0], id=str(i)) for i in range(c.MAX_ITEMS+1)]
        kept, dropped = c.merge([], rows, NOW)
        self.assertEqual((len(kept), dropped), (c.MAX_ITEMS, 1))


class SecurityTests(unittest.TestCase):
    def test_bad_urls(self):
        for url in ['http://example.org/x','https://example.org:444/x','https://user:pw@example.org/x',
                    'https://evil.example/x','https://example.org.evil/x','https://127.0.0.1/x',
                    'https://example.org/\nheader']:
            with self.subTest(url=url), self.assertRaises(ValueError): c.canonical(url, ['example.org','127.0.0.1'])

    def test_private_dns(self):
        for ip in ['127.0.0.1','169.254.169.254','10.0.0.1','::1','fc00::1']:
            with self.subTest(ip=ip), patch('socket.getaddrinfo',return_value=[(0,0,0,'',(ip,443))]), self.assertRaises(ValueError):
                c.addresses('example.org')

    def test_mixed_dns_rejected(self):
        with patch('socket.getaddrinfo',return_value=[(0,0,0,'',('8.8.8.8',443)),(0,0,0,'',('10.0.0.1',443))]), self.assertRaises(ValueError): c.addresses('example.org')

    def test_public_dns(self):
        with patch('socket.getaddrinfo',return_value=[(0,0,0,'',('8.8.8.8',443))]):
            self.assertEqual(c.addresses('example.org'), ['8.8.8.8'])

    def test_redirect_revalidation(self):
        class Response:
            status = 302
            def getheader(self, name, default=None): return 'https://127.0.0.1/secret' if name == 'Location' else default
        class Connection:
            def __init__(self,*args): pass
            def request(self,*args,**kwargs): pass
            def getresponse(self): return Response()
            def close(self): pass
        with patch.object(c,'PinnedHTTPS',Connection), patch.object(c,'addresses',return_value=['8.8.8.8']), self.assertRaises(ValueError):
            c.fetch(SOURCE['url'], SOURCE['allowed_hosts'])

    def test_fetch_limits_and_errors(self):
        class Response:
            status = 200
            headers = {}
            body = b'<rss><channel/></rss>'
            def getheader(self, name, default=None): return self.headers.get(name, default)
            def read1(self, size):
                chunk, self.body = self.body[:size], self.body[size:]
                return chunk
        response = Response()
        class Connection:
            def __init__(self,*args): pass
            def request(self,*args,**kwargs): pass
            def getresponse(self): return response
            def close(self): pass
        with patch.object(c,'PinnedHTTPS',Connection), patch.object(c,'addresses',return_value=['8.8.8.8']):
            self.assertEqual(c.fetch(SOURCE['url'], SOURCE['allowed_hosts'])[0], b'<rss><channel/></rss>')
            for headers, status, code in [({'Content-Length':str(c.MAX_BYTES+1)},200,'response_too_large'),
                                          ({'Content-Encoding':'gzip'},200,'unsupported_content_encoding'),
                                          ({'Retry-After':'7200'},429,'http_429'),
                                          ({'Location':'https://example.org/again'},302,'redirect_limit_or_missing_location')]:
                response.headers, response.status = headers, status
                with self.subTest(code=code), self.assertRaises(c.FetchError) as found:
                    c.fetch(SOURCE['url'], SOURCE['allowed_hosts'])
                self.assertEqual(found.exception.code, code)
            response.status, response.headers, response.body = 200, {}, b'x'*(c.MAX_BYTES+1)
            with self.assertRaises(c.FetchError): c.fetch(SOURCE['url'], SOURCE['allowed_hosts'])

    def test_retry_after(self):
        self.assertEqual(c.retry_seconds('7200',0),7200)
        self.assertEqual(c.retry_seconds('garbage',0),0)
        self.assertEqual(c.retry_seconds('-2',0),0)


class CollectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.manifest = self.root/'sources.json'
        self.manifest.write_text(json.dumps({'schema_version':1,'sources':[SOURCE]}))
        self.state = self.root/'private-state'

    def tearDown(self): self.temp.cleanup()

    def test_collect_no_public_mutation(self):
        public = self.root/'data.json'; public.write_text('{"approved":true}')
        result, failed = c.collect(self.manifest, self.state, lambda *a:(RSS,SOURCE['url']))
        self.assertFalse(failed)
        self.assertEqual(len(result['items']),1)
        self.assertEqual(public.read_text(),'{"approved":true}')
        self.assertFalse((self.state/'.collector.lock').exists())

    def test_429_retains_queue_and_reports_error(self):
        result, _ = c.collect(self.manifest,self.state,lambda *a:(RSS,SOURCE['url']))
        result['source_runs']['synthetic']['next_attempt_epoch'] = 0
        c.atomic_json(self.state/'candidates.json',result)
        def fail(*args): raise c.FetchError('http_429','7200')
        result, failed = c.collect(self.manifest,self.state,fail)
        self.assertTrue(failed)
        self.assertEqual(len(result['items']),1)
        self.assertEqual(result['source_runs']['synthetic']['status'],'error')
        self.assertIn('last_success_at', result['source_runs']['synthetic'])
        self.assertGreater(result['source_runs']['synthetic']['next_attempt_epoch'], c.time.time()+7100)

    def test_backoff_skips_fetch(self):
        c.collect(self.manifest,self.state,lambda *a:(RSS,SOURCE['url']))
        def unexpected(*args): self.fail('network should not run')
        result, _ = c.collect(self.manifest,self.state,unexpected)
        self.assertEqual(result['source_runs']['synthetic']['status'],'deferred_backoff')

    def test_disabled_no_network(self):
        self.manifest.write_text(json.dumps({'sources':[dict(SOURCE,enabled=False)]}))
        result, _ = c.collect(self.manifest,self.state,lambda *a:self.fail('disabled network'))
        self.assertEqual(result['source_runs']['synthetic']['status'],'disabled_unverified')

    def test_corrupt_json_not_overwritten(self):
        self.state.mkdir(); path=self.state/'candidates.json'; path.write_text('{bad')
        with self.assertRaises(ValueError): c.collect(self.manifest,self.state)
        self.assertEqual(path.read_text(),'{bad')

    def test_existing_lock_stops(self):
        self.state.mkdir(); (self.state/'.collector.lock').touch()
        with self.assertRaises(FileExistsError): c.collect(self.manifest,self.state)

    def test_invalid_encoding_records_error_and_backoff(self):
        body = b'<?xml version="1.0" encoding="X-INVALID"?><rss><channel/></rss>'
        result, failed = c.collect(self.manifest,self.state,lambda *a:(body, SOURCE['url']))
        self.assertTrue(failed)
        run = result['source_runs']['synthetic']
        self.assertEqual(run['error'], 'LookupError')
        self.assertEqual(run['last_result_status'], 'error')
        self.assertGreater(run['next_attempt_epoch'], c.time.time())
        self.assertTrue((self.state/'candidates.json').is_file())

    def test_multibyte_queue_retains_backoff_with_byte_eviction(self):
        sources = [dict(SOURCE, id='synthetic-'+str(i)) for i in range(20)]
        self.manifest.write_text(json.dumps({'sources':sources}))
        entries = ''.join('<item><title>'+('X'*500)+'</title><link>https://example.org/doc/'+str(i)+'</link><description>'+('😀'*2000)+'</description></item>' for i in range(100))
        body = ('<rss><channel>'+entries+'</channel></rss>').encode()
        self.assertLess(len(body),c.MAX_BYTES)
        result, failed = c.collect(self.manifest,self.state,lambda *a:(body,SOURCE['url']))
        self.assertFalse(failed)
        self.assertLess((self.state/'candidates.json').stat().st_size, c.MAX_STATE_BYTES+1)
        self.assertLess(len(result['items']),2000)
        self.assertEqual(result['retention']['dropped_this_run'],2000-len(result['items']))
        self.assertEqual(len(result['source_runs']),20)
        self.assertTrue(all(run['next_attempt_epoch'] > c.time.time() for run in result['source_runs'].values()))

    def test_partial_deferred_retains_failure_status(self):
        c.collect(self.manifest,self.state,lambda *a:(RSS.replace(b'example.org/policy',b'evil.example/policy'),SOURCE['url']))
        result, failed = c.collect(self.manifest,self.state,lambda *a:self.fail('should be deferred'))
        self.assertTrue(failed)
        self.assertEqual(result['source_runs']['synthetic']['last_result_status'],'partial')
        self.assertEqual(result['source_runs']['synthetic']['status'],'deferred_backoff')

    def test_overflow_date_does_not_abort_state(self):
        body = RSS.replace(b'Mon, 05 Oct 2026 08:00:00 GMT', b'0001-01-01T00:00:00+01:00')
        result, failed = c.collect(self.manifest,self.state,lambda *a:(body, SOURCE['url']))
        self.assertFalse(failed)
        self.assertIsNone(result['items'][0]['published_at'])
        self.assertTrue((self.state/'candidates.json').is_file())
        self.assertGreater(result['source_runs']['synthetic']['next_attempt_epoch'], c.time.time())

    def test_redirect_relative_link_uses_final_url(self):
        self.manifest.write_text(json.dumps({'sources':[dict(SOURCE,url='https://example.org/old/feed.xml')]}))
        body = RSS.replace(b'https://example.org/policy?id=1#top', b'doc')
        result, failed = c.collect(self.manifest,self.state,lambda *a:(body, 'https://example.org/new/feed.xml'))
        self.assertFalse(failed)
        self.assertEqual(result['items'][0]['canonical_url'], 'https://example.org/new/doc')

    def test_partial_not_reported_as_complete(self):
        result, failed = c.collect(self.manifest,self.state,lambda *a:(RSS.replace(b'example.org/policy',b'evil.example/policy'), SOURCE['url']))
        self.assertTrue(failed)
        self.assertEqual(result['source_runs']['synthetic']['status'], 'partial')
        self.assertEqual(result['source_runs']['synthetic']['skipped_items'], 1)

    def test_malformed_is_error(self):
        result, failed = c.collect(self.manifest,self.state,lambda *a:(b'<rss>',SOURCE['url']))
        self.assertTrue(failed)
        self.assertEqual(result['source_runs']['synthetic']['status'],'error')


if __name__ == '__main__': unittest.main()

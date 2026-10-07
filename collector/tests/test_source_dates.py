"""Fictional format regressions; never infer a timezone from source location."""
from pathlib import Path
import unittest
import collector as c

HERE = Path(__file__).parent
SOURCE = {'id': 'synthetic', 'url': 'https://example.org/feed', 'allowed_hosts': ['example.org']}
NOW = '2026-10-07T00:00:00Z'


class SourceDateTests(unittest.TestCase):
    def row(self, name, source_id, replace=None):
        body = (HERE / 'fixtures' / name).read_bytes()
        if replace:
            body = body.replace(*replace)
        return c.parse_feed(body, dict(SOURCE, id=source_id), NOW)[0][0]

    def test_moel_local_date_preserved_without_inventing_timezone(self):
        row = self.row('moel-local-date.xml', 'kr-moel-policy')
        self.assertEqual(row['published_raw'], '2024-02-29 17:07:20')
        self.assertIsNone(row['published_at'])
        self.assertEqual(row['published_local'], {'value': '2024-02-29T17:07:20',
                          'precision': 'second', 'timezone_unknown': True})

    def test_wda_datetime_field_is_source_specific(self):
        row = self.row('wda-local-date.xml', 'tw-wda-news')
        self.assertEqual(row['published_raw'], '20240229T110500')
        self.assertIsNone(row['published_at'])
        self.assertEqual(row['published_local'], {'value': '2024-02-29T11:05:00',
                          'precision': 'second', 'timezone_unknown': True})
        other = self.row('wda-local-date.xml', 'synthetic')
        self.assertIsNone(other['published_raw'])
        self.assertIsNone(other['published_local'])

    def test_unconfigured_local_date_stays_unknown(self):
        row = self.row('moel-local-date.xml', 'synthetic')
        self.assertIsNone(row['published_at'])
        self.assertIsNone(row['published_local'])

    def test_invalid_local_dates_fail_closed(self):
        for raw in (b'2023-02-29 17:07:20', b'2024-13-01 17:07:20', b'2024-02-29 25:07:20',
                    b'2024-2-29 17:07:20', b'2024-02-29', b'unknown'):
            with self.subTest(raw=raw):
                row = self.row('moel-local-date.xml', 'kr-moel-policy', (b'2024-02-29 17:07:20', raw))
                self.assertIsNone(row['published_at'])
                self.assertIsNone(row['published_local'])
        for raw in (b'20230229T110500', b'20240229T240000', b'20240229T1105', b'unknown'):
            with self.subTest(raw=raw):
                row = self.row('wda-local-date.xml', 'tw-wda-news', (b'20240229T110500', raw))
                self.assertIsNone(row['published_at'])
                self.assertIsNone(row['published_local'])

    def test_utc_dates_remain_separate(self):
        row = self.row('moel-local-date.xml', 'kr-moel-policy',
                       (b'2024-02-29 17:07:20', b'2024-02-29T17:07:20+09:00'))
        self.assertEqual(row['published_at'], '2024-02-29T08:07:20Z')
        self.assertIsNone(row['published_local'])

    def test_wda_standard_publication_date_has_priority(self):
        row = self.row('wda-local-date.xml', 'tw-wda-news',
                       (b'<DateTime>', b'<pubDate>Thu, 29 Feb 2024 02:05:00 GMT</pubDate><DateTime>'))
        self.assertEqual(row['published_at'], '2024-02-29T02:05:00Z')
        self.assertIsNone(row['published_local'])

    def test_wda_bom_and_inert_schema_attribute(self):
        body = (HERE / 'fixtures/wda-local-date.xml').read_bytes()
        body = body[body.index(b'<rss'):].replace(b'<rss version="2.0">',
            b'<rss version="2.0" xmlns:d1p1="schemaLocation" d1p1:xsi="http://example.org/fictional.xsd">')
        row = c.parse_feed(b'\xef\xbb\xbf' + body, dict(SOURCE, id='tw-wda-news'), NOW)[0][0]
        self.assertEqual(row['published_local']['value'], '2024-02-29T11:05:00')

    def test_local_date_change_produces_new_pending_version(self):
        first = self.row('moel-local-date.xml', 'kr-moel-policy')
        second = self.row('moel-local-date.xml', 'kr-moel-policy',
                          (b'2024-02-29 17:07:20', b'2024-03-01 17:07:20'))
        self.assertNotEqual(first['content_hash'], second['content_hash'])
        self.assertEqual(first['document_id'], second['document_id'])
        rows, dropped = c.merge([first], [second], NOW)
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(row['status'] == 'pending' for row in rows))


if __name__ == '__main__':
    unittest.main()

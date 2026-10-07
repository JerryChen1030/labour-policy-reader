"""Bounded, fictional WDA diagnostics; no body or protection identifier may escape."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('wda_probe', ROOT / 'tools/rss_health_probe.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
SOURCE = {'id': 'tw-wda-news', 'url': 'https://example.org/feed', 'allowed_hosts': ['example.org']}
REJECTED = (Path(__file__).parent / 'fixtures/wda-request-rejected.html').read_bytes()


class WdaDiagnosticsTests(unittest.TestCase):
    def test_denial_signals_are_fixed_labels_and_parser_still_rejects(self):
        result = p.probe(SOURCE, lambda *_: (REJECTED, SOURCE['url']))
        self.assertEqual(result['status'], 'error')
        self.assertEqual(result['error'], 'xml_dtd_or_entities_forbidden')
        self.assertIsNone(result['items'])
        d = result['response_diagnostics']
        self.assertTrue(d['html_tag_observed'])
        self.assertTrue(d['doctype_observed'])
        self.assertEqual(d['title_category'], 'request_rejected')
        self.assertIn('request_rejected', d['text_marker_categories'])
        for text in ('SYNTHETIC-PRIVATE-ID', 'private@example.org', '192.0.2.123',
                     'Please consult', 'support ID', 'Request Rejected'):
            self.assertNotIn(text, json.dumps(result))

    def test_unknown_html_remains_unknown(self):
        body = b'<!DOCTYPE html><html><head><title>PRIVATE-TITLE</title></head><body>PRIVATE-TEXT</body></html>'
        d = p.wda_response_diagnostics(body, 'text/html')
        self.assertEqual(d['title_category'], 'unknown_or_absent')
        self.assertEqual(d['text_marker_categories'], [])
        self.assertNotIn('PRIVATE', json.dumps(d))

    def test_script_and_comment_markers_do_not_count_as_visible_denial(self):
        body = b'<html><script>"access denied"; "verify you are human"</script><!--request blocked--><body>Neutral</body></html>'
        d = p.wda_response_diagnostics(body, 'text/html')
        self.assertEqual(d['text_marker_categories'], [])

    def test_nested_templates_remain_inert(self):
        body = b'<html><body><template><template>neutral</template>access denied</template>Neutral visible body</body></html>'
        d = p.wda_response_diagnostics(body, 'text/html')
        self.assertEqual(d['text_marker_categories'], [])

    def test_self_closing_template_syntax_stays_inert(self):
        body = b'<html><body><template/>access denied</template>Neutral visible body</body></html>'
        d = p.wda_response_diagnostics(body, 'text/html')
        self.assertEqual(d['text_marker_categories'], [])

    def test_marker_words_in_rss_content_are_not_classified(self):
        body = b'<rss><channel><item><title>Access denied</title></item></channel></rss>'
        d = p.wda_response_diagnostics(body, 'text/xml')
        self.assertFalse(d['html_tag_observed'])
        self.assertEqual(d['title_category'], 'unknown_or_absent')
        self.assertEqual(d['text_marker_categories'], [])

    def test_mislabeled_rss_cannot_claim_denial(self):
        body = b'<rss><channel><item><title>Access denied</title></item></channel></rss>'
        d = p.wda_response_diagnostics(body, 'text/html')
        self.assertFalse(d['html_tag_observed'])
        self.assertEqual(d['title_category'], 'unknown_or_absent')
        self.assertEqual(d['text_marker_categories'], [])

    def test_diagnostic_scan_is_bounded(self):
        body = b'<html><body>' + b'x' * p.HTML_DIAGNOSTIC_BYTES + b'access denied</body></html>'
        d = p.wda_response_diagnostics(body, 'text/html')
        self.assertEqual(d['inspected_bytes'], p.HTML_DIAGNOSTIC_BYTES)
        self.assertTrue(d['inspection_truncated'])
        self.assertEqual(d['text_marker_categories'], [])

    def test_truncated_title_cannot_claim_exact_denial_title(self):
        start = b'<html><head><title>'
        prefix = start + b' ' * (p.HTML_DIAGNOSTIC_BYTES - len(start) - len(b'Access Denied')) + b'Access Denied'
        body = prefix + b' is a Fictional Book</title></head><body>Neutral</body></html>'
        d = p.wda_response_diagnostics(body, 'text/html')
        self.assertTrue(d['inspection_truncated'])
        self.assertEqual(d['title_category'], 'unknown_or_absent')

    def test_challenge_title_and_html_entities_use_only_known_labels(self):
        body = b'<html><title>Access&#32;Denied</title><body>Verify you are human</body></html>'
        d = p.wda_response_diagnostics(body, 'text/html')
        self.assertEqual(d['title_category'], 'access_denied')
        self.assertIn('human_verification', d['text_marker_categories'])

    def test_wda_only_cli_starts_one_bounded_wda_child(self):
        child = subprocess.CompletedProcess([], 0, json.dumps({'source_id':'tw-wda-news','status':'ok'}), '')
        with patch.object(p.subprocess, 'run', return_value=child) as run, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(p.main(['--only-source', 'tw-wda-news']), 0)
        run.assert_called_once()
        self.assertEqual(run.call_args.args[0][-2:], ['--source', 'tw-wda-news'])
        self.assertEqual(run.call_args.kwargs['timeout'], 70)
        self.assertTrue(run.call_args.kwargs['check'])

    def test_wda_only_cli_error_is_nonzero(self):
        child = subprocess.CompletedProcess([], 0, json.dumps({'source_id':'tw-wda-news','status':'error'}), '')
        with patch.object(p.subprocess, 'run', return_value=child) as run, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(p.main(['--only-source', 'tw-wda-news']), 1)
        run.assert_called_once()

    def test_invalid_cli_selector_never_fetches(self):
        with patch.object(p.subprocess, 'run') as run, patch.object(p, 'probe') as probe:
            self.assertEqual(p.main(['--only-source', 'jp-mhlw-news']), 2)
            self.assertEqual(p.main(['--only-source', 'tw-wda-news', 'extra']), 2)
        run.assert_not_called()
        probe.assert_not_called()

    def test_wda_timeout_is_terminal_without_retry(self):
        with patch.object(p.subprocess, 'run', side_effect=subprocess.TimeoutExpired('synthetic', 70)) as run, \
             contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(p.main(['--only-source', 'tw-wda-news']), 1)
        run.assert_called_once()
        self.assertEqual(json.loads(output.getvalue())['error'], 'source_wall_timeout')

    def test_html_inspection_never_fetches_embedded_resources(self):
        body = b'<!DOCTYPE html SYSTEM "https://example.org/external"><html><body><img src="https://example.org/pixel"></body></html>'
        with patch('socket.socket', side_effect=AssertionError('No networking allowed')):
            d = p.wda_response_diagnostics(body, 'text/html')
        self.assertTrue(d['html_tag_observed'])
        self.assertEqual(d['text_marker_categories'], [])

    def test_manual_workflow_is_wda_only(self):
        workflow = (ROOT / '.github/workflows/manual-rss-health.yml').read_text()
        self.assertIn('python3 tools/rss_health_probe.py --only-source tw-wda-news', workflow)


if __name__ == '__main__':
    unittest.main()

#!/usr/bin/env python3
"""One-shot, metadata-only RSS health check. Never persists feed or candidates."""
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'collector'))
import collector

SOURCE_IDS = ('jp-mhlw-news', 'kr-moel-policy', 'tw-wda-news')
SAFE_ERRORS = {'redirect_limit_or_missing_location', 'redirect_limit',
               'unsupported_content_encoding', 'response_too_large', 'fetch_deadline'}
HTML_DIAGNOSTIC_BYTES = 16 * 1024


class _DiagnosticHTML(HTMLParser):
    """Transient bounded text inspection only; never executes or returns HTML."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text, self.title = [], []
        self.html_tag, self.in_title, self.ignored = False, False, None

    def handle_starttag(self, tag, attrs):
        if tag == 'html':
            self.html_tag = True
        if self.ignored is None and tag in ('script', 'style', 'template'):
            self.ignored = tag
        if tag == 'title' and self.ignored is None:
            self.in_title = True

    def handle_endtag(self, tag):
        if tag == self.ignored:
            self.ignored = None
        if tag == 'title':
            self.in_title = False

    def handle_data(self, text):
        if self.ignored is None:
            self.text.append(text)
            if self.in_title:
                self.title.append(text)


def wda_response_diagnostics(body, content_type):
    """Return fixed labels, never titles, text, identifiers, addresses or URLs."""
    sample = body[:HTML_DIAGNOSTIC_BYTES]
    result = dict(inspected_bytes=len(sample), inspection_truncated=len(body) > len(sample),
                  html_tag_observed=False, doctype_observed=bool(re.search(br'<!\s*DOCTYPE', sample, re.I)),
                  entity_declaration_observed=bool(re.search(br'<!\s*ENTITY', sample, re.I)),
                  title_category='unknown_or_absent', text_marker_categories=[])
    leading = sample.removeprefix(b'\xef\xbb\xbf')
    html_hint = re.match(br'\s*(?:<\?xml[^>]*>\s*)?(?:<!doctype\s+html(?:\s|>)|<html(?:\s|>))', leading, re.I)
    if content_type != 'text/html' and not html_hint:
        return result
    parser = _DiagnosticHTML()
    try:
        parser.feed(sample.decode('utf-8', errors='replace'))
        parser.close()
    except (ValueError, AssertionError):
        # Unsupported HTML syntax is not an invitation to repair/execute the page.
        return result
    result['html_tag_observed'] = parser.html_tag
    title = ' '.join(' '.join(parser.title).lower().split())
    titles = {'request rejected': 'request_rejected', 'access denied': 'access_denied',
              '403 forbidden': 'forbidden', 'forbidden': 'forbidden',
              'just a moment...': 'challenge_page', 'security check': 'security_check'}
    result['title_category'] = titles.get(title, 'unknown_or_absent')
    text = ' '.join(' '.join(parser.text).lower().split())
    markers = {'request_rejected': ('the requested url was rejected', 'request rejected'),
               'access_denied': ('access denied',), 'request_blocked': ('request blocked',),
               'human_verification': ('verify you are human', 'verify that you are human'),
               'javascript_required': ('enable javascript', 'javascript is required'),
               'unusual_traffic': ('unusual traffic',), 'policy_restriction': ('security policy',),
               'rate_limited': ('too many requests',)}
    result['text_marker_categories'] = sorted(label for label, phrases in markers.items()
                                               if any(phrase in text for phrase in phrases))
    return result


def probe(source, fetcher=None):
    # Only this in-memory copy is enabled; repository source configuration is untouched.
    source = dict(source, enabled=True)
    result = dict(source_id=source['id'], status='error', http_status=None,
                  items=None, skipped_items=None, date_field_coverage=None,
                  last_date=None, last_source_local_date=None, date_status=None,
                  content_type=None, bytes=None, sha256=None, error=None)
    transport = {}
    try:
        if fetcher is None:
            body, final_url = collector.fetch(source['url'], source['allowed_hosts'], metadata=transport)
        else:
            body, final_url = fetcher(source['url'], source['allowed_hosts'])
        result.update(http_status=200, bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
        if source['id'] == 'tw-wda-news':
            result['response_diagnostics'] = wda_response_diagnostics(body, transport.get('content_type'))
        rows, skipped = collector.parse_feed(body, source, collector.stamp(), final_url)
        dates = [r[k] for r in rows for k in ('published_at', 'updated_at') if r[k]]
        local_dates = [r['published_local']['value'][:10] for r in rows if r['published_local']]
        utc_items = sum(bool(r['published_at'] or r['updated_at']) for r in rows)
        known_items = sum(bool(r['published_at'] or r['updated_at'] or r['published_local']) for r in rows)
        date_status = ('empty_feed' if not rows else 'utc_known' if utc_items == len(rows)
                       else 'source_local_timezone_unknown' if known_items == len(rows)
                       else 'incomplete_or_unknown')
        result.update(status='partial' if skipped else 'ok', items=len(rows), skipped_items=skipped,
                      date_field_coverage=dict(accepted_items=len(rows),
                          published_raw=sum(bool(r['published_raw']) for r in rows),
                          updated_raw=sum(bool(r['updated_raw']) for r in rows),
                          published_parsed=sum(bool(r['published_at']) for r in rows),
                          published_local=len(local_dates),
                          updated_parsed=sum(bool(r['updated_at']) for r in rows)),
                      last_date=max(dates) if dates else None,
                      last_source_local_date=max(local_dates) if local_dates else None,
                      date_status=date_status)
    except collector.FeedParseError as exc:
        result['error'] = exc.code if exc.code in collector.FEED_ERROR_CODES else 'feed_parse_error'
    except collector.FetchError as exc:
        code = exc.code
        if isinstance(code, str) and code.startswith('http_') and code[5:].isdigit() and len(code) == 8:
            result.update(http_status=int(code[5:]), error=code)
        else:
            result['error'] = code if code in SAFE_ERRORS else 'fetch_error'
    except Exception as exc:
        # Never emit exception messages: XML, server responses or URLs may contain private text.
        result['error'] = type(exc).__name__ if type(exc).__name__ in {
            'gaierror', 'TimeoutError', 'SSLError', 'SSLCertVerificationError',
            'ConnectionResetError', 'ConnectionRefusedError', 'OSError', 'ParseError', 'ValueError'
        } else 'probe_error'
    mime = transport.get('content_type')
    if mime is not None:
        result['content_type'] = mime if mime in collector.SAFE_CONTENT_TYPES else 'other_or_missing'
    return result


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    sources = json.loads((ROOT / 'collector/sources.json').read_text())['sources']
    assert tuple(s['id'] for s in sources) == SOURCE_IDS
    assert all(s['enabled'] is False for s in sources)
    if len(argv) == 2 and argv[0] == '--source' and argv[1] in SOURCE_IDS:
        source = next(s for s in sources if s['id'] == argv[1])
        print(json.dumps(probe(source), sort_keys=True), flush=True)
        return 0
    if argv == ['--only-source', 'tw-wda-news']:
        selected_ids = ('tw-wda-news',)
    elif not argv:
        selected_ids = SOURCE_IDS
    else:
        return 2
    failed = False
    for source_id in selected_ids:
        try:
            child = subprocess.run([sys.executable, __file__, '--source', source_id],
                                   capture_output=True, text=True, timeout=70, check=True)
            result = json.loads(child.stdout)
        except subprocess.TimeoutExpired:
            result = dict(source_id=source_id, status='error', error='source_wall_timeout')
        except Exception:
            result = dict(source_id=source_id, status='error', error='probe_process_error')
        print(json.dumps(result, sort_keys=True), flush=True)
        failed |= result['status'] != 'ok'
    return int(failed)


if __name__ == '__main__':
    sys.exit(main())

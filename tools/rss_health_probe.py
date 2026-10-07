#!/usr/bin/env python3
"""One-shot, metadata-only RSS health check. Never persists feed or candidates."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'collector'))
import collector

SOURCE_IDS = ('jp-mhlw-news', 'kr-moel-policy', 'tw-wda-news')
SAFE_ERRORS = {'redirect_limit_or_missing_location', 'redirect_limit',
               'unsupported_content_encoding', 'response_too_large', 'fetch_deadline'}


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


def main():
    sources = json.loads((ROOT / 'collector/sources.json').read_text())['sources']
    assert tuple(s['id'] for s in sources) == SOURCE_IDS
    assert all(s['enabled'] is False for s in sources)
    if len(sys.argv) == 3 and sys.argv[1] == '--source' and sys.argv[2] in SOURCE_IDS:
        source = next(s for s in sources if s['id'] == sys.argv[2])
        print(json.dumps(probe(source), sort_keys=True), flush=True)
        return 0
    if len(sys.argv) != 1:
        return 2
    failed = False
    for source_id in SOURCE_IDS:
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

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


def probe(source, fetcher=collector.fetch):
    # Only this in-memory copy is enabled; repository source configuration is untouched.
    source = dict(source, enabled=True)
    result = dict(source_id=source['id'], status='error', http_status=None,
                  items=None, skipped_items=None, date_field_coverage=None,
                  last_date=None, bytes=None, sha256=None, error=None)
    try:
        body, final_url = fetcher(source['url'], source['allowed_hosts'])
        result.update(http_status=200, bytes=len(body), sha256=hashlib.sha256(body).hexdigest())
        rows, skipped = collector.parse_feed(body, source, collector.stamp(), final_url)
        dates = [r[k] for r in rows for k in ('published_at', 'updated_at') if r[k]]
        result.update(status='partial' if skipped else 'ok', items=len(rows), skipped_items=skipped,
                      date_field_coverage=dict(accepted_items=len(rows),
                          published_raw=sum(bool(r['published_raw']) for r in rows),
                          updated_raw=sum(bool(r['updated_raw']) for r in rows),
                          published_parsed=sum(bool(r['published_at']) for r in rows),
                          updated_parsed=sum(bool(r['updated_at']) for r in rows)),
                      last_date=max(dates) if dates else None)
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

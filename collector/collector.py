#!/usr/bin/env python3
"""Bounded, provider-free RSS/Atom candidate collection. Never publishes."""
import argparse
import datetime as dt
import email.utils
import hashlib
import http.client
import ipaddress
import json
import os
from pathlib import Path
import re
import socket
import ssl
import tempfile
import time
import urllib.parse
import xml.etree.ElementTree as ET

MAX_BYTES = 2 * 1024 * 1024
MAX_ITEMS = 2000
MAX_STATE_BYTES = 16 * 1024 * 1024
TIMEOUT = 15
MAX_REDIRECTS = 3
MIN_INTERVAL = 3600
RETENTION_DAYS = 90
UTC = dt.timezone.utc


def stamp():
    return dt.datetime.now(UTC).isoformat().replace('+00:00', 'Z')


def date(value):
    if not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.strip().replace('Z', '+00:00'))
    except ValueError:
        try:
            parsed = email.utils.parsedate_to_datetime(value)
        except (ValueError, TypeError, OverflowError):
            return None
    if parsed.tzinfo is None:
        return None  # Never invent a timezone.
    try:
        return parsed.astimezone(UTC).isoformat().replace('+00:00', 'Z')
    except (OverflowError, ValueError):
        return None  # Offset conversion can exceed datetime's representable range.


def canonical(url, hosts):
    if len(url) > 4096 or re.search(r'[\x00-\x20\x7f]', url):
        raise ValueError('invalid URL characters/length')
    p = urllib.parse.urlsplit(url)
    if p.scheme != 'https' or p.username or p.password or p.port not in (None, 443):
        raise ValueError('only credential-free HTTPS on port 443 is allowed')
    host = (p.hostname or '').lower()
    if host not in hosts or not re.fullmatch(r'[a-z0-9.-]+', host):
        raise ValueError('host is not explicitly allowed')
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ValueError('IP literal forbidden')
    return urllib.parse.urlunsplit(('https', host, p.path or '/', p.query, ''))


def addresses(host):
    results = sorted({x[4][0] for x in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)})
    if not results or any(not ipaddress.ip_address(ip).is_global for ip in results):
        raise ValueError('DNS returned non-public address')
    return results


class PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, host, ip):
        super().__init__(host, timeout=TIMEOUT, context=ssl.create_default_context())
        self.ip = ip

    def connect(self):
        # Connect to the checked IP; TLS certificate/SNI still use the original host.
        raw = socket.create_connection((self.ip, 443), self.timeout)
        try:
            self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
        except Exception:
            raw.close()
            raise


class FetchError(Exception):
    def __init__(self, code, retry_after=None):
        super().__init__(code)
        self.code, self.retry_after = code, retry_after


def fetch(url, hosts):
    deadline = time.monotonic() + 45
    for hop in range(MAX_REDIRECTS + 1):
        url = canonical(url, hosts)
        p = urllib.parse.urlsplit(url)
        conn = PinnedHTTPS(p.hostname, addresses(p.hostname)[0])
        try:
            conn.request('GET', urllib.parse.urlunsplit(('', '', p.path, p.query, '')),
                         headers={'User-Agent': 'PolicyCandidateCollector/1.0',
                                  'Accept': 'application/atom+xml, application/rss+xml, application/xml, text/xml',
                                  'Accept-Encoding': 'identity'})
            res = conn.getresponse()
            if res.status in (301, 302, 303, 307, 308):
                if hop == MAX_REDIRECTS or not res.getheader('Location'):
                    raise FetchError('redirect_limit_or_missing_location')
                url = urllib.parse.urljoin(url, res.getheader('Location'))
                continue
            if res.status != 200:
                raise FetchError('http_' + str(res.status), res.getheader('Retry-After'))
            if res.getheader('Content-Encoding', 'identity').lower() != 'identity':
                raise FetchError('unsupported_content_encoding')
            length = res.getheader('Content-Length')
            if length and int(length) > MAX_BYTES:
                raise FetchError('response_too_large')
            chunks, size = [], 0
            while True:
                if time.monotonic() > deadline:
                    raise FetchError('fetch_deadline')
                chunk = res.read1(min(65536, MAX_BYTES + 1 - size))
                if not chunk:
                    break
                chunks.append(chunk)
                size += len(chunk)
                if size > MAX_BYTES:
                    raise FetchError('response_too_large')
            return b''.join(chunks), url
        finally:
            conn.close()
    raise FetchError('redirect_limit')


def local(tag):
    return tag.rsplit('}', 1)[-1]


def childtext(node, name):
    found = next((x for x in node if local(x.tag) == name), None)
    return ''.join(found.itertext()).strip() if found is not None else ''


def plain(value, limit):
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]*>', '', value)).strip()[:limit]


def parse_feed(body, source, fetched_at, final_url=None):
    if len(body) > MAX_BYTES:
        raise ValueError('response_too_large')
    if b'\x00' in body or re.search(br'<!\s*(DOCTYPE|ENTITY)', body, re.I):
        raise ValueError('DTD/entities/non-UTF8 encoding forbidden')
    root = ET.fromstring(body)
    kind = local(root.tag)
    if kind not in ('rss', 'RDF', 'feed'):
        raise ValueError('not RSS/RDF/Atom')
    if kind == 'rss' and not any(local(n.tag) == 'channel' for n in root):
        raise ValueError('RSS channel missing')
    nodes = [n for n in root.iter() if local(n.tag) in ('item', 'entry')]
    if len(nodes) > MAX_ITEMS:
        raise ValueError('too_many_feed_items')
    rows, skipped = [], 0
    for node in nodes:
        atom = local(node.tag) == 'entry'
        link = childtext(node, 'link')
        if atom:
            link = next((n.get('href', '') for n in node if local(n.tag) == 'link'
                         and n.get('rel', 'alternate') == 'alternate'), '')
        try:
            url = canonical(urllib.parse.urljoin(final_url or source['url'], link), source['allowed_hosts'])
            if not link:
                raise ValueError('missing link')
        except ValueError:
            skipped += 1
            continue
        published_raw = childtext(node, 'published') if atom else childtext(node, 'pubDate') or childtext(node, 'date')
        updated_raw = childtext(node, 'updated')
        content = dict(title=plain(childtext(node, 'title'), 500),
                       summary=plain(childtext(node, 'summary') or childtext(node, 'description') or childtext(node, 'content'), 2000),
                       published_at=date(published_raw), updated_at=date(updated_raw),
                       published_raw=published_raw[:200] or None, updated_raw=updated_raw[:200] or None)
        hash_input = dict(content, untruncated_title=childtext(node, 'title'),
                          untruncated_text=childtext(node, 'summary') or childtext(node, 'description') or childtext(node, 'content'))
        digest = hashlib.sha256(json.dumps(hash_input, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        identity = hashlib.sha256((source['id'] + '\n' + url).encode()).hexdigest()
        rows.append(dict(id=identity + ':' + digest, document_id=identity,
                         source_id=source['id'], canonical_url=url, content_hash=digest,
                         fetched_at=fetched_at, last_seen_at=fetched_at, status='pending', **content))
    return rows, skipped


def merge(old, new, now):
    cutoff = dt.datetime.fromisoformat(now.replace('Z', '+00:00')) - dt.timedelta(days=RETENTION_DAYS)
    by_id = {}
    for row in old + new:
        previous = by_id.get(row['id'])
        candidate = dict(row)
        if previous:
            candidate['fetched_at'] = previous['fetched_at']
        candidate['status'] = 'pending'
        by_id[row['id']] = candidate
    retained = [r for r in by_id.values() if dt.datetime.fromisoformat(r['last_seen_at'].replace('Z', '+00:00')) >= cutoff]
    retained.sort(key=lambda x: (x['last_seen_at'], x['id']), reverse=True)
    return retained[:MAX_ITEMS], len(by_id) - min(len(retained), MAX_ITEMS)


def read_json(path, default):
    if not path.exists():
        return default
    if path.stat().st_size > MAX_STATE_BYTES:
        raise ValueError('state exceeds size limit')
    return json.loads(path.read_text(encoding='utf-8'))


def atomic_json(path, data):
    raw = (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode()
    if len(raw) > MAX_STATE_BYTES:
        raise ValueError('output exceeds size limit')
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix='.pending-')
    try:
        with os.fdopen(fd, 'wb') as out:
            out.write(raw)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def fit_queue_bytes(result):
    """Keep the newest prefix that fits, including run/backoff evidence and drop count."""
    rows = result['items']
    base_dropped = result['retention']['dropped_this_run']
    low, high, best = 0, len(rows), -1
    while low <= high:
        middle = (low + high) // 2
        result['items'] = rows[:middle]
        result['retention']['dropped_this_run'] = base_dropped + len(rows) - middle
        size = len((json.dumps(result, ensure_ascii=False, indent=2) + '\n').encode())
        if size <= MAX_STATE_BYTES:
            best, low = middle, middle + 1
        else:
            high = middle - 1
    if best < 0:
        raise ValueError('source status envelope exceeds size limit')
    result['items'] = rows[:best]
    result['retention']['dropped_this_run'] = base_dropped + len(rows) - best


def retry_seconds(value, now):
    if not value:
        return 0
    try:
        return max(0, min(30 * 86400, int(value)))
    except ValueError:
        parsed = date(value)
        if not parsed:
            return 0
        return max(0, min(30 * 86400, int(dt.datetime.fromisoformat(parsed.replace('Z', '+00:00')).timestamp() - now)))


def collect(manifest_path, directory, fetcher=fetch):
    manifest = read_json(Path(manifest_path), None)
    sources = manifest['sources']
    if len(sources) > 20 or len({s['id'] for s in sources}) != len(sources):
        raise ValueError('max 20 unique sources')
    for s in sources:
        canonical(s['url'], s['allowed_hosts'])
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    lock = directory / '.collector.lock'
    fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(fd)
    try:
        path = directory / 'candidates.json'
        old = read_json(path, {'schema_version': 1, 'items': [], 'source_runs': {}})
        if old['schema_version'] != 1:
            raise ValueError('unknown schema version')
        now, epoch = stamp(), time.time()
        runs, additions, failed = {}, [], False
        for s in sources:
            previous = old['source_runs'].get(s['id'], {})
            run = dict(previous)
            if not s.get('enabled', False):
                run['status'] = 'disabled_unverified'
            elif epoch < previous.get('next_attempt_epoch', 0):
                run['status'] = 'deferred_backoff'
                failed |= bool(previous.get('consecutive_errors', 0) or previous.get('skipped_items', 0))
            else:
                run['last_attempt_at'] = now
                try:
                    body, final_url = fetcher(s['url'], s['allowed_hosts'])
                    rows, skipped = parse_feed(body, s, now, final_url=final_url)
                    additions.extend(rows)
                    run.update(status='partial' if skipped else 'ok', last_success_at=now, consecutive_errors=0,
                               fetched_items=len(rows), skipped_items=skipped,
                               final_url=final_url, next_attempt_epoch=epoch + MIN_INTERVAL)
                    run['last_result_status'] = run['status']
                    run.pop('error', None)
                    failed |= bool(skipped)
                except (ValueError, LookupError, ET.ParseError, OSError, http.client.HTTPException, FetchError) as exc:
                    count = min(previous.get('consecutive_errors', 0) + 1, 20)
                    delay = max(min(86400, MIN_INTERVAL * 2 ** (count - 1)),
                                retry_seconds(getattr(exc, 'retry_after', None), epoch))
                    # Do not log response body, arbitrary exception strings, or credentials.
                    run.update(status='error', error=getattr(exc, 'code', type(exc).__name__),
                               consecutive_errors=count, next_attempt_epoch=epoch + delay)
                    run['last_result_status'] = 'error'
                    failed = True
            runs[s['id']] = run
        rows, dropped = merge(old['items'], additions, now)
        result = dict(schema_version=1, generated_at=now, items=rows, source_runs=runs,
                      retention=dict(days=RETENTION_DAYS, max_items=MAX_ITEMS, max_bytes=MAX_STATE_BYTES, dropped_this_run=dropped),
                      notice='Unreviewed candidates. Never auto-publish. Feed text is untrusted.')
        fit_queue_bytes(result)
        atomic_json(path, result)
        return result, failed
    finally:
        lock.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sources', default='sources.json')
    parser.add_argument('--state-dir', default='private-state')
    args = parser.parse_args()
    result, failed = collect(args.sources, args.state_dir)
    print(json.dumps({'candidate_count': len(result['items']),
                      'sources': {k: v['status'] for k, v in result['source_runs'].items()}}))
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())

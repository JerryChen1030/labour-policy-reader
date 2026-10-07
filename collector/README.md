# Portable policy feed candidate collector

A small Python 3.10+ standard-library program. It does not need OpenAI, an AI model, an API key, npm, or a paid service. It is a discovery queue, **not a fact checker or automatic publisher**. Code and synthetic fixtures are suitable for review before inclusion in a public repository. Runtime candidate text should remain private until reviewed.

## Current delivery status

- Candidate parser repair on 2026-10-07: 48 collector + 30 probe offline tests; see [PARSER-REPAIR.md](PARSER-REPAIR.md) for the reproduced issues, source-local date contract and unresolved historical WDA response. The first candidate runner test completed with WDA HTML rejection; a separately authorized WDA-only follow-up is described in [WDA-DIAGNOSTICS.md](WDA-DIAGNOSTICS.md)
- Historical 2026-10-06 CLI attempts below failed during DNS resolution; a later metadata-only runner probe reached HTTP and parsing. These earlier receipts are retained as historical evidence, not current readiness claims
- All three documented seed sources remain disabled and need an operator to resolve the environment limitation and review terms. This is **not** 76 operational sources or comprehensive policy coverage
- This collector has no deployment, account, token, recurring schedule or automatic approval/publishing behavior; publication of the separately reviewed static reader is a different operation
- Fixtures in `tests/fixtures` are clearly marked synthetic and must never be published as policy findings
- Free software can run on an operator-controlled Python machine. Hosting/Actions availability, quotas, free tiers and account ownership are external dependencies; no permanent-free guarantee is possible

## Run and test

From this directory:

```
python3 --version
python3 -m unittest discover -s tests -v
python3 collector.py --sources sources.json --state-dir private-state
```

The default smoke run makes no requests because every source is disabled. It writes `private-state/candidates.json` with empty items and `disabled_unverified` source statuses. Files in `private-state/` are ignored by Git. Do not force-add them to a public repository.

To start a real manual collection, first inspect the official source documentation, publisher terms and feed URL on the intended machine. Then explicitly enable one source in a local manifest, run the CLI and inspect its source status and sampled original documents. Add approved exact hostnames for cross-host article links only after checking ownership; wildcards are unsupported. A successful HTTP response or well-formed feed is not proof that a document is correct, current, effective, complete or permitted to republish. Keep the manifest's verification label accurate after recording your manual checks.

## Manual validation receipt — 2026-10-06 UTC

The official feed-directory pages were independently read through a web research tool. They document the exact seed URLs. This verifies documentation only: the web research tool is not the collector runtime and was not used as a proxy or substitute for its HTTP/parse test.

- Japan MHLW: https://www.mhlw.go.jp/rss/index.html documents https://www.mhlw.go.jp/stf/news.rdf
- Korea MOEL: https://www.moel.go.kr/site/rss/rssList.do documents https://www.moel.go.kr/rss/policy.do
- Taiwan WDA: https://www.wda.gov.tw/en/Rss.aspx links its Latest News feed at https://www.wda.gov.tw/OpenData.aspx?SN=C2BAAD4ED99D7E40. Its Chinese RSS notice (https://www.wda.gov.tw/cp.aspx?n=229) limits feed news to reading and reserves underlying rights; no public reuse permission is inferred
- Important MHLW restriction: its RSS page prohibits using the feed information to create websites/newsletters or redistribute it, commercially or non-commercially. Keep this source disabled for the public-reader workflow. Do not copy or summarize feed-derived content into that site merely because it is official; obtain appropriate permission or separately evaluate a permissible original-document workflow first

A bounded actual CLI attempt used the unchanged collector, a private manifest enabling only these two sources, a separate persisted private state directory, and a 130-second external process timeout. Both attempts failed at DNS resolution in the restricted runtime. A separately permitted elevated DNS diagnostic returned `gaierror -3 Temporary failure in name resolution` for both hosts. The configured network allowlist did not include either official domain, but this observation does not prove the cause. No explicit tool access denial was returned. The observed error is DNS failure; it does **not** establish that either official service is down. No proxy, hard-coded IP, TLS bypass, alternative executor or access-control workaround was used. One bounded WDA fallback was then tried using the same unchanged CLI with permitted elevated execution and a 70-second process limit; it also failed at DNS before HTTP. No further feeds were probed.

| Observation | jp-mhlw-news | kr-moel-policy |
|---|---|---|
| Attempt time | 2026-10-06T00:55:29.899754Z | 2026-10-06T00:55:29.899754Z |
| Result | error / gaierror | error / gaierror |
| HTTP status | unavailable; no response | unavailable; no response |
| Content type / final response URL | unavailable / unavailable | unavailable / unavailable |
| Response bytes received | 0 | 0 |
| Parsed / retained candidate items | 0 / 0 | 0 / 0 |
| Publication/update date coverage | not measured | not measured |
| Last successful fetch | none | none |
| Manual readiness | disabled; network + reuse review required | disabled; network + reuse review required |

WDA fallback receipt: attempted 2026-10-06T00:57:28.755965Z; `error / gaierror`; HTTP status, content type and final response URL unavailable; 0 received body bytes and 0 candidates; date coverage unmeasured; no last success. It remains disabled and requires network and reuse review.

Both live CLI invocations exited 1. Reinvocation with the **same** persisted state returned `deferred_backoff` for both sources, exit 1, and made no new HTTP attempt. Each retained its original error and next-attempt timestamp. The default disabled-source smoke still exits 0 with zero candidates. Offline fixture tests: 40 passed. No live feed body was received, parsed, approved or published. No operational source is being claimed as live-verified.

### Explicitly select sources for a future manual attempt

These commands are instructions for a runtime whose normal network policy permits the official destination, not a workaround for a blocked runtime. First review the source terms and exact HTTPS host ownership. Do not enable MHLW for a public-site workflow while the restriction above remains unresolved. The example selects only Korea's documented policy feed for a private discovery queue; it does not certify that feed as working or authorize republication.

```
mkdir -p private-state
python3 - <<'PYTHON'
import json
from pathlib import Path
manifest = json.loads(Path('sources.json').read_text(encoding='utf-8'))
selected = {'kr-moel-policy'}
assert selected <= {source['id'] for source in manifest['sources']}
for source in manifest['sources']:
    source['enabled'] = source['id'] in selected
    if source['enabled']:
        source['verification'] = 'manual_attempt_pending_validation'
Path('private-state/manual-sources.json').write_text(
    json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
PYTHON
python3 collector.py --sources private-state/manual-sources.json --state-dir private-state/manual
```

Where supported, prefix the last command with `timeout 130s` for a strict two-source wall-clock bound; `timeout` is an optional operating-system utility, not a Python dependency. Always reuse the same state directory for subsequent attempts so hourly spacing, error backoff and deduplication survive. Stop on errors or partial results and inspect `source_runs` privately; do not repeatedly discard state to force retries. A successful next run still requires source-by-source human review before enabling any routine use. Keep failing sources disabled in the operational manifest.

The resulting `private-state/manual/candidates.json` is a **private pending queue**, never the reader's `data.json`. Inspect source status, skipped links, dates and original documents. Apply the review steps below. Nothing in this command updates the public website, approves an item or installs a schedule. To stop collecting a selected source, set its private-manifest `enabled` value to `false` and retain its existing state.

## Outputs and contract

`candidates.json` has `schema_version: 1`, `generated_at`, `items`, `source_runs`, `retention`, and `notice`.

Each candidate has:
- `id`: source-and-canonical-URL document hash plus content hash, identifying one version
- `document_id`, `source_id`, `canonical_url`, `content_hash`
- `title` (at most 500 characters), `summary` (at most 2,000 characters), both untrusted feed text
- `published_at` and `updated_at`: separate UTC timestamps or null; `published_raw`/`updated_raw` retain bounded source values
- `published_local`: optional nullable source-local evidence with `value`, `precision: "second"`, and `timezone_unknown: true`; only the observed MOEL/WDA publication formats are recognized. Older queue rows may lack this additive field
- `fetched_at` (first observation of retained version), `last_seen_at`, `status: "pending"`

HTML-like markup is removed from text, but the output is not an HTML sanitizer. Render with `textContent`, never insert feed strings as HTML. Content hashes include untruncated title/text and dates as parsed from the feed; they are version markers, not signatures or proof of provenance. They do not detect changes to linked article/PDF bodies absent from the feed. Changed feed content yields another pending version; same-version repeat sightings deduplicate. Canonicalization removes fragments and default ports; it deliberately preserves query parameters and path case so distinct documents are not silently merged. Tracking-parameter variants and different source IDs can remain distinct.

Unknown, invalid, date-only or UTC-out-of-range dates remain null. Timezone-less values never populate UTC fields. Strictly recognized MOEL/WDA publication formats may populate separate source-local evidence without a timezone assumption. Relative item URLs resolve against the final feed URL after validated redirects. Never replace them with fetch time. The collector does not infer effective dates. Feed HTTP errors, 429s, invalid XML and unexpected HTML are error statuses, not “no new policy.” `partial` records skipped item links and exits nonzero; inspect these before interpreting coverage. `last_success_at` survives later errors; `last_result_status` preserves the last attempted outcome while a source is deferred. Deferred errors/partial results keep a nonzero exit status. A successful empty feed is only zero entries in that feed response.

## Human review into the public reader

The separate static reader uses `data.json` with top-level `asOf`, `updateMode`, `items`. The collector intentionally has no publish/export-approval command and never opens that file. Reviewers should:

1. Open the canonical original URL; check document identity, title, current content, dates, jurisdiction and publisher/republication terms
2. Review same-URL versions and determine whether a correction, separate entry, or no publication is appropriate; do not silently replace an already reviewed entry
3. Write a short neutral original summary rather than blindly republishing feed text. Remove personal allegations, private identifiers and other sensitive content. A feed's official host does not make every embedded statement suitable for public redistribution
4. In a separate staged copy of `data.json`, map a reviewed item as below, preserving existing approved items and all unrelated files
5. Validate the reader schema, dates, safe HTTPS links, rendering and differences; obtain publishing approval before committing/deploying. Record reviewer and evidence in a private review log

Suggested mapping:

| Reader field | Reviewed origin |
|---|---|
| `id` | Stable public ID chosen by reviewer; `document_id` can be a basis |
| `country`, `source`, `category`, `kind` | Human-classified metadata, never guessed from a feed title |
| `title`, `original`, `summary`, `note` | Neutral, reviewed public wording and original source title |
| `url` | Checked `canonical_url` |
| `date` | Confirmed publication calendar date, or null; use source-local date evidence rather than UTC day without checking |
| `dateLabel` | Publication-date label, or explicitly unknown |
| `checkedAt`, `verification` | Actual human check date and supported evidence status; never “verified” just because fetched |
| `dates.publication`, `dates.updated` | Independently checked date evidence |
| `dates.effective`, `dates.dataPeriod` | Check original document; otherwise unknown/null |
| `attachments` | Human-checked links only; not discovered by this collector |

Historical `grok.json` is independent. Do not merge candidate items or refresh counts into it. Do not import private raw CSV, personal allegations or internal operational notes into public output. Set public `asOf` only for the reviewed release, not every collection attempt.

## Bounds, rate limits and stopping

- Maximum 20 manifest sources; at most 2 MiB/feed, 2,000 feed entries, 2,000 retained versions total, 16 MiB queue JSON; 90 days since last observation
- One network attempt/source/hour at most **when using the same persisted state directory**. Errors back off 1, 2, 4… hours, capped at 24 hours. `Retry-After` is respected up to 30 days, with no retry within the invocation
- HTTPS port 443 only; explicit hostname allowlist for feeds, redirects and item links; maximum 3 redirects; public IP DNS results required. Checked IP is pinned for the TLS connection, preserving hostname validation and avoiding a second DNS lookup. Proxies are not used
- Socket timeout is 15 seconds; body read budget is 45 seconds (a blocking read can overshoot by a socket timeout). OS DNS resolution can exceed this budget; use an external process timeout if a strict wall-clock bound is required
- No compressed responses, DTD/entities or UTF-16 XML; no HTML scraping, search engine, browser, OCR, PDFs, login, CAPTCHA or robots bypass. UTF-8 feeds are the intended target
- A lock prevents concurrent runs in a state directory; writes are atomic. Corrupt JSON fails closed. After a crash, confirm no process is running before manually removing `.collector.lock`; keep a private backup before recovering corrupt state
- `retention.dropped_this_run` exposes count-, age- and byte-limit eviction. Byte-aware retention evicts the oldest candidate versions before writing so source health and retry/backoff evidence survive multibyte text growth. This queue is not a permanent audit archive; oldest unobserved versions can be evicted. Keep a separately secured archive if long-term provenance is required
- Disable a source with `enabled:false`; stop a manual run with Ctrl+C. There is no scheduler or daemon to stop. Keep state to retain backoff/dedup; deleting it resets those safeguards
- No public queue, uploads or telemetry. Logs contain only source IDs/status/counts; response bodies and secrets are not printed. Feed content may still include private or copyrighted material in the private queue

For sustained use, verify a few sources first. A daily operator-approved external scheduler could later call the same command with persistent state and a single-run lock. This delivery does not install or enable such a schedule. Define alerting, disk backup/retention, source ownership, and budget/quota limits before enabling one. Repeated errors require investigation, not a paid fallback or access-control workaround.

## GitHub Actions template

`templates/manual-check.yml` is dormant: it is outside `.github/workflows` and contains only `workflow_dispatch`, no cron. It runs synthetic tests and a disabled-source smoke check with read-only repository permission, no stored credentials, no deployment and no artifact upload. Review and pin the action to an approved immutable commit before activating. The runner is ephemeral; the template is **not a production persistent collector**. Real collection should initially use the manual CLI with private persistent state. Public Actions artifacts/logs are not a substitute for private review storage.

## Portability and backup

Copy this directory to a Python machine and run the same tests. The public-safe archive contains code, the disabled manifest, synthetic fixtures, documentation and the dormant workflow only. Verify the external SHA-256 checksum before extracting. Never put credentials, private candidate state, source CSV, personal records or internal notes in that archive.

For a private operational backup, separately copy the manifest actually used and `private-state/candidates.json` into access-controlled storage while the collector is stopped. This backup may contain unreviewed publisher text and must not be bundled with the public site. Restoring the same state preserves last-success/error/backoff and retained candidates; expired candidates may be evicted on the next run. Review retention and permissions before transferring it to another host.

The static website is a separate package; this collector archive is not a backup of that website or its approved data. A full portable release must include the independently reviewed static-site package as well.

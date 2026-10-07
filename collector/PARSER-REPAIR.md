# Candidate parser repair: 2026-10-07

## Evidence and scope

Baseline: `06e30f2c67c01d74e32f20a1090856dd1aa111d9`. The prior manual
[run 37404106416](https://github.com/JerryChen1030/labour-policy-reader/actions/runs/37404106416)
reported MHLW 103 items with UTC dates, MOEL 10 items with raw dates but no UTC
dates, and WDA HTTP 200 / 2,414 bytes / `ValueError`. Its body was not retained,
so the WDA failure's exact cause is unknown.

A separate read-only, certificate-verified HTTPS diagnostic on 2026-10-07
around 01:52–01:53 UTC, capped at 1 MiB per response, observed:

- MOEL's configured endpoint: HTTP 200, `text/xml;charset=utf-8`, 4,676 bytes,
  RSS 2.0, 10 items; `dc:date` values use `YYYY-MM-DD HH:MM:SS`
- WDA's configured endpoint: HTTP 200, `text/xml`, 182,361 bytes, RSS 2.0,
  50 items; unnamespaced `DateTime` values use `YYYYMMDDTHHMMSS`. Its UTF-8 BOM
  and inert schema attribute are accepted without retrieving external schemas
- Neither date format supplies a timezone. Neither response had DTD/entity
  declarations. The larger WDA response is different from the failed runner
  response and cannot establish the older failure's cause

This diagnostic is not the final candidate's GitHub Actions test, a guarantee
of runner access, source completeness, or permission to republish. Only
structural metadata is recorded here; no captured feed title, body, raw date
value, or personal information is included in this candidate.

## Changes

- Recognize the observed MOEL local format for `kr-moel-policy`
- Recognize WDA's `DateTime` publication field and compact local format only
  for `tw-wda-news`; standard publication fields retain priority
- Preserve `published_raw` separately. Add nullable `published_local` evidence:
  `value` is an ISO local date/time, `precision` is `second`, and
  `timezone_unknown` is true. No timezone or UTC instant is inferred from
  geography, fetch time, or a plausible date. Invalid calendar/time values and
  other formats remain unknown. `published_at` stays null for these local values
- Keep original hashes for unaffected items. Source-local evidence is included
  in version hashes only when present. The additive field is compatible with
  old queue rows that lack it; newly recognized evidence can create a new
  pending version, never an approved item
- Add safe parser reason codes and allowlisted response MIME metadata. HTML,
  missing RSS channel, DTD/entities, NUL encodings, oversized responses and
  excessive entries remain errors. Arbitrary XML/exception/header text is not
  emitted. A future WDA failure can be distinguished without exposing its body
- Report UTC coverage separately from source-local coverage. `last_date` remains
  UTC-only; `last_source_local_date` is the latest local calendar date and is
  not an effective date or an instant. `date_status` explicitly distinguishes
  UTC-known, source-local/timezone-unknown, incomplete/unknown, and empty feeds

The existing TLS, public-DNS/IP pinning, host allowlist, redirect, size, item,
socket and subprocess limits are unchanged. Sources stay disabled; the workflow
remains dispatch-only on a public repository's standard `ubuntu-latest` runner.
No main merge, website data change, deployment, schedule, artifact, paid service,
or automatic article publication is part of this repair.

## Validation and remaining uncertainty

All original 48 offline tests pass. New synthetic tests reproduce the missing
MOEL local evidence, ignored WDA field and opaque parser diagnostics before the
implementation change. The full candidate suite has 48 collector and 14 probe
tests, covering malformed/calendar dates, timezone uncertainty, ordinary UTC
dates, field priority, synthetic BOM/schema attributes, versioning, dangerous
XML/HTML rejection, MIME redaction and unknown-date reporting. Fixtures use
fictional text, dates and example.org URLs.

The one authorized three-source candidate run is still pending at preparation.
Its result must be recorded against the exact candidate commit. Do not rerun
automatically if the WDA runner response fails again; report its safe diagnostic
code and seek authorization for any additional network run. A passing current
response will not resolve what the old unretained 2,414-byte response contained.

## Source-use restrictions

[MHLW RSS terms](https://www.mhlw.go.jp/rss/index.html) prohibit RSS-based
websites/newsletters and redistribution, commercial or noncommercial. It stays
disabled for public-reader use. Its feed update time can differ from publication.
[MOEL copyright rules](https://www.moel.go.kr/site/copyright/copyrightList.do)
require checking the original document's markings and rights.
[WDA RSS notice](https://www.wda.gov.tw/cp.aspx?n=229) limits feed use to reading
and reserves underlying rights; its broader website reuse notice must not be
treated as automatic permission to republish RSS content. The configured WDA
URL is the English-feed candidate, not a substitution for Chinese news feeds.
No source-use license is added or inferred by this repair.

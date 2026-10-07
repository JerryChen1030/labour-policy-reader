# WDA-only bounded follow-up, 2026-10-07

The user separately authorized one additional WDA-only manual verification on
the public repository's standard GitHub-hosted runner. The prior three-source
run remains [37560311959](https://github.com/JerryChen1030/labour-policy-reader/actions/runs/37560311959)
at commit `4bca065ec12d230f7eeac013ce59c6b8558cae90`; it is not being rerun.
This follow-up stays in the existing draft candidate, with no main merge,
deployment, schedule, source enablement or automatic publication.

## Established evidence and remaining question

The prior runner received WDA HTTP 200, `text/html`, 2,414 bytes and rejected
the response with `xml_dtd_or_entities_forbidden`. It did not receive an accepted
RSS document. MOEL's 10 local dates and MHLW's 116 UTC dates passed separately.
The earlier cloud observation of valid WDA RSS does not establish runner access
or explain the HTML response.

At 03:29 UTC, an unchanged-collector cloud attempt and one permitted shell
sandbox escalation both failed DNS before HTTP. Neither supplied a new body;
these failures cannot establish a WDA refusal, recovery or outage. No header,
endpoint, proxy, fingerprint, credential or TLS change was attempted.

## Minimal diagnostic change

- The workflow now invokes `python3 tools/rss_health_probe.py --only-source
  tw-wda-news`. That mode starts exactly one WDA subprocess, with the existing
  70-second wall timeout. MHLW and MOEL are not fetched by this verification
- WDA response inspection is capped at the first 16 KiB of the already bounded
  response. It makes no extra requests and does not execute scripts, follow
  links, load schemas, submit forms or solve challenges
- Only byte counts, truncation/HTML/DTD/entity booleans and finite category
  labels can be emitted. Recognized rejection/challenge phrases map to fixed
  labels; arbitrary titles, text, protection identifiers, addresses, URLs and
  response headers are never emitted. Scripts, styles, templates and comments
  are excluded from text-marker matching
- Markers are evidence of specific recognized wording, not proof of a vendor,
  IP reputation rule, geography rule or other hidden server policy. An
  unrecognized or truncated page keeps an unknown interpretation
- Inspection is separate from the feed parser. Existing DTD/entity, encoding,
  TLS, public-DNS/IP pinning, redirect, host, size and time checks remain intact
  and keep failing closed. An HTML rejection is never converted into an empty
  feed or an accepted candidate

The request headers and configured WDA endpoint are unchanged. There is no
automatic retry, alternate network route or attempt to evade a source refusal.
If the runner confirms an access-denial/challenge response, stop and report it.
If no recognized reason is present, report the remaining uncertainty. Another
live attempt requires a new authorization.

## Offline verification

The new synthetic tests fail against the prior implementation and pass with
this diagnostic change. The full suite contains 48 collector and 26 probe
tests. Tests cover redaction, unknown HTML, script/comment exclusion, no RSS
title classification, the 16 KiB limit, encoded text, no embedded-resource
fetches, exactly one WDA child, invalid selectors, failure/timeout exit status,
and the WDA-only manual workflow. The original 62 tests are retained.

Fixtures are fictional. No captured WDA body or protection identifier is
committed. Existing source-rights restrictions remain in force. The additional
runner result must be recorded on the draft PR against its exact reviewed head;
it is pending when this candidate is prepared.

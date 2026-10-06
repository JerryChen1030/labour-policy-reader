#!/usr/bin/env python3
"""Offline, dependency-free release integrity and public-boundary checks."""
from pathlib import Path
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[1]
manifest = json.loads((ROOT / 'PUBLIC-MANIFEST.json').read_text())
allowed = set(manifest['files']) | {'PUBLIC-MANIFEST.json'}
actual = {str(p.relative_to(ROOT)) for p in ROOT.rglob('*') if p.is_file()
          and '.git' not in p.relative_to(ROOT).parts
          and '__pycache__' not in p.relative_to(ROOT).parts}
assert actual == allowed, ('Unexpected or missing files', actual ^ allowed)
for name, expected in manifest['files'].items():
    p = ROOT / name
    assert not p.is_symlink(), name
    b = p.read_bytes()
    assert len(b) == expected['bytes'], name
    assert hashlib.sha256(b).hexdigest() == expected['sha256'], name
for name in allowed:
    assert not any(x in name.split('/') for x in ['private-state', '.openai', '.env']), name
site = ROOT / 'docs'
for name in ['data.json', 'grok.json', 'strategy.json', 'expansion-sources.json', 'manifest.json']:
    json.loads((site / name).read_text())
assert len(json.loads((site / 'data.json').read_text())['items']) == 16
assert len(json.loads((site / 'grok.json').read_text())['records']) == 94
html = (site / 'index.html').read_text()
for link in re.findall(r'(?:src|href)=[\"\']([^\"\']+)', html):
    if not link.startswith(('https:', 'http:', '#', 'mailto:', 'data:image/svg+xml,')):
        assert (site / link.split('#')[0].split('?')[0]).is_file(), link
assert '.github/workflows' not in '\n'.join(allowed)
print(f'PASS: {len(allowed)} allowlisted files, SHA-256, static JSON, 94/16 counts, asset paths; no active workflow')

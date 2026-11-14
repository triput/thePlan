#!/bin/sh
# HELD: execute only within the separately approved exact-image collection run.
set -eu
exec /usr/local/bin/python3 -I -S -B - <<'PY'
import base64
import hashlib
import json
import sys

PATHS = (
    '/usr/local/lib/python3.12/http/client.py',
    '/usr/local/lib/python3.12/ssl.py',
    '/usr/local/lib/python3.12/email/message.py',
)
PER_FILE = 131072
TOTAL = 393216
ENVELOPE = 786432
rows = []
total = 0
for name in PATHS:
    with open(name, 'rb') as source:
        data = source.read(PER_FILE + 1)
    if not data or len(data) > PER_FILE:
        raise RuntimeError('source-size refusal')
    total += len(data)
    if total > TOTAL:
        raise RuntimeError('aggregate-size refusal')
    rows.append({'path': name, 'bytes': len(data),
                 'sha256': hashlib.sha256(data).hexdigest().upper(),
                 'base64': base64.b64encode(data).decode('ascii')})
payload = (json.dumps({'kind': 'T05-NATIVE-SOURCE-BYTES-V1', 'files': rows},
                      separators=(',', ':')) + '\n').encode('ascii')
if len(payload) > ENVELOPE:
    raise RuntimeError('envelope-size refusal')
sys.stdout.buffer.write(payload)
sys.stdout.buffer.flush()
PY

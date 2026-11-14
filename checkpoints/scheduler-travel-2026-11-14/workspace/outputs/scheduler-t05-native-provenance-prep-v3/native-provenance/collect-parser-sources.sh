#!/bin/sh
# HELD — not executed during prep. Copy to bounded capture dir inside ro packet mount.
set -eu
CAPTURE_ROOT="${CAPTURE_ROOT:-/packet/native-provenance/captured}"
mkdir -p "$CAPTURE_ROOT"
MAX_BYTES=59093
for rel in \
  /usr/local/lib/python3.12/http/client.py \
  /usr/local/lib/python3.12/ssl.py \
  /usr/local/lib/python3.12/email/message.py
do
  base=$(basename "$rel")
  dir=$(dirname "$rel" | sed 's|^/||' | tr '/' '_')
  dest="$CAPTURE_ROOT/${dir}__${base}"
  size=$(wc -c <"$rel" | tr -d ' ')
  if [ "$size" -gt "$MAX_BYTES" ]; then
    echo "STOP: file exceeds per-file cap: $rel" >&2
    exit 125
  fi
  cp -- "$rel" "$dest" || { echo "STOP: cp failed $rel" >&2; exit 125; }
  sha256sum "$dest"
  printf 'size_bytes=%s path=%s dest=%s\n' "$size" "$rel" "$dest"
done
echo "COLLECT_PARSER_SOURCES_HELD_COMPLETE"

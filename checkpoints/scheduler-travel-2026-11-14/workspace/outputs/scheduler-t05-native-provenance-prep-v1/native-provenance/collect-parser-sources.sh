#!/bin/sh
# HELD recipe — not executed during T05 native provenance preparation.
# Read-only copy of exactly three stdlib modules from pinned runner layout.
set -eu
ROOT="${PACKET_ROOT:-/packet}"
OUT="${CAPTURE_ROOT:-/packet/native-provenance/captured}"
MAX_BYTES=8388608
for rel in \
  /usr/local/lib/python3.12/http/client.py \
  /usr/local/lib/python3.12/ssl.py \
  /usr/local/lib/python3.12/email/message.py
do
  base=$(basename "$rel")
  dir=$(dirname "$rel" | sed 's|^/||' | tr '/' '_')
  dest="$OUT/${dir}__${base}"
  size=$(wc -c <"$rel" | tr -d ' ')
  if [ "$size" -gt "$MAX_BYTES" ]; then
    echo "STOP: file exceeds capture cap: $rel" >&2
    exit 125
  fi
  cp -- "$rel" "$dest"
  sha256sum "$dest"
  printf 'size_bytes=%s path=%s\n' "$size" "$rel"
done
echo "COLLECT_PARSER_SOURCES_HELD_COMPLETE"

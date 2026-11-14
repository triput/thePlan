#!/bin/sh
# PREPARED ONLY. Invoke only inside an approved disposable fixture container.
# Runner-owned C06 gate CA/leaf under existing /tmp. Never writes /fixture-tls.
# No untrusted CA. No DB private-key copy. Recipe authored; not executed in source prep.
set -eu
umask 077
test -x /bin/sh
test -x /usr/bin/openssl
test "$(id -u)" = 65534
TLS_DIR=/tmp/c06-gate-tls
test "$TLS_DIR" = /tmp/c06-gate-tls
test "$TLS_DIR" != /fixture-tls
if test -e /fixture-tls; then
  exit 1
fi
test -d "$TLS_DIR"
test -z "$(ls -A "$TLS_DIR")"
test "$(stat -c %u "$TLS_DIR")" = 65534
test "$(stat -c %a "$TLS_DIR")" = 700
TMPDIR=/tmp
export TMPDIR
/usr/bin/openssl req -x509 -newkey rsa:3072 -nodes -sha256 -days 2 \
  -subj /CN=Dex-Disposable-C06-Gate-CA \
  -keyout "$TLS_DIR/ca.key" -out "$TLS_DIR/ca.crt"
/usr/bin/openssl req -new -newkey rsa:3072 -nodes -sha256 \
  -subj /CN=native-fixture.invalid \
  -keyout "$TLS_DIR/server.key" -out "$TLS_DIR/server.csr"
printf '%s\n' 'subjectAltName=DNS:native-fixture.invalid' \
  'extendedKeyUsage=serverAuth' 'basicConstraints=critical,CA:FALSE' \
  'keyUsage=critical,digitalSignature,keyEncipherment' > "$TLS_DIR/server.ext"
/usr/bin/openssl x509 -req -sha256 -days 2 -in "$TLS_DIR/server.csr" \
  -CA "$TLS_DIR/ca.crt" -CAkey "$TLS_DIR/ca.key" -CAcreateserial \
  -extfile "$TLS_DIR/server.ext" -out "$TLS_DIR/server.crt"
/usr/bin/openssl verify -CAfile "$TLS_DIR/ca.crt" -verify_hostname native-fixture.invalid "$TLS_DIR/server.crt"
chmod 600 "$TLS_DIR/server.key" "$TLS_DIR/ca.key"
test -O "$TLS_DIR/ca.key" && test -O "$TLS_DIR/server.key"
test -O "$TLS_DIR/ca.crt" && test -O "$TLS_DIR/server.crt"
test "$(stat -c %u "$TLS_DIR/ca.key")" = 65534
test "$(stat -c %u "$TLS_DIR/server.key")" = 65534
test "$(stat -c %a "$TLS_DIR/ca.key")" = 600
test "$(stat -c %a "$TLS_DIR/server.key")" = 600
test "$(stat -c %u "$TLS_DIR/ca.crt")" = 65534
test "$(stat -c %u "$TLS_DIR/server.crt")" = 65534
# Public CA/leaf may be hashed into receipts. Never copy private keys to evidence.
# Keys remain in runner /tmp and are disposed with separately authorized exact-ID cleanup.

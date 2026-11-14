#!/bin/sh
# PREPARED ONLY — recipe source. DO NOT execute under preparation approval.
# No certificate/key generation authorized by prep. Invoke only inside an
# approved disposable fixture container under a later launch card.
# Vendor SANs for graph.microsoft.com / login.microsoftonline.com /
# www.googleapis.com / oauth2.googleapis.com. Wrong-CA and wrong-name distinct.
# tmpfs private keys. Never writes DB trust store. No untrusted CA into DB.
#
# CALLER CONTRACT (generation invocation — later launch card only):
#   1. Create/admit private TLS_DIR=/tmp/np-provider-tls (uid 65534, mode 0700, empty)
#      separately from DB /public-ca (read-only public mount; never replaced).
#   2. Invoke this recipe under the separately reviewed bounded owned-child /
#      reader retirement source (port/framing lineage). A bare recipe is not
#      proof that the child is bounded.
#   3. Generation itself remains HELD until launch approval.
set -eu
umask 077
test -x /bin/sh
test -x /usr/bin/openssl
test "$(id -u)" = 65534
TLS_DIR=/tmp/np-provider-tls
test "$TLS_DIR" = /tmp/np-provider-tls
test "$TLS_DIR" != /fixture-tls
test "$TLS_DIR" != /public-ca
if test -e /fixture-tls; then
  exit 1
fi
test -d "$TLS_DIR"
test -z "$(ls -A "$TLS_DIR")"
test "$(stat -c %u "$TLS_DIR")" = 65534
test "$(stat -c %a "$TLS_DIR")" = 700
TMPDIR=/tmp
export TMPDIR

# Fixture CA
/usr/bin/openssl req -x509 -newkey rsa:3072 -nodes -sha256 -days 2 \
  -subj /CN=Dex-Disposable-NP-Provider-CA \
  -keyout "$TLS_DIR/ca.key" -out "$TLS_DIR/ca.crt"

# Wrong CA (distinct trust material for NP-T03-WRONG-CA)
/usr/bin/openssl req -x509 -newkey rsa:3072 -nodes -sha256 -days 2 \
  -subj /CN=Dex-Disposable-NP-Wrong-CA \
  -keyout "$TLS_DIR/wrong-ca.key" -out "$TLS_DIR/wrong-ca.crt"

# Vendor SAN leaf (correct name)
/usr/bin/openssl req -new -newkey rsa:3072 -nodes -sha256 \
  -subj /CN=graph.microsoft.com \
  -keyout "$TLS_DIR/server.key" -out "$TLS_DIR/server.csr"
printf '%s\n' \
  'subjectAltName=DNS:graph.microsoft.com,DNS:login.microsoftonline.com,DNS:www.googleapis.com,DNS:oauth2.googleapis.com' \
  'extendedKeyUsage=serverAuth' 'basicConstraints=critical,CA:FALSE' \
  'keyUsage=critical,digitalSignature,keyEncipherment' > "$TLS_DIR/server.ext"
/usr/bin/openssl x509 -req -sha256 -days 2 -in "$TLS_DIR/server.csr" \
  -CA "$TLS_DIR/ca.crt" -CAkey "$TLS_DIR/ca.key" -CAcreateserial \
  -extfile "$TLS_DIR/server.ext" -out "$TLS_DIR/server.crt"

# Wrong-name leaf (distinct SAN for NP-T03-WRONG-NAME)
/usr/bin/openssl req -new -newkey rsa:3072 -nodes -sha256 \
  -subj /CN=wrong-name.fixture.invalid \
  -keyout "$TLS_DIR/wrong-name.key" -out "$TLS_DIR/wrong-name.csr"
printf '%s\n' \
  'subjectAltName=DNS:wrong-name.fixture.invalid' \
  'extendedKeyUsage=serverAuth' 'basicConstraints=critical,CA:FALSE' \
  'keyUsage=critical,digitalSignature,keyEncipherment' > "$TLS_DIR/wrong-name.ext"
/usr/bin/openssl x509 -req -sha256 -days 2 -in "$TLS_DIR/wrong-name.csr" \
  -CA "$TLS_DIR/ca.crt" -CAkey "$TLS_DIR/ca.key" -CAcreateserial \
  -extfile "$TLS_DIR/wrong-name.ext" -out "$TLS_DIR/wrong-name.crt"

/usr/bin/openssl verify -CAfile "$TLS_DIR/ca.crt" -verify_hostname graph.microsoft.com "$TLS_DIR/server.crt"
chmod 600 "$TLS_DIR/server.key" "$TLS_DIR/ca.key" "$TLS_DIR/wrong-ca.key" "$TLS_DIR/wrong-name.key"
test -O "$TLS_DIR/ca.key" && test -O "$TLS_DIR/server.key"
test -O "$TLS_DIR/ca.crt" && test -O "$TLS_DIR/server.crt"
test "$(stat -c %u "$TLS_DIR/ca.key")" = 65534
test "$(stat -c %u "$TLS_DIR/server.key")" = 65534
test "$(stat -c %a "$TLS_DIR/ca.key")" = 600
test "$(stat -c %a "$TLS_DIR/server.key")" = 600
# Public CA/leaf may be hashed into receipts. Never copy private keys to evidence.
# Keys remain in runner /tmp and are disposed with separately authorized exact-ID cleanup.
# RECIPE ONLY — preparation must not run this script.

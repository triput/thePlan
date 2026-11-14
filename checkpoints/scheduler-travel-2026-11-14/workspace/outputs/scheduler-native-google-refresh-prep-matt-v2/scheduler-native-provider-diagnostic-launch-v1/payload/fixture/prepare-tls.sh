#!/bin/sh
# PREPARED ONLY. Invoke only inside an approved disposable fixture container.
set -eu
umask 077
TLS_DIR=/fixture-tls
test -d "$TLS_DIR"
test -z "$(ls -A "$TLS_DIR")"
# Supervisor must verify /fixture-tls is the reviewed tmpfs, not a host mount.
openssl req -x509 -newkey rsa:3072 -nodes -sha256 -days 2 \
  -subj /CN=Dex-Disposable-Fixture-CA \
  -keyout "$TLS_DIR/ca.key" -out "$TLS_DIR/ca.crt"
openssl req -new -newkey rsa:3072 -nodes -sha256 \
  -subj /CN=native-fixture.invalid \
  -keyout "$TLS_DIR/server.key" -out "$TLS_DIR/server.csr"
printf '%s\n' 'subjectAltName=DNS:native-fixture.invalid' \
  'extendedKeyUsage=serverAuth' 'basicConstraints=critical,CA:FALSE' \
  'keyUsage=critical,digitalSignature,keyEncipherment' > "$TLS_DIR/server.ext"
openssl x509 -req -sha256 -days 2 -in "$TLS_DIR/server.csr" \
  -CA "$TLS_DIR/ca.crt" -CAkey "$TLS_DIR/ca.key" -CAcreateserial \
  -extfile "$TLS_DIR/server.ext" -out "$TLS_DIR/server.crt"
openssl verify -CAfile "$TLS_DIR/ca.crt" -verify_hostname native-fixture.invalid "$TLS_DIR/server.crt"
chmod 600 "$TLS_DIR/server.key" "$TLS_DIR/ca.key"
openssl req -x509 -newkey rsa:3072 -nodes -sha256 -days 2 \
  -subj /CN=Dex-Untrusted-Fixture-CA \
  -keyout "$TLS_DIR/untrusted-ca.key" -out "$TLS_DIR/untrusted-ca.crt"
chmod 600 "$TLS_DIR/untrusted-ca.key"
# Public CA and certificate may be hashed into receipts. Never copy private keys
# to evidence output. Supervisor owns tmpfs lifecycle and exact-ID cleanup.

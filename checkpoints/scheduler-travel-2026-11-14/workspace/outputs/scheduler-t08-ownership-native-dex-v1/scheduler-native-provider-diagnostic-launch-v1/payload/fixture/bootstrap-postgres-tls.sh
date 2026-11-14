#!/bin/sh
# Prepared only. Requires reviewed PostgreSQL/OpenSSL/Python image and tmpfs.
set -eu
umask 077
for interface in /sys/class/net/*; do
    [ "$interface" = /sys/class/net/lo ] || exit 65
done
[ "$(id -u)" -ne 0 ] || exit 65
data=/var/lib/postgresql/data/fixture
[ ! -e "$data" ] || exit 65
[ -d /fixture-tls ] || exit 65
/bin/sh /packet/fixture/prepare-tls.sh > /var/lib/postgresql/data/tls-setup.log 2>&1
initdb -D "$data" -U dex_fixture --auth-local=trust --auth-host=reject --no-instructions
printf '%s\n' 'CREATE DATABASE dex_fixture;' | postgres --single -D "$data" postgres
cat > "$data/pg_hba.conf" <<'HBA'
hostssl dex_fixture dex_fixture 127.0.0.1/32 trust
host all all 0.0.0.0/0 reject
host all all ::/0 reject
HBA
# Postgres becomes PID1 so the exact-ID SIGINT reaches it directly.
# Bootstrap errors exit nonzero; no restart/recovery loop.
exec postgres -D "$data" -c listen_addresses=127.0.0.1 -c port=5432 \
    -c unix_socket_directories= -c max_connections=8 -c shared_buffers=32MB \
    -c statement_timeout=5000 -c lock_timeout=1000 -c ssl=on \
    -c ssl_cert_file=/fixture-tls/server.crt -c ssl_key_file=/fixture-tls/server.key \
    -c ssl_min_protocol_version=TLSv1.2 -c logging_collector=off \
    -c log_destination=stderr > /fixture-tls/server.log 2>&1

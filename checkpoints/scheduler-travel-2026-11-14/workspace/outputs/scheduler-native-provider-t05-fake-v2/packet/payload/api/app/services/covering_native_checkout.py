"""Prepared joined libpq checkout and local retirement; no ORM factory installed."""
import os
from dataclasses import dataclass
from ipaddress import ip_address
from pathlib import Path
from selectors import DefaultSelector, EVENT_READ, EVENT_WRITE
from threading import get_ident

from psycopg import pq
from psycopg.conninfo import make_conninfo
from app.services.covering_target_transaction import CoveringRootOutcomeUnknown


@dataclass(frozen=True)
class PostgreSQLPeer:
    hostname: str
    address: str
    port: int
    database: str
    username: str
    ca_file: str
    absent_passfile: str
    # Explicit approved client-certificate paths or explicit absent paths.
    client_cert: str
    client_key: str

    def validate(self):
        ip_address(self.address)
        if (not self.hostname or not self.database or not self.username
                or type(self.port) is not int or not 1<=self.port<=65535
                or not self.ca_file or not self.absent_passfile
                or not self.client_cert or not self.client_key):
            raise ValueError("incomplete PostgreSQL profile")
        if Path(self.absent_passfile).exists():
            raise ValueError("passfile must be explicitly absent")
        if any(k.upper().startswith("PG") for k in os.environ):
            raise ValueError("ambient libpq configuration refused")


class NativeLease:
    def __init__(self, pgconn, remaining):
        self.pgconn=pgconn
        self.remaining=remaining
        self.owner=get_ident()
        self.closed=False
        self.busy=False

    def check(self):
        if get_ident()!=self.owner or self.closed:
            raise CoveringRootOutcomeUnknown()
        return self.remaining()

    def ready(self, mask):
        with DefaultSelector() as selector:
            fd=self.pgconn.socket
            if fd<0 or mask not in (EVENT_READ,EVENT_WRITE,EVENT_READ|EVENT_WRITE):
                raise CoveringRootOutcomeUnknown()
            selector.register(fd,mask)
            while True:
                events=selector.select(min(self.check(),0.05))
                if self.pgconn.socket!=fd:
                    raise CoveringRootOutcomeUnknown()
                if events:
                    self.check()
                    return events[0][1]

    def drive(self, generator):
        if self.busy:
            raise CoveringRootOutcomeUnknown()
        self.check()
        self.busy=True
        try:
            mask=next(generator)
            while True:
                self.check()
                mask=generator.send(self.ready(int(mask)))
        except StopIteration as completed:
            self.check()
            return completed.value
        except BaseException:
            # No cancel helper, second connection, rollback or retry on UNKNOWN.
            self.close()
            raise CoveringRootOutcomeUnknown() from None
        finally:
            generator.close()
            self.busy=False

    def close(self):
        if get_ident()!=self.owner:
            raise CoveringRootOutcomeUnknown()
        if not self.closed:
            self.closed=True
            self.pgconn.finish()


def checkout_postgresql(profile, *, password, remaining):
    """One dial attempt using numeric hostaddr and verify-full hostname.

    Caller must reserve a role before entry and own any returned PGconn.
    Password is supplied only at an eventual authorized binding, never discovered.
    """
    profile.validate()
    remaining()
    info=make_conninfo(host=profile.hostname,hostaddr=profile.address,
        port=profile.port,dbname=profile.database,user=profile.username,
        password=password,sslmode="verify-full",sslrootcert=profile.ca_file,
        sslcert=profile.client_cert,sslkey=profile.client_key,
        passfile=profile.absent_passfile,gssencmode="disable",
        application_name="covering_refresh",connect_timeout=0)
    pgconn=None
    lease=None
    try:
        pgconn=pq.PGconn.connect_start(info.encode("utf-8"))
        lease=NativeLease(pgconn,remaining)
        while True:
            lease.check()
            state=pgconn.connect_poll()
            lease.check()
            if state==pq.PollingStatus.OK:
                break
            mask={pq.PollingStatus.READING:EVENT_READ,
                  pq.PollingStatus.WRITING:EVENT_WRITE}.get(state)
            if mask is None:
                raise CoveringRootOutcomeUnknown()
            lease.ready(mask)
        if pgconn.status!=pq.ConnStatus.OK or not pgconn.ssl_in_use:
            raise CoveringRootOutcomeUnknown()
        pgconn.nonblocking=1
        return lease
    except BaseException:
        if lease is not None:
            lease.close()
        elif pgconn is not None:
            pgconn.finish()
        raise CoveringRootOutcomeUnknown() from None


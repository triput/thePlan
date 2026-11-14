"""Fixture-only binding for Jim's real SQL assessment cases. Not installed.

Setup/mutator transactions are explicitly outside application evidence. Native
ASSESSMENT sessions use the frozen production factory and its terminal receipt.
"""
from dataclasses import dataclass
from threading import Lock, get_ident
import sys

import psycopg
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.services.covering_native_orm_factory import NativeORMFactories
from app.services.covering_request_budget import CoveringRequestBudget
from app.services.covering_role_admission import CoveringRole
from app.services.covering_target_transaction import CoveringRootOutcomeUnknown


@dataclass
class Owned:
    thread: int
    kind: str
    session: object
    engine: object = None
    binding: object = None
    budget: object = None


class AssessmentFactory:
    def __init__(self, *, profile, password_supplier, runtime_pins, record):
        self.profile = profile
        self.password_supplier = password_supplier
        self.runtime_pins = runtime_pins
        self.record = record
        self._owned = {}
        self._lock = Lock()
        self._stopped = False
        self._native = []

    def _register(self, item):
        with self._lock:
            if id(item.session) in self._owned:
                raise RuntimeError('duplicate session')
            self._owned[id(item.session)] = item
        self.record('session_open', {'kind': item.kind, 'thread': item.thread})
        return item.session

    def _take(self, session, kinds):
        with self._lock:
            item = self._owned.get(id(session))
            if item is None or item.session is not session or item.thread != get_ident() or item.kind not in kinds:
                raise RuntimeError('session ownership mismatch')
            del self._owned[id(session)]
        return item

    def _setup(self, kind):
        with self._lock:
            if self._stopped:
                raise RuntimeError('fixture stopped')
        self.runtime_pins.verify()
        self.profile.validate()
        p = self.profile
        def creator():
            # Synthetic setup only. Bound connect/query/lock waits; no retries.
            return psycopg.connect(host=p.hostname, hostaddr=p.address, port=p.port,
                dbname=p.database, user=p.username, password=self.password_supplier(),
                sslmode='verify-full', sslrootcert=p.ca_file, sslcert=p.client_cert,
                sslkey=p.client_key, passfile=p.absent_passfile, gssencmode='disable',
                connect_timeout=5, options='-c statement_timeout=5000 -c lock_timeout=1000',
                application_name='dex_fixture_setup')
        engine = create_engine('postgresql+psycopg://', creator=creator, poolclass=NullPool)
        session = None
        try:
            session = Session(engine, expire_on_commit=False)
            return self._register(Owned(get_ident(), kind, session, engine=engine))
        except BaseException:
            # Preserve the primary failure; prevent continuation after partial setup.
            with self._lock:
                self._stopped = True
                if session is not None:
                    self._owned.pop(id(session), None)
            try:
                if session is not None:
                    session.close()
            except BaseException:
                pass
            try:
                engine.dispose()
            except BaseException:
                pass
            raise

    def open_setup_session(self):
        return self._setup('setup')

    def open_mutator_session(self):
        return self._setup('mutator')

    def open_assessment_session(self):
        with self._lock:
            if self._stopped:
                raise RuntimeError('fixture stopped')
        budget = CoveringRequestBudget()
        factory = NativeORMFactories(profile=self.profile,
            password_supplier=self.password_supplier, runtime_pins=self.runtime_pins)
        self._native.append(factory)  # Retain any quarantined driver evidence.
        try:
            binding = factory.session_factory(CoveringRole.ASSESSMENT, None, budget.work_remaining)
        except BaseException:
            with self._lock:
                self._stopped = True
            raise
        return self._register(Owned(get_ident(), 'assessment', binding.session,
                                    binding=binding, budget=budget))

    def close(self, session):
        item = self._take(session, ('setup', 'mutator'))
        try:
            session.close()
        finally:
            item.engine.dispose()
        self.record('session_closed', {'kind': item.kind, 'application_terminal_proof': False})

    def close_known(self, session):
        item = self._take(session, ('assessment',))
        driver = item.binding.identity
        primary = sys.exception()
        unknown = (isinstance(primary, CoveringRootOutcomeUnknown)
                   or driver._io_unknown or driver._cutoff or driver.closed)
        if unknown:
            with self._lock:
                self._stopped = True
            # Never call close_known or send terminal SQL after native UNKNOWN.
            # Quarantine is local cutoff/retirement only; factory forbids retry.
            if not driver.closed and not driver._retirement_attempted:
                try:
                    item.binding.quarantine()
                except BaseException:
                    # Native driver retains retirement failure; no retry or terminal SQL.
                    pass
            self.record('assessment_unknown', {'new_terminal_sent': False})
            raise CoveringRootOutcomeUnknown()
        try:
            with item.budget.cleanup():
                completion = item.binding.close_known(item.budget.cleanup_remaining)
            if not (completion.identity is driver and completion.outcome_known
                    and completion.retired and completion.locks_exited):
                raise CoveringRootOutcomeUnknown()
        except BaseException:
            with self._lock:
                self._stopped = True
            if not driver.closed and not driver._retirement_attempted:
                try:
                    item.binding.quarantine()
                except BaseException:
                    # Native driver retains retirement failure; no retry or terminal SQL.
                    pass
            raise
        self.record('assessment_retired', {'native_terminal_acknowledged': True})

    def require_drained(self):
        with self._lock:
            if self._owned or self._stopped:
                raise RuntimeError('fixture not cleanly drained')
        if any(factory.quarantined for factory in self._native):
            raise RuntimeError('native quarantine retained')

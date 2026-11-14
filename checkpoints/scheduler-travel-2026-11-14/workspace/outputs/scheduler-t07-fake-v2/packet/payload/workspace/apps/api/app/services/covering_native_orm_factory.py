"""Covering-only ORM/native factory. Uninstalled; execution separately held.

A fresh NullPool engine and one-use creator own each admitted role. Native
terminal evidence, not Session.commit returning, determines the outcome.
"""
from dataclasses import dataclass
import socket
import sys
from threading import get_ident

import psycopg
from psycopg import pq
import sqlalchemy
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.services.covering_native_checkout import checkout_postgresql
from app.services.covering_native_terminal import exchange_root_terminal
from app.services.covering_parent_adapter import (
    RootCommand, RootOperation, NativeTerminalResult, CoveringTerminalNotDispatched,
)
from app.services.covering_request_budget import CoveringDeadlineExceeded
from app.services.covering_role_admission import CoveringRole
from app.services.covering_role_connector import ParentBinding, SessionBinding, RoleCompletion
from app.services.covering_target_transaction import CoveringRootOutcomeUnknown, RootOutcome

# Strong references prevent GC/another thread from silently closing a driver
# whose cutoff or local retirement could not be proved. No automatic recovery.
_UNRETIRED = []


@dataclass(frozen=True)
class NativeRuntimePins:
    python: tuple
    psycopg: str
    sqlalchemy: str
    pq_implementation: str
    pq_runtime: int
    pq_build: int

    def verify(self):
        actual=(tuple(sys.version_info[:3]),psycopg.__version__,sqlalchemy.__version__,
                pq.__impl__,pq.version(),pq.__build_version__)
        expected=(self.python,self.psycopg,self.sqlalchemy,self.pq_implementation,
                  self.pq_runtime,self.pq_build)
        if actual!=expected:
            raise CoveringRootOutcomeUnknown()


class _CoveringCursor(psycopg.Cursor):
    def _check_results(self, results):
        connection=self._conn
        connection._unique_error=False
        try:
            super()._check_results(results)
        except psycopg.Error as exc:
            # Only the reviewed collision may authorize automatic root rollback.
            # Savepoint activity is checked separately at the rollback boundary.
            connection._unique_error=(
                len(results)==1 and results[0].status==pq.ExecStatus.FATAL_ERROR
                and exc.sqlstate=="23505"
                and exc.diag.constraint_name=="unique_external_event"
                and connection.pgconn.status==pq.ConnStatus.OK
                and connection.pgconn.transaction_status==pq.TransactionStatus.INERROR
                and not connection.pgconn.is_busy())
            raise

    def execute(self, query, params=None, **kwargs):
        self._conn._guard()
        if isinstance(query,(str,bytes)):
            raw=query.decode("ascii",errors="ignore") if isinstance(query,bytes) else query
            command=raw.strip().upper().rstrip(";").strip()
            if command in ("COMMIT","ROLLBACK","END","ABORT"):
                raise CoveringRootOutcomeUnknown()
        return super().execute(query,params,**kwargs)

    def copy(self,*args,**kwargs):
        raise CoveringRootOutcomeUnknown()

    def stream(self,*args,**kwargs):
        # psycopg streaming cleanup may invoke an out-of-band cancel.
        raise CoveringRootOutcomeUnknown()

    def _maybe_prepare_gen(self, pgq, *, prepare=None, binary=None):
        # No prepared-statement maintenance after acknowledged rollback.
        return (yield from super()._maybe_prepare_gen(pgq,prepare=False,binary=binary))

    def executemany(self, query, params_seq, *, returning=False):
        self._conn._guard()
        with self._conn.lock:
            self._conn.wait(self._executemany_gen_no_pipeline(query,params_seq,returning))


class CoveringORMConnection(psycopg.Connection):
    def __init__(self, lease, role):
        super().__init__(lease.pgconn)
        self.lease=lease
        self.role=role
        self.owner=get_ident()
        self.cursor_factory=_CoveringCursor
        self.prepare_threshold=None
        self.root=None
        self.orm=None
        self.sa=None
        self.adapter=None
        self.operation=None
        self.terminal=None
        self._sequence=0
        self._busy=False
        self._unique_error=False
        self._automatic=False
        self._cutoff=False
        self._io_unknown=False
        self._retiring=False
        self._retired=False
        self._retirement_attempted=False
        self._quarantine_registered=False
        self._resources=None

    def _retain(self):
        if not self._quarantine_registered:
            self._quarantine_registered=True
            _UNRETIRED.append(self)

    @classmethod
    def connect(cls,*args,**kwargs):
        raise CoveringRootOutcomeUnknown()  # Only explicit admitted checkout.

    def _guard(self):
        if get_ident()!=self.owner or self.closed or self._cutoff or self._busy or self._io_unknown:
            raise CoveringRootOutcomeUnknown()
        if self.terminal is not None:
            raise CoveringRootOutcomeUnknown()
        self.lease.check()

    def capture(self, session, connection):
        root=session.get_transaction()
        if (self.root is not None or root is None or not root.is_active
                or session.in_nested_transaction()
                or connection.connection.driver_connection is not self
                or self.pgconn.transaction_status!=pq.TransactionStatus.INTRANS):
            raise CoveringRootOutcomeUnknown()
        self.root,self.orm,self.sa=root,session,connection
        session.info["covering_remaining"]=lambda:self.lease.check()

    def bind_parent(self, adapter):
        if self.role is not CoveringRole.PARENT or self.adapter is not None:
            raise CoveringRootOutcomeUnknown()
        if self.orm.get_transaction() is not self.root:
            raise CoveringRootOutcomeUnknown()
        self.adapter=adapter
        self.orm.info["covering_native_flush_bound"]=adapter
        adapter.arm_flush_rollback()

    def cursor(self,*args,**kwargs):
        self._guard()
        if (args and args[0]) or kwargs.get("name"):
            raise CoveringRootOutcomeUnknown()
        return super().cursor(*args,**kwargs)

    def pipeline(self,*args,**kwargs):
        raise CoveringRootOutcomeUnknown()
    def transaction(self,*args,**kwargs):
        raise CoveringRootOutcomeUnknown()
    def cancel(self,*args,**kwargs):
        raise CoveringRootOutcomeUnknown()
    def cancel_safe(self,*args,**kwargs):
        raise CoveringRootOutcomeUnknown()
    def tpc_begin(self,*args,**kwargs):
        raise CoveringRootOutcomeUnknown()
    def reset(self,*args,**kwargs):
        raise CoveringRootOutcomeUnknown()

    def wait(self, generator, interval=0.1):
        # Do not use psycopg's default interrupt path: it may open a cancellation
        # connection and drain outside our request budget.
        if get_ident()!=self.owner or self._busy or self._cutoff or self.closed or self._io_unknown:
            raise CoveringRootOutcomeUnknown()
        self._busy=True
        try:
            self.lease.check()
            mask=next(generator)
            while True:
                ready=self.lease.ready(int(mask))
                self.lease.check()
                mask=generator.send(ready)
        except StopIteration as done:
            # Preserve a terminal already received and classified by the
            # exchange generator, even if the clock expires immediately after.
            return done.value
        except CoveringTerminalNotDispatched:
            raise  # Parent policy may perform its one known cleanup rollback.
        except BaseException as exc:
            known_collision=(self.role is CoveringRole.PARENT
                and isinstance(exc,psycopg.Error) and self._unique_error
                and self.pgconn.transaction_status==pq.TransactionStatus.INERROR
                and not self.pgconn.is_busy())
            if known_collision:
                raise
            # Latch before unwinding into SQLAlchemy, which might otherwise
            # attempt automatic rollback on the still-writable transport.
            self._io_unknown=True
            raise CoveringRootOutcomeUnknown() from None
        finally:
            try:
                generator.close()
            except BaseException:
                self._io_unknown=True
                raise CoveringRootOutcomeUnknown() from None
            finally:
                self._busy=False
                if self._io_unknown:
                    self.cut_off_frontend()

    def _exec_command(self, command, result_format=pq.Format.TEXT):
        raw=command.encode("ascii") if isinstance(command,str) else command
        if self.root is None or raw not in (b"COMMIT",b"ROLLBACK"):
            if self.terminal is not None or self._cutoff:
                raise CoveringRootOutcomeUnknown()
            return (yield from super()._exec_command(command,result_format))
        operation=self.operation
        if (operation is None or operation.root is not self.root
                or raw!=operation.command.value or self.terminal is not None
                or result_format!=pq.Format.TEXT):
            raise CoveringRootOutcomeUnknown()
        dispatched=False
        def sent():
            nonlocal dispatched
            dispatched=True
        try:
            self.terminal=yield from exchange_root_terminal(
                self.pgconn,captured_root=self.root,operation=operation,
                remaining=self.lease.remaining,mark_dispatch=sent)
        except CoveringDeadlineExceeded:
            if not dispatched:
                raise CoveringTerminalNotDispatched() from None
            raise CoveringRootOutcomeUnknown() from None
        if self._automatic:
            self.adapter.observe_flush_rollback(self.terminal)
        return None

    def _new_operation(self, command):
        self._sequence+=1
        return RootOperation(self.root,self._sequence,command)

    def _ordinary_terminal(self, command):
        if self.role is CoveringRole.PARENT:
            raise CoveringRootOutcomeUnknown()
        if command is RootCommand.COMMIT and self.role is not CoveringRole.RECORDER:
            # TOKEN/TELEMETRY commits require explicit factory-owned finish.
            raise CoveringRootOutcomeUnknown()
        if self.terminal is not None:
            # ORM local logical cleanup only; never repeat terminal SQL.
            if command is RootCommand.ROLLBACK and self.pgconn.transaction_status==pq.TransactionStatus.IDLE:
                return
            raise CoveringRootOutcomeUnknown()
        self.operation=self._new_operation(command)
        try:
            if command is RootCommand.COMMIT:
                return psycopg.Connection.commit(self)
            return psycopg.Connection.rollback(self)
        finally:
            self.operation=None

    def commit(self):
        if self.root is None:
            return psycopg.Connection.commit(self)
        if self.operation is None:
            return self._ordinary_terminal(RootCommand.COMMIT)
        if self.operation.command is not RootCommand.COMMIT:
            raise CoveringRootOutcomeUnknown()
        return psycopg.Connection.commit(self)

    def rollback(self):
        if get_ident()!=self.owner:
            raise CoveringRootOutcomeUnknown()
        if self._io_unknown and not self._cutoff and not self.closed:
            raise CoveringRootOutcomeUnknown()
        if self._cutoff or self.closed:
            # Invalidation may clean ORM bookkeeping after the socket is gone.
            return None
        if self.root is None:
            return psycopg.Connection.rollback(self)
        if self.terminal is not None:
            if self.pgconn.transaction_status==pq.TransactionStatus.IDLE:
                return None
            raise CoveringRootOutcomeUnknown()
        if self.operation is not None:
            if self.operation.command is not RootCommand.ROLLBACK:
                raise CoveringRootOutcomeUnknown()
            return psycopg.Connection.rollback(self)
        if self.role is not CoveringRole.PARENT:
            return self._ordinary_terminal(RootCommand.ROLLBACK)
        if self.adapter is None:
            raise CoveringRootOutcomeUnknown()
        operation=self.adapter.begin_flush_rollback(
            self.orm.get_transaction(),
            known_error_drained=self._unique_error and not self.pgconn.is_busy()
                and self.pgconn.transaction_status==pq.TransactionStatus.INERROR,
            savepoint_active=self.sa.in_nested_transaction())
        self.operation=operation
        self._automatic=True
        old=self.lease.remaining
        self.lease.remaining=lambda:self.adapter.flush_rollback_remaining(operation)
        try:
            return psycopg.Connection.rollback(self)
        finally:
            self.lease.remaining=old
            self._automatic=False
            self._unique_error=False
            self.operation=None

    def finish(self, operation, *, remaining):
        if (get_ident()!=self.owner or operation.root is not self.root
                or self.operation is not None or self.terminal is not None
                or self.orm.get_transaction() is not self.root
                or self.orm.in_nested_transaction()):
            raise CoveringRootOutcomeUnknown()
        # Refuse BEFORE entering Session.commit, where SQLAlchemy could otherwise
        # mark its logical transaction failed before fallback rollback is chosen.
        try:
            remaining()
        except CoveringDeadlineExceeded:
            raise CoveringTerminalNotDispatched() from None
        self.operation=operation
        self.lease.remaining=remaining
        try:
            if operation.command is RootCommand.COMMIT:
                self.orm.commit()
            else:
                self.orm.rollback()
            if type(self.terminal) is not NativeTerminalResult or self.terminal.operation is not operation:
                raise CoveringRootOutcomeUnknown()
            return self.terminal
        finally:
            self.operation=None

    def token_terminal(self, *, commit, remaining):
        result=self.finish(self._new_operation(RootCommand.COMMIT if commit else RootCommand.ROLLBACK),
                           remaining=remaining)
        if not (result.command_sent and result.drained and result.idle
                and result.command_tag==result.operation.command.value):
            raise CoveringRootOutcomeUnknown()
        return RootOutcome.COMMIT_ACKNOWLEDGED if commit else RootOutcome.ROLLBACK_ACKNOWLEDGED

    def cut_off_frontend(self):
        if get_ident()!=self.owner or self._busy:
            self._retain()
            return False
        if self._cutoff:
            return True
        if self.closed:
            self._cutoff=True
            return True
        fd=self.pgconn.socket
        if fd<0:
            self._retain()
            return False
        wrapper=None
        try:
            # Borrow the exact socket handle; detach avoids a second owner/close.
            wrapper=socket.socket(fileno=fd)
            if self.pgconn.socket!=fd:
                self._retain()
                return False
            wrapper.shutdown(socket.SHUT_WR)
            self._cutoff=True
            return True
        except OSError:
            self._retain()
            return False
        finally:
            if wrapper is not None:
                wrapper.detach()

    def close(self):
        if get_ident()!=self.owner:
            raise CoveringRootOutcomeUnknown()
        if self.closed:
            return
        if self.root is not None and self.terminal is None and not self._cutoff:
            raise CoveringRootOutcomeUnknown()
        psycopg.Connection.close(self)
        self.lease.closed=True

    def retire(self):
        if self._retirement_attempted:
            return self._retired
        if self._retiring or get_ident()!=self.owner:
            self._retain()
            return False
        self._retirement_attempted=True
        self._retiring=True
        try:
            self.close()
            if self._resources is not None:
                self._resources()
            self._retired=True
            return True
        except BaseException:
            self._retain()
            raise
        finally:
            self._retiring=False


class NativeORMFactories:
    """Explicit factory object; never constructed or installed at app startup."""
    def __init__(self, *, profile, password_supplier, runtime_pins):
        self.profile=profile
        self.password_supplier=password_supplier
        self.runtime_pins=runtime_pins
        # Retain failed cutoff objects for honest reconciliation, never reconnect.
        self.quarantined=[]

    def _open(self, role, remaining):
        self.runtime_pins.verify()
        remaining()
        lease=checkout_postgresql(self.profile,password=self.password_supplier(),remaining=remaining)
        driver=None
        engine=None
        connection=None
        session=None
        try:
            driver=CoveringORMConnection(lease,role)
            def release_local():
                # Invalidation removes the physical connection BEFORE logical
                # ORM close; the one-use creator refuses any replacement.
                if connection is not None:
                    connection.invalidate()
                if session is not None:
                    session.close()
                if connection is not None:
                    connection.close()
                if engine is not None:
                    engine.dispose()
            driver._resources=release_local
            used=False
            def creator():
                nonlocal used
                if used:
                    raise CoveringRootOutcomeUnknown()
                used=True
                return driver
            engine=create_engine("postgresql+psycopg://",creator=creator,poolclass=NullPool,
                                 pool_reset_on_return=None,use_native_hstore=False)
            connection=engine.connect()
            session=Session(bind=connection,autoflush=False,expire_on_commit=False)
            session.begin()
            session.execute(text("SELECT 1"))
            driver.capture(session,connection)
            if role is CoveringRole.TOKEN:
                session.info["covering_token_terminal"]=driver.token_terminal
            return driver,session
        except BaseException:
            if driver is None:
                lease.close()
            else:
                try:
                    if not driver.cut_off_frontend() or not driver.retire():
                        self.quarantined.append(driver)
                except BaseException:
                    driver._retain()
                    self.quarantined.append(driver)
            raise CoveringRootOutcomeUnknown() from None

    def parent_factory(self,target,remaining):
        driver,session=self._open(CoveringRole.PARENT,remaining)
        return ParentBinding(session,driver,driver.root,driver)

    def session_factory(self,role,target,remaining):
        driver,session=self._open(role,remaining)
        def quarantine():
            if not driver.cut_off_frontend() or not driver.retire():
                self.quarantined.append(driver)
        def close_known(cleanup_remaining):
            driver.lease.remaining=cleanup_remaining
            if driver.terminal is None:
                command=RootCommand.COMMIT if role is CoveringRole.TELEMETRY else RootCommand.ROLLBACK
                driver.finish(driver._new_operation(command),remaining=cleanup_remaining)
            terminal=driver.terminal
            if (type(terminal) is not NativeTerminalResult
                    or terminal.operation.root is not driver.root
                    or terminal.command_sent is not True or not terminal.drained
                    or not terminal.idle or terminal.command_tag!=terminal.operation.command.value):
                raise CoveringRootOutcomeUnknown()
            if not driver.retire():
                raise CoveringRootOutcomeUnknown()
            return RoleCompletion(driver,True,True,True)
        return SessionBinding(session,driver,close_known,quarantine)


"""Prepared factory policy checks. No sockets, DBAPI construction or database."""
from types import SimpleNamespace as NS
from threading import get_ident
import pytest
from psycopg import pq

from app.services import covering_native_orm_factory as native
from app.services.covering_parent_adapter import (
    RootOperation, RootCommand, NativeTerminalResult, CoveringTerminalNotDispatched,
)
from app.services.covering_request_budget import CoveringDeadlineExceeded
from app.services.covering_role_admission import CoveringRole
from app.services.covering_target_transaction import CoveringRootOutcomeUnknown


def waiting(ready):
    events=[]
    obj=NS(owner=get_ident(),closed=False,_cutoff=False,_busy=False,_io_unknown=False,
        _unique_error=False,role=CoveringRole.PARENT,
        pgconn=NS(transaction_status=pq.TransactionStatus.INTRANS,is_busy=lambda:False),
        lease=NS(check=lambda:100,ready=ready))
    def cutoff():
        events.append(("cutoff",obj._busy,obj._io_unknown))
        obj._cutoff=True
        return True
    obj.cut_off_frontend=cutoff
    return obj,events


def test_joined_wait_returns_exact_received_evidence():
    obj,events=waiting(lambda mask:mask)
    expected=object()
    def exchange():
        assert (yield 1)==1
        return expected
    assert native.CoveringORMConnection.wait(obj,exchange()) is expected
    assert not obj._busy and events==[]


def test_uncertain_wait_latches_before_orm_unwind():
    def failed(mask):
        raise OSError("synthetic")
    obj,events=waiting(failed)
    def exchange():
        try:
            yield 1
        finally:
            events.append(("generator_closed",obj._io_unknown))
    with pytest.raises(CoveringRootOutcomeUnknown):
        native.CoveringORMConnection.wait(obj,exchange())
    assert events==[("generator_closed",True),("cutoff",False,True)]


def test_wait_preserves_proven_predispatch_refusal():
    obj,events=waiting(lambda mask:mask)
    def exchange():
        yield 1
        raise CoveringTerminalNotDispatched()
    with pytest.raises(CoveringTerminalNotDispatched):
        native.CoveringORMConnection.wait(obj,exchange())
    assert not obj._io_unknown and events==[]


def test_generator_close_failure_still_cuts_off_transport():
    def failed(mask):
        raise OSError("synthetic")
    obj,events=waiting(failed)
    def exchange():
        try:
            yield 1
        finally:
            raise RuntimeError("synthetic generator cleanup failure")
    with pytest.raises(CoveringRootOutcomeUnknown):
        native.CoveringORMConnection.wait(obj,exchange())
    assert not obj._busy and obj._io_unknown
    assert events==[("cutoff",False,True)]


def test_acknowledged_rollback_has_no_second_native_command():
    obj=NS(owner=get_ident(),_io_unknown=False,_cutoff=False,closed=False,
           root=object(),terminal=object(),
           pgconn=NS(transaction_status=pq.TransactionStatus.IDLE))
    assert native.CoveringORMConnection.rollback(obj) is None


def test_foreign_thread_rollback_is_refused():
    obj=NS(owner=get_ident()+1)
    with pytest.raises(CoveringRootOutcomeUnknown):
        native.CoveringORMConnection.rollback(obj)


def test_wrong_root_finish_never_reaches_orm():
    obj=NS(owner=get_ident(),root=object())
    operation=RootOperation(object(),1,RootCommand.COMMIT)
    with pytest.raises(CoveringRootOutcomeUnknown):
        native.CoveringORMConnection.finish(obj,operation,remaining=lambda:100)


def test_predispatch_expiry_never_enters_orm_commit():
    root=object()
    obj=NS(owner=get_ident(),root=root,operation=None,terminal=None,
           orm=NS(get_transaction=lambda:root,in_nested_transaction=lambda:False))
    def expired():
        raise CoveringDeadlineExceeded()
    with pytest.raises(CoveringTerminalNotDispatched):
        native.CoveringORMConnection.finish(obj,RootOperation(root,1,RootCommand.COMMIT),
                                           remaining=expired)


def test_failed_retirement_is_not_retried():
    events=[]
    def failed_resources():
        events.append("resources")
        raise RuntimeError("synthetic local cleanup failure")
    obj=NS(_retirement_attempted=False,_retiring=False,_retired=False,owner=get_ident(),
           close=lambda:events.append("close"),_resources=failed_resources,
           _retain=lambda:events.append("retained"))
    with pytest.raises(RuntimeError):
        native.CoveringORMConnection.retire(obj)
    assert native.CoveringORMConnection.retire(obj) is False
    assert events==["close","resources","retained"]


def test_parent_binding_stamps_exact_adapter_and_arms_once():
    root=object(); events=[]
    adapter=NS(arm_flush_rollback=lambda:events.append("armed"))
    obj=NS(role=CoveringRole.PARENT,adapter=None,root=root,
           orm=NS(get_transaction=lambda:root,info={}))
    native.CoveringORMConnection.bind_parent(obj,adapter)
    assert obj.orm.info["covering_native_flush_bound"] is adapter
    with pytest.raises(CoveringRootOutcomeUnknown):
        native.CoveringORMConnection.bind_parent(obj,adapter)
    assert events==["armed"]


def close_fixture(role, terminal=None):
    root=object() if terminal is None else terminal.operation.root
    events=[]
    driver=NS(root=root,terminal=terminal,lease=NS(remaining=None),
        retire=lambda:events.append("retire") or True,
        cut_off_frontend=lambda:True)
    driver._new_operation=lambda command:RootOperation(root,1,command)
    def finish(operation,remaining):
        events.append(operation.command)
        driver.terminal=NativeTerminalResult(operation,True,operation.command.value,True,True)
        return driver.terminal
    driver.finish=finish
    factories=native.NativeORMFactories(profile=None,password_supplier=None,runtime_pins=None)
    factories._open=lambda role,remaining:(driver,object())
    binding=factories.session_factory(role,None,lambda:100)
    return driver,binding,events


def test_telemetry_close_commits_exactly_once_then_retires():
    driver,binding,events=close_fixture(CoveringRole.TELEMETRY)
    result=binding.close_known(lambda:30)
    assert result.identity is driver and result.retired and result.outcome_known
    assert events==[RootCommand.COMMIT,"retire"]


def test_token_close_does_not_repeat_acknowledged_terminal():
    operation=RootOperation(object(),1,RootCommand.COMMIT)
    terminal=NativeTerminalResult(operation,True,b"COMMIT",True,True)
    driver,binding,events=close_fixture(CoveringRole.TOKEN,terminal)
    binding.close_known(lambda:30)
    assert events==["retire"]


def test_wrong_terminal_tag_cannot_complete_role():
    operation=RootOperation(object(),1,RootCommand.COMMIT)
    terminal=NativeTerminalResult(operation,True,b"ROLLBACK",True,True)
    _,binding,events=close_fixture(CoveringRole.TOKEN,terminal)
    with pytest.raises(CoveringRootOutcomeUnknown):
        binding.close_known(lambda:30)
    assert events==[]


def test_runtime_mismatch_precedes_password_and_checkout():
    events=[]
    def mismatch():
        raise CoveringRootOutcomeUnknown()
    factories=native.NativeORMFactories(profile=None,
        password_supplier=lambda:events.append("password"),
        runtime_pins=NS(verify=mismatch))
    with pytest.raises(CoveringRootOutcomeUnknown):
        factories._open(CoveringRole.AUTH,lambda:100)
    assert events==[]


def test_release_plan_creates_distinct_request_resources(monkeypatch):
    from app.services import covering_release_plan as module
    from app.services.covering_domain_dispatch import CoveringDomainPorts
    seen=[]
    class Factories:
        def __init__(self,**kwargs):
            pass
        def parent_factory(self,*args):
            pytest.fail("checkout during plan construction")
        def session_factory(self,*args):
            pytest.fail("checkout during plan construction")
    def ports(**kwargs):
        seen.append(kwargs["transport"])
        return CoveringDomainPorts(None,None,None)
    monkeypatch.setattr(module,"NativeORMFactories",Factories)
    monkeypatch.setattr(module,"make_domain_ports",ports)
    plan=module.CoveringReleasePlan(None,None,None,(),None)
    first=plan.for_request(NS(work_remaining=lambda:210))
    second=plan.for_request(NS(work_remaining=lambda:210))
    assert first.parent_factory.__self__ is not second.parent_factory.__self__
    assert seen[0].counter is not seen[1].counter


"""Prepared native cases. No entry point; execution requires a reviewed supervisor.

Requires a separately provisioned disposable TLS PostgreSQL fixture and exact
reviewed runtime pins. No schema creation, environment discovery or fallback.
"""
from contextlib import contextmanager
from uuid import UUID

from sqlalchemy import text

from app.services.covering_native_orm_factory import NativeORMFactories
from app.services.covering_parent_adapter import CoveringParentAdapter, RootCommand
from app.services.covering_request_budget import CoveringRequestBudget
from app.services.covering_role_admission import CoveringRole
from app.services.covering_target_transaction import RootOutcome


@contextmanager
def refuse_recorder(_remaining):
    raise AssertionError("positive parent case must not admit a recorder")
    yield  # Preserve contextmanager protocol; never reached.


def parent_terminal_case(*, profile, password_supplier, runtime_pins, marker, commit):
    """N02/N03: real factory + adapter; observer must separately check persistence.

    Fixture setup owns native_fixture_probe(marker UUID PRIMARY KEY). Each case
    receives a unique marker and a fresh budget. No retries or cleanup-on-error.
    Adapter target_scope owns the production abort path; supervisor stops after
    any raised error. No ordinary Session.commit/rollback is substituted.
    """
    if type(marker) is not UUID or type(commit) is not bool:
        raise ValueError("explicit UUID marker and boolean outcome required")
    budget = CoveringRequestBudget()
    factories = NativeORMFactories(profile=profile,
        password_supplier=password_supplier, runtime_pins=runtime_pins)
    binding = factories.parent_factory((marker, marker, marker), budget.work_remaining)
    adapter = CoveringParentAdapter(root=binding.root, driver=binding.driver,
        budget=budget, failure_session=refuse_recorder)
    with adapter.target_scope():
        binding.driver.bind_parent(adapter)
        assert binding.session.get_transaction() is binding.root
        assert binding.session.info["covering_native_flush_bound"] is adapter
        binding.session.execute(text(
            "INSERT INTO native_fixture_probe(marker) VALUES (:marker)"), {"marker": marker})
        outcome = adapter.finish_root(commit=commit)
        expected = RootOutcome.COMMIT_ACKNOWLEDGED if commit else RootOutcome.ROLLBACK_ACKNOWLEDGED
        assert outcome is expected
        terminal = binding.driver.terminal
        command = RootCommand.COMMIT if commit else RootCommand.ROLLBACK
        assert terminal.operation.root is binding.root
        assert terminal.operation.command is command
        assert terminal.command_sent is True
        assert terminal.command_tag == command.value
        assert terminal.drained is True and terminal.idle is True
        assert adapter.retire_parent() is True
        assert binding.driver.closed and binding.driver.lease.closed
        assert not factories.quarantined
    return {"case": "N02" if commit else "N03", "marker": str(marker),
            "terminal_tag": command.value.decode("ascii"),
            "retired": True, "persistence_observed": False}


def observe_marker(*, profile, password_supplier, runtime_pins, marker, expected_present):
    """Separate fixture observer after a KNOWN parent result, never after UNKNOWN.

    Use a new real factory ASSESSMENT session; close through its native terminal
    callback and cumulative cleanup budget. Caller must gate on known outcome.
    """
    if type(marker) is not UUID or type(expected_present) is not bool:
        raise ValueError("explicit marker and expected presence required")
    budget = CoveringRequestBudget()
    factories = NativeORMFactories(profile=profile,
        password_supplier=password_supplier, runtime_pins=runtime_pins)
    binding = factories.session_factory(CoveringRole.ASSESSMENT, None, budget.work_remaining)
    try:
        count = binding.session.execute(text(
            "SELECT count(*) FROM native_fixture_probe WHERE marker = :marker"),
            {"marker": marker}).scalar_one()
        with budget.cleanup():
            completion = binding.close_known(budget.cleanup_remaining)
        assert completion.outcome_known and completion.locks_exited and completion.retired
        assert count == int(expected_present)
    except BaseException:
        # Never try another checkout or terminal operation here. The production
        # quarantine callback owns one cutoff/retirement attempt.
        if not binding.identity.closed:
            binding.quarantine()
        raise
    return {"marker": str(marker), "present": bool(count), "observer_retired": True}

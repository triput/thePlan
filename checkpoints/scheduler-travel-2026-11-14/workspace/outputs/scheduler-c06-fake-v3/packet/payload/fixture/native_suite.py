"""Native case adapters. Prepared for an explicitly approved isolated run only."""
from contextlib import contextmanager
from dataclasses import replace
from threading import Thread
from uuid import uuid4

from sqlalchemy import Column, Integer, MetaData, Table, UniqueConstraint, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import registry

from app.services.covering_native_orm_factory import NativeORMFactories
from app.services.covering_parent_adapter import CoveringParentAdapter, RootOperation, RootCommand
from app.services.covering_request_budget import CoveringRequestBudget, CoveringBudgetStopped
from app.services.covering_target_transaction import CoveringRootOutcomeUnknown, RootOutcome
from native_parent_cases import parent_terminal_case, observe_marker, refuse_recorder


metadata = MetaData(schema='dex_fixture_native')
collision = Table('collision', metadata, Column('id', Integer, primary_key=True),
    Column('value', Integer, nullable=False), UniqueConstraint('value', name='unique_external_event'))
mapper = registry()


class Collision:
    pass


mapper.map_imperatively(Collision, collision)


def provision_native(setup_factory):
    session = setup_factory.open_setup_session()
    try:
        session.execute(text('CREATE SCHEMA dex_fixture_native'))
        metadata.create_all(session.connection(), checkfirst=False)
        session.execute(text('CREATE TABLE native_fixture_probe(marker UUID PRIMARY KEY)'))
        session.execute(collision.insert().values(id=1, value=7))
        session.commit()
    finally:
        setup_factory.close(session)


class NativeCases:
    def __init__(self, profile, pins):
        self.profile, self.pins = profile, pins

    def args(self, profile=None):
        return dict(profile=profile or self.profile, password_supplier=lambda: '', runtime_pins=self.pins)

    @contextmanager
    def parent(self, *, profile=None, budget=None):
        budget = budget or CoveringRequestBudget()
        factory = NativeORMFactories(**self.args(profile))
        marker = uuid4()
        binding = factory.parent_factory((marker, marker, marker), budget.work_remaining)
        adapter = CoveringParentAdapter(root=binding.root, driver=binding.driver,
            budget=budget, failure_session=refuse_recorder)
        with adapter.target_scope():
            binding.driver.bind_parent(adapter)
            yield binding, adapter, budget

    def result(self, case, **evidence):
        return dict(case_id=case, passed=True, skipped=False, workers_joined=True, **evidence)

    def tls(self):
        # Real native checkout on the valid peer, followed by known rollback.
        with self.parent() as (binding, adapter, budget):
            assert adapter.finish_root(commit=False) is RootOutcome.ROLLBACK_ACKNOWLEDGED
            assert adapter.retire_parent()
        refused = []
        for label, peer in (
            ('hostname', replace(self.profile, hostname='wrong-fixture.invalid')),
            ('ca', replace(self.profile, ca_file='/public-ca/untrusted-ca.crt'))):
            factory = NativeORMFactories(**self.args(peer))
            try:
                unexpected = factory.parent_factory((None, None, None), CoveringRequestBudget().work_remaining)
            except CoveringRootOutcomeUnknown:
                refused.append(label)
            else:
                # Unexpected successful connection is a failure, never continue.
                unexpected.driver.cut_off_frontend()
                unexpected.driver.retire()
                raise AssertionError('invalid TLS peer admitted')
        return self.result('N01', tls_refusals=refused)

    def terminal(self, commit):
        marker = uuid4()
        terminal = parent_terminal_case(**self.args(), marker=marker, commit=commit)
        observed = observe_marker(**self.args(), marker=marker, expected_present=commit)
        return self.result('N02' if commit else 'N03', terminal=terminal, persistence=observed)

    def identity(self):
        with self.parent() as (binding, adapter, budget):
            operation = RootOperation(object(), 1, RootCommand.COMMIT)
            try:
                binding.driver.finish(operation, remaining=budget.work_remaining)
            except CoveringRootOutcomeUnknown:
                pass
            else:
                raise AssertionError('wrong root admitted')
            errors = []
            def other_owner():
                try:
                    binding.driver.finish(RootOperation(binding.root, 2, RootCommand.COMMIT),
                                          remaining=budget.work_remaining)
                except BaseException as exc:
                    errors.append(type(exc))
            thread = Thread(target=other_owner)
            thread.start()
            thread.join(timeout=2)
            assert not thread.is_alive()
            assert errors == [CoveringRootOutcomeUnknown]
            assert binding.driver.terminal is None and binding.driver.operation is None
            assert adapter.finish_root(commit=False) is RootOutcome.ROLLBACK_ACKNOWLEDGED
            assert adapter.retire_parent()
        return self.result('N04', root_and_owner_refused=True)

    def unique_collision(self):
        with self.parent() as (binding, adapter, budget):
            row = Collision()
            row.id, row.value = 2, 7
            binding.session.add(row)
            try:
                binding.session.flush()
            except IntegrityError as exc:
                assert exc.orig.sqlstate == '23505'
                assert exc.orig.diag.constraint_name == 'unique_external_event'
            else:
                raise AssertionError('collision did not occur')
            assert adapter.acknowledged_outcome is RootOutcome.ROLLBACK_ACKNOWLEDGED
            assert adapter.finish_root(commit=False) is RootOutcome.ROLLBACK_ACKNOWLEDGED
            assert binding.driver.terminal.command_tag == b'ROLLBACK'
            assert adapter.retire_parent()
        return self.result('N05', native_flush_rollback_acknowledged=True)

    def lost_ack(self, commit):
        peer = replace(self.profile, port=15432 if commit else 15433)
        observed = False
        driver = None
        try:
            with self.parent(profile=peer) as (binding, adapter, budget):
                driver = binding.driver
                binding.session.execute(text('INSERT INTO native_fixture_probe(marker) VALUES (:marker)'),
                                        {'marker': uuid4()})
                # Arm on this same guarded connection only after setup and INSERT.
                with driver.cursor() as cursor:
                    cursor.execute('SELECT 1 /* dex-arm-lost-ack */',
                                   prepare=False, binary=False)
                    assert cursor.fetchone() == (1,)
                    assert cursor.fetchone() is None
                assert adapter.finish_root(commit=commit) is RootOutcome.UNKNOWN
                try:
                    budget.work_remaining()
                except CoveringBudgetStopped:
                    observed = True
                else:
                    raise AssertionError('work admission remained open')
                # target_scope raises UNKNOWN and owns local abort/retirement.
        except CoveringRootOutcomeUnknown:
            assert observed and driver is not None
            assert driver._cutoff and driver.closed and driver._retired
        else:
            raise AssertionError('native UNKNOWN not propagated')
        return self.result('N06' if commit else 'N07', expected_unknown=True,
                           stopped_admission=True, local_retirement=True)

    def cutoff(self):
        clock = [0.0]
        budget = CoveringRequestBudget(clock=lambda: clock[0])
        with self.parent(budget=budget) as (binding, adapter, _):
            clock[0] = 211.0
            assert adapter.finish_root(commit=True) is RootOutcome.COMMIT_DEADLINE_ROLLBACK_ACKNOWLEDGED
            assert binding.driver.terminal.command_tag == b'ROLLBACK'
            clock[0] = 212.0
            assert adapter.retire_parent()
        assert budget._cleanup_left == 29.0
        return self.result('N08', commit_refused_before_dispatch=True, cleanup_charged_seconds=1)

    def registry(self):
        return {'N01': self.tls, 'N02': lambda: self.terminal(True),
                'N03': lambda: self.terminal(False), 'N04': self.identity,
                'N05': self.unique_collision, 'N06': lambda: self.lost_ack(True),
                'N07': lambda: self.lost_ack(False), 'N08': self.cutoff}

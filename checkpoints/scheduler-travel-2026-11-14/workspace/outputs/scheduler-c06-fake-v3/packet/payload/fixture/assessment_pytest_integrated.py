"""Real assessment pytest composition; prepared only, no default execution."""
import os
import pytest


class Evidence:
    def __init__(self, expected):
        self.expected = expected
        self.collected = []
        self.passed = []
        self.failed = False
        self._primary_exc = None

    def pytest_collection_modifyitems(self, session, config, items):
        try:
            self.collected = [self.key(item) for item in items]
            self.by_nodeid = {item.nodeid: self.key(item) for item in items}
            if self.collected != self.expected:
                raise RuntimeError('assessment collection differs from reviewed inventory')
        except BaseException as exc:
            if self._primary_exc is None:
                self._primary_exc = exc
            raise

    @pytest.hookimpl(tryfirst=True)
    def pytest_runtest_makereport(self, item, call):
        if (self._primary_exc is None and call.excinfo is not None
                and call.when in ('setup', 'call', 'teardown')):
            self._primary_exc = call.excinfo.value
        # Observe only; pytest must generate the report.

    @staticmethod
    def key(item):
        name = item.originalname or item.name
        if hasattr(item, 'callspec'):
            name += '[' + item.callspec.params['gate'] + ']'
        return name

    def pytest_runtest_logreport(self, report):
        if report.failed or report.skipped or getattr(report, 'wasxfail', False):
            self.failed = True
        if report.when == 'call' and report.passed:
            self.passed.append(self.by_nodeid[report.nodeid])


def run_assessment(*, factory, expected_nodeids, basetemp):
    # Import only inside the later approved isolated runner, never during prep.
    if os.environ.get('PYTEST_DISABLE_PLUGIN_AUTOLOAD') != '1':
        raise RuntimeError('external pytest plugin autoload must be disabled')
    from tests.support.assessment_sql_fixture import bind_assessment_session_factory
    evidence = Evidence(expected_nodeids)
    bind_assessment_session_factory(factory)
    try:
        code = pytest.main(['apps/api/tests/test_assessment_cases_a01_a10.py',
            '-x', '-q', '--noconftest', '-c', 'apps/api/tests/support/_empty_pytest.ini', '-p', 'no:cacheprovider',
            '--basetemp=' + basetemp], plugins=[evidence])
        if code != 0 or evidence.failed or evidence.passed != expected_nodeids:
            error = RuntimeError('assessment suite failed, skipped or incomplete')
            if evidence._primary_exc is not None:
                raise error from evidence._primary_exc
            raise error
        factory.require_drained()
        return {'passed_nodeids': evidence.passed, 'skipped': 0}
    finally:
        # Clear only the in-process binding; no DB purge or reconnect.
        bind_assessment_session_factory(None)

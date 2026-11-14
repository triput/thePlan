"""Real assessment pytest composition; prepared only, no default execution."""
import os
import pytest


class Evidence:
    def __init__(self, expected):
        self.expected = expected
        self.collected = []
        self.passed = []
        self.failed = False

    def pytest_collection_modifyitems(self, session, config, items):
        self.collected = [item.nodeid for item in items]
        if self.collected != self.expected:
            raise RuntimeError('assessment collection differs from reviewed inventory')

    def pytest_runtest_logreport(self, report):
        if report.failed or report.skipped:
            self.failed = True
        if report.when == 'call' and report.passed:
            self.passed.append(report.nodeid)


def run_assessment(*, factory, expected_nodeids, basetemp):
    # Import only inside the later approved isolated runner, never during prep.
    if os.environ.get('PYTEST_DISABLE_PLUGIN_AUTOLOAD') != '1':
        raise RuntimeError('external pytest plugin autoload must be disabled')
    from tests.support.assessment_sql_fixture import bind_assessment_session_factory
    evidence = Evidence(expected_nodeids)
    bind_assessment_session_factory(factory)
    try:
        code = pytest.main(['apps/api/tests/test_assessment_cases_a01_a10.py',
            '-x', '-q', '--noconftest', '-p', 'no:cacheprovider',
            '--basetemp=' + basetemp], plugins=[evidence])
        if code != 0 or evidence.failed or evidence.passed != expected_nodeids:
            raise RuntimeError('assessment suite failed, skipped or incomplete')
        factory.require_drained()
        return {'passed_nodeids': evidence.passed, 'skipped': 0}
    finally:
        # Clear only the in-process binding; no DB purge or reconnect.
        bind_assessment_session_factory(None)

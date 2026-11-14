"""Integrated runner entry; refuses held/missing exact runtime configuration."""
import contextlib
import hashlib
import json
import logging
import os
from pathlib import Path
import resource
import sys
import types
from threading import Timer

ROOT = Path(__file__).resolve().parents[1]


class BoundedOutput:
    def __init__(self):
        self.length = 0
        self.sha = hashlib.sha256()
    def write(self, value):
        data = value.encode('utf-8', errors='replace')
        self.length += len(data)
        if self.length > 1048576:
            raise RuntimeError('runner console cap')
        self.sha.update(data)
        return len(value)
    def flush(self):
        pass
    def isatty(self):
        return False


def stop_payload(error):
    """Bounded locations only. Never format exception messages, locals or SQL."""
    original = {'status': 'STOP', 'kind': type(error).__name__}
    try:
        import re
        def kind(exc):
            name = type(exc).__name__
            return name if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,79}', name) else 'Exception'
        root = ROOT.resolve()
        owned = {}
        for row in (root/'SHA256SUMS.txt').read_text().splitlines():
            pin, rel = row.split('  ', 1)
            if re.fullmatch(r'[A-F0-9]{64}', pin) and re.fullmatch(r'[A-Za-z0-9_./-]{1,240}', rel) and rel.endswith('.py'):
                path = (root/rel).resolve()
                if path.is_relative_to(root) and path.relative_to(root).as_posix() == rel:
                    owned[rel] = pin
        exceptions, seen = [], set()
        current, truncated = error, False
        while current is not None and len(exceptions) < 3 and id(current) not in seen:
            seen.add(id(current))
            frames = []
            tb = current.__traceback__
            walked = 0
            while tb is not None and walked < 128:
                walked += 1
                path = Path(tb.tb_frame.f_code.co_filename).resolve()
                if path.is_relative_to(root):
                    rel = path.relative_to(root).as_posix()
                    if rel in owned:
                        data = path.read_bytes()
                        if hashlib.sha256(data).hexdigest().upper() == owned[rel] and 1 <= tb.tb_lineno <= len(data.splitlines()):
                            frames.append({'path': rel, 'line': tb.tb_lineno})
                            if len(frames) > 8:
                                del frames[0]
                                truncated = True
                        else:
                            truncated = True
                    else:
                        truncated = True
                else:
                    truncated = True
                tb = tb.tb_next
            truncated = truncated or tb is not None
            exceptions.append({'kind': kind(current), 'frames': frames})
            current = current.__cause__ if current.__cause__ is not None else current.__context__
        truncated = truncated or current is not None
        result = {'status': 'STOP', 'kind': kind(error), 'diagnostic': {
            'version': 1, 'exceptions': exceptions, 'truncated': truncated}}
        while len((json.dumps(result)+'\n').encode('utf-8')) > 4096:
            populated = next((entry for entry in exceptions if entry['frames']), None)
            if populated is None:
                raise ValueError('diagnostic cap')
            del populated['frames'][0]
            result['diagnostic']['truncated'] = True
        return result
    except BaseException:
        return original  # Diagnostic failure must not replace the primary kind.

def main():
    if not (sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode):
        raise RuntimeError('require -I -S -B')
    config = json.loads((ROOT/'runner-config.json').read_text())
    if config.get('launch_ready') is not True:
        raise RuntimeError('HELD: runtime pins and launch review incomplete')
    # Includes imports/schema preparation, before run_suite's per-suite guard.
    watchdog = Timer(config['runner_seconds'], lambda: os._exit(124))
    watchdog.daemon = True
    watchdog.start()
    if os.getuid() == 0 or set(os.listdir('/sys/class/net')) != {'lo'}:
        raise RuntimeError('isolation refused')
    if any(k.upper().startswith('PG') for k in os.environ):
        raise RuntimeError('ambient PG configuration refused')
    api = ROOT/'workspace/apps/api'
    if (api/'.env').exists() or Path('/tmp/.env').exists():
        raise RuntimeError('ambient application env file')
    if config['python'] != list(sys.version_info[:3]):
        raise RuntimeError('Python runtime mismatch')
    # Exact reviewed site directories only; no site initialization/.pth execution.
    sys.path.extend(config['site_directories'])
    sys.path[:0] = [str(ROOT/'fixture'), str(api)]
    tests = types.ModuleType('tests')
    tests.__path__ = [str(api/'tests')]
    sys.modules['tests'] = tests
    os.environ.clear()
    os.environ.update(DATABASE_URL='postgresql+psycopg://fixture_disabled@127.0.0.1:1/fixture_disabled',
        SESSION_SECRET='i01-i02-fixture-session-secret-v1-not-production', SEED_DEMO_USER='false',
        SCHEDULE_DISPATCH='external', PYTEST_DISABLE_PLUGIN_AUTOLOAD='1', TMPDIR='/tmp',
        TOKEN_ENCRYPTION_KEY='AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=')
    logging.disable(logging.CRITICAL)
    resource.setrlimit(resource.RLIMIT_FSIZE, (1048576, 1048576))
    os.chdir(ROOT/'workspace')
    import psycopg
    import sqlalchemy
    from psycopg import pq
    actual = {'python': list(sys.version_info[:3]), 'psycopg': psycopg.__version__,
        'sqlalchemy': sqlalchemy.__version__, 'pq_implementation': pq.__impl__,
        'pq_runtime': pq.version(), 'pq_build': pq.__build_version__}
    if actual != config['runtime_pins']:
        raise RuntimeError('native runtime mismatch')
    from app import db
    def refused(*args, **kwargs):
        raise RuntimeError('ambient application/provider access refused')
    sqlalchemy.event.listen(db.engine, 'do_connect', refused)
    db.SessionLocal = refused
    import httpx
    httpx.HTTPTransport.handle_request = refused
    httpx.AsyncHTTPTransport.handle_async_request = refused
    from app.services.covering_joined_https import JoinedTLS
    JoinedTLS.__init__ = refused
    def audit(event, args):
        if event in ('subprocess.Popen', 'os.system', 'os.exec', 'os.posix_spawn'):
            refused()
    sys.addaudithook(audit)
    from app.services.covering_native_checkout import PostgreSQLPeer
    from app.services.covering_native_orm_factory import NativeRuntimePins
    from assessment_binding import AssessmentFactory
    from assessment_pytest_integrated import run_assessment
    from native_suite import NativeCases, provision_native
    from integrated_runner import run_suite
    from i01_i02_suite import build_i01_i02_registry
    import app.models  # Register real schema only after runtime/guard setup.
    pins = NativeRuntimePins(**{**actual, 'python': tuple(actual['python'])})
    profile = PostgreSQLPeer(hostname='native-fixture.invalid', address='127.0.0.1',
        port=5432, database='dex_fixture', username='dex_fixture',
        ca_file='/public-ca/ca.crt', absent_passfile='/tmp/absent-passfile',
        client_cert='/tmp/absent-client.crt', client_key='/tmp/absent-client.key')
    evidence = []
    def record(kind, data):
        evidence.append({'kind': kind, 'data': data})
        if len(evidence) > 4096:
            raise RuntimeError('evidence count cap')
    factory = AssessmentFactory(profile=profile, password_supplier=lambda: '', runtime_pins=pins, record=record)
    # Setup transaction is explicit and outside application/native outcome proof.
    setup = factory.open_setup_session()
    try:
        db.Base.metadata.create_all(setup.connection(), checkfirst=False)
        setup.commit()
    finally:
        factory.close(setup)
    provision_native(factory)
    registry = NativeCases(profile, pins).registry()
    def assessment():
        result = run_assessment(factory=factory,
            expected_nodeids=config['assessment_case_ids'], basetemp='/tmp/assessment-pytest')
        return {'case_id': 'ASSESSMENT_SQL', 'passed': True, 'workers_joined': True,
                'skipped': False, 'assessment': result}
    registry['ASSESSMENT_SQL'] = assessment
    # Bounded I01/I02 registration: only case_ids present in frozen runner-config.
    i01_i02 = build_i01_i02_registry(
        factory=factory, profile=profile, pins=pins, password_supplier=lambda: '')
    for case_id in config['case_ids']:
        if case_id in i01_i02:
            registry[case_id] = i01_i02[case_id]
    # Parent transport independently validates this generated public CA hash.
    config['ca_sha256'] = hashlib.sha256(Path('/public-ca/ca.crt').read_bytes()).hexdigest().upper()
    capture = BoundedOutput()
    with contextlib.redirect_stdout(capture), contextlib.redirect_stderr(capture):
        report = run_suite(config=config, registry=registry, runtime_pins=actual,
                           record_case=record, outer_watchdog=watchdog)
    factory.require_drained()
    report['evidence'] = evidence
    report['console'] = {'bytes': capture.length, 'sha256': capture.sha.hexdigest()}
    payload = json.dumps(report, sort_keys=True)
    if len(payload.encode()) > 1048576:
        raise RuntimeError('final evidence cap')
    watchdog.cancel()
    watchdog.join(1)
    if watchdog.is_alive():
        raise RuntimeError('outer watchdog not joined')
    print(payload)


if __name__ == '__main__':
    try:
        main()
    except BaseException as error:
        # No SQL/raw exception body, retry or fixture cleanup on failure.
        print(json.dumps(stop_payload(error)), file=sys.stderr)
        raise SystemExit(1)

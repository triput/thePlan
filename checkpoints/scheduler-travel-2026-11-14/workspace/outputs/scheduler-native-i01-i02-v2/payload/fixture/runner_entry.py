"""Integrated runner entry; refuses held/missing exact runtime configuration."""
import contextlib
import hashlib
import json
import logging
import os
from pathlib import Path
import resource
import signal
import stat
import subprocess
import sys
from threading import Thread, Timer
from time import monotonic
import types

ROOT = Path(__file__).resolve().parents[1]
C06_GATE_TLS_DIR = '/tmp/c06-gate-tls'
C06_GATE_CLIENT_CA = '/tmp/c06-gate-tls/ca.crt'
C06_BACKEND_DB_CA = '/public-ca/ca.crt'
C06_PREPARE_SCRIPT = 'fixture/prepare-c06-runner-tls.sh'
C06_SH_ABS = '/bin/sh'
C06_OPENSSL_ABS = '/usr/bin/openssl'
C06_GEN_SECONDS = 30
C06_REAP_SECONDS = 5
C06_READER_JOIN_SECONDS = 5
C06_DISCLOSED_RETIREMENT_SECONDS = 45
C06_WAIT_POLL_SECONDS = 0.05
C06_CAPTURE_CAP = 65536
C06_RUNNER_BUDGET_SECONDS = 600
C06_SUITE_BUDGET_SECONDS = 900
C06_ARTIFACT_CEILING = 1048576
C06_REQUIRED_UID = 65534
C06_CHILD_ENV = {
    'PATH': '/usr/bin:/bin',
    'TMPDIR': '/tmp',
    'HOME': '/tmp',
    'LANG': 'C',
    'LC_ALL': 'C',
}


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


class C06RunnerTlsError(RuntimeError):
    """Bounded C06 generation/admission/retirement failure. No raw output or keys."""


def exclusive_create_c06_gate_tls_dir():
    """Create /tmp/c06-gate-tls once as UID 65534 mode 0700. Refuse pre-existing. No delete."""
    if os.getuid() != C06_REQUIRED_UID:
        raise C06RunnerTlsError('c06 uid')
    if os.path.lexists(C06_GATE_TLS_DIR):
        raise C06RunnerTlsError('c06 gate tls pre-exists')
    previous = os.umask(0o077)
    try:
        os.mkdir(C06_GATE_TLS_DIR, 0o700)
        os.chmod(C06_GATE_TLS_DIR, 0o700)
    finally:
        os.umask(previous)
    owned = os.stat(C06_GATE_TLS_DIR)
    if owned.st_uid != C06_REQUIRED_UID or stat.S_IMODE(owned.st_mode) != 0o700:
        raise C06RunnerTlsError('c06 gate tls ownership')
    if os.listdir(C06_GATE_TLS_DIR):
        raise C06RunnerTlsError('c06 gate tls nonempty')
    return C06_GATE_TLS_DIR


class C06CaptureSink:
    """Retained buffer is capped; observed total can exceed retained length.

    Repeated cap is a counter plus overflow flag, not an unbounded event list.
    """

    def __init__(self):
        self.retained = bytearray()
        self.observed = 0
        self.overflow = False
        self.cap_observations = 0
        self.reader_error = False
        self.saw_eof = False


def _c06_capture_reader(stream, sink, events):
    del events  # bounded sink flags only; callers must not grow an event list
    try:
        while True:
            chunk = stream.read(4096)
            if not chunk:
                sink.saw_eof = True
                return
            sink.observed += len(chunk)
            if sink.overflow:
                if sink.cap_observations < 1:
                    sink.cap_observations = 1
                continue
            if len(sink.retained) + len(chunk) > C06_CAPTURE_CAP:
                room = C06_CAPTURE_CAP - len(sink.retained)
                if room > 0:
                    sink.retained.extend(chunk[:room])
                sink.overflow = True
                sink.cap_observations = 1
                continue
            sink.retained.extend(chunk)
    except BaseException:
        sink.reader_error = True


def _c06_owned_pgid(proc):
    """Session id from start_new_session: leader pid names the owned group."""
    return proc.pid


def _c06_group_probe(pgid):
    """Group presence independent of leader poll. Signal 0; no host enumeration."""
    if pgid is None:
        return 'unknown'
    try:
        os.killpg(pgid, 0)
        return 'present'
    except ProcessLookupError:
        return 'absent'
    except PermissionError:
        return 'permission'
    except OSError:
        return 'unknown'


def _c06_retire_process_group(proc, owned_pgid):
    """Retire owned group independently of leader exit. Shell-only kill is insufficient."""
    deadline = monotonic() + C06_REAP_SECONDS
    leader_exited = proc.poll() is not None
    state = _c06_group_probe(owned_pgid)
    if state == 'absent':
        return {
            'group_retired': True,
            'group_state': state,
            'leader_exited': leader_exited,
        }
    if state in ('permission', 'unknown'):
        return {
            'group_retired': False,
            'group_state': state,
            'leader_exited': leader_exited,
        }
    try:
        os.killpg(owned_pgid, signal.SIGTERM)
    except ProcessLookupError:
        return {
            'group_retired': True,
            'group_state': 'absent',
            'leader_exited': proc.poll() is not None,
        }
    except PermissionError:
        return {
            'group_retired': False,
            'group_state': 'permission',
            'leader_exited': proc.poll() is not None,
        }
    except OSError:
        return {
            'group_retired': False,
            'group_state': 'unknown',
            'leader_exited': proc.poll() is not None,
        }
    while monotonic() < deadline:
        state = _c06_group_probe(owned_pgid)
        if state == 'absent':
            return {
                'group_retired': True,
                'group_state': state,
                'leader_exited': proc.poll() is not None,
            }
        if state in ('permission', 'unknown'):
            return {
                'group_retired': False,
                'group_state': state,
                'leader_exited': proc.poll() is not None,
            }
        left = deadline - monotonic()
        if left <= (C06_REAP_SECONDS / 2.0):
            try:
                os.killpg(owned_pgid, signal.SIGKILL)
            except ProcessLookupError:
                return {
                    'group_retired': True,
                    'group_state': 'absent',
                    'leader_exited': proc.poll() is not None,
                }
            except OSError:
                pass
        try:
            proc.wait(timeout=min(C06_WAIT_POLL_SECONDS, max(0.0, left)))
        except subprocess.TimeoutExpired:
            continue
        except BaseException:
            continue
    try:
        os.killpg(owned_pgid, signal.SIGKILL)
    except ProcessLookupError:
        state = 'absent'
    except OSError:
        state = _c06_group_probe(owned_pgid)
    else:
        try:
            proc.wait(timeout=max(0.0, deadline - monotonic()))
        except subprocess.TimeoutExpired:
            pass
        except BaseException:
            pass
        state = _c06_group_probe(owned_pgid)
    return {
        'group_retired': state == 'absent',
        'group_state': state,
        'leader_exited': proc.poll() is not None,
    }


def _c06_join_started_readers(started, evidence):
    joined = True
    for reader in started:
        try:
            reader.join(C06_READER_JOIN_SECONDS)
        except BaseException as error:
            evidence.append({
                'phase': 'reader_join',
                'kind': type(error).__name__,
            })
            joined = False
            continue
        if reader.is_alive():
            joined = False
    return joined


def _c06_close_owned_pipes(endpoints, evidence):
    """Close only pipes whose reader is not still live. Never close under an unjoined reader."""
    unretired = 0
    for endpoint in endpoints:
        pipe = endpoint['pipe']
        reader = endpoint.get('reader')
        started = endpoint.get('started') is True
        if started and reader is not None and reader.is_alive():
            unretired += 1
            evidence.append({
                'phase': 'pipe_unretired',
                'kind': 'reader_alive',
            })
            continue
        try:
            pipe.close()
            endpoint['closed'] = True
        except BaseException as error:
            evidence.append({
                'phase': 'pipe_close',
                'kind': type(error).__name__,
            })
    return unretired


def _c06_attach_secondary(primary, extra):
    """Preserve generation/admission primary; attach retirement evidence. Do not replace kind."""
    if primary is None:
        return None
    payload = dict(extra)
    existing = getattr(primary, 'fixture_c06_tls', None)
    if isinstance(existing, dict):
        existing.update(payload)
    else:
        primary.fixture_c06_tls = payload
    return primary


def _c06_public_provenance():
    """Hash public CA/leaf only. Never hash or copy key/CSR/serial bytes."""
    gate = Path(C06_GATE_CLIENT_CA).read_bytes()
    leaf = Path(C06_GATE_TLS_DIR, 'server.crt').read_bytes()
    db = Path(C06_BACKEND_DB_CA).read_bytes()
    if not (1 <= len(gate) <= C06_ARTIFACT_CEILING and 1 <= len(leaf) <= C06_ARTIFACT_CEILING
            and 1 <= len(db) <= C06_ARTIFACT_CEILING):
        raise C06RunnerTlsError('c06 public artifact ceiling')
    for name in ('ca.key', 'server.key'):
        path = os.path.join(C06_GATE_TLS_DIR, name)
        owned = os.stat(path)
        if owned.st_uid != C06_REQUIRED_UID or stat.S_IMODE(owned.st_mode) != 0o600:
            raise C06RunnerTlsError('c06 key mode')
    gate_sha = hashlib.sha256(gate).hexdigest().upper()
    db_sha = hashlib.sha256(db).hexdigest().upper()
    if gate_sha == db_sha:
        raise C06RunnerTlsError('c06 public CA hashes not distinct')
    return {
        'gate_ca_path': C06_GATE_CLIENT_CA,
        'gate_ca_bytes': len(gate),
        'gate_ca_sha256': gate_sha,
        'server_crt_bytes': len(leaf),
        'server_crt_sha256': hashlib.sha256(leaf).hexdigest().upper(),
        'db_public_ca_path': C06_BACKEND_DB_CA,
        'db_public_ca_bytes': len(db),
        'db_public_ca_sha256': db_sha,
        'distinct_public_ca': True,
    }


def _c06_sanitized_status(kind, stdout_sink, stderr_sink, extra):
    payload = {
        'status': 'STOP' if kind != 'C06RunnerTlsPrepared' else 'prepared',
        'kind': kind,
        'stdout_retained_bytes': len(stdout_sink.retained),
        'stdout_observed_bytes': stdout_sink.observed,
        'stdout_sha256': hashlib.sha256(bytes(stdout_sink.retained)).hexdigest().upper(),
        'stderr_retained_bytes': len(stderr_sink.retained),
        'stderr_observed_bytes': stderr_sink.observed,
        'stderr_sha256': hashlib.sha256(bytes(stderr_sink.retained)).hexdigest().upper(),
        'generation_seconds': C06_GEN_SECONDS,
        'reap_seconds': C06_REAP_SECONDS,
        'reader_join_seconds': C06_READER_JOIN_SECONDS,
        'disclosed_collection_retirement_seconds': C06_DISCLOSED_RETIREMENT_SECONDS,
        'runner_budget_seconds': C06_RUNNER_BUDGET_SECONDS,
        'suite_budget_seconds': C06_SUITE_BUDGET_SECONDS,
        'capture_cap': C06_CAPTURE_CAP,
    }
    payload.update(extra)
    return payload


def prepare_c06_runner_tls():
    """Once: exclusive /tmp dir, bounded /bin/sh+/usr/bin/openssl, admit public provenance.

    Must run after TMPDIR=/tmp and RLIMIT_FSIZE, before the subprocess audit hook.
    Shared 30s generation/admission deadline covers create/start/wait. Recipe is not
    executed during source prep. No retry, reuse, or directory deletion.
    """
    admission_deadline = monotonic() + C06_GEN_SECONDS
    exclusive_create_c06_gate_tls_dir()
    script = ROOT / C06_PREPARE_SCRIPT
    if not script.is_file() or script.resolve().as_posix() != (ROOT / C06_PREPARE_SCRIPT).resolve().as_posix():
        raise C06RunnerTlsError('c06 prepare script')
    stdout_sink = C06CaptureSink()
    stderr_sink = C06CaptureSink()
    constructed_readers = []
    started_readers = []
    owned_endpoints = []
    secondary = []
    proc = None
    owned_pgid = None
    group_report = {
        'group_retired': False,
        'group_state': 'not_started',
        'leader_exited': False,
    }
    readers_joined = False
    pipes_closed = False
    primary = None
    try:
        if monotonic() >= admission_deadline:
            primary = C06RunnerTlsError('c06 generation timeout')
        else:
            proc = subprocess.Popen(
                [C06_SH_ABS, str(script)],
                executable=C06_SH_ABS,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=dict(C06_CHILD_ENV),
                cwd='/tmp',
                start_new_session=True,
                close_fds=True,
            )
            owned_pgid = _c06_owned_pgid(proc)
            stdout_reader = Thread(
                target=_c06_capture_reader, args=(proc.stdout, stdout_sink, None),
                name='c06-openssl-stdout', daemon=False)
            stderr_reader = Thread(
                target=_c06_capture_reader, args=(proc.stderr, stderr_sink, None),
                name='c06-openssl-stderr', daemon=False)
            constructed_readers = [stdout_reader, stderr_reader]
            owned_endpoints = [
                {'pipe': proc.stdout, 'reader': stdout_reader, 'sink': stdout_sink,
                 'started': False, 'closed': False},
                {'pipe': proc.stderr, 'reader': stderr_reader, 'sink': stderr_sink,
                 'started': False, 'closed': False},
            ]
            for endpoint in owned_endpoints:
                reader = endpoint['reader']
                try:
                    reader.start()
                except BaseException as error:
                    secondary.append({
                        'phase': 'reader_start',
                        'kind': type(error).__name__,
                    })
                    if primary is None:
                        primary = C06RunnerTlsError('c06 reader start')
                    break
                endpoint['started'] = True
                started_readers.append(reader)
            while primary is None:
                if stdout_sink.overflow or stderr_sink.overflow:
                    primary = C06RunnerTlsError('c06 capture cap')
                    break
                if stdout_sink.reader_error or stderr_sink.reader_error:
                    primary = C06RunnerTlsError('c06 capture reader')
                    break
                remaining = admission_deadline - monotonic()
                if remaining <= 0:
                    primary = C06RunnerTlsError('c06 generation timeout')
                    break
                try:
                    proc.wait(timeout=min(C06_WAIT_POLL_SECONDS, remaining))
                    break
                except subprocess.TimeoutExpired:
                    continue
            if primary is None and proc.returncode != 0:
                primary = C06RunnerTlsError('c06 generation refused')
    except C06RunnerTlsError as error:
        if primary is None:
            primary = error
        else:
            secondary.append({'phase': 'generation', 'kind': type(error).__name__})
    except BaseException as error:
        wrapped = C06RunnerTlsError(type(error).__name__)
        wrapped.__cause__ = error
        if primary is None:
            primary = wrapped
        else:
            secondary.append({'phase': 'generation', 'kind': type(error).__name__})
    if owned_pgid is not None and proc is not None:
        try:
            group_report = _c06_retire_process_group(proc, owned_pgid)
        except BaseException as error:
            group_report = {
                'group_retired': False,
                'group_state': 'unknown',
                'leader_exited': proc.poll() is not None,
            }
            secondary.append({'phase': 'group_retire', 'kind': type(error).__name__})
    try:
        readers_joined = _c06_join_started_readers(started_readers, secondary)
    except BaseException as error:
        readers_joined = False
        secondary.append({'phase': 'reader_join', 'kind': type(error).__name__})
    # Recheck reader outcomes after joins: wait return is not EOF, and a late
    # throw after leader exit must not reach public provenance.
    if stdout_sink.reader_error or stderr_sink.reader_error:
        if primary is None:
            primary = C06RunnerTlsError('c06 capture reader')
        else:
            secondary.append({'phase': 'reader_outcome', 'kind': 'c06 capture reader'})
    started_sinks = [item['sink'] for item in owned_endpoints if item.get('started')]
    readers_eof = all(sink.saw_eof and not sink.reader_error for sink in started_sinks)
    if started_sinks and not readers_eof:
        if primary is None:
            primary = C06RunnerTlsError('c06 reader eof unknown')
        else:
            secondary.append({'phase': 'reader_outcome', 'kind': 'c06 reader eof unknown'})
    if stdout_sink.overflow or stderr_sink.overflow:
        if primary is None:
            primary = C06RunnerTlsError('c06 capture cap')
        else:
            secondary.append({'phase': 'reader_outcome', 'kind': 'c06 capture cap'})
    pipes_unretired = 0
    try:
        pipes_unretired = _c06_close_owned_pipes(owned_endpoints, secondary)
        pipes_closed = pipes_unretired == 0 and not any(
            item.get('phase') == 'pipe_close' for item in secondary)
    except BaseException as error:
        pipes_closed = False
        secondary.append({'phase': 'pipe_close', 'kind': type(error).__name__})
    extra = {
        'child_retired': group_report.get('group_retired') is True,
        'group_state': group_report.get('group_state'),
        'leader_exited': group_report.get('leader_exited'),
        'readers_joined': readers_joined,
        'readers_eof': readers_eof if started_sinks else True,
        'readers_constructed': len(constructed_readers),
        'readers_started': len(started_readers),
        'owned_pipes': len(owned_endpoints),
        'pipes_closed': pipes_closed,
        'pipes_unretired': pipes_unretired,
        'secondary_retirement': list(secondary),
        'stdout_observed_bytes': stdout_sink.observed,
        'stdout_retained_bytes': len(stdout_sink.retained),
        'stdout_cap_observations': stdout_sink.cap_observations,
        'stderr_observed_bytes': stderr_sink.observed,
        'stderr_retained_bytes': len(stderr_sink.retained),
        'stderr_cap_observations': stderr_sink.cap_observations,
    }
    retirement_unknown = (
        owned_pgid is not None and group_report.get('group_state') in ('present', 'permission', 'unknown')
    ) or (started_readers and not readers_joined) or (started_sinks and not readers_eof) or (
        pipes_unretired > 0) or (owned_endpoints and not pipes_closed)
    if primary is not None:
        extra.update(_c06_sanitized_status(type(primary).__name__, stdout_sink, stderr_sink, extra))
        _c06_attach_secondary(primary, extra)
        raise primary
    if retirement_unknown:
        primary = C06RunnerTlsError('c06 retirement unknown')
        extra.update(_c06_sanitized_status(type(primary).__name__, stdout_sink, stderr_sink, extra))
        _c06_attach_secondary(primary, extra)
        raise primary
    if proc is None or proc.returncode != 0 or stdout_sink.overflow or stderr_sink.overflow:
        raise C06RunnerTlsError('c06 generation mismatch')
    if stdout_sink.reader_error or stderr_sink.reader_error or not readers_eof:
        raise C06RunnerTlsError('c06 capture reader')
    extra.update(_c06_public_provenance())
    extra.update(_c06_sanitized_status('C06RunnerTlsPrepared', stdout_sink, stderr_sink, extra))
    extra['openssl_abs'] = C06_OPENSSL_ABS
    extra['sh_abs'] = C06_SH_ABS
    extra['child_path'] = C06_CHILD_ENV['PATH']
    extra['tmpdir'] = C06_CHILD_ENV['TMPDIR']
    return extra


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
    # Runner-owned C06 CA/leaf once, before the unchanged subprocess audit hook.
    config['c06_runner_tls'] = prepare_c06_runner_tls()
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
    if config['c06_runner_tls'].get('db_public_ca_sha256') != config['ca_sha256']:
        raise RuntimeError('c06 db public CA hash mismatch')
    if config['c06_runner_tls'].get('gate_ca_sha256') == config['ca_sha256']:
        raise RuntimeError('c06 public CA hashes not distinct')
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
